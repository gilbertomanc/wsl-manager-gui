"""Tools MCP mapeadas al catalogo (seccion 21.4): mismas operaciones que CLI/GUI.

El paquete 'mcp' se importa perezosamente: si no esta instalado, las tools
siguen listandose via get_tool_defs() pero serve() falla con mensaje claro.
"""
from __future__ import annotations

from src.cli.common import CliContext
from src.core.config import GlobalLimits
from src.core.profiles import ProfileService
from src.core.scheduler import Scheduler
from src.core.watcher import Watcher


def get_tool_defs() -> list[dict]:
    return [
        {"name": "list_distros", "description": "Lista distros con estado, version e IP", "inputSchema": {"type": "object", "properties": {}}},
        {"name": "start", "description": "Inicia una distro", "inputSchema": {"type": "object", "properties": {"distro": {"type": "string"}}, "required": ["distro"]}},
        {"name": "stop", "description": "Detiene una distro", "inputSchema": {"type": "object", "properties": {"distro": {"type": "string"}}, "required": ["distro"]}},
        {"name": "restart", "description": "Reinicia una distro", "inputSchema": {"type": "object", "properties": {"distro": {"type": "string"}}, "required": ["distro"]}},
        {"name": "shutdown_all", "description": "Apaga todas las distros", "inputSchema": {"type": "object", "properties": {}}},
        {"name": "get_ips", "description": "IPs de todas las distros", "inputSchema": {"type": "object", "properties": {}}},
        {"name": "snapshot", "description": "Snapshot de una distro", "inputSchema": {"type": "object", "properties": {"distro": {"type": "string"}}, "required": ["distro"]}},
        {"name": "clone", "description": "Clona una distro", "inputSchema": {"type": "object", "properties": {"distro": {"type": "string"}, "new_name": {"type": "string"}}, "required": ["distro", "new_name"]}},
        {"name": "set_global_limits", "description": "Limites globales (memory_gb, processors, swap_gb)", "inputSchema": {"type": "object", "properties": {"memory_gb": {"type": "number"}, "processors": {"type": "integer"}, "swap_gb": {"type": "number"}}}},
        {"name": "get_metrics", "description": "Metricas de RAM/CPU por distro", "inputSchema": {"type": "object", "properties": {"distro": {"type": "string"}}}},
        {"name": "status", "description": "Estado global (distros + alertas)", "inputSchema": {"type": "object", "properties": {}}},
        {"name": "schedule_add", "description": "Programa una tarea", "inputSchema": {"type": "object", "properties": {"name": {"type": "string"}, "type": {"type": "string"}, "distro": {"type": "string"}, "time": {"type": "string"}, "days": {"type": "string"}}, "required": ["name", "type"]}},
        {"name": "profile_apply", "description": "Aplica un perfil", "inputSchema": {"type": "object", "properties": {"name": {"type": "string"}}, "required": ["name"]}},
        {"name": "run_command", "description": "Ejecuta un comando en una distro", "inputSchema": {"type": "object", "properties": {"distro": {"type": "string"}, "cmd": {"type": "string"}}, "required": ["distro", "cmd"]}},
        {"name": "doctor", "description": "Diagnostico del entorno WSL", "inputSchema": {"type": "object", "properties": {}}},
    ]


