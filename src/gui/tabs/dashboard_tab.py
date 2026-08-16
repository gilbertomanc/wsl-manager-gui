"""Pestana Dashboard (W1-W4): tabla de distros + ciclo de vida.

Usa ttkbootstrap Tableview (busqueda, ordenado por columna y filas
alternadas integradas). El refresco y las acciones pesadas (wsl.exe)
corren en un hilo de fondo: la UI nunca se congela.
"""
from __future__ import annotations

import tkinter as tk
from tkinter import filedialog, messagebox

import ttkbootstrap as ttk

from src.core.logger import get_logger
from src.gui.widgets import BackgroundRefresher, status_text

log = get_logger("gui.dashboard")

_COLUMNS = [
    {"text": "Distro", "width": 190, "stretch": True},
    {"text": "Estado", "width": 120},
    {"text": "WSL", "width": 70},
    {"text": "IP", "width": 160},
    {"text": "Grupo", "width": 130},
]


class DashboardTab(ttk.Frame):
    def __init__(self, master, ctx) -> None:
        super().__init__(master)
        self.ctx = ctx
        self._refresher = BackgroundRefresher(self.winfo_toplevel())
        self._build()
        self.refresh()

    def _build(self) -> None:
        bar = ttk.Frame(self)
        bar.pack(fill="x", padx=6, pady=6)
        ttk.Button(bar, text="Refrescar", bootstyle="success", command=self.refresh).pack(side="left", padx=2)
        ttk.Button(bar, text="Iniciar todas", bootstyle="info", command=self._start_all).pack(side="left", padx=2)
        ttk.Button(bar, text="Apagar todas", bootstyle="danger", command=self._shutdown_all).pack(side="left", padx=2)

        from ttkbootstrap.widgets import Tableview

        self.table = Tableview(
            self,
            coldata=_COLUMNS,
            rowdata=[],
            bootstyle="info",
            stripecolor=("#2a2f37", None),
            searchable=True,
            height=12,
        )
        self.table.pack(fill="both", expand=True, padx=8, pady=4)
        self.table.view.bind("<Double-1>", lambda _e: self._actions())

        actions = ttk.Frame(self)
        actions.pack(fill="x", padx=6, pady=4)
        for text, cb, bootstyle in [
            ("Iniciar", self._start, "info"),
            ("Detener", self._stop, "secondary"),
            ("Reiniciar", self._restart, "secondary"),
            ("Terminal", self._shell, "secondary"),
            ("Explorador", self._explorer, "secondary"),
            ("Nueva distro...", self._install_new, "success"),
            ("Importar...", self._import, "success"),
            ("Exportar...", self._export, "secondary"),
            ("Snapshot", self._snapshot, "secondary"),
            ("Clonar...", self._clone, "secondary"),
        ]:
            ttk.Button(actions, text=text, bootstyle=bootstyle, command=cb).pack(side="left", padx=2)

        self.status_var = tk.StringVar(value="cargando...")
        ttk.Label(self, textvariable=self.status_var, style="Muted.TLabel").pack(anchor="w", padx=10, pady=(0, 4))

    # -- datos (en segundo plano) ----------------------------------------------------

    def refresh(self) -> None:
        """Dispara un refresco en segundo plano; si ya hay uno en curso se
        omite (throttle) para no saturar WSL ni congelar la UI."""
        if not self._refresher.submit(self._load, self._apply):
            return
        self.status_var.set("actualizando...")

    def _load(self):
        distros = self.ctx.wsl.list_distros()
        for d in distros:
            if d.state == "Running":
                d.ip = self.ctx.wsl.get_ip(d.name)
        inst = {i.name: i for i in self.ctx.config.distros.instances}
        return distros, inst

    def _apply(self, data, err) -> None:
        if err is not None or data is None:
            self.status_var.set(f"error: {err}")
            return
        distros, inst = data
        # Preservar seleccion y busqueda a traves del rebuild (Tableview
        # auto-selecciona la primera fila tras build_table_data).
        prev_selection = None
        sel = self.table.get_rows(selected=True)
        if sel:
            prev_selection = str(sel[0].values[0])
        prev_search = self.table.searchcriteria
        self._distros = distros
        rows = [
            [
                d.name,
                status_text(d.state),
                f"WSL{d.version}",
                d.ip or "-",
                inst.get(d.name).group if d.name in inst else "",
            ]
            for d in distros
        ]
        self.table.build_table_data(_COLUMNS, rows)
        if prev_search:
            self.table.searchcriteria = prev_search
            self.table.search_table_data(prev_search)
        if prev_selection:
            for row in self.table.get_rows():
                if str(row.values[0]) == prev_selection:
                    self.table.view.selection_set(row.iid)
                    self.table.view.focus(row.iid)
                    self.table.view.see(row.iid)
                    break
        running = sum(1 for d in distros if d.state == "Running")
        self.status_var.set(f"{running}/{len(distros)} distros corriendo")

    # -- acciones ---------------------------------------------------------------------

    def _selected(self) -> str | None:
        rows = self.table.get_rows(selected=True)
        if not rows:
            messagebox.showinfo("WSL Manager", "Selecciona una distro")
            return None
        return str(rows[0].values[0])

    def _start(self) -> None:
        name = self._selected()
        if not name:
            return
        r = self.ctx.wsl.start(name)
        self._after_action(r, name, "iniciada desde GUI")
        self.refresh()

    def _stop(self) -> None:
        name = self._selected()
        if not name:
            return
        r = self.ctx.wsl.stop(name)
        self._after_action(r, name, "detenida desde GUI")
        self.refresh()

    def _restart(self) -> None:
        name = self._selected()
        if not name:
            return
        r = self.ctx.wsl.restart(name)
        self._after_action(r, name, "reiniciada desde GUI")
        self.refresh()

    def _shell(self) -> None:
        name = self._selected()
        if not name:
            return
        r = self.ctx.wsl.open_shell(name)
        self._after_action(r, name, "terminal abierta")

    def _explorer(self) -> None:
        name = self._selected()
        if not name:
            return
        r = self.ctx.wsl.open_explorer(name)
        self._after_action(r, name, "explorador abierto")

    def _after_action(self, r, name: str, ok_msg: str) -> None:
        if r and not r.ok:
            messagebox.showerror("WSL Manager", r.error)
            return
        self.ctx.metrics.log_event("gui_action", name, ok_msg)

    def _export(self) -> None:
        name = self._selected()
        if not name:
            return
        path = filedialog.asksaveasfilename(defaultextension=".tar", initialfile=f"{name}.tar", filetypes=[("TAR", "*.tar")])
        if not path:
            return
        self.status_var.set("exportando... (puede tardar)")
        self._refresher.submit(
            lambda: self.ctx.wsl.export(name, path),
            lambda r, err: self._export_done(r, err, name, path),
        )

    def _install_new(self) -> None:
        """Crea una distro nueva via wsl --install (catalogo de WSL)."""
        import tkinter.simpledialog as sd

        name = sd.askstring(
            "Nueva distro",
            "Nombre de la distro a instalar (descarga del catalogo WSL):\n\n"
            "Ejemplos: Ubuntu-24.04, Ubuntu-22.04, Debian, Kali-Linux, Alpine,\n"
            "Fedora, openSUSE-Leap-15.6, OracleLinux_8_9",
        )
        if not name:
            return
        name = name.strip()
        if not name:
            return
        self.status_var.set(f"instalando {name}... (descarga, puede tardar minutos)")
        self._refresher.submit(
            lambda: self.ctx.wsl.install_new(name),
            lambda r, err: self._install_done(r, err, name),
        )

    def _install_done(self, r, err, name) -> None:
        if err is not None:
            messagebox.showerror("WSL Manager", str(err))
            self.status_var.set("error en instalacion")
            return
        if not r.ok:
            messagebox.showerror("WSL Manager", r.error or r.output)
            self.status_var.set("error en instalacion")
            return
        self.status_var.set(f"{name} instalada")
        messagebox.showinfo("WSL Manager", f"Distro '{name}' instalada.")
        self.refresh()

    def _import(self) -> None:
        """Importa una distro nueva desde un archivo (tar/tar.gz/tar.xz)."""
        import tkinter.simpledialog as sd
        from pathlib import Path

        name = sd.askstring("Importar distro", "Nombre para la distro importada:")
        if not name:
            return
        name = name.strip()
        if not name:
            return
        path = filedialog.askopenfilename(
            title="Archivo de la distro a importar",
            filetypes=[("Imagen WSL", "*.tar *.tar.gz *.tgz *.tar.xz"), ("Todos los archivos", "*.*")],
        )
        if not path:
            return
        install_dir = str(Path.home() / "wsl" / name)
        self.status_var.set(f"importando {name}... (puede tardar)")
        self._refresher.submit(
            lambda: self.ctx.wsl.import_distro(path, name, install_dir),
            lambda r, err: self._import_done(r, err, name, path),
        )

    def _import_done(self, r, err, name, path) -> None:
        if err is not None:
            messagebox.showerror("WSL Manager", str(err))
            self.status_var.set("error en importacion")
            return
        if not r.ok:
            messagebox.showerror("WSL Manager", r.error or r.output)
            self.status_var.set("error en importacion")
            return
        self.ctx.metrics.log_event("gui_import", name, f"importada de {path}")
        self.status_var.set(f"{name} importada")
        messagebox.showinfo("WSL Manager", f"Distro '{name}' importada.")
        self.refresh()

    def _export_done(self, r, err, name, path) -> None:
        if err is not None:
            messagebox.showerror("WSL Manager", str(err))
            return
        if not r.ok:
            messagebox.showerror("WSL Manager", r.error)
            return
        self.ctx.metrics.log_event("gui_export", name, f"exportada a {path}")
        self.status_var.set("exportada")
        messagebox.showinfo("WSL Manager", f"Exportada a {path}")

    def _snapshot(self) -> None:
        name = self._selected()
        if not name:
            return
        self.status_var.set("creando snapshot...")
        self._refresher.submit(
            lambda: self.ctx.wsl.snapshot(name, self.ctx.config.snapshots.retention_days, self.ctx.config.snapshots.target_dir),
            lambda p, err: self._snapshot_done(p, err, name),
        )

    def _snapshot_done(self, path, err, name) -> None:
        if err is not None:
            messagebox.showerror("WSL Manager", str(err))
            self.status_var.set("error en snapshot")
            return
        size = path.stat().st_size if path.exists() else 0
        self.ctx.metrics.record_snapshot(name, str(path), size)
        self.status_var.set("snapshot listo")
        messagebox.showinfo("WSL Manager", f"Snapshot: {path}\n({size / 1e6:.1f} MB)")

    def _clone(self) -> None:
        import tkinter.simpledialog as sd

        name = self._selected()
        if not name:
            return
        new_name = sd.askstring("Clonar", f"Nuevo nombre para clon de {name}:")
        if not new_name:
            return
        self.status_var.set("clonando... (puede tardar)")
        self._refresher.submit(
            lambda: self.ctx.wsl.clone(name, new_name),
            lambda r, err: self._clone_done(r, err),
        )

    def _clone_done(self, r, err) -> None:
        if err is not None:
            messagebox.showerror("WSL Manager", str(err))
            self.status_var.set("error en clonado")
            return
        if not r.ok:
            messagebox.showerror("WSL Manager", r.error)
            self.status_var.set("error en clonado")
            return
        self.status_var.set("clonada")
        self.refresh()

    def _start_all(self) -> None:
        self.status_var.set("iniciando todas...")
        self._refresher.submit(
            lambda: [self.ctx.wsl.start(d.name) for d in self.ctx.wsl.list_distros()],
            lambda _r, _e: self.refresh(),
        )

    def _shutdown_all(self) -> None:
        if messagebox.askyesno("WSL Manager", "¿Apagar TODAS las distros?"):
            self.ctx.wsl.shutdown_all()
            self.refresh()
