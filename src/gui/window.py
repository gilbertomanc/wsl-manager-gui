"""Ventana principal con pestanas (seccion 7.2 del plan).

Diseno pulido: cabecera con estado, barra de estado inferior, tipografia
mayor y espaciado consistente. Todo el trabajo pesado corre en hilos de
fondo (BackgroundRefresher) para que la UI nunca se congele.
"""
from __future__ import annotations

import tkinter as tk

import ttkbootstrap as ttk

from src.gui.tabs import (
    autostart_tab,
    config_tab,
    dashboard_tab,
    logs_tab,
    monitor_tab,
    profiles_tab,
    resources_tab,
    scheduler_tab,
    settings_tab,
)

_FONT = "Segoe UI"


class MainWindow:
    def __init__(self, ctx, theme: str = "darkly") -> None:
        self.ctx = ctx
        self.root = ttk.Window(themename=theme, title="WSL Manager")
        self.root.geometry("1020x640")
        self.root.minsize(840, 500)
        self._setup_style()
        self._build()

    def _setup_style(self) -> None:
        style = ttk.Style()
        style.configure("Treeview", rowheight=28, font=(_FONT, 10))
        style.configure("Treeview.Heading", font=(_FONT, 10, "bold"))
        style.configure("TNotebook.Tab", font=(_FONT, 10), padding=(16, 7))
        style.configure("Treeview", borderwidth=0, relief="flat")
        style.configure("TLabel", font=(_FONT, 10))
        style.configure("TButton", font=(_FONT, 10))
        style.configure("TEntry", font=(_FONT, 10))
        style.configure("TCombobox", font=(_FONT, 10))
        style.configure("Header.TLabel", font=(_FONT, 14, "bold"))
        style.configure("Muted.TLabel", foreground="#8f9aa8")

    def _build(self) -> None:
        header = ttk.Frame(self.root, padding=(16, 12))
        header.pack(fill="x")
        ttk.Label(header, text="WSL Manager", style="Header.TLabel").pack(side="left")
        ttk.Label(header, text="Gestion de distros WSL2", style="Muted.TLabel").pack(side="left", padx=(10, 0))
        self.header_status = ttk.Label(header, text="", style="Muted.TLabel")
        self.header_status.pack(side="right")
        ttk.Separator(self.root).pack(fill="x")

        nb = ttk.Notebook(self.root, padding=6)
        nb.pack(fill="both", expand=True, padx=8, pady=(4, 0))

        self.tabs = {
            "dashboard": dashboard_tab.DashboardTab(nb, self.ctx),
            "resources": resources_tab.ResourcesTab(nb, self.ctx),
            "monitor": monitor_tab.MonitorTab(nb, self.ctx),
            "config": config_tab.ConfigTab(nb, self.ctx),
            "autostart": autostart_tab.AutoStartTab(nb, self.ctx),
            "scheduler": scheduler_tab.SchedulerTab(nb, self.ctx),
            "profiles": profiles_tab.ProfilesTab(nb, self.ctx),
            "logs": logs_tab.LogsTab(nb, self.ctx),
            "settings": settings_tab.SettingsTab(nb, self.ctx),
        }
        labels = {
            "dashboard": "Dashboard",
            "resources": "Recursos",
            "monitor": "Monitor",
            "config": "Configuracion",
            "autostart": "Autoarranque",
            "scheduler": "Programador",
            "profiles": "Perfiles",
            "logs": "Logs",
            "settings": "Ajustes",
        }
        for key, frame in self.tabs.items():
            nb.add(frame, text=labels[key])

        ttk.Separator(self.root).pack(fill="x")
        bar = ttk.Frame(self.root, padding=(16, 6))
        bar.pack(fill="x", side="bottom")
        self.status_var = tk.StringVar(value="listo")
        ttk.Label(bar, textvariable=self.status_var, style="Muted.TLabel").pack(side="left")
        ttk.Label(bar, text="ejecutando en segundo plano (bandeja del sistema)", style="Muted.TLabel").pack(side="right")

    def set_status(self, text: str) -> None:
        self.status_var.set(text)

    def set_header_status(self, text: str) -> None:
        self.header_status.configure(text=text)

    def show(self) -> None:
        self.root.deiconify()
        self.root.lift()
        self.root.focus_force()

    def hide(self) -> None:
        self.root.withdraw()

    def toggle(self) -> None:
        if self.root.state() == "normal" and self.root.winfo_viewable():
            self.hide()
        else:
            self.show()

    def refresh_dashboard(self) -> None:
        if "dashboard" in self.tabs:
            self.tabs["dashboard"].refresh()

    def run(self) -> None:
        self.root.mainloop()

    def close(self) -> None:
        try:
            self.root.destroy()
        except tk.TclError:
            pass
