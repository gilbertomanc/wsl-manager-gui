"""Widgets reutilizables: tabla con scrollbar y helpers de refresh."""
from __future__ import annotations

import logging
import queue
import threading
import tkinter as tk
from tkinter import ttk

log = logging.getLogger("wslmanager.gui")


def make_tree(parent, columns: list[tuple[str, str, int]]) -> ttk.Treeview:
    """columns: [(id, titulo, ancho)]. Devuelve Treeview con scrollbars."""
    frame = ttk.Frame(parent)
    frame.pack(fill="both", expand=True, padx=6, pady=6)
    tree = ttk.Treeview(frame, columns=[c[0] for c in columns], show="headings", height=10)
    for cid, title, width in columns:
        tree.heading(cid, text=title)
        tree.column(cid, width=width, anchor="w")
    vsb = ttk.Scrollbar(frame, orient="vertical", command=tree.yview)
    tree.configure(yscrollcommand=vsb.set)
    tree.grid(row=0, column=0, sticky="nsew")
    vsb.grid(row=0, column=1, sticky="ns")
    frame.rowconfigure(0, weight=1)
    frame.columnconfigure(0, weight=1)
    return tree


def status_text(state: str) -> str:
    return "● RUNNING" if state.lower() == "running" else "○ stopped"


class BackgroundRefresher:
    """Ejecuta un trabajo pesado (p.ej. llamadas wsl.exe) en un hilo de fondo
    y entrega el resultado en el hilo principal de tkinter via cola + after().

    - submit() devuelve False si ya hay un trabajo en curso (throttle): la UI
      nunca se bloquea ni se acumulan refrescos.
    - on_done(resultado, error) se invoca SIEMPRE en el hilo principal.
    """

    def __init__(self, root: tk.Misc, poll_ms: int = 80) -> None:
        self._root = root
        self._q: queue.Queue = queue.Queue()
        self._busy = False
        root.after(poll_ms, self._poll)

    def submit(self, work, on_done) -> bool:
        if self._busy:
            return False
        self._busy = True
        threading.Thread(target=self._worker, args=(work, on_done), daemon=True).start()
        return True

    def _worker(self, work, on_done) -> None:
        try:
            result = work()
            self._q.put((on_done, result, None))
        except Exception as e:  # noqa: BLE001
            self._q.put((on_done, None, e))
        finally:
            self._q.put((None, None, None))

    def _poll(self) -> None:
        try:
            while True:
                on_done, result, err = self._q.get_nowait()
                if on_done is None:
                    self._busy = False
                else:
                    try:
                        on_done(result, err)
                    except Exception:  # noqa: BLE001
                        log.exception("on_done de refresh fallo")
        except queue.Empty:
            pass
        try:
            self._root.after(80, self._poll)
        except Exception:  # noqa: BLE001 - ventana cerrada
            pass
