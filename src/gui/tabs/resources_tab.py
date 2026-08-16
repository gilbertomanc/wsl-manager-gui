"""Pestana Recursos (R1): limites globales de la VM via .wslconfig."""
from __future__ import annotations

import tkinter as tk
from tkinter import messagebox

import ttkbootstrap as ttk

from src.core.config import GlobalLimits


class ResourcesTab(ttk.Frame):
    def __init__(self, master, ctx) -> None:
        super().__init__(master)
        self.ctx = ctx
        self._build()

    def _build(self) -> None:
        cur = self.ctx.resources.get_global_limits()

        form = ttk.Frame(self)
        form.pack(fill="x", padx=12, pady=12)
        self.memory_var = tk.StringVar(value=f"{cur.memory_gb} GB" if cur.memory_gb else "")
        self.proc_var = tk.StringVar(value=str(cur.processors) if cur.processors else "")
        self.swap_var = tk.StringVar(value=f"{cur.swap_gb} GB" if cur.swap_gb else "")
        self.reclaim_var = tk.StringVar(value=cur.auto_memory_reclaim or "disabled")
        self.sparse_var = tk.BooleanVar(value=bool(cur.sparse_vhd))

        rows = [
            ("Memoria de la VM (ej: 8 GB)", self.memory_var, "dejar vacio = sin limite"),
            ("Procesadores", self.proc_var, "dejar vacio = sin limite"),
            ("Swap (ej: 4 GB)", self.swap_var, "dejar vacio = sin limite"),
        ]
        for i, (label, var, hint) in enumerate(rows):
            ttk.Label(form, text=label).grid(row=i, column=0, sticky="w", pady=3)
            ttk.Entry(form, textvariable=var, width=16).grid(row=i, column=1, sticky="w", padx=6)
            ttk.Label(form, text=hint).grid(row=i, column=2, sticky="w")

        ttk.Label(form, text="Auto-memory reclaim:").grid(row=3, column=0, sticky="w", pady=3)
        ttk.Combobox(
            form, textvariable=self.reclaim_var, values=["disabled", "gradual", "dropcache"], width=14, state="readonly"
        ).grid(row=3, column=1, sticky="w", padx=6)
        ttk.Checkbutton(form, text="Sparse VHD (ahorro de disco)", variable=self.sparse_var).grid(row=4, column=0, columnspan=2, sticky="w", pady=6)

        ttk.Button(form, text="Aplicar limites", command=self._apply).grid(row=5, column=0, sticky="w", pady=8)
        ttk.Label(
            form,
            text="Los cambios requieren 'wsl --shutdown' (boton del Dashboard).\nSe hace backup automatico de .wslconfig antes de escribir.",
            foreground="#888",
        ).grid(row=6, column=0, columnspan=3, sticky="w")

    def _apply(self) -> None:
        limits = GlobalLimits()

        def parse_gb(v: str) -> float | None:
            v = v.strip().upper()
            if not v:
                return None
            try:
                return float(v[:-2]) if v.endswith("GB") else (float(v[:-2]) / 1024 if v.endswith("MB") else float(v))
            except ValueError:
                return None

        mem = parse_gb(self.memory_var.get())
        swap = parse_gb(self.swap_var.get())
        if mem is not None:
            limits.memory_gb = mem
        if swap is not None:
            limits.swap_gb = swap
        if self.proc_var.get().strip().isdigit():
            limits.processors = int(self.proc_var.get().strip())
        limits.auto_memory_reclaim = self.reclaim_var.get()  # type: ignore[assignment]
        limits.sparse_vhd = self.sparse_var.get()

        r = self.ctx.resources.set_global_limits(limits)
        if not r.ok:
            messagebox.showerror("WSL Manager", r.error)
            return
        self.ctx.metrics.log_event("gui_limits", message="limites aplicados desde GUI")
        messagebox.showinfo("WSL Manager", "Limites aplicados.\nEjecuta 'wsl --shutdown' para que surtan efecto.")
