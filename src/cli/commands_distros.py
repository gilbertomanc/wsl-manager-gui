"""Comandos de distros (W1-W14): list, start, stop, restart, ips, export,
import, snapshot, clone, group, run, vhd, rename."""
from __future__ import annotations

from typing import Optional

import typer

from src.cli.common import EXIT_ERROR
from src.core.config import snapshot_dir

app = typer.Typer(help="Gestion de distros WSL (W1-W14)", no_args_is_help=True)


@app.command("list")
def list_distros(ctx: typer.Context, json_out: bool = typer.Option(False, "--json"), filter: Optional[str] = typer.Option(None, "--filter")):
    """Lista distros con estado, version, default e IP."""
    c = ctx.obj
    distros = c.wsl.list_distros()
    for d in distros:
        if d.state == "Running":
            d.ip = c.wsl.get_ip(d.name)
    if filter:
        distros = [d for d in distros if filter.lower() in d.name.lower()]
    if json_out:
        c.emit_json([d.to_dict() for d in distros])
        return
    if not distros:
        typer.echo("(sin distros o WSL no disponible)")
        return
    for d in distros:
        mark = "*" if d.default else " "
        typer.echo(f"{mark} {d.name:<28} {d.state:<10} WSL{d.version}  IP={d.ip or '-'}")


@app.command("start")
def start(
    ctx: typer.Context,
    distro: Optional[str] = typer.Argument(None),
    cascade: bool = typer.Option(False, "--cascade", help="inicia respetando dependencias (W8)"),
    all_: bool = typer.Option(False, "--all", help="inicia todas las distros"),
):
    """Inicia una distro (o todas con --all, o en cascada con --cascade)."""
    c = ctx.obj
    if cascade:
        from src.core.profiles import ProfileService

        svc = ProfileService(c.store, c.wsl)
        order = svc._topo_order({d.name for d in c.wsl.list_distros()}, {})
        for name in order:
            r = c.wsl.start(name)
            typer.echo(f"  {name}: {'OK' if r.ok else r.error}")
            if not r.ok:
                raise typer.Exit(EXIT_ERROR)
        c.metrics.log_event("start_cascade", message="cascada completada")
        return
    if all_:
        for d in c.wsl.list_distros():
            r = c.wsl.start(d.name)
            typer.echo(f"  {d.name}: {'OK' if r.ok else r.error}")
        return
    if not distro:
        typer.echo("especifica <distro> o usa --all / --cascade", err=True)
        raise typer.Exit(2)
    r = c.wsl.start(distro)
    if not r.ok:
        typer.echo(f"error: {r.error}", err=True)
        raise typer.Exit(EXIT_ERROR)
    c.metrics.log_event("distro_start", distro, "iniciada via CLI")
    typer.echo(f"{distro}: iniciada")


@app.command("stop")
def stop(ctx: typer.Context, distro: str):
    """Detiene una distro."""
    c = ctx.obj
    r = c.wsl.stop(distro)
    if not r.ok:
        typer.echo(f"error: {r.error}", err=True)
        raise typer.Exit(EXIT_ERROR)
    c.metrics.log_event("distro_stop", distro, "detenida via CLI")
    typer.echo(f"{distro}: detenida")


@app.command("restart")
def restart(ctx: typer.Context, distro: str):
    """Reinicia una distro."""
    c = ctx.obj
    r = c.wsl.restart(distro)
    if not r.ok:
        typer.echo(f"error: {r.error}", err=True)
        raise typer.Exit(EXIT_ERROR)
    typer.echo(f"{distro}: reiniciada")


@app.command("stop-all")
def stop_all(ctx: typer.Context):
    """Apaga todas las distros (wsl --shutdown)."""
    c = ctx.obj
    r = c.wsl.shutdown_all()
    if not r.ok:
        typer.echo(f"error: {r.error}", err=True)
        raise typer.Exit(EXIT_ERROR)
    typer.echo("todas las distros apagadas")


@app.command("ips")
def ips(ctx: typer.Context, distro: Optional[str] = None, json_out: bool = typer.Option(False, "--json")):
    """IPs de las distros (W3)."""
    c = ctx.obj
    if distro:
        result = {distro: c.wsl.get_ip(distro)}
    else:
        result = c.wsl.get_all_ips()
    if json_out:
        c.emit_json(result)
        return
    for name, ip in result.items():
        typer.echo(f"{name:<28} {ip or '-'}")


@app.command("export")
def export(ctx: typer.Context, distro: str, path: str):
    """Exporta una distro a un .tar (W4)."""
    c = ctx.obj
    r = c.wsl.export(distro, path)
    if not r.ok:
        typer.echo(f"error: {r.error}", err=True)
        raise typer.Exit(EXIT_ERROR)
    c.metrics.log_event("distro_export", distro, f"exportada a {path}")
    typer.echo(f"exportada a {path}")


@app.command("import")
def import_distro(ctx: typer.Context, path: str, name: str, install_dir: Optional[str] = None):
    """Importa una distro desde un .tar (W4)."""
    c = ctx.obj
    dest = install_dir or str(snapshot_dir() / f"install-{name}")
    r = c.wsl.import_distro(path, name, dest)
    if not r.ok:
        typer.echo(f"error: {r.error}", err=True)
        raise typer.Exit(EXIT_ERROR)
    c.metrics.log_event("distro_import", name, f"importada de {path}")
    typer.echo(f"{name}: importada en {dest}")


@app.command("clone")
def clone(ctx: typer.Context, distro: str, new_name: str):
    """Clona una distro (W7): export -> import con nombre nuevo."""
    c = ctx.obj
    r = c.wsl.clone(distro, new_name)
    if not r.ok:
        typer.echo(f"error: {r.error}", err=True)
        raise typer.Exit(EXIT_ERROR)
    c.metrics.log_event("distro_clone", distro, f"clonada como {new_name}")
    typer.echo(f"{distro} clonada como {new_name}")