class McpTools:
    def __init__(self, ctx: CliContext) -> None:
        self.ctx = ctx

    def call(self, name: str, arguments: dict | None = None) -> dict:
        ctx = self.ctx
        args = arguments or {}
        fn = getattr(self, f"tool_{name}", None)
        if fn is None:
            return {"error": f"tool desconocida: {name}"}
        try:
            return fn(**args)
        except TypeError as e:
            return {"error": f"argumentos invalidos: {e}"}
        except Exception as e:  # noqa: BLE001
            return {"error": str(e)}

    # --- tools ---------------------------------------------------------------

    def tool_list_distros(self) -> dict:
        distros = self.ctx.wsl.list_distros()
        for d in distros:
            if d.state == "Running":
                d.ip = self.ctx.wsl.get_ip(d.name)
        return {"distros": [d.to_dict() for d in distros]}

    def tool_start(self, distro: str) -> dict:
        r = self.ctx.wsl.start(distro)
        self.ctx.metrics.log_event("mcp_start", distro, "iniciada via MCP")
        return {"ok": r.ok, "error": r.error or None}

    def tool_stop(self, distro: str) -> dict:
        r = self.ctx.wsl.stop(distro)
        return {"ok": r.ok, "error": r.error or None}

    def tool_restart(self, distro: str) -> dict:
        r = self.ctx.wsl.restart(distro)
        return {"ok": r.ok, "error": r.error or None}

    def tool_shutdown_all(self) -> dict:
        r = self.ctx.wsl.shutdown_all()
        return {"ok": r.ok, "error": r.error or None}

    def tool_get_ips(self) -> dict:
        return {"ips": self.ctx.wsl.get_all_ips()}

    def tool_snapshot(self, distro: str) -> dict:
        try:
            path = self.ctx.wsl.snapshot(distro, self.ctx.config.snapshots.retention_days, self.ctx.config.snapshots.target_dir)
        except RuntimeError as e:
            return {"ok": False, "error": str(e)}
        size = path.stat().st_size if path.exists() else 0
        self.ctx.metrics.record_snapshot(distro, str(path), size)
        return {"ok": True, "path": str(path), "size_bytes": size}

    def tool_clone(self, distro: str, new_name: str) -> dict:
        r = self.ctx.wsl.clone(distro, new_name)
        return {"ok": r.ok, "error": r.error or None}

    def tool_set_global_limits(self, memory_gb: float | None = None, processors: int | None = None, swap_gb: float | None = None) -> dict:
        limits = GlobalLimits(memory_gb=memory_gb, processors=processors, swap_gb=swap_gb)
        r = self.ctx.resources.set_global_limits(limits)
        return {"ok": r.ok, "error": r.error or None, "note": "requiere wsl --shutdown"}

    def tool_get_metrics(self, distro: str | None = None) -> dict:
        return {"metrics": [m.to_dict() for m in self.ctx.resources.get_metrics(distro)]}

    def tool_status(self) -> dict:
        return Watcher(self.ctx.store, self.ctx.metrics, self.ctx.bus, self.ctx.wsl).snapshot_state()

    def tool_schedule_add(self, name: str, type: str, distro: str | None = None, time: str = "09:00", days: str = "mon,tue,wed,thu,fri") -> dict:
        import uuid

        from src.core.config import ScheduleAction, ScheduleSpec, ScheduleTask

        task = ScheduleTask(
            id=f"tarea-{uuid.uuid4().hex[:8]}",
            name=name,
            action=ScheduleAction(type=type, distro=distro),  # type: ignore[arg-type]
            schedule=ScheduleSpec(days=[d.strip() for d in days.split(",")], time=time),
        )
        Scheduler(self.ctx.store, self.ctx.metrics, self.ctx.bus, self.ctx.wsl).add_task(task)
        return {"ok": True, "id": task.id}

    def tool_profile_apply(self, name: str) -> dict:
        try:
            ok = ProfileService(self.ctx.store, self.ctx.wsl).apply(name)
        except KeyError as e:
            return {"ok": False, "error": str(e)}
        return {"ok": ok}

    def tool_run_command(self, distro: str, cmd: str) -> dict:
        r = self.ctx.wsl.run_command(distro, cmd)
        return {"ok": r.ok, "output": r.output, "error": r.error or None}

    def tool_doctor(self) -> dict:
        ctx = self.ctx
        checks = []
        v = ctx.wsl.version()
        checks.append({"check": "wsl.exe", "ok": v.ok, "detail": v.output.strip()[:80] or v.error})
        try:
            distros = ctx.wsl.list_distros()
            checks.append({"check": "distros", "ok": True, "detail": f"{len(distros)} distro(s)"})
        except Exception as e:  # noqa: BLE001
            checks.append({"check": "distros", "ok": False, "detail": str(e)})
        return {"ok": all(c["ok"] for c in checks), "checks": checks}
