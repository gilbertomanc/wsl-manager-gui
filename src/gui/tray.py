"""System tray dinamico (seccion 7.1): icono + menu contextual.

Icono generado con Pillow (sin assets externos): ok / atencion / error.
"""
from __future__ import annotations

import logging

from PIL import Image, ImageDraw

log = logging.getLogger("wslmanager.tray")

try:
    import pystray

    _AVAILABLE = True
except Exception:  # pragma: no cover
    _AVAILABLE = False


def _make_icon(color: str = "#28a745") -> Image.Image:
    img = Image.new("RGBA", (64, 64), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    draw.rounded_rectangle((4, 4, 60, 60), radius=12, fill=color)
    draw.text((14, 16), "W", fill="white", font=None)
    draw.ellipse((14, 36, 20, 42), fill="white")
    return img


class TrayApp:
    def __init__(self, ctx, window) -> None:
        self.ctx = ctx
        self.window = window
        self.icon = None
        self._items: dict[str, object] = {}

    def build_menu(self) -> "pystray.Menu":
        menu_items = [
            pystray.MenuItem("Mostrar/Ocultar ventana", self._toggle, default=True),
            pystray.Menu.SEPARATOR,
        ]
        try:
            distros = self.ctx.wsl.list_distros()
        except Exception:  # noqa: BLE001
            distros = []
        for d in distros:
            sub = pystray.Menu(
                pystray.MenuItem("Iniciar", lambda i, n=d.name: self._action(i, "start", n)),
                pystray.MenuItem("Detener", lambda i, n=d.name: self._action(i, "stop", n)),
                pystray.MenuItem("Terminal", lambda i, n=d.name: self._action(i, "shell", n)),
            )
            menu_items.append(pystray.MenuItem(d.name, sub))
        if distros:
            menu_items.append(pystray.Menu.SEPARATOR)
        menu_items.extend(
            [
                pystray.MenuItem("Apagar todas", lambda i: self._action(i, "shutdown", "")),
                pystray.MenuItem("Snapshot de todas", lambda i: self._action(i, "snapshots", "")),
                pystray.Menu.SEPARATOR,
                pystray.MenuItem("Salir", self._quit),
            ]
        )
        return pystray.Menu(*menu_items)

    def start(self) -> None:
        if not _AVAILABLE:
            log.warning("pystray no disponible; la GUI corre sin tray")
            return
        try:
            self.icon = pystray.Icon("wsl-manager", _make_icon(), "WSL Manager", self.build_menu())
            self.icon.run_detached()
        except Exception:  # noqa: BLE001
            log.exception("tray fallo al iniciar")

    def update(self) -> None:
        """Reconstruye el menu (estado dinamico)."""
        if self.icon is None:
            return
        try:
            self.icon.menu = self.build_menu()
        except Exception:  # noqa: BLE001
            log.exception("tray menu update fallo")

    # -- callbacks -------------------------------------------------------------

    def _toggle(self, _icon=None, _item=None) -> None:
        self.window.toggle()

    def _action(self, _icon, action: str, distro: str) -> None:
        try:
            if action == "start":
                self.ctx.wsl.start(distro)
            elif action == "stop":
                self.ctx.wsl.stop(distro)
            elif action == "shell":
                self.ctx.wsl.open_shell(distro)
            elif action == "shutdown":
                self.ctx.wsl.shutdown_all()
            elif action == "snapshots":
                for d in self.ctx.wsl.list_distros():
                    if d.state == "Running":
                        self.ctx.wsl.snapshot(d.name, self.ctx.config.snapshots.retention_days, self.ctx.config.snapshots.target_dir)
            self.window.refresh_dashboard()
        except Exception as e:  # noqa: BLE001
            log.error("accion del tray fallo: %s", e)

    def _quit(self, _icon=None, _item=None) -> None:
        log.info("salida solicitada desde el tray")
        if self.icon is not None:
            self.icon.stop()
        if self.ctx.config.on_close.stop_distros:
            try:
                self.ctx.wsl.shutdown_all()
            except Exception:  # noqa: BLE001
                pass
        self.window.close()
