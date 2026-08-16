"""Tests de escritura segura de .wslconfig (R2/R7)."""
from __future__ import annotations

from pathlib import Path

from src.providers.wsl_config_provider import WslConfigProvider


def _provider(tmp_path: Path, monkeypatch) -> WslConfigProvider:
    p = WslConfigProvider(str(tmp_path))
    monkeypatch.setattr("src.providers.wsl_config_provider.backups_dir", lambda: tmp_path / "backups")
    (tmp_path / "backups").mkdir(exist_ok=True)
    return p


def test_write_creates_backup_and_file(tmp_path, monkeypatch):
    p = _provider(tmp_path, monkeypatch)
    # el backup solo existe si habia algo previo que respaldar
    (tmp_path / ".wslconfig").write_text("[wsl2]\nmemory=4GB\n", encoding="utf-8")
    r = p.write_wslconfig({"wsl2": {"memory": "8GB"}})
    assert r.ok
    assert (tmp_path / ".wslconfig").exists()
    backups = list((tmp_path / "backups").glob("wslconfig-*.bak"))
    assert len(backups) == 1
    assert "4GB" in backups[0].read_text(encoding="utf-8")


def test_write_rejects_invalid_ini(tmp_path, monkeypatch):
    p = _provider(tmp_path, monkeypatch)
    # un valor con salto de linea y seccion sin cerrar rompe configparser
    r = p.write_wslconfig({"wsl2": {"memory": "8GB"}, "rota": {"x": "a\n[invalida"}})
    assert not r.ok


def test_read_missing_returns_empty(tmp_path, monkeypatch):
    p = _provider(tmp_path, monkeypatch)
    assert p.read_wslconfig() == {}


def test_roundtrip_after_write(tmp_path, monkeypatch):
    p = _provider(tmp_path, monkeypatch)
    p.write_wslconfig({"wsl2": {"memory": "8GB", "processors": "4"}})
    parsed = p.read_wslconfig()
    assert parsed["wsl2"]["memory"] == "8GB"
    assert parsed["wsl2"]["processors"] == "4"
