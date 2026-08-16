"""Smoke tests del CLI con typer.testing (seccion 19.6)."""
from __future__ import annotations

import json

from typer.testing import CliRunner

from src.cli.cli import app

runner = CliRunner()


def test_version():
    r = runner.invoke(app, ["version"])
    assert r.exit_code == 0
    assert "wsl-manager" in r.output


def test_help():
    r = runner.invoke(app, ["--help"])
    assert r.exit_code == 0
    for cmd in ["distros", "limits", "monitor", "schedule", "ux", "config", "autostart", "api", "web", "list", "status", "supervise"]:
        assert cmd in r.output


def test_limits_global_get_json(tmp_path):
    cfg = tmp_path / "config.json"
    r = runner.invoke(app, ["--config", str(cfg), "limits", "global", "--json"])
    assert r.exit_code == 0
    data = json.loads(r.output)
    # JSON con solo campos no-nulos (puede ser {} si no hay limites)
    assert set(data).issubset({"memory_gb", "processors", "swap_gb", "auto_memory_reclaim", "sparse_vhd"})


def test_status_json(tmp_path):
    cfg = tmp_path / "config.json"
    r = runner.invoke(app, ["--config", str(cfg), "status", "--json"])
    assert r.exit_code == 0
    data = json.loads(r.output)
    assert "distros" in data


def test_autostart_list_json(tmp_path):
    cfg = tmp_path / "config.json"
    r = runner.invoke(app, ["--config", str(cfg), "autostart", "list", "--json"])
    assert r.exit_code == 0
    assert isinstance(json.loads(r.output), dict)


def test_config_validate(tmp_path):
    cfg = tmp_path / "config.json"
    r = runner.invoke(app, ["--config", str(cfg), "config", "validate"])
    assert r.exit_code == 0
    assert "config valida" in r.output


def test_status_direct(tmp_path):
    cfg = tmp_path / "config.json"
    r = runner.invoke(app, ["--config", str(cfg), "status", "--json"])
    assert r.exit_code == 0
    assert "distros" in json.loads(r.output)


def test_schedule_add_and_list(tmp_path):
    cfg = tmp_path / "config.json"
    r = runner.invoke(app, ["--config", str(cfg), "schedule", "add", "--name", "Test", "--type", "distro_start", "--distro", "x", "--time", "10:00"])
    assert r.exit_code == 0
    r2 = runner.invoke(app, ["--config", str(cfg), "schedule", "list", "--json"])
    tasks = json.loads(r2.output)
    assert tasks[0]["name"] == "Test"


def test_doctor_json(tmp_path):
    cfg = tmp_path / "config.json"
    r = runner.invoke(app, ["--config", str(cfg), "ux", "doctor", "--json"])
    assert r.exit_code == 0
    data = json.loads(r.output)
    assert "checks" in data
