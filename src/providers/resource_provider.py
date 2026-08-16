"""ResourceProvider: limites globales (.wslconfig), por distro (systemd,
experimental) y metricas (R1-R8).
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Optional

from src.core.config import ConfigStore, GlobalLimits, PerDistroLimits
from src.providers.base import CommandResult, DistroMetrics
from src.providers.wsl_config_provider import WslConfigProvider
from src.providers.wsl_provider import WslProvider
from src.utils.subprocess_async import run

_WSL_CONFIG_SECTION = "wsl2"


class ResourceProvider:
    def __init__(self, config_store: ConfigStore, wsl_provider: WslProvider | None = None) -> None:
        self._store = config_store
        self._wsl = wsl_provider or WslProvider(config_store)
        self._cfg_file = WslConfigProvider()

    # -- limites globales (R1) ---------------------------------------------------

    def get_global_limits(self) -> GlobalLimits:
        return self._store.get().resources.global_limits

    def set_global_limits(self, limits: GlobalLimits) -> CommandResult:
        """Escribe [wsl2] en .wslconfig con backup + validacion; persiste en config.json."""
        sections = self._cfg_file.read_wslconfig()
        section = dict(sections.get(_WSL_CONFIG_SECTION, {}))
        mapping = {
            "memory_gb": "memory",
            "processors": "processors",
            "swap_gb": "swap",
            "auto_memory_reclaim": "autoMemoryReclaim",
            "sparse_vhd": "sparseVhd",
        }
        values = limits.model_dump(exclude_none=True)

        def gb(v: float) -> str:
            return str(int(v)) if float(v).is_integer() else str(v)

        if "memory_gb" in values:
            section["memory"] = f"{gb(values['memory_gb'])}GB"
        if "processors" in values:
            section["processors"] = str(values["processors"])
        if "swap_gb" in values:
            section["swap"] = f"{gb(values['swap_gb'])}GB"
        if "auto_memory_reclaim" in values:
            section["autoMemoryReclaim"] = values["auto_memory_reclaim"]
        if "sparse_vhd" in values:
            section["sparseVhd"] = "true" if values["sparse_vhd"] else "false"
        sections[_WSL_CONFIG_SECTION] = section

        r = self._cfg_file.write_wslconfig(sections)
        if not r.ok:
            return r

        cfg = self._store.get()
        cfg.resources.global_limits = limits
        self._store.save(cfg)
        return CommandResult(ok=True, output="limites globales aplicados (requieren wsl --shutdown)")

    # -- limites por distro (R4, experimental via systemd) -------------------------

    def _wsl_root(self, distro: str, cmd: str) -> CommandResult:
        return run(["wsl.exe", "-d", distro, "-u", "root", "--", "sh", "-lc", cmd], timeout=60)

    def get_distro_limits(self, distro: str) -> Optional[PerDistroLimits]:
        for item in self._store.get().resources.per_distro:
            if item.distro == distro:
                return item
        return None

    def set_distro_limits(self, limits: PerDistroLimits) -> CommandResult:
        """Escribe drop-ins de systemd en la distro (scope all/user/service)."""
        if not limits.enabled:
            return self.clear_distro_limits(limits.distro)

        mem = limits.memory_max
        quota = limits.cpu_quota
        tasks = limits.tasks_max

        if limits.scope == "service" and limits.service:
            svc = limits.service.replace(".service", "")
            path = f"/etc/systemd/system/{svc}.service.d/99-wsl-manager.conf"
            body = "[Service]\n"
            if mem:
                body += f"MemoryMax={mem}\n"
            if quota:
                body += f"CPUQuota={quota}\n"
            if tasks:
                body += f"TasksMax={tasks}\n"
            cmd = f"mkdir -p /etc/systemd/system/{svc}.service.d && printf '%s' {self._quote(body)} > {path} && systemctl daemon-reload"
        elif limits.scope == "user":
            path = "/etc/systemd/user.conf.d/99-wsl-manager.conf"
            body = "[Manager]\n"
            if mem:
                body += f"DefaultMemoryMax={mem}\n"
            if tasks:
                body += f"DefaultTasksMax={tasks}\n"
            cmd = f"mkdir -p /etc/systemd/user.conf.d && printf '%s' {self._quote(body)} > {path} && systemctl daemon-reload"
        else:  # all
            path = "/etc/systemd/system.conf.d/99-wsl-manager.conf"
            body = "[Manager]\n"
            if mem:
                body += f"DefaultMemoryMax={mem}\n"
            if quota:
                body += f"DefaultCPUQuotaSec={quota}\n"
            if tasks:
                body += f"DefaultTasksMax={tasks}\n"
            cmd = f"mkdir -p /etc/systemd/system.conf.d && printf '%s' {self._quote(body)} > {path} && systemctl daemon-reload"

        r = self._wsl_root(limits.distro, cmd)
        if not r.ok:
            # No persistir un limite que no se pudo aplicar
            return CommandResult(ok=False, error=f"no se pudo aplicar en la distro: {r.error.strip() or r.output.strip()}")

        cfg = self._store.get()
        existing = [i for i in cfg.resources.per_distro if i.distro != limits.distro]
        existing.append(limits)
        cfg.resources.per_distro = existing
        self._store.save(cfg)
        return CommandResult(ok=True, output=f"limites de '{limits.distro}' aplicados via systemd")

    @staticmethod
    def _quote(text: str) -> str:
        return "'" + text.replace("'", "'\\''") + "'"

    def clear_distro_limits(self, distro: str) -> CommandResult:
        cfg = self._store.get()
        cfg.resources.per_distro = [i for i in cfg.resources.per_distro if i.distro != distro]
        self._store.save(cfg)
        # Quita los drop-ins si existen (ignora errores)
        cmds = [
            "rm -rf /etc/systemd/system.conf.d/99-wsl-manager.conf",
            "rm -rf /etc/systemd/user.conf.d/99-wsl-manager.conf",
        ]
        for c in cmds:
            self._wsl_root(distro, c)
        return CommandResult(ok=True, output=f"limites de '{distro}' eliminados")

    # -- metricas (R3) -------------------------------------------------------------

    def get_metrics(self, distro: str | None = None) -> list[DistroMetrics]:
        names = [distro] if distro else [d.name for d in self._wsl.list_distros()]
        return [m for m in (self._wsl.metrics(n) for n in names) if m is not None]

    # -- recomendador (R8, P2) -------------------------------------------------------

    def recommend_limits(self, ram_gb: float, cpus: int) -> dict:
        """Sugerencia basica: mitad de la RAM del host como tope de VM."""
        suggested_memory = max(2.0, round(ram_gb / 2, 1))
        return {
            "memory_gb": suggested_memory,
            "processors": max(1, cpus // 2),
            "note": "sugerencia: 50% de la RAM del host; ajustar segun uso real",
        }
