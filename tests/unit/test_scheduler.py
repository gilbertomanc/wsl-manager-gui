"""Tests del Scheduler y de ProfileService con providers mockeados."""
from __future__ import annotations

from datetime import datetime
from unittest.mock import MagicMock

from src.core.config import ConfigStore, ScheduleAction, ScheduleSpec, ScheduleTask
from src.core.event_bus import EventBus
from src.core.metrics_store import MetricsStore
from src.core.profiles import ProfileService
from src.core.scheduler import Scheduler
from src.providers.base import CommandResult, Distro


def _ctx(tmp_path):
    store = ConfigStore(tmp_path / "config.json")
    store.load()
    wsl = MagicMock()
    wsl.start.return_value = CommandResult(ok=True)
    wsl.stop.return_value = CommandResult(ok=True)
    ms = MetricsStore(tmp_path / "m.db")
    bus = EventBus()
    return store, wsl, ms, bus


def test_add_remove_task(tmp_path):
    store, wsl, ms, bus = _ctx(tmp_path)
    s = Scheduler(store, ms, bus, wsl)
    s.add_task(ScheduleTask(id="t1", name="x", action=ScheduleAction(type="distro_start", distro="u"), schedule=ScheduleSpec()))
    assert s.list_tasks()[0]["id"] == "t1"
    assert s.remove_task("t1")
    assert not s.remove_task("nope")


def test_run_task_start(tmp_path):
    store, wsl, ms, bus = _ctx(tmp_path)
    s = Scheduler(store, ms, bus, wsl)
    s.add_task(ScheduleTask(id="t1", name="x", action=ScheduleAction(type="distro_start", distro="u"), schedule=ScheduleSpec()))
    assert s.run_task("t1")
    wsl.start.assert_called_once_with("u")
    assert ms.list_events()[0]["type"] == "scheduler_run"


def test_run_task_unknown(tmp_path):
    store, wsl, ms, bus = _ctx(tmp_path)
    s = Scheduler(store, ms, bus, wsl)
    assert not s.run_task("no-existe")


def test_tick_fires_only_once_per_minute(tmp_path):
    store, wsl, ms, bus = _ctx(tmp_path)
    s = Scheduler(store, ms, bus, wsl)
    s.add_task(ScheduleTask(id="t1", name="x", action=ScheduleAction(type="distro_start", distro="u"), schedule=ScheduleSpec()))
    now = datetime.now()
    # fuerza a que la hora coincida con la tarea
    store.get().scheduler.tasks[0].schedule.time = now.strftime("%H:%M")
    store.get().scheduler.tasks[0].schedule.days = [now.strftime("%A").lower()[:3]]
    s._tick()
    s._tick()
    assert wsl.start.call_count == 1  # no se repite


def test_profile_capture_and_apply(tmp_path):
    store, wsl, ms, bus = _ctx(tmp_path)
    wsl.list_distros.return_value = [Distro(name="u1", state="Running", version=2), Distro(name="u2", state="Stopped", version=2)]
    svc = ProfileService(store, wsl)
    item = svc.capture("dev", "perfil dev")
    assert item.distros_to_start == ["u1"]
    assert svc.list()[0]["active"]

    wsl.list_distros.return_value = [Distro(name="u1", state="Stopped", version=2), Distro(name="u2", state="Running", version=2)]
    assert svc.apply("dev")
    wsl.start.assert_called_once_with("u1")
    wsl.stop.assert_called_once_with("u2")


def test_profile_apply_unknown(tmp_path):
    store, wsl, ms, bus = _ctx(tmp_path)
    svc = ProfileService(store, wsl)
    try:
        svc.apply("no-existe")
        assert False, "deberia lanzar KeyError"
    except KeyError:
        pass


def test_profile_topo_order(tmp_path):
    store, wsl, ms, bus = _ctx(tmp_path)
    cfg = store.get()
    cfg.distros.instances = [
        type("I", (), {"name": "app", "depends_on": [type("D", (), {"distro": "db"})()]})(),
        type("I", (), {"name": "db", "depends_on": []})(),
    ]
    svc = ProfileService(store, wsl)
    order = svc._topo_order({"app", "db"}, {})
    assert order.index("db") < order.index("app")
