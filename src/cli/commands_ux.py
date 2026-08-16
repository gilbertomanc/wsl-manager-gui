"""Comandos de configuracion y UX (U1-U10): config, doctor, diag, status, supervise, watch, gui, api, autostart, web."""
from __future__ import annotations

import json
import platform
import sys
import time
import zipfile
from datetime import datetime
from pathlib import Path
from typing import Optional

import typer

from src.cli.common import EXIT_ERROR
from src.core.config import ConfigStore, localappdata_dir
from src.core.event_bus import EventBus
from src.core.metrics_store import MetricsStore
from src.core.notifier import notify
from src.core.power_events import PowerWatcher
from src.core.scheduler import Scheduler
from src.core.watcher import Watcher

app = typer.Typer(help="Configuracion y diagnostico (U1-U10)", no_args_is_help=True)

config_app = typer.Typer(help="Gestion del config.json (U5)", no_args_is_help=True)


@config_app.command("validate", help="Valida el config.json (U5)")
def config_validate(ctx: typer.Context, path: Optional[str] = typer.Option(None, "--path")):
    try:
        if path:
            ConfigStore.validate_file(path)
        else:
            ctx.obj.store.load()
        typer.echo("config valida")
    except Exception as e:
        typer.echo(f"config INVALIDA: {e}", err=True)
        raise typer.Exit(3)


@config_app.command("show", help="Muestra la config efectiva")
def config_show(ctx: typer.Context, json_out: bool = typer.Option(False, "--json")):
    cfg = ctx.obj.store.get()
    if json_out:
        ctx.obj.emit_json(cfg.model_dump(by_alias=True, exclude_none=True))
    else:
        typer.echo(json.dumps(cfg.model_dump(by_alias=True, exclude_none=True), indent=2, ensure_ascii=False))


@config_app.command("export")
def config_export(ctx: typer.Context, path: str):
    """Exporta la config a un archivo (U5)."""
    cfg = ctx.obj.store.get()
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    Path(path).write_text(json.dumps(cfg.model_dump(by_alias=True, exclude_none=True), indent=2, ensure_ascii=False), encoding="utf-8")
    typer.echo(f"config exportada a {path}")


@config_app.command("import")
def config_import(ctx: typer.Context, path: str):
    """Importa y valida una config (U5)."""
    try:
        cfg = ConfigStore.validate_file(path)
    except Exception as e:
        typer.echo(f"error: {e}", err=True)
        raise typer.Exit(3)
    ctx.obj.store.save(cfg)
    typer.echo("config importada y guardada")


app.add_typer(config_app, name="config")


# ---------------------------------------------------------------- doctor --

@app.command("doctor", help="Detector de problemas (U8)")
def doctor(ctx: typer.Context, json_out: bool = typer.Option(False, "--json")):
    c = ctx.obj
    checks: list[dict] = []
    ok = True

    def add(name: str, passed: bool, detail: str = "") -> None:
        nonlocal ok
        ok = ok and passed
        checks.append({"check": name, "ok": passed, "detail": detail})

    # WSL instalado
    r = c.wsl.version()
    add("wsl.exe disponible", r.ok, r.output.strip()[:120] if r.ok else r.error)

    # Distros
    try:
        distros = c.wsl.list_distros()
        add("distros detectadas", len(distros) > 0, f"{len(distros)} distro(s)")
    except Exception as e:
        add("distros detectadas", False, str(e))

    # config
    try:
        c.store.load()
        add("config.json valida", True, str(c.store.path))
    except Exception as e:
        add("config.json valida", False, str(e))

    # metrics db
    try:
        m = MetricsStore()
        m.list_alerts(1)
        add("metrics.db escribible", True, str(m.path))
    except Exception as e:
        add("metrics.db escribible", False, str(e))

    # permisos escritura de .wslconfig
    try:
        c.wsl_config.backup_now()
        add("backup de .wslconfig posible", True)
    except Exception as e:
        add("backup de .wslconfig posible", False, str(e))

    if json_out:
        c.emit_json({"ok": ok, "checks": checks})
        return
    for chk in checks:
        mark = "OK " if chk["ok"] else "FAIL"
        typer.echo(f"[{mark}] {chk['check']}: {chk['detail']}")
    typer.echo("doctor: TODO OK" if ok else "doctor: hay problemas que revisar")
    if not ok:
        raise typer.Exit(EXIT_ERROR)


