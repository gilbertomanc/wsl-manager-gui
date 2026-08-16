"""Tests del Watcher: estado, alertas y eventos con providers mockeados."""
from __future__ import annotations

from unittest.mock import MagicMock

from src.core.config import ConfigStore
from src.core.event_bus import EventBus
from src.core.metrics_store import MetricsStore
from src.core.watcher import Watcher
from src.providers.base import Distro, DistroMetrics


def _watcher(tmp_path, distros, metrics_map):
    store = ConfigStore(tmp_path / "config.json")
    cfg = store.load()
    cfg.alerts.memory_percent = 85
    cfg.alerts.check_interval_seconds = 5
    store.save(cfg)

    wsl = MagicMock()
    wsl.list_distros.return_value = distros
    wsl.get_ip.side_effect = lambda n: {"ubuntu-dev": "172.18.0.2", "db": "172.18.0.3"}.get(n)
    wsl.metrics.side_effect = lambda n: metrics_map.get(n)

    ms = MetricsStore(tmp_path / "m.db")
    bus = EventBus()
    w = Watcher(store, ms, bus, wsl)
    return w, ms, bus


def test_tick_records_state(tmp_path):
    distros = [Distro(name="ubuntu-dev", state="Running", version=2), Distro(name="db", state="Stopped", version=2)]
    metrics = {"ubuntu-dev": DistroMetrics(name="ubuntu-dev", running=True, ip="172.18.0.2", ram_total_mb=8192, ram_used_mb=4096, ram_percent=50.0)}
    w, ms, bus = _watcher(tmp_path, distros, metrics)

    events = []
    bus.subscribe("state-changed", lambda e, p: events.append(p))
    w._tick()

    assert len(events) == 1
    payload = events[0]["distros"]
    assert payload[0]["name"] == "ubuntu-dev"
    assert payload[0]["ip"] == "172.18.0.2"
    rows = ms.list_metrics()
    assert len(rows) == 2  # una por distro


def test_ram_alert_and_resolution(tmp_path):
    distros = [Distro(name="ubuntu-dev", state="Running", version=2)]
    metrics = {"ubuntu-dev": DistroMetrics(name="ubuntu-dev", running=True, ram_total_mb=1000, ram_used_mb=950, ram_percent=95.0)}
    w, ms, bus = _watcher(tmp_path, distros, metrics)
    w._tick()
    assert ms.list_alerts()[0]["tipo"] == "memory"
    # baja -> se resuelve
    metrics["ubuntu-dev"].ram_used_mb = 100
    metrics["ubuntu-dev"].ram_percent = 10.0
    w._tick()
    assert ms.list_alerts()[0]["estado"] == "resolved"


def test_unexpected_stop_alert(tmp_path):
    distros = [Distro(name="db", state="Running", version=2)]
    w, ms, bus = _watcher(tmp_path, distros, {})
    w._tick()
    # siguiente tick: detenida sin accion del usuario
    w._wsl.list_distros.return_value = [Distro(name="db", state="Stopped", version=2)]
    w._tick()
    alerts = ms.list_alerts()
    assert any(a["tipo"] == "distro_stopped" for a in alerts)


def test_watcher_never_dies(tmp_path):
    import threading
    import time

    distros = [Distro(name="db", state="Running", version=2)]
    w, ms, bus = _watcher(tmp_path, distros, {})
    w._wsl.list_distros.side_effect = RuntimeError("boom")
    t = threading.Thread(target=w._loop)
    t.start()
    time.sleep(0.6)
    assert t.is_alive()  # el loop sobrevive a ticks con error
    w.stop()
    t.join(timeout=2)
    assert not t.is_alive()
