"""Smoke check integral: CLI real + panel web + API REST (seccion 19.6 del plan).

Uso: .venv\\Scripts\\python scripts\\smoke_check.py
No inicia/detiene distros: solo operaciones de solo lectura (list/status/ips/doctor).
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import threading
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

PY = sys.executable
RESULTS: list[tuple[str, bool, str]] = []


def check(name: str, fn) -> None:
    try:
        fn()
        RESULTS.append((name, True, ""))
        print(f"  [OK] {name}")
    except Exception as e:  # noqa: BLE001
        RESULTS.append((name, False, str(e)))
        print(f"  [FAIL] {name}: {e}")


def run_cli(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run([PY, "-m", "src.cli", *args], capture_output=True, text=True, cwd=ROOT, timeout=180, encoding="utf-8", errors="replace")


def test_cli_version() -> None:
    r = run_cli("version")
    assert r.returncode == 0, r.stderr
    assert "wsl-manager" in r.stdout


def test_cli_list_json() -> None:
    r = run_cli("list", "--json")
    assert r.returncode == 0, r.stderr
    data = json.loads(r.stdout)
    assert isinstance(data, list)


def test_cli_status_json() -> None:
    r = run_cli("status", "--json")
    assert r.returncode == 0, r.stderr
    data = json.loads(r.stdout)
    assert "distros" in data


def test_cli_ips() -> None:
    r = run_cli("ips", "--json")
    assert r.returncode == 0, r.stderr
    assert isinstance(json.loads(r.stdout), dict)


def test_cli_doctor() -> None:
    r = run_cli("doctor", "--json")
    assert r.returncode == 0, r.stderr
    data = json.loads(r.stdout)
    assert "checks" in data


def test_cli_config_validate() -> None:
    r = run_cli("config", "validate")
    assert r.returncode == 0, r.stderr
    assert "config valida" in r.stdout


def test_cli_limits_get() -> None:
    r = run_cli("limits", "global", "--json")
    assert r.returncode == 0, r.stderr
    assert isinstance(json.loads(r.stdout), dict)


def test_cli_monitor_once() -> None:
    r = run_cli("monitor", "once", "--json")
    assert r.returncode == 0, r.stderr
    assert "metrics" in json.loads(r.stdout)


def test_web_panel() -> None:
    import uvicorn

    from src.cli.common import new_context
    from src.web.web_app import create_web_app

    ctx = new_context()
    server = uvicorn.Server(uvicorn.Config(create_web_app(ctx), host="127.0.0.1", port=8790, log_level="warning"))
    t = threading.Thread(target=server.run, daemon=True)
    t.start()
    try:
        deadline = time.time() + 15
        while not server.started and time.time() < deadline:
            time.sleep(0.2)
        assert server.started, "uvicorn no arranco"

        import httpx

        with httpx.Client(base_url="http://127.0.0.1:8790", timeout=10) as client:
            r = client.get("/")
            assert r.status_code == 200 and "WSL Manager" in r.text
            r = client.get("/api/status")
            assert r.status_code == 200 and "distros" in r.json()
            r = client.get("/api/metrics")
            assert r.status_code == 200
            r = client.get("/api/alerts")
            assert r.status_code == 200
            r = client.get("/api/events")
            assert r.status_code == 200
    finally:
        server.should_exit = True
        t.join(timeout=10)


def test_api_rest() -> None:
    import uvicorn

    from src.api.server import create_app
    from src.cli.common import new_context

    ctx = new_context()
    server = uvicorn.Server(uvicorn.Config(create_app(ctx), host="127.0.0.1", port=8791, log_level="warning"))
    t = threading.Thread(target=server.run, daemon=True)
    t.start()
    try:
        deadline = time.time() + 15
        while not server.started and time.time() < deadline:
            time.sleep(0.2)
        assert server.started

        import httpx

        with httpx.Client(base_url="http://127.0.0.1:8791", timeout=10) as client:
            r = client.get("/api/v1/health")
            assert r.status_code == 200 and r.json()["ok"] is True
            r = client.get("/api/v1/distros")
            assert r.status_code == 200 and "distros" in r.json()
            r = client.get("/api/v1/status")
            assert r.status_code == 200
            r = client.get("/api/v1/metrics")
            assert r.status_code == 200
            r = client.get("/api/v1/limits/global")
            assert r.status_code == 200
            r = client.get("/api/v1/schedule")
            assert r.status_code == 200
            r = client.get("/api/v1/profiles")
            assert r.status_code == 200
    finally:
        server.should_exit = True
        t.join(timeout=10)


def test_gui_imports() -> None:
    import importlib

    for mod in ["src.gui.window", "src.gui.tray", "src.gui.tabs.dashboard_tab", "src.app", "src.mcp.tools", "src.web.web_app"]:
        importlib.import_module(mod)


def main() -> None:
    print("== WSL Manager smoke check ==")
    print(f"  python: {sys.version.split()[0]}")
    print("  CLI:")
    check("version", test_cli_version)
    check("list --json", test_cli_list_json)
    check("status --json", test_cli_status_json)
    check("ips --json", test_cli_ips)
    check("doctor --json", test_cli_doctor)
    check("config validate", test_cli_config_validate)
    check("limits global --json", test_cli_limits_get)
    check("monitor once --json", test_cli_monitor_once)
    print("  Interfaces:")
    check("panel web (127.0.0.1:8790)", test_web_panel)
    check("API REST (127.0.0.1:8791)", test_api_rest)
    check("imports GUI/MCP/web", test_gui_imports)

    failed = [r for r in RESULTS if not r[1]]
    print(f"\n== Resultado: {len(RESULTS) - len(failed)}/{len(RESULTS)} OK ==")
    for name, ok, err in RESULTS:
        if not ok:
            print(f"  [FAIL] {name}: {err}")
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
