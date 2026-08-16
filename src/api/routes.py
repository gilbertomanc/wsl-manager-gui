"""Rutas de la API REST mapeadas al catalogo (seccion 21.3)."""
from __future__ import annotations

import logging
import time
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Request

from src.api.auth import AuthService
from src.cli.common import CliContext
from src.core.config import GlobalLimits, PerDistroLimits, ScheduleTask, snapshot_dir
from src.core.profiles import ProfileService
from src.core.scheduler import Scheduler
from src.core.watcher import Watcher

log = logging.getLogger("wslmanager.api")

router = APIRouter(prefix="/api/v1")


def get_ctx(request: Request) -> CliContext:
    return request.app.state.ctx  # type: ignore[attr-defined]


def get_auth(request: Request) -> AuthService:
    return request.app.state.auth  # type: ignore[attr-defined]


def require(scope: str):
    def dep(request: Request) -> None:
        get_auth(request).require(request, scope)

    return Depends(dep)


Ctx = Depends(get_ctx)


def _fail(exc: Exception | str, detail: str = "operacion fallida") -> HTTPException:
    """Loguea el detalle real y devuelve un mensaje generico (no fuga informacion)."""
    log.error("api error: %s", exc)
    return HTTPException(status_code=500, detail=detail)


# --------------------------------------------------------------- health ----

@router.get("/health", dependencies=[require("read")])
def health(ctx: CliContext = Ctx):
    return {"ok": True, "ts": time.time(), "version": "0.1.0"}


# -------------------------------------------------------------- distros ----

@router.get("/distros", dependencies=[require("read")])
def list_distros(ctx: CliContext = Ctx):
    distros = ctx.wsl.list_distros()
    for d in distros:
        if d.state == "Running":
            d.ip = ctx.wsl.get_ip(d.name)
    return {"distros": [d.to_dict() for d in distros]}


@router.post("/distros/{name}/start", dependencies=[require("write")])
def start(ctx: CliContext = Ctx, name: str = ..., request: Request = ...):
    r = ctx.wsl.start(name)
    if not r.ok:
        raise _fail(r.error)
    ctx.metrics.log_event("api_start", name, "iniciada via API")
    return {"ok": True, "distro": name}


@router.post("/distros/{name}/stop", dependencies=[require("write")])
def stop(ctx: CliContext = Ctx, name: str = ..., request: Request = ...):
    r = ctx.wsl.stop(name)
    if not r.ok:
        raise _fail(r.error)
    ctx.metrics.log_event("api_stop", name, "detenida via API")
    return {"ok": True, "distro": name}


@router.post("/distros/{name}/restart", dependencies=[require("write")])
def restart(ctx: CliContext = Ctx, name: str = ..., request: Request = ...):
    r = ctx.wsl.restart(name)
    if not r.ok:
        raise _fail(r.error)
    return {"ok": True, "distro": name}


@router.post("/shutdown", dependencies=[require("write")])
def shutdown_all(ctx: CliContext = Ctx):
    r = ctx.wsl.shutdown_all()
    if not r.ok:
        raise _fail(r.error)
    return {"ok": True}


@router.get("/ips", dependencies=[require("read")])
def ips(ctx: CliContext = Ctx):
    return {"ips": ctx.wsl.get_all_ips()}


@router.post("/distros/{name}/export", dependencies=[require("write")])
def export(ctx: CliContext = Ctx, name: str = ..., body: dict = ...):
    # M1: restringir el destino al directorio de snapshots (o target_dir configurado)
    base = Path(ctx.config.snapshots.target_dir or snapshot_dir()).resolve()
    target = Path(body.get("path", "")).resolve()
    if base not in target.parents:
        raise HTTPException(status_code=403, detail="ruta fuera del directorio de snapshots")
    r = ctx.wsl.export(name, str(target))
    if not r.ok:
        raise _fail(r.error)
    ctx.metrics.log_event("api_export", name, f"exportada a {target}")
    return {"ok": True}


@router.post("/distros/{name}/snapshot", dependencies=[require("write")])
def snapshot(ctx: CliContext = Ctx, name: str = ...):
    try:
        path = ctx.wsl.snapshot(name, ctx.config.snapshots.retention_days, ctx.config.snapshots.target_dir)
    except RuntimeError as e:
        raise _fail(e)
    size = path.stat().st_size if path.exists() else 0
    ctx.metrics.record_snapshot(name, str(path), size)
    return {"ok": True, "path": str(path), "size_bytes": size}


