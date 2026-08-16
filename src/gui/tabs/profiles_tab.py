"""Pestana Perfiles (A3): capturar y aplicar perfiles de distros."""
from __future__ import annotations

import tkinter as tk
from tkinter import messagebox

import ttkbootstrap as ttk

from src.core.profiles import ProfileService
from src.gui.widgets import make_tree


class ProfilesTab(ttk.Frame):
    def __init__(self, master, ctx) -> None:
        super().__init__(master)
        self.ctx = ctx
        self._build()
        self.refresh()

    def _build(self) -> None:
        bar = ttk.Frame(self)
        bar.pack(fill="x", padx=6, pady=6)
        ttk.Button(bar, text="Refrescar", bootstyle="success", command=self.refresh).pack(side="left", padx=2)
        ttk.Button(bar, text="Capturar perfil...", bootstyle="info", command=self._capture).pack(side="left", padx=2)
        ttk.Button(bar, text="Aplicar", bootstyle="secondary", command=self._apply).pack(side="left", padx=2)

        self.tree = make_tree(
            self,
            [("name", "Perfil", 150), ("desc", "Descripcion", 240), ("distros", "Distros a iniciar", 320)],
        )
        ttk.Label(self, text="Capturar = guarda el estado actual (distros activas). Aplicar = transiciona al perfil.", style="Muted.TLabel").pack(anchor="w", padx=10, pady=(0, 4))

    def refresh(self) -> None:
        items = ProfileService(self.ctx.store, self.ctx.wsl).list()
        self.tree.delete(*self.tree.get_children())
        for i in items:
            mark = "* " if i["active"] else ""
            self.tree.insert("", "end", values=(f"{mark}{i['name']}", i["description"], ", ".join(i["distros_to_start"])))

    def _selected(self) -> str | None:
        sel = self.tree.selection()
        if not sel:
            return None
        return self.tree.item(sel[0], "values")[0].lstrip("* ")

    def _capture(self) -> None:
        import tkinter.simpledialog as sd

        name = sd.askstring("Capturar perfil", "Nombre del perfil:")
        if not name:
            return
        svc = ProfileService(self.ctx.store, self.ctx.wsl)
        item = svc.capture(name)
        self.ctx.metrics.log_event("gui_profile_capture", message=f"perfil {name} capturado")
        messagebox.showinfo("WSL Manager", f"Perfil '{name}' capturado:\n{', '.join(item.distros_to_start) or '(nada corriendo)'}")
        self.refresh()

    def _apply(self) -> None:
        name = self._selected()
        if not name:
            return
        try:
            ok = ProfileService(self.ctx.store, self.ctx.wsl).apply(name)
        except KeyError as e:
            messagebox.showerror("WSL Manager", str(e))
            return
        if not ok:
            messagebox.showerror("WSL Manager", "Fallo al aplicar el perfil (ver logs)")
            return
        self.ctx.metrics.log_event("gui_profile_apply", message=f"perfil {name} aplicado")
        messagebox.showinfo("WSL Manager", f"Perfil '{name}' aplicado")
        self.refresh()
