"""Tests del panel web local (M7) con TestClient y providers mockeados.

El panel exige clave (Authorization: Bearer) en TODOS los /api/*.
"""
from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient

from src.core.config import ConfigStore
from src.core.event_bus import EventBus
from src.core.metrics_store import MetricsStore
from src.providers.base import CommandResult, Distro, DistroMetrics
from src.web.web_app import create_web_app

PASSWORD = "secreto"
AUTH = {"Authorization": f"Bearer {PASSWORD}"}


@pytest.fixture
def ctx(tmp_path, monkeypatch):
    # Aisla el SecretsStore (DPAPI) para que los tests no vean los secrets
    # reales del usuario en %APPDATA%.
    monkeypatch.setattr(
        "src.utils.secrets.secrets_path", lambda: tmp_path / "secrets.json"
    )
    store = ConfigStore(tmp_path / "config.json")
    cfg = store.load()
    cfg.ui.web_panel_password = PASSWORD
    wsl = MagicMock()
    wsl.list_distros.return_value = [Distro(name="ubuntu-dev", state="Running", version=2)]
    wsl.get_ip.return_value = "172.18.0.2"
    wsl.metrics.return_value = DistroMetrics(name="ubuntu-dev", running=True, ip="172.18.0.2", ram_total_mb=8192, ram_used_mb=2048, ram_percent=25.0)
    wsl.start.return_value = CommandResult(ok=True)
    wsl.stop.return_value = CommandResult(ok=True)
    resources = MagicMock()
    resources.get_metrics.return_value = [wsl.metrics.return_value]
    ms = MetricsStore(tmp_path / "m.db")
    bus = EventBus()
    return SimpleNamespace(store=store, config=cfg, metrics=ms, bus=bus, wsl=wsl, resources=resources)


def test_index_html_public(ctx):
    """El HTML del dashboard es publico; la clave protege los /api/*."""
    client = TestClient(create_web_app(ctx))
    r = client.get("/")
    assert r.status_code == 200
    assert "WSL Manager" in r.text
    assert "login" in r.text  # el JS pide la clave


def test_api_requires_password(ctx):
    client = TestClient(create_web_app(ctx))
    assert client.get("/api/status").status_code == 401
    assert client.get("/api/status", headers={"Authorization": "Bearer malo"}).status_code == 401
    assert client.post("/api/distros/ubuntu-dev/start").status_code == 401


def test_api_status_authed(ctx):
    client = TestClient(create_web_app(ctx))
    r = client.get("/api/status", headers=AUTH)
    assert r.status_code == 200
    data = r.json()
    assert data["distros"][0]["name"] == "ubuntu-dev"
    assert data["distros"][0]["running"] is True
    assert data["distros"][0]["ram_percent"] == 25.0


def test_api_metrics_authed(ctx):
    client = TestClient(create_web_app(ctx))
    r = client.get("/api/metrics", headers=AUTH)
    assert r.status_code == 200
    assert r.json()["metrics"][0]["ram_used_mb"] == 2048


def test_api_actions_authed(ctx):
    client = TestClient(create_web_app(ctx))
    assert client.post("/api/distros/ubuntu-dev/start", headers=AUTH).status_code == 200
    assert client.post("/api/distros/ubuntu-dev/stop", headers=AUTH).status_code == 200
    assert client.post("/api/shutdown", headers=AUTH).status_code == 200
