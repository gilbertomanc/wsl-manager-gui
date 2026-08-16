"""Watcher: poll de estado de distros + IPs + metricas + alertas (M1-M5).

Nunca muere: excepciones capturadas y registradas. Emite eventos
"state-changed" con el estado global; inserta metricas en SQLite.
"""
from __future__ import annotations

import logging
import threading
import time

from src.core.config import ConfigStore
from src.core.event_bus import EventBus
from src.core.metrics_store import MetricsStore
from src.core.notifier import notify
from src.providers.wsl_provider import WslProvider

log = logging.getLogger("wslmanager.watcher")


class Watcher:
    def __init__(
        self,
        config_store: ConfigStore,
        metrics_store: MetricsStore,
        event_bus: EventBus,
        wsl_provider: WslProvider | None = None,
    ) -> None:
        self._cfg = config_store
        self._metrics = metrics_store
        self._bus = event_bus
        self._wsl = wsl_provider or WslProvider(config_store)
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None
        self._last_state: dict[str, str] = {}
        self._last_alert_ram: dict[str, float] = {}

    def start(self) -> None:
        if self._thread and self._thread.is_alive():
            return
        self._stop.clear()
        self._thread = threading.Thread(target=self._loop, name="watcher", daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()
        if self._thread:
            self._thread.join(timeout=10)

    # -- loop ------------------------------------------------------------------

    def _loop(self) -> None:
        cfg = self._cfg.get()
        interval = max(2, cfg.alerts.check_interval_seconds)
        while not self._stop.is_set():
            started = time.time()
            try:
                self._tick()
            except Exception:  # noqa: BLE001 - el watcher nunca muere
                log.exception("tick del watcher fallo")
            elapsed = time.time() - started
            self._stop.wait(max(1.0, interval - elapsed))

    def _tick(self) -> None:
        cfg = self._cfg.get()
        distros = self._wsl.list_distros()
        running = {d.name for d in distros if d.state == "Running"}

        payload = []
        for d in distros:
            ip = None
            if d.state == "Running":
                ip = self._wsl.get_ip(d.name)
                d.ip = ip
            # metricas
            m = self._wsl.metrics(d.name) if d.state == "Running" else None
            self._metrics.insert_metric(
                d.name,
                d.state,
                m.ram_used_mb if m else None,
                m.ram_percent if m else None,
                ip,
            )
            # alerta de RAM (M4)
            if m and m.ram_percent is not None and m.ram_percent >= cfg.alerts.memory_percent:
                last = self._last_alert_ram.get(d.name, 0.0)
                if m.ram_percent - last >= 5:  # histéresis: no repetir a cada tick
                    self._metrics.add_alert("memory", f"RAM de {d.name} al {m.ram_percent:.0f}%", "warning", d.name)
                    notify("WSL Manager", f"RAM de {d.name} al {m.ram_percent:.0f}%")
                    self._last_alert_ram[d.name] = m.ram_percent
            # alerta de detencion inesperada (M5)
            if cfg.alerts.distro_stopped_unexpected:
                if self._last_state.get(d.name) == "Running" and d.state != "Running":
                    self._metrics.add_alert("distro_stopped", f"{d.name} se detuvo", "warning", d.name)
                    notify("WSL Manager", f"{d.name} se detuvo")
            self._last_state[d.name] = d.state
            payload.append(d.to_dict())

        # resolucion de alertas de RAM ya bajas
        for name, last in list(self._last_alert_ram.items()):
            m = next((x for x in payload if x["name"] == name), None)
            if m is None or (m.get("ram_percent") or 0) < cfg.alerts.memory_percent - 5:
                self._metrics.resolve_alerts("memory", name)
                self._last_alert_ram.pop(name, None)

        self._bus.emit("state-changed", {"distros": payload, "ts": time.time()})

    # -- consulta directa (para CLI sin GUI) --------------------------------------

    def snapshot_state(self) -> dict:
        cfg = self._cfg.get()
        distros = self._wsl.list_distros()
        for d in distros:
            if d.state == "Running":
                d.ip = self._wsl.get_ip(d.name)
        return {
            "ts": time.time(),
            "distros": [d.to_dict() for d in distros],
            "alerts": cfg.alerts.model_dump(),
        }
