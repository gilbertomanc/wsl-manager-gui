"""Entry point de la app: single instance + tray + ventana + workers.

Flags (seccion 12.4): --minimized, --tray-only, --validate-config,
--autostart-distro <name> --delay <N> (invocado desde HKCU Run).
"""
from __future__ import annotations

import argparse
import sys
import threading
import time
from pathlib import Path
from typing import Any

# Permite 'python src/app.py' desde cualquier cwd
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.core.config import ConfigError, ConfigStore
from src.core.event_bus import EventBus
from src.core.logger import get_logger, setup_logging
from src.core.metrics_store import MetricsStore
from src.core.power_events import PowerWatcher
from src.core.scheduler import Scheduler
from src.core.watcher import Watcher

log = get_logger("app")


def _single_instance() -> bool:
    """Mutex global: si otra instancia corre, sale."""
    try:
        import ctypes

        kernel32 = ctypes.windll.kernel32
        mutex = kernel32.CreateMutexW(None, False, "WSLManager-SingleInstance")
        return kernel32.GetLastError() != 183  # ERROR_ALREADY_EXISTS
    except Exception:  # pragma: no cover
        return True


_SHOW_EVENT_NAME = "WSLManager-ShowWindow"


def _signal_show_window() -> bool:
    """True si hay otra instancia corriendo y se le pidio mostrar la ventana."""
    try:
        import ctypes

        kernel32 = ctypes.windll.kernel32
        h = kernel32.OpenEventW(0x0002, False, _SHOW_EVENT_NAME)  # EVENT_MODIFY_STATE
        if not h:
            return False
        try:
            kernel32.SetEvent(h)
            return True
        finally:
            kernel32.CloseHandle(h)
    except Exception:  # pragma: no cover
        return False


def _create_show_event():
    try:
        import ctypes

        return ctypes.windll.kernel32.CreateEventW(None, False, False, _SHOW_EVENT_NAME) or None
    except Exception:  # pragma: no cover
        return None


def _parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(prog="wsl-manager", description="WSL Manager (GUI)")
    p.add_argument("--minimized", action="store_true", help="arranca directo a tray")
    p.add_argument("--tray-only", action="store_true", help="solo tray, sin ventana")
    p.add_argument("--show-window", action="store_true", help="muestra la ventana de la instancia en ejecucion")
    p.add_argument("--validate-config", action="store_true", help="valida config.json y sale")
    p.add_argument("--autostart-distro", help="distro a arrancar con retraso (HKCU Run)")
    p.add_argument("--delay", type=int, default=0, help="segundos de espera antes del arranque")
    p.add_argument("--log-level", default="INFO")
    return p.parse_args()


def _handle_autostart(args: argparse.Namespace) -> None:
    if not args.autostart_distro:
        return
    if args.delay > 0:
        time.sleep(args.delay)
    from src.providers.wsl_provider import WslProvider

    store = ConfigStore()
    WslProvider(store).start(args.autostart_distro)
    log.info("autostart: %s iniciada (delay %ss)", args.autostart_distro, args.delay)


def main() -> None:
    args = _parse_args()
    setup_logging(args.log_level)

    # Modo autostart: arranca la distro y termina (sin GUI)
    _handle_autostart(args)
    if args.autostart_distro:
        log.info("modo autostart completado")
        sys.exit(0)

    store = ConfigStore()
    try:
        store.load()
    except ConfigError as e:
        log.error("config invalida: %s", e)
        print(f"[wsl-manager] {e}", file=sys.stderr)
        print("[wsl-manager] modo seguro: corrige o borra el config.json", file=sys.stderr)
        sys.exit(3)

    if args.validate_config:
        print("config valida")
        sys.exit(0)

    # --show-window: pide a la instancia en ejecucion que muestre su ventana.
    if args.show_window:
        for _ in range(15):  # reintenta ~3s por si la instancia aun arranca
            if _signal_show_window():
                log.info("ventana solicitada a la instancia en ejecucion")
                sys.exit(0)
            time.sleep(0.2)
        log.info("no hay instancia en ejecucion; abriendo normalmente")

    if not _single_instance():
        log.warning("otra instancia de WSL Manager ya esta corriendo")
        sys.exit(0)

    cfg = store.get()
    ctx = _build_ctx(store, cfg)
    _start_services(ctx)
    _apply_boot(ctx)

    # GUI (opcional para entornos sin display)
    from src.gui.tray import TrayApp
    from src.gui.window import MainWindow

    try:
        window = MainWindow(ctx, theme=cfg.ui.theme)
    except Exception:  # noqa: BLE001 - sin display
        log.exception("GUI no disponible; corriendo headless")
        _run_headless(ctx)
        return

    tray = TrayApp(ctx, window)
    tray.start()
    if args.minimized or cfg.ui.start_minimized:
        window.hide()
    else:
        window.show()
    window.root.protocol(
        "WM_DELETE_WINDOW",
        lambda: window.hide() if cfg.ui.close_to_tray else window.close(),
    )

    # Escucha el evento "mostrar ventana" (acceso directo con --show-window).
    show_handle = _create_show_event()
    if show_handle:
        import ctypes

        window.root.bind("<<WSLManagerShowWindow>>", lambda _e: window.show())

        def _watch_show_event(handle) -> None:
            kernel32 = ctypes.windll.kernel32
            while True:
                try:
                    if kernel32.WaitForSingleObject(handle, 1000) == 0:
                        window.root.event_generate("<<WSLManagerShowWindow>>")
                except Exception:  # noqa: BLE001 - ventana cerrada
                    break

        threading.Thread(target=_watch_show_event, args=(show_handle,), daemon=True).start()

    # API REST + panel web opcionales (se sincronizan con Ajustes en runtime)
    services: dict[str, Any] = {}
    _start_api(ctx, services)
    _start_web_panel(ctx, services)

    # Refresh periodico del tray + dashboard + servicios. IMPORTANTE: tkinter
    # solo se toca desde el hilo principal; antes esto corria en un thread y
    # dejaba la UI congelada (botones sin respuesta).
    def _schedule_refresh() -> None:
        try:
            _ensure_services(ctx, services)
            tray.update()
            window.refresh_dashboard()
        except Exception:  # noqa: BLE001
            pass
        try:
            window.root.after(cfg.ui.refresh_interval_seconds * 5000, _schedule_refresh)
        except Exception:  # noqa: BLE001
            pass

    _schedule_refresh()
    window.run()


