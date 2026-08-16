"""Pestana Programador (A2): tareas programadas."""
from __future__ import annotations

import tkinter as tk
from tkinter import messagebox

import ttkbootstrap as ttk

from src.core.config import ScheduleAction, ScheduleSpec, ScheduleTask
from src.core.scheduler import Scheduler
from src.gui.widgets import make_tree


class SchedulerTab(ttk.Frame):
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
            [("id", "ID", 130), ("name", "Nombre", 170), ("type", "Accion", 120), ("target", "Objetivo", 130), ("time", "Hora", 70), ("days", "Dias", 150)],
        )
        actions = ttk.Frame(self)
        actions.pack(fill="x", padx=6, pady=4)
        ttk.Button(actions, text="Nueva tarea...", bootstyle="info", command=self._add).pack(side="left", padx=2)
        ttk.Button(actions, text="Eliminar", bootstyle="secondary", command=self._remove).pack(side="left", padx=2)
        ttk.Button(actions, text="Ejecutar ahora", bootstyle="warning", command=self._run_now).pack(side="left", padx=2)

    def refresh(self) -> None:
        tasks = self.ctx.store.get().scheduler.tasks
        self.tree.delete(*self.tree.get_children())
        for t in tasks:
            target = t.action.distro or t.action.profile or ""
            days = ",".join(d[:2] for d in t.schedule.days)
            self.tree.insert("", "end", values=(t.id, t.name, t.action.type, target, t.schedule.time, days))

    def _selected(self) -> str | None:
        sel = self.tree.selection()
        if not sel:
            return None
        return self.tree.item(sel[0], "values")[0]

    def _add(self) -> None:
        import uuid

        from tkinter import simpledialog

        distros = [d.name for d in self.ctx.wsl.list_distros()]

        class _Dialog(simpledialog.Dialog):
            def body(self, master):
                self.name = tk.StringVar(value="Iniciar dev")
                self.type_ = tk.StringVar(value="distro_start")
                self.distro = tk.StringVar(value=distros[0] if distros else "")
                self.time = tk.StringVar(value="09:00")
                self.days = tk.StringVar(value="mon,tue,wed,thu,fri")
                ttk.Label(master, text="Nombre:").grid(row=0, column=0, sticky="w")
                ttk.Entry(master, textvariable=self.name, width=20).grid(row=0, column=1, padx=4, pady=2)
                ttk.Label(master, text="Accion:").grid(row=1, column=0, sticky="w")
                ttk.Combobox(
                    master, textvariable=self.type_, values=["distro_start", "distro_stop", "snapshot", "apply_profile"], state="readonly", width=18
                ).grid(row=1, column=1, padx=4, pady=2)
                ttk.Label(master, text="Distro:").grid(row=2, column=0, sticky="w")
                ttk.Combobox(master, textvariable=self.distro, values=distros, state="readonly", width=18).grid(row=2, column=1, padx=4, pady=2)
                ttk.Label(master, text="Hora (HH:MM):").grid(row=3, column=0, sticky="w")
                ttk.Entry(master, textvariable=self.time, width=10).grid(row=3, column=1, sticky="w", padx=4, pady=2)
                ttk.Label(master, text="Dias (mon,tue,...):").grid(row=4, column=0, sticky="w")
                ttk.Entry(master, textvariable=self.days, width=20).grid(row=4, column=1, padx=4, pady=2)

            def apply(self):
                self.result = (self.name.get(), self.type_.get(), self.distro.get(), self.time.get(), self.days.get())

        dlg = _Dialog(self, title="Nueva tarea")
        if not dlg.result:
            return
        name, type_, distro, time_, days = dlg.result
        task = ScheduleTask(
            id=f"tarea-{uuid.uuid4().hex[:8]}",
            name=name,
            action=ScheduleAction(type=type_, distro=distro or None),  # type: ignore[arg-type]
            schedule=ScheduleSpec(days=[d.strip() for d in days.split(",")], time=time_),
        )
        Scheduler(self.ctx.store, self.ctx.metrics, self.ctx.bus, self.ctx.wsl).add_task(task)
        self.ctx.metrics.log_event("gui_schedule", message=f"tarea {name} creada")
        self.refresh()

    def _remove(self) -> None:
        task_id = self._selected()
        if not task_id:
            return
        s = Scheduler(self.ctx.store, self.ctx.metrics, self.ctx.bus, self.ctx.wsl)
        if s.remove_task(task_id):
            self.refresh()

    def _run_now(self) -> None:
        task_id = self._selected()
        if not task_id:
            return
        s = Scheduler(self.ctx.store, self.ctx.metrics, self.ctx.bus, self.ctx.wsl)
        ok = s.run_task(task_id)
        messagebox.showinfo("WSL Manager", "Tarea ejecutada OK" if ok else "La tarea fallo (ver logs)")
        self.refresh()
