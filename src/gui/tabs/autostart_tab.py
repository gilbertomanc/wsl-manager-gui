"""Pestana Autoarranque (W5): distros que inician con Windows (HKCU Run)."""
from __future__ import annotations

import tkinter as tk
from tkinter import messagebox

import ttkbootstrap as ttk

from src.gui.widgets import make_tree


class AutoStartTab(ttk.Frame):
    def __init__(self, master, ctx) -> None:
        super().__init__(master)
        self.ctx = ctx
        self._build()
        self.refresh()

    def _build(self) -> None:
        bar = ttk.Frame(self)
        bar.pack(fill="x", padx=6, pady=6)
        ttk.Button(bar, text="Refrescar", bootstyle="success", command=self.refresh).pack(side="left", padx=2)

        self.tree = make_tree(
            self,
            [("distro", "Distro", 180), ("delay", "Retraso (s)", 110), ("cmd", "Comando en Run", 500)],
        )
        ttk.Label(
            self,
            text="Con WSL Manager: las distros marcadas aqui se inician automaticamente al entrar a Windows (HKCU Run).",
            style="Muted.TLabel",
        ).pack(anchor="w", padx=10, pady=(0, 4))

        actions = ttk.Frame(self)
        actions.pack(fill="x", padx=6, pady=4)
        ttk.Button(actions, text="Activar autoarranque...", bootstyle="info", command=self._enable).pack(side="left", padx=2)
        ttk.Button(actions, text="Desactivar", bootstyle="secondary", command=self._disable).pack(side="left", padx=2)

    def refresh(self) -> None:
        items = self.ctx.autostart.list_autostart()
        self.tree.delete(*self.tree.get_children())
        for distro, info in items.items():
            self.tree.insert("", "end", values=(distro, info["delay_s"], info["command"]))
        if not items:
            self.tree.insert("", "end", values=("(sin distros en autoarranque)", "", ""))

    def _selected(self) -> str | None:
        sel = self.tree.selection()
        if not sel:
            return None
        return self.tree.item(sel[0], "values")[0]

    def _enable(self) -> None:
        import tkinter.simpledialog as sd

        distros = [d.name for d in self.ctx.wsl.list_distros()]
        if not distros:
            messagebox.showinfo("WSL Manager", "No hay distros detectadas")
            return
        from tkinter import simpledialog

        class _Dialog(simpledialog.Dialog):
            def body(self, master):
                self.distro = tk.StringVar(value=distros[0])
                self.delay = tk.StringVar(value="0")
                ttk.Label(master, text="Distro:").grid(row=0, column=0, sticky="w")
                ttk.Combobox(master, textvariable=self.distro, values=distros, state="readonly", width=24).grid(row=0, column=1, padx=4)
                ttk.Label(master, text="Retraso (s):").grid(row=1, column=0, sticky="w", pady=4)
                ttk.Entry(master, textvariable=self.delay, width=10).grid(row=1, column=1, sticky="w", padx=4)

            def apply(self):
                self.result = (self.distro.get(), int(self.delay.get() or 0))

        dlg = _Dialog(self, title="Autoarranque")
        if dlg.result:
            distro, delay = dlg.result
            r = self.ctx.autostart.set_autostart(distro, True, delay)
            if not r.ok:
                messagebox.showerror("WSL Manager", r.error)
                return
            self.ctx.metrics.log_event("gui_autostart", distro, f"autoarranque con delay {delay}s")
            self.refresh()

    def _disable(self) -> None:
        distro = self._selected()
        if not distro or distro.startswith("("):
            return
        r = self.ctx.autostart.set_autostart(distro, False)
        if not r.ok:
            messagebox.showerror("WSL Manager", r.error)
            return
        self.refresh()
