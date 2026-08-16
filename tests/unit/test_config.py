"""Tests del schema de config y del ConfigStore."""
from __future__ import annotations

import json

import pytest
from pydantic import ValidationError

from src.core.config import AppConfig, ConfigError, ConfigStore, ScheduleTask


def test_defaults_valid():
    cfg = AppConfig()
    assert cfg.version == 1
    assert cfg.alerts.memory_percent == 85
    assert cfg.api.port == 8791
    assert cfg.resources.global_limits.memory_gb is None
    # servicios (web/MCP) deshabilitados por defecto y sin secretos
    assert cfg.ui.web_panel_enabled is False
    assert cfg.ui.web_panel_port == 8790
    assert cfg.ui.web_panel_password == ""
    assert cfg.mcp.enabled is False
    assert cfg.mcp.token == ""


def test_full_example_roundtrip():
    data = {
        "version": 1,
        "distros": {
            "instances": [
                {"name": "ubuntu-dev", "group": "dev", "auto_start": True, "delay_s": 5,
                 "depends_on": [{"distro": "ubuntu-db", "wait_port": 5432, "timeout_s": 60}]}
            ]
        },
        "resources": {"global": {"memory_gb": 8, "processors": 4, "auto_memory_reclaim": "gradual"}},
        "alerts": {"memory_percent": 90, "check_interval_seconds": 10},
        "scheduler": {
            "tasks": [
                {"id": "t1", "name": "Iniciar dev", "action": {"type": "distro_start", "distro": "ubuntu-dev"},
                 "schedule": {"days": ["mon", "fri"], "time": "09:00"}}
            ]
        },
        "profiles": {"active": "dev", "items": [{"name": "dev", "distros_to_start": ["ubuntu-dev"]}]},
    }
    cfg = AppConfig.model_validate(data)
    assert cfg.distros.instances[0].depends_on[0].wait_port == 5432
    assert cfg.resources.global_limits.memory_gb == 8
    assert cfg.scheduler.tasks[0].id == "t1"
    # roundtrip
    dumped = json.loads(cfg.model_dump_json(by_alias=True, exclude_none=True))
    again = AppConfig.model_validate(dumped)
    assert again.scheduler.tasks[0].name == "Iniciar dev"


def test_invalid_action_type_rejected():
    with pytest.raises(ValidationError):
        AppConfig.model_validate(
            {"scheduler": {"tasks": [{"id": "x", "name": "x", "action": {"type": "volando"}, "schedule": {"time": "09:00"}}]}}
        )


def test_invalid_alerts_type_rejected():
    with pytest.raises(ValidationError):
        AppConfig.model_validate({"alerts": {"memory_percent": "mucho"}})


def test_store_roundtrip(tmp_path):
    store = ConfigStore(tmp_path / "config.json")
    cfg = store.load(create_if_missing=True)
    assert store.path.exists()
    cfg.alerts.memory_percent = 77
    store.save(cfg)
    store2 = ConfigStore(tmp_path / "config.json")
    assert store2.load().alerts.memory_percent == 77


def test_store_invalid_file(tmp_path):
    p = tmp_path / "config.json"
    p.write_text("{no es json")
    store = ConfigStore(p)
    with pytest.raises(ConfigError):
        store.load()


def test_validate_file_ok_and_bad(tmp_path):
    good = tmp_path / "good.json"
    good.write_text(json.dumps({"version": 1}))
    assert ConfigStore.validate_file(good).version == 1
    bad = tmp_path / "bad.json"
    bad.write_text('{"alerts": {"memory_percent": "xx"}}')
    with pytest.raises(ConfigError):
        ConfigStore.validate_file(bad)
