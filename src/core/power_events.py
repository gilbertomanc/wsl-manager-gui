"""PowerEvents: deteccion de suspension/reanudacion (A4).

Via psutil.boot_time: si el uptime baja de golpe hubo suspension o reinicio.
Al reanudar se re-detectan IPs y estados y se reaplican limites.
"""
from __future__ import annotations

import logging
import threading
import time

import psutil

from src.core.config import ConfigStore
from src.core.event_bus import EventBus
from src.core.metrics_store import MetricsStore

log = logging.getLogger("wslmanager.power")


class PowerWatcher:
    def __init__(self, config_store: ConfigStore, metrics_store: MetricsStore, event_bus: EventBus) -> None:
        self._cfg = config_store
        self._metrics = metrics_store
        self._bus = event_bus
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None
        self._last_boot = psutil.boot_time()

    def start(self) -> None:
        if self._thread and self._thread.is_alive():
            return
        self._stop.clear()
        self._thread = threading.Thread(target=self._loop, name="power", daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()
        if self._thread:
            self._thread.join(timeout=10)

    def _loop(self) -> None:
        while not self._stop.is_set():
            try:
                boot = psutil.boot_time()
                if boot > self._last_boot + 5:
                    log.info("suspension/reanudacion detectada (uptime %ss -> %ss)", self._last_boot, boot)
                    self._metrics.log_event("power_resume", message="sistema reanudado; re-deteccion de IPs")
                    self._bus.emit("power-resume", {"boot_time": boot})
                    self._last_boot = boot
            except Exception:  # noqa: BLE001
                log.exception("power watcher fallo")
            self._stop.wait(15)
