"""Entry point CLI: wsl-manager (paridad total con la GUI, seccion 19 del plan).

Exit codes: 0 OK, 1 error funcional, 2 error de argumentos, 3 config invalida.
"""
from __future__ import annotations

import sys
from typing import Optional

import typer

from src import __version__
from src.cli import commands_distros, commands_limits, commands_monitor, commands_schedule, commands_ux
from src.cli.common import new_context

app = typer.Typer(
    name="wsl-manager",
    help="WSL Manager: gestion de distros WSL (GUI/CLI/API/MCP/web con los mismos providers)",
    no_args_is_help=True,
)

app.add_typer(commands_distros.app, name="distros", help="Gestion de distros (W1-W14)")
app.add_typer(commands_limits.app, name="limits", help="Limites y recursos (R1-R8)")
app.add_typer(commands_monitor.app, name="monitor", help="Monitoring y alertas (M1-M8)")
app.add_typer(commands_schedule.app, name="schedule", help="Programador (A2)")
app.add_typer(commands_ux.app, name="ux", help="Config, diagnostico, gui, api, web (U1-U10)")
app.add_typer(commands_ux.config_app, name="config", help="Gestion del config.json (U5)")
app.add_typer(commands_ux.autostart_app, name="autostart", help="Autoarranque de distros (W5)")
app.add_typer(commands_ux.api_app, name="api", help="Gestion de la API REST (P1)")
app.add_typer(commands_ux.web_app, name="web", help="Panel web local (M7, P2)")


@app.callback()
def main_callback(
    ctx: typer.Context,
    config: Optional[str] = typer.Option(None, "--config", help="ruta alternativa de config.json"),
    log_level: Optional[str] = typer.Option(None, "--log-level", help="DEBUG|INFO|WARNING|ERROR"),
):
    """Contexto compartido para todos los comandos."""
    # stdout de Windows es cp1252: fuerza UTF-8 tolerante para salidas de wsl.exe
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except Exception:  # noqa: BLE001
            pass
    ctx.obj = new_context(config)
    if log_level:
        from src.core.logger import setup_logging

        setup_logging(log_level)


# ---------------------------------------------------------------------------
# Comandos directos (seccion 19.4: wsl-manager list, start, stop, ...).
# Wrappers explicitos: misma firma que el comando del grupo 'distros'.
# ---------------------------------------------------------------------------

@app.command("list")
def _list(ctx: typer.Context, json_out: bool = typer.Option(False, "--json"), filter: Optional[str] = typer.Option(None, "--filter")):
    """Lista distros con estado, version, default e IP (W1)."""
    return commands_distros.list_distros(ctx, json_out=json_out, filter=filter)


@app.command("start")
def _start(
    ctx: typer.Context,
    distro: Optional[str] = typer.Argument(None),
    cascade: bool = typer.Option(False, "--cascade", help="inicia respetando dependencias (W8)"),
    all_: bool = typer.Option(False, "--all", help="inicia todas las distros"),
):
    """Inicia una distro (o todas con --all, o en cascada con --cascade) (W2)."""
    return commands_distros.start(ctx, distro, cascade=cascade, all_=all_)


@app.command("stop")
def _stop(ctx: typer.Context, distro: str):
    """Detiene una distro (W2)."""
    return commands_distros.stop(ctx, distro)


@app.command("restart")
def _restart(ctx: typer.Context, distro: str):
    """Reinicia una distro (W2)."""
    return commands_distros.restart(ctx, distro)


@app.command("stop-all")
def _stop_all(ctx: typer.Context):
    """Apaga todas las distros (W2)."""
    return commands_distros.stop_all(ctx)


@app.command("ips")
def _ips(ctx: typer.Context, distro: Optional[str] = None, json_out: bool = typer.Option(False, "--json")):
    """IPs de las distros (W3)."""
    return commands_distros.ips(ctx, distro=distro, json_out=json_out)


@app.command("export")
def _export(ctx: typer.Context, distro: str, path: str):
    """Exporta una distro a un .tar (W4)."""
    return commands_distros.export(ctx, distro, path)


@app.command("import")
def _import(ctx: typer.Context, path: str, name: str, install_dir: Optional[str] = None):
    """Importa una distro desde un .tar (W4)."""
    return commands_distros.import_distro(ctx, path, name, install_dir)


@app.command("snapshot")
def _snapshot(ctx: typer.Context, distro: str, retention: int = typer.Option(0, "--retention", help="dias de retencion (0 = config)")):
    """Crea un snapshot fechado de la distro (W6)."""
    return commands_distros.snapshot(ctx, distro, retention)


