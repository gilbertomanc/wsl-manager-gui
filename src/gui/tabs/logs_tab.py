"""Pestana Logs: cola circular del log en memoria + refresh."""
from __future__ import annotations

import tkinter as tk

import ttkbootstrap as ttk


class LogsTab(ttk.Frame):
    def __init__(self, master, ctx) -> None:
        super().__init__(master)
        self.ctx = ctx
        self._build()
        self.refresh()

    def _build(self) -> None:
        bar = ttk.Frame(self)
        bar.pack(fill="x", padx=6, pady=6)
        ttk.Button(bar, text="Refrescar", bootstyle="success", command=self.refresh).pack(side="left", padx=2)
        ttk.Label(bar, text="  Ultimos eventos del journal (SQLite)", style="Muted.TLabel").pack(side="left")

        self.text = tk.Text(self, wrap="none", font=("Consolas", 9), state="disabled", height=14)
        self.text.pack(fill="both", expand=True, padx=6, pady=6)

    def refresh(self) -> None:
        import datetime

        rows = self.ctx.metrics.list_events(200)
        self.text.configure(state="normal")
        self.text.delete("1.0", "end")
        for r in reversed(rows):
            ts = datetime.datetime.fromtimestamp(r["ts"]).strftime("%H:%M:%S")
            self.text.insert("end", f"{ts}  {r['type']:<22} {r['distro'] or '':<20} {r['message']}\n")
        self.text.configure(state="disabled")
