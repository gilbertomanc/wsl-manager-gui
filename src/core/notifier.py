"""Notifier: toasts nativos (winotify) con fallback a logging (M4/M5)."""
from __future__ import annotations

import logging

log = logging.getLogger("wslmanager.notifier")

try:
    from winotify import Notification, audio  # type: ignore

    _AVAILABLE = True
except Exception:  # pragma: no cover
    _AVAILABLE = False


def notify(title: str, message: str, icon: str = "") -> bool:
    """Toast de Windows si es posible; si no, log."""
    if _AVAILABLE:
        try:
            n = Notification(app_id="WSL Manager", title=title, msg=message, duration="short")
            if icon:
                n.set_icon(icon)
            n.show()
            return True
        except Exception as e:  # pragma: no cover
            log.warning("toast fallo (%s); se registra en log", e)
    log.info("NOTIFY: %s - %s", title, message)
    return False
