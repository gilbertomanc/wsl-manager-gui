"""Scheduler: tareas programadas (A2) + purga de retencion.

Acciones: distro_start, distro_stop, apply_profile, snapshot.
Dias: mon..sun. Hora: HH:MM. Revisa cada 30s.
"""
from __future__ import annotations

import logging
import threading
import time
from datetime import datetime

from src.core.config import ConfigStore
from src.core.event_bus import EventBus
from src.core.metrics_store import MetricsStore
from src.core.notifier import notify
from src.core.profiles import ProfileService
from src.providers.wsl_provider import WslProvider

log = logging.getLogger("wslmanager.scheduler")

_DAYS = {"mon": 0, "tue": 1, "wed": 2, "thu": 3, "fri": 4, "sat": 5, "sun": 6}
_CHECK_EVERY = 30


class Scheduler:
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
        self._profiles = ProfileService(config_store, self._wsl)
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None
        self._last_fired: dict[str, str] = {}  # id -> "YYYY-MM-DD HH:MM" ya ejecutada

    def start(self) -> None:
        if self._thread and self._thread.is_alive():
            return
        self._stop.clear()
        self._thread = threading.Thread(target=self._loop, name="scheduler", daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()
        if self._thread:
            self._thread.join(timeout=10)

    def _loop(self) -> None:
        while not self._stop.is_set():
            try:
                self._tick()
            except Exception:  # noqa: BLE001
                log.exception("tick del scheduler fallo")
            self._stop.wait(_CHECK_EVERY)

    def _tick(self) -> None:
        cfg = self._cfg.get()
        now = datetime.now()
        today_key = f"{now.isocalendar().year}-{now.isocalendar().week}"
        for task in cfg.scheduler.tasks:
            if not task.enabled:
                continue
            if now.strftime("%A").lower()[:3] not in task.schedule.days:
                continue
            try:
                hh, mm = task.schedule.time.split(":")
                if (int(hh), int(mm)) != (now.hour, now.minute):
                    continue
            except (ValueError, TypeError):
                log.warning("tarea %s con hora invalida: %s", task.id, task.schedule.time)
                continue
            key = f"{task.id}|{today_key}|{now.strftime('%Y-%m-%d %H:%M')}"
            if self._last_fired.get(task.id) == key:
                continue
            self._last_fired[task.id] = key
            self.run_task(task.id)

    def run_task(self, task_id: str) -> bool:
        cfg = self._cfg.get()
        task = next((t for t in cfg.scheduler.tasks if t.id == task_id), None)
        if task is None:
            return False
        a = task.action
        ok = False
        if a.type == "distro_start" and a.distro:
            r = self._wsl.start(a.distro)
            ok = r.ok
        elif a.type == "distro_stop" and a.distro:
            r = self._wsl.stop(a.distro)
            ok = r.ok
        elif a.type == "apply_profile" and a.profile:
            ok = self._profiles.apply(a.profile)
        elif a.type == "snapshot" and a.distro:
            try:
                path = self._wsl.snapshot(a.distro, cfg.snapshots.retention_days, cfg.snapshots.target_dir)
                size = path.stat().st_size if path.exists() else None
                self._metrics.record_snapshot(a.distro, str(path), size)
                ok = True
                notify("WSL Manager", f"Snapshot de {a.distro} completado")
            except Exception as e:  # noqa: BLE001
                log.error("snapshot programado fallo: %s", e)
        self._metrics.log_event(
            "scheduler_run", a.distro, f"tarea '{task.name}' -> {a.type}",
            {"task_id": task_id, "ok": ok},
        )
        self._bus.emit("scheduler-run", {"task_id": task_id, "ok": ok})
        return ok

    def list_tasks(self) -> list[dict]:
        return [t.model_dump() for t in self._cfg.get().scheduler.tasks]

    def add_task(self, task) -> None:
        cfg = self._cfg.get()
        cfg.scheduler.tasks.append(task)
        self._cfg.save(cfg)

    def remove_task(self, task_id: str) -> bool:
        cfg = self._cfg.get()
        before = len(cfg.scheduler.tasks)
        cfg.scheduler.tasks = [t for t in cfg.scheduler.tasks if t.id != task_id]
        self._cfg.save(cfg)
        return len(cfg.scheduler.tasks) < before
