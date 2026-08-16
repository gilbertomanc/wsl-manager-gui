"""Tests del ResourceProvider (limites globales) con mocks."""
from __future__ import annotations

from unittest.mock import patch

from src.core.config import ConfigStore, GlobalLimits
from src.providers.resource_provider import ResourceProvider
from src.providers.wsl_config_provider import WslConfigProvider


def _provider(tmp_path):
    store = ConfigStore(tmp_path / "config.json")
    store.load()
    rp = ResourceProvider(store)
    return rp, store


def _ok_result():
    return type("R", (), {"ok": True, "error": ""})()


def test_get_global_defaults(tmp_path):
    rp, _ = _provider(tmp_path)
    limits = rp.get_global_limits()
    assert limits.memory_gb is None


def test_set_global_writes_wslconfig(tmp_path):
    rp, store = _provider(tmp_path)
    with patch.object(WslConfigProvider, "write_wslconfig", return_value=_ok_result()) as m:
        r = rp.set_global_limits(GlobalLimits(memory_gb=8, processors=4, swap_gb=2, auto_memory_reclaim="gradual"))
    assert r.ok
    sections = m.call_args[0][0]
    assert sections["wsl2"]["memory"] == "8GB"
    assert sections["wsl2"]["processors"] == "4"
    assert sections["wsl2"]["autoMemoryReclaim"] == "gradual"
    # persistido en config.json
    assert store.load().resources.global_limits.memory_gb == 8


def test_set_global_float_format(tmp_path):
    rp, _ = _provider(tmp_path)
    with patch.object(WslConfigProvider, "write_wslconfig", return_value=_ok_result()) as m:
        rp.set_global_limits(GlobalLimits(memory_gb=8.5))
    assert m.call_args[0][0]["wsl2"]["memory"] == "8.5GB"


def test_set_global_error_propagates(tmp_path):
    rp, store = _provider(tmp_path)
    with patch.object(WslConfigProvider, "write_wslconfig", return_value=type("R", (), {"ok": False, "error": "no"})()):
        r = rp.set_global_limits(GlobalLimits(memory_gb=4))
    assert not r.ok
    assert store.load().resources.global_limits.memory_gb is None  # no se persistio


def test_recommend_limits(tmp_path):
    rp, _ = _provider(tmp_path)
    rec = rp.recommend_limits(32, 16)
    assert rec["memory_gb"] == 16.0
    assert rec["processors"] == 8
