"""Comandos de monitor y alertas (M1-M8)."""
from __future__ import annotations

import time
from typing import Optional

import typer

from src.cli.common import CliContext

app = typer.Typer(help="Monitoring y alertas (M1-M8)", no_args_is_help=True)


@app.command("once", help="Snapshot de estado y metricas (M1/M3)")
def once(ctx: typer.Context, json_out: bool = typer.Option(False, "--json")):
    c = ctx.obj
    distros = c.wsl.list_distros()
    metrics = []
    for d in distros:
        m = c.wsl.metrics(d.name)
        metrics.append(m.to_dict() if m else d.to_dict())
    if json_out:
        c.emit_json({"ts": time.time(), "metrics": metrics})
        return
    for m in metrics:
        ram = f"RAM {m.get('ram_used_mb')}/{m.get('ram_total_mb')} MB ({m.get('ram_percent')}%)" if m.get("ram_total_mb") else "RAM n/d"
        typer.echo(f"{m['name']:<28} {'RUN' if m.get('running') else 'STOP':<5} {ram}")


@app.command("metrics", help="Metricas por distro (R3)")
def metrics_cmd(
    ctx: typer.Context,
    distro: Optional[str] = None,
    json_out: bool = typer.Option(False, "--json"),
    watch: bool = typer.Option(False, "--watch", help="refresca cada 3s"),
):
    c = ctx.obj
    while True:
        rows = c.resources.get_metrics(distro)
        if json_out:
            c.emit_json([m.to_dict() for m in rows])
        else:
            for m in rows:
                ram = f"{m.ram_used_mb}/{m.ram_total_mb} MB" if m.ram_total_mb else "-"
                typer.echo(f"{m.name:<28} {'RUN' if m.running else 'STOP':<5} RAM={ram:<14} CPU={m.cpus or '-'} up={m.uptime_s or 0}s")
        if not watch:
            return
        time.sleep(3)


@app.command("thresholds", help="Umbrales de alerta (M4)")
def thresholds(
    ctx: typer.Context,
    get: bool = typer.Option(False, "--get"),
    memory_percent: Optional[int] = typer.Option(None, "--memory-percent"),
    interval: Optional[int] = typer.Option(None, "--check-interval"),
    json_out: bool = typer.Option(False, "--json"),
):
    c = ctx.obj
    cfg = c.config
    if get or (memory_percent is None and interval is None):
        if json_out:
            c.emit_json(cfg.alerts.model_dump())
            return
        typer.echo(cfg.alerts.model_dump())
        return
    if memory_percent is not None:
        cfg.alerts.memory_percent = memory_percent
    if interval is not None:
        cfg.alerts.check_interval_seconds = max(2, interval)
    c.store.save(cfg)
    typer.echo("umbrales actualizados")


@app.command("alerts", help="Historial de alertas (M6)")
def alerts(ctx: typer.Context, json_out: bool = typer.Option(False, "--json")):
    rows = ctx.obj.metrics.list_alerts()
    if json_out:
        ctx.obj.emit_json(rows)
        return
    for r in rows:
        typer.echo(f"{r['ts']:.0f}  [{r['severity']:<7}] {r['tipo']:<16} {r['distro'] or '':<20} {r['message']}")


@app.command("events", help="Journal de eventos (U6)")
def events(ctx: typer.Context, limit: int = typer.Option(50, "--limit"), json_out: bool = typer.Option(False, "--json")):
    rows = ctx.obj.metrics.list_events(limit)
    if json_out:
        ctx.obj.emit_json(rows)
        return
    for r in rows:
        typer.echo(f"{r['ts']:.0f}  {r['type']:<20} {r['distro'] or '':<20} {r['message']}")


@app.command("history", help="Historial de metricas en SQLite (M3)")
def history(ctx: typer.Context, distro: Optional[str] = None, limit: int = typer.Option(100, "--limit")):
    for r in ctx.obj.metrics.list_metrics(distro, limit):
        typer.echo(
            f"{r['ts']:.0f}  {r['distro']:<20} {r['state']:<8} RAM={r['ram_mb'] or 0} MB ({r['ram_percent'] or 0}%) IP={r['ip'] or '-'}"
        )