# ---------------------------------------------------------------- diag ----

@app.command("diag", help="Bundle de diagnostico (U7)")
def diag(ctx: typer.Context, out: Optional[str] = typer.Option(None, "--out", help="ruta del zip")):
    c = ctx.obj
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    target = Path(out) if out else Path.cwd() / f"wsl-manager-diag-{stamp}.zip"
    with zipfile.ZipFile(target, "w", zipfile.ZIP_DEFLATED) as z:
        def add(name: str, content: str) -> None:
            z.writestr(name, content)

        add("info.txt", f"fecha: {datetime.now().isoformat()}\nplataforma: {platform.platform()}\npython: {sys.version}\n")
        add("wsl-version.txt", c.wsl.version().output)
        add("wsl-list.txt", c.wsl._wsl(["-l", "-v"]).output)  # noqa: SLF001
        add("config.json", json.dumps(c.store.get().model_dump(by_alias=True, exclude_none=True), indent=2))
        add("status.json", json.dumps(Watcher(c.store, MetricsStore(), EventBus(), c.wsl).snapshot_state(), indent=2, default=str))
        logf = localappdata_dir() / "logs" / "wsl-manager.log"
        if logf.exists():
            add("logs/wsl-manager.log", logf.read_text(encoding="utf-8", errors="replace")[-200_000:])
    typer.echo(f"bundle de diagnostico: {target}")


# ---------------------------------------------------------------- status --

@app.command("status", help="Estado global (P0)")
def status(ctx: typer.Context, json_out: bool = typer.Option(False, "--json")):
    c = ctx.obj
    state = Watcher(c.store, c.metrics, c.bus, c.wsl).snapshot_state()
    if json_out:
        c.emit_json(state)
        return
    running = [d for d in state["distros"] if d["running"]]
    typer.echo(f"distros: {len(running)}/{len(state['distros'])} corriendo")
    for d in state["distros"]:
        typer.echo(f"  {'*' if d['default'] else ' '} {d['name']:<26} {d['state']:<10} IP={d['ip'] or '-'}")


# ------------------------------------------------------- supervise/watch --

@app.command("supervise", help="Watcher en foreground sin GUI (P0)")
def supervise(ctx: typer.Context, log_level: Optional[str] = typer.Option(None, "--log-level")):
    from src.core.logger import get_logger, setup_logging

    c = ctx.obj
    setup_logging(log_level or c.config.ui.log_level)
    log = get_logger("supervise")
    watcher = Watcher(c.store, c.metrics, c.bus, c.wsl)
    scheduler = Scheduler(c.store, c.metrics, c.bus, c.wsl)
    power = PowerWatcher(c.store, c.metrics, c.bus)
    watcher.start()
    scheduler.start()
    power.start()
    log.info("supervise activo (Ctrl+C para salir)")
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        log.info("deteniendo supervise")
        watcher.stop()
        scheduler.stop()
        power.stop()


@app.command("watch", help="Eventos en vivo estilo tail -f (P1)")
def watch(ctx: typer.Context, json_out: bool = typer.Option(False, "--json")):
    c = ctx.obj
    bus = EventBus()
    watcher = Watcher(c.store, c.metrics, bus, c.wsl)

    def on_event(event: str, payload: dict) -> None:
        if json_out:
            print(json.dumps({"event": event, **payload}, default=str))
        else:
            if event == "state-changed":
                distros = payload.get("distros", [])
                running = sum(1 for d in distros if d.get("running"))
                typer.echo(f"[{time.strftime('%H:%M:%S')}] estado: {running}/{len(distros)} corriendo")
            else:
                typer.echo(f"[{time.strftime('%H:%M:%S')}] {event}: {json.dumps(payload, default=str)[:120]}")

    bus.subscribe_all(on_event)
    watcher.start()
    typer.echo("vigilando eventos (Ctrl+C para salir)")
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        watcher.stop()


