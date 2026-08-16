"""Comandos de automatizacion: scheduler (A2) y perfiles (A3)."""
from __future__ import annotations

import uuid
from typing import Optional

import typer

from src.cli.common import EXIT_ERROR
from src.core.config import ScheduleAction, ScheduleSpec, ScheduleTask
from src.core.profiles import ProfileService
from src.core.scheduler import Scheduler

app = typer.Typer(help="Automatizacion (A2-A3)", no_args_is_help=True)


@app.command("add")
def schedule_add(
    ctx: typer.Context,
    name: str = typer.Option(..., "--name"),
    type_: str = typer.Option(..., "--type", help="distro_start|distro_stop|apply_profile|snapshot"),
    distro: Optional[str] = typer.Option(None, "--distro"),
    profile: Optional[str] = typer.Option(None, "--profile"),
    time_: str = typer.Option("09:00", "--time"),
    days: str = typer.Option("mon,tue,wed,thu,fri", "--days"),
):
    """Añade una tarea programada (A2)."""
    c = ctx.obj
    if type_ not in ("distro_start", "distro_stop", "apply_profile", "snapshot"):
        typer.echo(f"tipo invalido: {type_}", err=True)
        raise typer.Exit(2)
    task = ScheduleTask(
        id=f"tarea-{uuid.uuid4().hex[:8]}",
        name=name,
        action=ScheduleAction(type=type_, distro=distro, profile=profile),  # type: ignore[arg-type]
        schedule=ScheduleSpec(days=[d.strip() for d in days.split(",")], time=time_),
    )
    scheduler = Scheduler(c.store, c.metrics, c.bus, c.wsl)
    scheduler.add_task(task)
    c.metrics.log_event("schedule_add", message=f"tarea '{name}' creada")
    typer.echo(f"tarea creada: {task.id} ({name} -> {type_})")


@app.command("list")
def schedule_list(ctx: typer.Context, json_out: bool = typer.Option(False, "--json")):
    tasks = ctx.obj.store.get().scheduler.tasks
    if json_out:
        ctx.obj.emit_json([t.model_dump() for t in tasks])
        return
    for t in tasks:
        status = "ON " if t.enabled else "OFF"
        typer.echo(f"{status} {t.id:<14} {t.name:<24} {t.action.type:<14} {t.action.distro or t.action.profile or '':<20} {','.join(t.schedule.days)} {t.schedule.time}")


@app.command("remove")
def schedule_remove(ctx: typer.Context, task_id: str):
    c = ctx.obj
    scheduler = Scheduler(c.store, c.metrics, c.bus, c.wsl)
    if scheduler.remove_task(task_id):
        typer.echo(f"tarea {task_id} eliminada")
    else:
        typer.echo(f"tarea {task_id} no encontrada", err=True)
        raise typer.Exit(EXIT_ERROR)


@app.command("enable")
def schedule_enable(ctx: typer.Context, task_id: str, enabled: bool = typer.Option(True, "--enabled/--disabled")):
    c = ctx.obj
    cfg = c.store.get()
    for t in cfg.scheduler.tasks:
        if t.id == task_id:
            t.enabled = enabled
            c.store.save(cfg)
            typer.echo(f"tarea {task_id} {'habilitada' if enabled else 'deshabilitada'}")
            return
    typer.echo(f"tarea {task_id} no encontrada", err=True)
    raise typer.Exit(EXIT_ERROR)


profile_app = typer.Typer(help="Perfiles de distros (A3)", no_args_is_help=True)


@profile_app.command("list")
def profile_list(ctx: typer.Context, json_out: bool = typer.Option(False, "--json")):
    c = ctx.obj
    svc = ProfileService(c.store, c.wsl)
    items = svc.list()
    if json_out:
        c.emit_json(items)
        return
    for i in items:
        mark = "*" if i["active"] else " "
        typer.echo(f"{mark} {i['name']:<20} {i['description']:<30} {', '.join(i['distros_to_start'])}")


@profile_app.command("capture")
def profile_capture(ctx: typer.Context, name: str, desc: Optional[str] = typer.Option(None, "--desc")):
    c = ctx.obj
    svc = ProfileService(c.store, c.wsl)
    item = svc.capture(name, desc or "")
    c.metrics.log_event("profile_capture", message=f"perfil '{name}' capturado")
    typer.echo(f"perfil '{name}' capturado: {', '.join(item.distros_to_start) or '(nada corriendo)'}")


@profile_app.command("apply")
def profile_apply(ctx: typer.Context, name: str):
    c = ctx.obj
    svc = ProfileService(c.store, c.wsl)
    try:
        ok = svc.apply(name)
    except KeyError as e:
        typer.echo(f"error: {e}", err=True)
        raise typer.Exit(EXIT_ERROR)
    if not ok:
        typer.echo("fallo al aplicar el perfil", err=True)
        raise typer.Exit(EXIT_ERROR)
    c.metrics.log_event("profile_apply", message=f"perfil '{name}' aplicado")
    typer.echo(f"perfil '{name}' aplicado")


app.add_typer(profile_app, name="profile")
