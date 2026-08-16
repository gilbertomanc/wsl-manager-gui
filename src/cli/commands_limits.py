"""Comandos de limites y recursos (R1-R8)."""
from __future__ import annotations

from typing import Optional

import typer

from src.cli.common import EXIT_ERROR
from src.core.config import GlobalLimits, PerDistroLimits

app = typer.Typer(help="Limites y recursos (R1-R8)", no_args_is_help=True)


@app.command("global")
def limits_global(
    ctx: typer.Context,
    action: Optional[str] = typer.Argument(None, help="set|get (opcional)"),
    get: bool = typer.Option(False, "--get", help="lee los limites actuales"),
    memory: Optional[str] = typer.Option(None, "--memory", help="ej: 8GB"),
    processors: Optional[int] = typer.Option(None, "--processors"),
    swap: Optional[str] = typer.Option(None, "--swap", help="ej: 4GB"),
    reclaim: Optional[str] = typer.Option(None, "--reclaim", help="gradual|dropcache|disabled"),
    sparse: Optional[bool] = typer.Option(None, "--sparse/--no-sparse"),
    json_out: bool = typer.Option(False, "--json"),
):
    """Limites globales de la VM via .wslconfig (R1). Sin flags: get."""
    c = ctx.obj
    want_set = action == "set"
    want_get = action == "get" or get or (action is None and not any([memory, processors, swap, reclaim, sparse is not None]))
    if want_get and not want_set:
        cur = c.resources.get_global_limits()
        if json_out:
            c.emit_json(cur.model_dump(exclude_none=True))
            return
        typer.echo("Limites globales (.wslconfig [wsl2]):")
        typer.echo(f"  memory:            {cur.memory_gb} GB" if cur.memory_gb else "  memory:            (sin limite)")
        typer.echo(f"  processors:        {cur.processors}" if cur.processors else "  processors:        (sin limite)")
        typer.echo(f"  swap:              {cur.swap_gb} GB" if cur.swap_gb else "  swap:              (sin limite)")
        typer.echo(f"  autoMemoryReclaim: {cur.auto_memory_reclaim}" if cur.auto_memory_reclaim else "  autoMemoryReclaim: (sin valor)")
        typer.echo(f"  sparseVhd:         {cur.sparse_vhd}" if cur.sparse_vhd is not None else "  sparseVhd:         (sin valor)")
        return

    def parse_gb(v: str) -> float:
        v = v.strip().upper()
        if v.endswith("GB"):
            return float(v[:-2])
        if v.endswith("MB"):
            return float(v[:-2]) / 1024
        return float(v)

    limits = GlobalLimits()
    if memory:
        limits.memory_gb = parse_gb(memory)
    if processors:
        limits.processors = processors
    if swap:
        limits.swap_gb = parse_gb(swap)
    if reclaim:
        limits.auto_memory_reclaim = reclaim  # type: ignore[assignment]
    if sparse is not None:
        limits.sparse_vhd = sparse
    r = c.resources.set_global_limits(limits)
    if not r.ok:
        typer.echo(f"error: {r.error}", err=True)
        raise typer.Exit(EXIT_ERROR)
    c.metrics.log_event("limits_global_set", message="limites globales actualizados")
    typer.echo("limites aplicados. Ejecuta 'wsl --shutdown' para que surtan efecto.")


@app.command("distro")
def limits_distro(
    ctx: typer.Context,
    action: str = typer.Argument(help="set|get|clear"),
    distro: Optional[str] = typer.Argument(None),
    memory_max: Optional[str] = typer.Option(None, "--memory-max", help="ej: 4G"),
    cpu_quota: Optional[str] = typer.Option(None, "--cpu-quota", help="ej: 200%"),
    tasks_max: Optional[int] = typer.Option(None, "--tasks-max"),
    scope: str = typer.Option("all", "--scope", help="all|user|service"),
    service: Optional[str] = typer.Option(None, "--service"),
    json_out: bool = typer.Option(False, "--json"),
):
    """Limites por distro via systemd (R4, experimental)."""
    c = ctx.obj
    if action == "get":
        cur = c.resources.get_distro_limits(distro or "")
        if json_out:
            c.emit_json(cur.model_dump(exclude_none=True) if cur else {})
            return
        if cur:
            typer.echo(cur.model_dump(exclude_none=True))
        else:
            typer.echo(f"{distro}: sin limites configurados")
        return
    if action == "clear":
        r = c.resources.clear_distro_limits(distro or "")
        typer.echo(r.output)
        return
    if action == "set":
        if not distro:
            typer.echo("faltan argumentos", err=True)
            raise typer.Exit(2)
        limits = PerDistroLimits(
            distro=distro,
            memory_max=memory_max,
            cpu_quota=cpu_quota,
            tasks_max=tasks_max,
            scope=scope,  # type: ignore[arg-type]
            service=service,
        )
        r = c.resources.set_distro_limits(limits)
        if not r.ok:
            typer.echo(f"error: {r.error}", err=True)
            raise typer.Exit(EXIT_ERROR)
        c.metrics.log_event("limits_distro_set", distro, "limites por distro actualizados")
        typer.echo(r.output)
        return
    typer.echo("accion debe ser set|get|clear", err=True)
    raise typer.Exit(2)


@app.command("service")
def limits_service(
    ctx: typer.Context,
    action: str = typer.Argument(help="set|clear"),
    distro: Optional[str] = typer.Argument(None),
    service: Optional[str] = typer.Option(..., "--service"),
    memory_max: Optional[str] = typer.Option(None, "--memory-max"),
    cpu_quota: Optional[str] = typer.Option(None, "--cpu-quota"),
):
    """Limites por servicio systemd (R4 opcion B, experimental)."""
    c = ctx.obj
    if action == "set" and distro:
        limits = PerDistroLimits(distro=distro, memory_max=memory_max, cpu_quota=cpu_quota, scope="service", service=service)
        r = c.resources.set_distro_limits(limits)
    elif action == "clear" and distro:
        r = c.resources.clear_distro_limits(distro)
    else:
        typer.echo("uso: limits service set <distro> --service X [--memory-max 2G]", err=True)
        raise typer.Exit(2)
    if not r.ok:
        typer.echo(f"error: {r.error}", err=True)
        raise typer.Exit(EXIT_ERROR)
    typer.echo(r.output)
