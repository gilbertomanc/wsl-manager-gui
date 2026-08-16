"""Pestana Monitor (P1): metricas en vivo de RAM por distro.

Medidores circulares (ttkbootstrap Meter) por distro + tabla de detalle.
El sondeo de WSL corre en un hilo de fondo (nunca bloquea la UI).
"""
from __future__ import annotations

import tkinter as tk
from tkinter import ttk

from src.gui.widgets import BackgroundRefresher, make_tree

_INTERVAL_MS = 15_000


def _bootstyle_for(pct: float) -> str:
    if pct is None:
        return "secondary"
    if pct >= 90:
        return "danger"
    if pct >= 70:
        return "warning"
    return "success"


class MonitorTab(ttk.Frame):
    def __init__(self, master, ctx) -> None:
        super().__init__(master)
        self.ctx = ctx
        self._refresher = BackgroundRefresher(self.winfo_toplevel())
        self._job: str | None = None
        self._scheduled = False
        self._meters: dict[str, tk.Widget] = {}
        self._build()
        self.refresh()

    def _build(self) -> None:
        from ttkbootstrap.widgets import Meter

        self.meters_frame = ttk.Frame(self)
        self.meters_frame.pack(fill="x", padx=8, pady=(8, 2))

        self.tree = make_tree(
            self,
            [("name", "Distro", 160), ("state", "Estado", 100), ("ram", "RAM usada/total", 180), ("pct", "%", 80), ("cpu", "CPU", 80), ("up", "Uptime (s)", 110)],
        )
        ttk.Label(self, text="Metricas de la VM compartida WSL2. Se refresca cada 15s.", style="Muted.TLabel").pack(anchor="w", padx=10, pady=(0, 4))

    def refresh(self) -> None:
        self._refresher.submit(self._load, self._apply)
        if not self._scheduled and self.winfo_exists():
            self._scheduled = True
            self._job = self.after(_INTERVAL_MS, self._tick)

    def _tick(self) -> None:
        self._scheduled = False
        self.refresh()

    def _load(self):
        return self.ctx.resources.get_metrics()

    def _apply(self, metrics, err) -> None:
        if err is not None or metrics is None:
            return
        self._render_meters(metrics)
        self.tree.delete(*self.tree.get_children())
        for m in metrics:
            ram = f"{m.ram_used_mb}/{m.ram_total_mb} MB" if m.ram_total_mb else "-"
            self.tree.insert(
                "", "end",
                values=(m.name, "RUNNING" if m.running else "STOPPED", ram, f"{m.ram_percent:.0f}%" if m.ram_percent is not None else "-", m.cpus or "-", m.uptime_s or 0),
            )

    def _render_meters(self, metrics) -> None:
        from ttkbootstrap.widgets import Meter

        names = [m.name for m in metrics]
        for old_name, old_meter in list(self._meters.items()):
            if old_name not in names:
                old_meter.destroy()
                self._meters.pop(old_name, None)

        for i, m in enumerate(metrics):
            if m.name not in self._meters:
                meter = Meter(
                    self.meters_frame,
                    amount_total=100,
                    amount_used=0,
                    subtext=m.name,
                    bootstyle="secondary",
                    meter_type="semi",
                    meter_size=130,
                    meter_thickness=12,
                    amount_format="{:.0f}",
                    text_right="%",
                )
                meter.pack(side="left", padx=8, pady=4)
                self._meters[m.name] = meter
            pct = m.ram_percent or 0
            self._meters[m.name].configure(amount_used=pct, bootstyle=_bootstyle_for(pct))

    def destroy(self) -> None:
        if self._job:
            self.after_cancel(self._job)
        super().destroy()