@app.command("snapshot")
def snapshot(ctx: typer.Context, distro: str, retention: int = typer.Option(0, "--retention", help="dias de retencion (0 = config)")):
    """Crea un snapshot fechado de la distro (W6)."""
    c = ctx.obj
    cfg = c.config
    days = retention or cfg.snapshots.retention_days
    try:
        path = c.wsl.snapshot(distro, days, cfg.snapshots.target_dir)
    except RuntimeError as e:
        typer.echo(f"error: {e}", err=True)
        raise typer.Exit(EXIT_ERROR)
    size = path.stat().st_size if path.exists() else 0
    c.metrics.record_snapshot(distro, str(path), size)
    c.metrics.log_event("snapshot", distro, f"snapshot en {path}")
    typer.echo(f"snapshot: {path} ({size / 1e6:.1f} MB)")


@app.command("snapshots-list", help="Lista snapshots (W6)")
def snapshots_list(ctx: typer.Context, json_out: bool = typer.Option(False, "--json")):
    rows = ctx.obj.metrics.list_snapshots()
    if json_out:
        ctx.obj.emit_json(rows)
        return
    for r in rows:
        typer.echo(f"{r['ts']:.0f}  {r['distro']:<20} {r['size_bytes'] or 0:>12,} B  {r['path']}")


@app.command("snapshots-prune", help="Purga snapshots vencidos (W6)")
def snapshots_prune(ctx: typer.Context):
    c = ctx.obj
    days = c.config.snapshots.retention_days
    purged = c.wsl.prune_snapshots(days, c.config.snapshots.target_dir)
    typer.echo(f"purga con retencion {days}d: {len(purged)} archivo(s) eliminado(s)")
    for p in purged:
        typer.echo(f"  - {p}")


@app.command("group")
def group(ctx: typer.Context, action: str = typer.Argument(help="start|stop|list"), grupo: Optional[str] = typer.Argument(None)):
    """Actua sobre grupos de distros (W9)."""
    c = ctx.obj
    cfg = c.config
    if action == "list":
        groups: dict[str, list[str]] = {}
        for i in cfg.distros.instances:
            if i.group:
                groups.setdefault(i.group, []).append(i.name)
        for g, names in groups.items():
            typer.echo(f"{g}: {', '.join(names)}")
        return
    if not grupo:
        typer.echo("especifica el grupo", err=True)
        raise typer.Exit(2)
    names = [i.name for i in cfg.distros.instances if i.group == grupo]
    if not names:
        typer.echo(f"grupo '{grupo}' vacio o inexistente", err=True)
        raise typer.Exit(2)
    for n in names:
        r = c.wsl.start(n) if action == "start" else c.wsl.stop(n)
        typer.echo(f"  {n}: {'OK' if r.ok else r.error}")


@app.command("run")
def run(ctx: typer.Context, distro: str, cmd: str = typer.Argument(help="comando a ejecutar")):
    """Ejecuta un comando dentro de la distro (W10/W11)."""
    c = ctx.obj
    r = c.wsl.run_command(distro, cmd)
    if r.output:
        typer.echo(r.output.rstrip())
    if not r.ok:
        if r.error:
            typer.echo(r.error.rstrip(), err=True)
        raise typer.Exit(EXIT_ERROR)


@app.command("deps", help="Comprueba dependencias de arranque (W8/A5)")
def deps(ctx: typer.Context, check: str = typer.Argument("check", help="check")):
    c = ctx.obj
    cfg = c.config
    for i in cfg.distros.instances:
        for dep in i.depends_on:
            state = "OK" if dep.distro in c.wsl.running_distros() else "STOPPED"
            typer.echo(f"{i.name} -> {dep.distro}: {state}" + (f" (puerto {dep.wait_port})" if dep.wait_port else ""))


@app.command("vhd")
def vhd(ctx: typer.Context, action: str = typer.Argument(help="resize"), distro: Optional[str] = None, size: Optional[str] = None):
    """Gestion del disco VHD (W12, P2). Solo resize con --size."""
    typer.echo("vhd resize requiere PowerShell elevado; consulta docs/troubleshooting.md", err=True)
    raise typer.Exit(EXIT_ERROR)


@app.command("rename")
def rename(ctx: typer.Context, distro: str, nuevo: str):
    """Renombra una distro via clonado (W13, P2)."""
    c = ctx.obj
    r = c.wsl.clone(distro, nuevo)
    if not r.ok:
        typer.echo(f"error: {r.error}", err=True)
        raise typer.Exit(EXIT_ERROR)
    typer.echo(f"{distro} renombrada a {nuevo} (la original sigue; borrala con wsl --unregister)")


@app.command("set-default")
def set_default(ctx: typer.Context, distro: str):
    """Marca una distro como default."""
    c = ctx.obj
    r = c.wsl.set_default(distro)
    if not r.ok:
        typer.echo(f"error: {r.error}", err=True)
        raise typer.Exit(EXIT_ERROR)
    typer.echo(f"{distro} es ahora la distro default")


@app.command("shell", help="Abre una terminal para la distro")
def shell(ctx: typer.Context, distro: str):
    r = ctx.obj.wsl.open_shell(distro)
    if not r.ok:
        typer.echo(f"error: {r.error}", err=True)
        raise typer.Exit(EXIT_ERROR)


@app.command("explorer", help="Abre la carpeta de la distro en el explorador")
def explorer(ctx: typer.Context, distro: str):
    r = ctx.obj.wsl.open_explorer(distro)
    if not r.ok:
        typer.echo(f"error: {r.error}", err=True)
        raise typer.Exit(EXIT_ERROR)