def _build_ctx(store, cfg):
    from types import SimpleNamespace

    from src.providers.autostart_provider import AutoStartProvider
    from src.providers.resource_provider import ResourceProvider
    from src.providers.wsl_provider import WslProvider

    bus = EventBus()
    metrics = MetricsStore()
    wsl = WslProvider(store, cfg.windows.wsl_exe)
    return SimpleNamespace(
        store=store,
        config=cfg,
        bus=bus,
        metrics=metrics,
        wsl=wsl,
        resources=ResourceProvider(store, wsl),
        autostart=AutoStartProvider(),
    )


def _start_services(ctx) -> None:
    watcher = Watcher(ctx.store, ctx.metrics, ctx.bus, ctx.wsl)
    scheduler = Scheduler(ctx.store, ctx.metrics, ctx.bus, ctx.wsl)
    power = PowerWatcher(ctx.store, ctx.metrics, ctx.bus)
    watcher.start()
    scheduler.start()
    power.start()
    ctx.watcher = watcher
    ctx.scheduler = scheduler


def _apply_boot(ctx) -> None:
    """Aplica config al inicio (seccion 12.2): autoarranque de distros + limites."""
    cfg = ctx.config
    to_start = [i for i in cfg.distros.instances if i.auto_start]
    if cfg.distros.defaults.auto_start and not to_start:
        to_start = [i for i in cfg.distros.instances]
    for inst in to_start:
        if inst.delay_s:
            threading.Timer(inst.delay_s, lambda n=inst.name: ctx.wsl.start(n)).start()
        else:
            ctx.wsl.start(inst.name)
    if to_start:
        log.info("autoarranque: %s", ", ".join(i.name for i in to_start))


def _run_uvicorn(app, host: str, port: int) -> dict:
    """Arranca uvicorn en un hilo de fondo; devuelve el Server para pararlo."""
    import uvicorn

    # log_config=None: uvicorn no debe tocar el logging (bajo pythonw no hay
    # sys.stdout y su dictConfig por defecto falla).
    config = uvicorn.Config(
        app, host=host, port=port, log_level="warning",
        server_header=False, log_config=None,
    )
    server = uvicorn.Server(config)
    threading.Thread(target=server.run, daemon=True).start()
    return {"server": server, "host": host, "port": port}


def _stop_service(svc: dict | None) -> None:
    if svc:
        try:
            svc["server"].should_exit = True
        except Exception:  # noqa: BLE001
            pass


def _start_api(ctx, services: dict) -> None:
    cfg = ctx.config
    if not cfg.api.enabled or "api" in services:
        return
    from src.api.server import create_app

    try:
        services["api"] = _run_uvicorn(create_app(ctx), cfg.api.host, cfg.api.port)
        log.info("API REST en http://%s:%s", cfg.api.host, cfg.api.port)
    except Exception:  # noqa: BLE001
        log.exception("API REST fallo al iniciar")


def _start_web_panel(ctx, services: dict) -> None:
    cfg = ctx.config
    if not cfg.ui.web_panel_enabled or "web" in services:
        return
    if not cfg.ui.web_panel_password:
        log.error("panel web: activa una clave en Ajustes (obligatoria); no se arranca")
        return
    from src.web.web_app import create_web_app

    try:
        services["web"] = _run_uvicorn(
            create_web_app(ctx), cfg.ui.web_panel_bind, cfg.ui.web_panel_port
        )
        log.info("panel web en http://%s:%s", cfg.ui.web_panel_bind, cfg.ui.web_panel_port)
    except Exception:  # noqa: BLE001
        log.exception("panel web fallo al iniciar")


def _ensure_services(ctx, services: dict) -> None:
    """Sincroniza API/panel web con la config (permite on/off desde Ajustes)."""
    cfg = ctx.config
    if cfg.api.enabled and "api" not in services:
        _start_api(ctx, services)
    elif not cfg.api.enabled and "api" in services:
        _stop_service(services.pop("api", None))
    if cfg.ui.web_panel_enabled and cfg.ui.web_panel_password and "web" not in services:
        _start_web_panel(ctx, services)
    elif not (cfg.ui.web_panel_enabled and cfg.ui.web_panel_password) and "web" in services:
        _stop_service(services.pop("web", None))


def _run_headless(ctx) -> None:
    log.info("modo headless: watcher + scheduler activos (Ctrl+C para salir)")
    try:
        while True:
            time.sleep(5)
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
