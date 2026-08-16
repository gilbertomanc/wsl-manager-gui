"""Pestana Configuracion: edicion segura de .wslconfig con backup + validacion."""
from __future__ import annotations

import tkinter as tk
from tkinter import messagebox

import ttkbootstrap as ttk


class ConfigTab(ttk.Frame):
    def __init__(self, master, ctx) -> None:
        super().__init__(master)
        self.ctx = ctx
        self._build()
        self.refresh()

    def _build(self) -> None:
        bar = ttk.Frame(self)
        bar.pack(fill="x", padx=6, pady=6)
        ttk.Button(bar, text="Recargar", bootstyle="success", command=self.refresh).pack(side="left", padx=2)
        ttk.Button(bar, text="Guardar (con backup)", bootstyle="info", command=self._save).pack(side="left", padx=2)
        ttk.Label(bar, text="  ~/.wslconfig - configuracion de la VM WSL2", style="Muted.TLabel").pack(side="left")

        self.text = tk.Text(self, wrap="none", font=("Consolas", 10))
        self.text.pack(fill="both", expand=True, padx=6, pady=6)
        self._errors = tk.StringVar()
        ttk.Label(self, textvariable=self._errors, foreground="#c33").pack(anchor="w", padx=8)

    def refresh(self) -> None:
        from src.providers.wsl_config_provider import WslConfigProvider

        p = WslConfigProvider()
        text = p.wslconfig_path.read_text(encoding="utf-8") if p.wslconfig_path.exists() else "# (sin .wslconfig; se creara al guardar)\n"
        self.text.delete("1.0", "end")
        self.text.insert("1.0", text)
        self._errors.set("")

    def _save(self) -> None:
        from src.providers.wsl_config_provider import WslConfigProvider

        content = self.text.get("1.0", "end-1c")
        p = WslConfigProvider()
        if not p._validate_ini(content):
            self._errors.set("INI invalido: revisa las secciones [wsl2], [experimental], etc. No se guardo.")
            return
        backup = p.backup_now()
        try:
            p.wslconfig_path.write_text(content, encoding="utf-8")
        except OSError as e:
            messagebox.showerror("WSL Manager", str(e))
            return
        self.ctx.metrics.log_event("gui_wslconfig", message=f".wslconfig guardado (backup {backup.name})")
        self._errors.set(f"Guardado. Backup: {backup.name}. Requiere 'wsl --shutdown'.")
