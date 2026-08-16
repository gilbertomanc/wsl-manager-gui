"""ProfileService: captura y aplica perfiles de distros (A3).

Capture: estado actual (distros activas) -> perfil con nombre.
Apply: transiciona (inicia lo que falta, detiene lo que sobra) respetando
dependencias topologicas (W8/A5).
"""
from __future__ import annotations

import logging

from src.core.config import ConfigStore, ProfileItem
from src.providers.wsl_provider import WslProvider

log = logging.getLogger("wslmanager.profiles")


class ProfileService:
    def __init__(self, config_store: ConfigStore, wsl_provider: WslProvider | None = None) -> None:
        self._cfg = config_store
        self._wsl = wsl_provider or WslProvider(config_store)

    def list(self) -> list[dict]:
        p = self._cfg.get().profiles
        return [
            {"name": i.name, "description": i.description, "distros_to_start": i.distros_to_start, "active": i.name == p.active}
            for i in p.items
        ]

    def capture(self, name: str, description: str = "") -> ProfileItem:
        running = [d.name for d in self._wsl.list_distros() if d.state == "Running"]
        cfg = self._cfg.get()
        existing = [i for i in cfg.profiles.items if i.name != name]
        item = ProfileItem(name=name, description=description, distros_to_start=running)
        existing.append(item)
        cfg.profiles.items = existing
        cfg.profiles.active = name
        self._cfg.save(cfg)
        log.info("perfil '%s' capturado con %s", name, running)
        return item

    def apply(self, name: str, start_all: bool = True) -> bool:
        cfg = self._cfg.get()
        item = next((i for i in cfg.profiles.items if i.name == name), None)
        if item is None:
            raise KeyError(f"perfil '{name}' no existe")

        distros = {d.name: d for d in self._wsl.list_distros()}
        running_now = {d.name for d in distros.values() if d.state == "Running"}
        target = set(item.distros_to_start)

        # Iniciar en orden topologico (dependencias primero)
        order = self._topo_order(target, distros)
        for d in order:
            if d not in running_now and (start_all or d in target):
                r = self._wsl.start(d)
                if not r.ok:
                    log.error("fallo al iniciar %s en perfil %s: %s", d, name, r.error)
                    return False

        # Detener lo que sobra (politica del perfil)
        for d in running_now - target:
            if d not in {"docker-desktop", "rancher-desktop", "rancher-desktop-data"}:
                self._wsl.stop(d)

        cfg.profiles.active = name
        self._cfg.save(cfg)
        return True

    def _topo_order(self, names: set[str], distros: dict[str, object]) -> list[str]:
        """Orden de arranque respetando depends_on (W8)."""
        instances = {i.name: i for i in self._cfg.get().distros.instances}
        visited: set[str] = set()
        order: list[str] = []

        def visit(name: str) -> None:
            if name in visited or name not in names:
                return
            visited.add(name)
            inst = instances.get(name)
            if inst:
                for dep in inst.depends_on:
                    visit(dep.distro)
            order.append(name)

        for n in sorted(names):
            visit(n)
        return order
