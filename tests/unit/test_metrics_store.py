"""Tests del MetricsStore (SQLite)."""
from __future__ import annotations

from src.core.metrics_store import MetricsStore


def test_insert_and_query(tmp_path):
    m = MetricsStore(tmp_path / "m.db")
    m.log_event("distro_start", "ubuntu-dev", "iniciada")
    m.insert_metric("ubuntu-dev", "Running", 2048, 25.0, "172.18.0.2")
    m.add_alert("memory", "RAM al 90%", "warning", "ubuntu-dev")

    events = m.list_events()
    assert events[0]["type"] == "distro_start"
    assert events[0]["distro"] == "ubuntu-dev"

    metrics = m.list_metrics()
    assert metrics[0]["ram_mb"] == 2048
    assert metrics[0]["ram_percent"] == 25.0

    alerts = m.list_alerts()
    assert alerts[0]["tipo"] == "memory"
    assert alerts[0]["estado"] == "open"

    m.resolve_alerts("memory", "ubuntu-dev")
    assert m.list_alerts()[0]["estado"] == "resolved"


def test_snapshot_record(tmp_path):
    m = MetricsStore(tmp_path / "m.db")
    m.record_snapshot("ubuntu-dev", "C:/snaps/a.tar", 12345)
    rows = m.list_snapshots()
    assert rows[0]["size_bytes"] == 12345


def test_tokens(tmp_path):
    import hashlib

    m = MetricsStore(tmp_path / "m.db")
    tid = m.add_token(hashlib.sha256(b"abc").hexdigest(), "write", None, "ci")
    assert m.token_exists(hashlib.sha256(b"abc").hexdigest())["scope"] == "write"
    assert m.token_exists(hashlib.sha256(b"xyz").hexdigest()) is None
    assert m.revoke_token(tid)
    assert m.token_exists(hashlib.sha256(b"abc").hexdigest()) is None


def test_prune(tmp_path):
    import time

    m = MetricsStore(tmp_path / "m.db")
    m.insert_metric("ubuntu-dev", "Running", 100, 10.0, None)
    old = time.time() - 100 * 86400
    m._exec("UPDATE metrics SET ts = ?", (old,))  # envejece todas
    m.prune(metrics_days=30)
    assert m.list_metrics() == []