# ------------------------------------------------------------- resources ----

@router.get("/limits/global", dependencies=[require("read")])
def limits_global_get(ctx: CliContext = Ctx):
    return ctx.resources.get_global_limits().model_dump(exclude_none=True)


@router.post("/limits/global", dependencies=[require("admin")])
def limits_global_set(ctx: CliContext = Ctx, limits: GlobalLimits = ...):
    r = ctx.resources.set_global_limits(limits)
    if not r.ok:
        raise _fail(r.error)
    return {"ok": True}


@router.get("/limits/distro/{name}", dependencies=[require("read")])
def limits_distro_get(ctx: CliContext = Ctx, name: str = ...):
    item = ctx.resources.get_distro_limits(name)
    return item.model_dump(exclude_none=True) if item else {}


@router.post("/limits/distro", dependencies=[require("admin")])
def limits_distro_set(ctx: CliContext = Ctx, limits: PerDistroLimits = ...):
    r = ctx.resources.set_distro_limits(limits)
    if not r.ok:
        raise _fail(r.error)
    return {"ok": True}


@router.get("/metrics", dependencies=[require("read")])
def metrics(ctx: CliContext = Ctx, distro: str | None = None):
    return {"metrics": [m.to_dict() for m in ctx.resources.get_metrics(distro)]}


# ---------------------------------------------------------------- monitor ---

@router.get("/status", dependencies=[require("read")])
def status(ctx: CliContext = Ctx):
    return Watcher(ctx.store, ctx.metrics, ctx.bus, ctx.wsl).snapshot_state()


@router.get("/alerts", dependencies=[require("read")])
def alerts(ctx: CliContext = Ctx, limit: int = 100):
    return {"alerts": ctx.metrics.list_alerts(limit)}


@router.get("/events", dependencies=[require("read")])
def events(ctx: CliContext = Ctx, limit: int = 100):
    return {"events": ctx.metrics.list_events(limit)}


@router.get("/snapshots", dependencies=[require("read")])
def snapshots(ctx: CliContext = Ctx):
    return {"snapshots": ctx.metrics.list_snapshots()}


# -------------------------------------------------------------- scheduler ---

@router.get("/schedule", dependencies=[require("read")])
def schedule_list(ctx: CliContext = Ctx):
    return {"tasks": [t.model_dump() for t in ctx.store.get().scheduler.tasks]}


@router.post("/schedule", dependencies=[require("admin")])
def schedule_add(ctx: CliContext = Ctx, task: ScheduleTask = ...):
    scheduler = Scheduler(ctx.store, ctx.metrics, ctx.bus, ctx.wsl)
    scheduler.add_task(task)
    return {"ok": True, "id": task.id}


@router.delete("/schedule/{task_id}", dependencies=[require("admin")])
def schedule_remove(ctx: CliContext = Ctx, task_id: str = ...):
    scheduler = Scheduler(ctx.store, ctx.metrics, ctx.bus, ctx.wsl)
    if not scheduler.remove_task(task_id):
        raise HTTPException(status_code=404, detail=f"tarea {task_id} no existe")
    return {"ok": True}


# ---------------------------------------------------------------- profiles ---

@router.get("/profiles", dependencies=[require("read")])
def profiles_list(ctx: CliContext = Ctx):
    return {"profiles": ProfileService(ctx.store, ctx.wsl).list()}


@router.post("/profiles/{name}/apply", dependencies=[require("write")])
def profiles_apply(ctx: CliContext = Ctx, name: str = ...):
    try:
        ok = ProfileService(ctx.store, ctx.wsl).apply(name)
    except KeyError as e:
        raise HTTPException(status_code=404, detail=str(e))
    if not ok:
        raise HTTPException(status_code=500, detail="fallo al aplicar el perfil")
    return {"ok": True, "profile": name}


@router.post("/profiles/{name}/capture", dependencies=[require("write")])
def profiles_capture(ctx: CliContext = Ctx, name: str = ...):
    item = ProfileService(ctx.store, ctx.wsl).capture(name)
    return {"ok": True, "profile": item.name, "distros_to_start": item.distros_to_start}
