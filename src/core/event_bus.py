"""Event bus thread-safe: workers publican, la UI (o CLI watch) consume."""
from __future__ import annotations

import threading
from collections import defaultdict
from typing import Any, Callable

Listener = Callable[[str, dict[str, Any]], None]


class EventBus:
    def __init__(self) -> None:
        self._listeners: dict[str, list[Listener]] = defaultdict(list)
        self._lock = threading.RLock()
        self._history: list[tuple[str, dict[str, Any]]] = []

    def subscribe(self, event: str, fn: Listener) -> None:
        with self._lock:
            self._listeners[event].append(fn)

    def subscribe_all(self, fn: Listener) -> None:
        with self._lock:
            self._listeners["*"].append(fn)

    def emit(self, event: str, payload: dict[str, Any] | None = None) -> None:
        payload = payload or {}
        with self._lock:
            self._history.append((event, payload))
            if len(self._history) > 1000:
                del self._history[: len(self._history) - 1000]
            listeners = list(self._listeners.get(event, [])) + list(self._listeners.get("*", []))
        for fn in listeners:
            try:
                fn(event, payload)
            except Exception:  # noqa: BLE001 - un listener no puede tumbar el bus
                import logging

                logging.getLogger("wslmanager.event_bus").exception("listener fallo")

    def recent(self, n: int = 50) -> list[tuple[str, dict[str, Any]]]:
        with self._lock:
            return list(self._history[-n:])