# ---------------------------------------------------------------- gui ----

@app.command("gui")
def gui(ctx: typer.Context, action: str = typer.Argument(help="show|hide|quit")):
    """Controla la instancia GUI via IPC (P1). Requiere la GUI corriendo."""
    typer.echo(
        f"gui {action}: el IPC se habilita con la GUI en ejecucion "
        "(stub: usa la GUI para show/hide, o wsl-manager quit desde ella)",
    )


# ------------------------------------------------------------- autostart --

autostart_app = typer.Typer(help="Autoarranque de distros (W5)", no_args_is_help=True)


@autostart_app.command("set")
def autostart_set(ctx: typer.Context, distro: str, delay: int = typer.Option(0, "--delay", help="segundos de espera")):
    c = ctx.obj
    r = c.autostart.set_autostart(distro, True, delay)
    if not r.ok:
        typer.echo(f"error: {r.error}", err=True)
        raise typer.Exit(EXIT_ERROR)
    c.metrics.log_event("autostart_set", distro, f"autoarranque activado (delay {delay}s)")
    typer.echo(r.output)


@autostart_app.command("unset")
def autostart_unset(ctx: typer.Context, distro: str):
    r = ctx.obj.autostart.set_autostart(distro, False)
    if not r.ok:
        typer.echo(f"error: {r.error}", err=True)
        raise typer.Exit(EXIT_ERROR)
    typer.echo(r.output)


@autostart_app.command("list")
def autostart_list(ctx: typer.Context, json_out: bool = typer.Option(False, "--json")):
    items = ctx.obj.autostart.list_autostart()
    if json_out:
        ctx.obj.emit_json(items)
        return
    if not items:
        typer.echo("(sin distros en autoarranque)")
        return
    for distro, info in items.items():
        typer.echo(f"{distro:<24} {info['command']}")


app.add_typer(autostart_app, name="autostart")


# ---------------------------------------------------------------- api ----

api_app = typer.Typer(help="Gestion de la API REST (P1)", no_args_is_help=True)


@api_app.command("enable")
def api_enable(ctx: typer.Context, port: int = typer.Option(8791, "--port")):
    cfg = ctx.obj.store.get()
    cfg.api.enabled = True
    cfg.api.port = port
    ctx.obj.store.save(cfg)
    typer.echo(f"API habilitada en http://{cfg.api.host}:{port} (activa en la proxima ejecucion)")


@api_app.command("disable")
def api_disable(ctx: typer.Context):
    cfg = ctx.obj.store.get()
    cfg.api.enabled = False
    ctx.obj.store.save(cfg)
    typer.echo("API deshabilitada")


@api_app.command("status")
def api_status(ctx: typer.Context, json_out: bool = typer.Option(False, "--json")):
    cfg = ctx.obj.store.get().api
    if json_out:
        ctx.obj.emit_json(cfg.model_dump())
        return
    typer.echo(cfg.model_dump())