@app.command("snapshots-list")
def _snapshots_list(ctx: typer.Context, json_out: bool = typer.Option(False, "--json")):
    """Lista snapshots (W6)."""
    return commands_distros.snapshots_list(ctx, json_out=json_out)


@app.command("snapshots-prune")
def _snapshots_prune(ctx: typer.Context):
    """Purga snapshots vencidos (W6)."""
    return commands_distros.snapshots_prune(ctx)


@app.command("clone")
def _clone(ctx: typer.Context, distro: str, new_name: str):
    """Clona una distro (W7)."""
    return commands_distros.clone(ctx, distro, new_name)


@app.command("group")
def _group(ctx: typer.Context, action: str = typer.Argument(help="start|stop|list"), grupo: Optional[str] = typer.Argument(None)):
    """Actua sobre grupos de distros (W9)."""
    return commands_distros.group(ctx, action, grupo)


@app.command("run")
def _run(ctx: typer.Context, distro: str, cmd: str = typer.Argument(help="comando a ejecutar")):
    """Ejecuta un comando dentro de la distro (W10/W11)."""
    return commands_distros.run(ctx, distro, cmd)


@app.command("deps")
def _deps(ctx: typer.Context, check: str = typer.Argument("check", help="check")):
    """Comprueba dependencias de arranque (W8/A5)."""
    return commands_distros.deps(ctx, check)


@app.command("shell")
def _shell(ctx: typer.Context, distro: str):
    """Abre una terminal para la distro."""
    return commands_distros.shell(ctx, distro)


@app.command("explorer")
def _explorer(ctx: typer.Context, distro: str):
    """Abre la carpeta de la distro en el explorador."""
    return commands_distros.explorer(ctx, distro)


@app.command("set-default")
def _set_default(ctx: typer.Context, distro: str):
    """Marca una distro como default."""
    return commands_distros.set_default(ctx, distro)


@app.command("profile-list")
def _profile_list(ctx: typer.Context, json_out: bool = typer.Option(False, "--json")):
    """Lista perfiles (A3)."""
    return commands_schedule.profile_list(ctx, json_out=json_out)


@app.command("profile-capture")
def _profile_capture(ctx: typer.Context, name: str, desc: Optional[str] = typer.Option(None, "--desc")):
    """Captura el estado actual como perfil (A3)."""
    return commands_schedule.profile_capture(ctx, name, desc)


@app.command("profile-apply")
def _profile_apply(ctx: typer.Context, name: str):
    """Aplica un perfil (A3)."""
    return commands_schedule.profile_apply(ctx, name)


@app.command("version")
def version():
    """Muestra la version."""
    typer.echo(f"wsl-manager {__version__}")


@app.command("status")
def _status(ctx: typer.Context, json_out: bool = typer.Option(False, "--json")):
    """Estado global (P0)."""
    return commands_ux.status(ctx, json_out=json_out)


@app.command("doctor")
def _doctor(ctx: typer.Context, json_out: bool = typer.Option(False, "--json")):
    """Detector de problemas (U8)."""
    return commands_ux.doctor(ctx, json_out=json_out)


@app.command("diag")
def _diag(ctx: typer.Context, out: Optional[str] = typer.Option(None, "--out", help="ruta del zip")):
    """Bundle de diagnostico (U7)."""
    return commands_ux.diag(ctx, out=out)


@app.command("supervise")
def _supervise(ctx: typer.Context, log_level: Optional[str] = typer.Option(None, "--log-level")):
    """Watcher en foreground sin GUI (P0)."""
    return commands_ux.supervise(ctx, log_level=log_level)


@app.command("watch")
def _watch(ctx: typer.Context, json_out: bool = typer.Option(False, "--json")):
    """Eventos en vivo estilo tail -f (P1)."""
    return commands_ux.watch(ctx, json_out=json_out)


@app.command("mcp")
def _mcp(ctx: typer.Context, action: str = typer.Argument(help="serve|test")):
    """Servidor MCP (P1)."""
    return commands_ux.mcp(ctx, action)


@app.command("gui")
def _gui(ctx: typer.Context, action: str = typer.Argument(help="show|hide|quit")):
    """Controla la instancia GUI via IPC (P1)."""
    return commands_ux.gui(ctx, action)


def main() -> None:
    app()


if __name__ == "__main__":
    main()