@api_app.command("tokens")
def api_tokens(
    ctx: typer.Context,
    action: str = typer.Argument(help="create|list|revoke"),
    scope: str = typer.Option("read", "--scope", help="read|write|admin"),
    expires_days: Optional[int] = typer.Option(None, "--expires", help="dias de validez"),
    note: str = typer.Option("", "--note"),
    token_id: Optional[int] = typer.Option(None, "--id"),
):
    """Tokens de la API/MCP (P1)."""
    import hashlib
    import secrets

    c = ctx.obj
    if action == "list":
        rows = c.metrics.list_tokens()
        for r in rows:
            typer.echo(f"#{r['id']}  scope={r['scope']:<6} creado={r['created']:.0f} expira={r['expires'] or '-'}  {r['note']}")
        return
    if action == "revoke":
        if token_id is None:
            typer.echo("--id requerido", err=True)
            raise typer.Exit(2)
        if c.metrics.revoke_token(token_id):
            typer.echo(f"token #{token_id} revocado")
        else:
            typer.echo(f"token #{token_id} no existe", err=True)
            raise typer.Exit(EXIT_ERROR)
        return
    if action == "create":
        token = secrets.token_urlsafe(32)
        expires = time.time() + expires_days * 86400 if expires_days else None
        c.metrics.add_token(hashlib.sha256(token.encode()).hexdigest(), scope, expires, note)
        typer.echo(f"TOKEN (guardalo, no se vuelve a mostrar): {token}")
        typer.echo(f"uso: Authorization: Bearer {token}")
        return
    typer.echo("accion debe ser create|list|revoke", err=True)
    raise typer.Exit(2)


app.add_typer(api_app, name="api")


# ---------------------------------------------------------------- mcp ----

@app.command("mcp", help="Servidor MCP (P1): mcp serve | mcp test")
def mcp(ctx: typer.Context, action: str = typer.Argument(help="serve|test")):
    if action == "serve":
        try:
            from src.mcp.server import run_stdio
        except ImportError:
            typer.echo("falta el paquete 'mcp'. Instala: pip install mcp", err=True)
            raise typer.Exit(EXIT_ERROR)
        run_stdio(ctx.obj)
        return
    if action == "test":
        typer.echo("MCP test: check de dependencia")
        try:
            import mcp  # noqa: F401

            typer.echo("paquete mcp instalado")
        except ImportError:
            typer.echo("paquete mcp NO instalado", err=True)
            raise typer.Exit(EXIT_ERROR)
        return
    typer.echo("accion debe ser serve|test", err=True)
    raise typer.Exit(2)


# ---------------------------------------------------------------- web ----

web_app = typer.Typer(help="Panel web local (M7, P2): dashboard en el navegador", no_args_is_help=True)


@web_app.command("serve")
def web_serve(ctx: typer.Context, port: int = typer.Option(8790, "--port"), host: str = typer.Option("127.0.0.1", "--host")):
    """Arranca el panel web en foreground (http://127.0.0.1:8790)."""
    import uvicorn

    from src.web.web_app import create_web_app

    uvicorn.run(create_web_app(ctx.obj), host=host, port=port, log_level="info", server_header=False)


@web_app.command("enable")
def web_enable(ctx: typer.Context):
    cfg = ctx.obj.store.get()
    cfg.ui.web_panel_enabled = True
    ctx.obj.store.save(cfg)
    typer.echo("panel web habilitado (arranca con la app; o 'web serve')")


@web_app.command("disable")
def web_disable(ctx: typer.Context):
    cfg = ctx.obj.store.get()
    cfg.ui.web_panel_enabled = False
    ctx.obj.store.save(cfg)
    typer.echo("panel web deshabilitado")


app.add_typer(web_app, name="web")


# ---------------------------------------------------------------- otros --

@app.command("test-notify", help="Prueba un toast de Windows")
def test_notify(ctx: typer.Context):
    notify("WSL Manager", "Notificacion de prueba")
    typer.echo("toast enviado (o registrado en log si no hay soporte)")


@app.command("run-server", help="Arranca la API REST en foreground (P1)")
def run_server(ctx: typer.Context, port: Optional[int] = typer.Option(None, "--port")):
    import uvicorn

    from src.api.server import create_app

    cfg = ctx.obj.store.get().api
    app_obj = create_app(ctx.obj)
    uvicorn.run(app_obj, host=cfg.host, port=port or cfg.port, log_level="info", server_header=False)
