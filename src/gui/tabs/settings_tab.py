"""Pestana Ajustes: tema, comportamiento (segundo plano + autoarranque),
panel web (clave obligatoria), API REST y servidor MCP."""
from __future__ import annotations

import tkinter as tk
from pathlib import Path
from tkinter import messagebox
from winreg import HKEY_CURRENT_USER, CreateKey, DeleteValue, OpenKey, QueryValueEx, SetValueEx

import ttkbootstrap as ttk

_RUN_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"
_AUTOSTART_NAME = "WSLManagerGUI"


def _autostart_command() -> str:
    vbs = Path(__file__).resolve().parents[3] / "start_wsl_manager_gui.vbs"
    return f'wscript.exe "{vbs}"'


def _ensure_autostart_vbs() -> None:
    """Crea el lanzador VBS (ventana oculta) si no existe: el autoarranque
    via wscript necesita ese archivo y, sin el, podia abrirse una terminal
    o un error breve al iniciar sesion."""
    p = Path(__file__).resolve().parents[3] / "start_wsl_manager_gui.vbs"
    if p.exists():
        return
    content = (
        "' Lanzador oculto de WSL Manager (auto-generado): sin terminal.\n"
        "Set sh = CreateObject(\"WScript.Shell\")\n"
        "Set fso = CreateObject(\"Scripting.FileSystemObject\")\n"
        "dir = fso.GetParentFolderName(WScript.ScriptFullName)\n"
        "sh.Run \"\"\"\" & dir & \"\\.venv\\Scripts\\pythonw.exe\"\" \"\"\""
        " & dir & \"\\src\\app.py\"\" --minimized\", 0, False\n"
    )
    try:
        p.write_text(content, encoding="utf-8")
    except OSError:
        pass


def autostart_active() -> bool:
    try:
        with OpenKey(HKEY_CURRENT_USER, _RUN_KEY) as k:
            return QueryValueEx(k, _AUTOSTART_NAME)[0] == _autostart_command()
    except OSError:
        return False


def _set_autostart(active: bool) -> None:
    if active:
        _ensure_autostart_vbs()
    with CreateKey(HKEY_CURRENT_USER, _RUN_KEY) as k:
        if active:
            SetValueEx(k, _AUTOSTART_NAME, 0, 1, _autostart_command())  # REG_SZ
        else:
            try:
                DeleteValue(k, _AUTOSTART_NAME)
            except OSError:
                pass


class SettingsTab(ttk.Frame):
    def __init__(self, master, ctx) -> None:
        super().__init__(master)
        self.ctx = ctx
        self._build()

    def _build(self) -> None:
        ui = self.ctx.config.ui
        api = self.ctx.config.api
        mcp = self.ctx.config.mcp

        form = ttk.Frame(self)
        form.pack(fill="x", padx=12, pady=10)

        # -- general ------------------------------------------------------------
        self.theme_var = tk.StringVar(value=ui.theme)
        ttk.Label(form, text="Tema:").grid(row=0, column=0, sticky="w", pady=3)
        ttk.Combobox(form, textvariable=self.theme_var, values=["darkly", "superhero", "cyborg", "cosmo", "flatly", "journal"], state="readonly", width=14).grid(row=0, column=1, sticky="w", padx=6)

        self.min_var = tk.BooleanVar(value=ui.start_minimized)
        ttk.Checkbutton(form, text="Iniciar en segundo plano (solo bandeja, sin ventana)", variable=self.min_var).grid(row=1, column=0, columnspan=2, sticky="w", pady=3)

        self.tray_var = tk.BooleanVar(value=ui.close_to_tray)
        ttk.Checkbutton(form, text="Ejecutar en segundo plano: cerrar ventana -> minimizar a bandeja (la app sigue viva)", variable=self.tray_var).grid(row=2, column=0, columnspan=2, sticky="w", pady=3)

        self.stop_var = tk.BooleanVar(value=self.ctx.config.on_close.stop_distros)
        ttk.Checkbutton(form, text="Al salir de la app: detener todas las distros", variable=self.stop_var).grid(row=3, column=0, columnspan=2, sticky="w", pady=3)

        self.auto_var = tk.BooleanVar(value=autostart_active())
        ttk.Checkbutton(form, text="Autoarranque: iniciar con Windows en segundo plano (bandeja)", variable=self.auto_var).grid(row=4, column=0, columnspan=2, sticky="w", pady=3)

        ttk.Separator(form).grid(row=5, column=0, columnspan=3, sticky="ew", pady=8)

        # -- panel web ----------------------------------------------------------
        ttk.Label(form, text="Panel web", style="Header.TLabel").grid(row=6, column=0, columnspan=3, sticky="w", pady=(0, 4))
        self.web_var = tk.BooleanVar(value=ui.web_panel_enabled)
        ttk.Checkbutton(form, text="Panel web habilitado", variable=self.web_var).grid(row=7, column=0, columnspan=2, sticky="w", pady=3)
        self.web_port_var = tk.StringVar(value=str(ui.web_panel_port))
        ttk.Label(form, text="Puerto:").grid(row=8, column=0, sticky="w")
        ttk.Entry(form, textvariable=self.web_port_var, width=8).grid(row=8, column=1, sticky="w", padx=6)
        self.web_bind_var = tk.StringVar(value=ui.web_panel_bind)
        ttk.Label(form, text="Bind:").grid(row=9, column=0, sticky="w")
        ttk.Entry(form, textvariable=self.web_bind_var, width=14).grid(row=9, column=1, sticky="w", padx=6)
        self.web_pw_var = tk.StringVar()
        ttk.Label(form, text="Clave (obligatoria):").grid(row=10, column=0, sticky="w")
        ttk.Entry(form, textvariable=self.web_pw_var, width=20, show="*").grid(row=10, column=1, sticky="w", padx=6)
        ttk.Label(form, text="El panel exige esta clave para entrar; dejala vacia solo si deshabilitas el panel.", style="Muted.TLabel").grid(row=11, column=0, columnspan=3, sticky="w")

        ttk.Separator(form).grid(row=12, column=0, columnspan=3, sticky="ew", pady=8)

        # -- MCP ----------------------------------------------------------------
        ttk.Label(form, text="Servidor MCP (agentes LLM)", style="Header.TLabel").grid(row=13, column=0, columnspan=3, sticky="w", pady=(0, 4))
        self.mcp_var = tk.BooleanVar(value=mcp.enabled)
        ttk.Checkbutton(form, text="MCP habilitado", variable=self.mcp_var).grid(row=14, column=0, columnspan=2, sticky="w", pady=3)
        self.mcp_transport_var = tk.StringVar(value=mcp.transport)
        ttk.Label(form, text="Transporte:").grid(row=15, column=0, sticky="w")
        ttk.Combobox(form, textvariable=self.mcp_transport_var, values=["stdio", "http"], state="readonly", width=8).grid(row=15, column=1, sticky="w", padx=6)
        self.mcp_port_var = tk.StringVar(value=str(mcp.port))
        ttk.Label(form, text="Puerto (http):").grid(row=16, column=0, sticky="w")
        ttk.Entry(form, textvariable=self.mcp_port_var, width=8).grid(row=16, column=1, sticky="w", padx=6)
        self.mcp_token_var = tk.BooleanVar(value=mcp.token_required)
        ttk.Checkbutton(form, text="Exigir token", variable=self.mcp_token_var).grid(row=17, column=0, columnspan=2, sticky="w", pady=3)
        self.mcp_key_var = tk.StringVar()
        ttk.Label(form, text="Token:").grid(row=18, column=0, sticky="w")
        ttk.Entry(form, textvariable=self.mcp_key_var, width=20, show="*").grid(row=18, column=1, sticky="w", padx=6)
        ttk.Label(form, text="Si exiges token y lo dejas vacio, se genera uno aleatorio al guardar.", style="Muted.TLabel").grid(row=19, column=0, columnspan=3, sticky="w")

        ttk.Separator(form).grid(row=20, column=0, columnspan=3, sticky="ew", pady=8)

        # -- API -----------------------------------------------------------------
        ttk.Label(form, text="API REST", style="Header.TLabel").grid(row=21, column=0, columnspan=3, sticky="w", pady=(0, 4))
        self.api_var = tk.BooleanVar(value=api.enabled)
        ttk.Checkbutton(form, text="API REST habilitada (loopback)", variable=self.api_var).grid(row=22, column=0, columnspan=2, sticky="w", pady=3)
        self.api_port_var = tk.StringVar(value=str(api.port))
        ttk.Label(form, text="Puerto API:").grid(row=23, column=0, sticky="w")
        ttk.Entry(form, textvariable=self.api_port_var, width=8).grid(row=23, column=1, sticky="w", padx=6)
        self.api_scope_var = tk.StringVar(value="write")
        ttk.Label(form, text="Scope del token:").grid(row=24, column=0, sticky="w")
        ttk.Combobox(form, textvariable=self.api_scope_var, values=["read", "write", "admin"], state="readonly", width=8).grid(row=24, column=1, sticky="w", padx=6)
        ttk.Button(form, text="Generar token API", bootstyle="info", command=self._gen_api_token).grid(row=25, column=1, sticky="w", padx=6, pady=3)
        ttk.Label(form, text="El token se genera (no se escribe) y se guarda con hash; se muestra UNA sola vez.", style="Muted.TLabel").grid(row=26, column=0, columnspan=3, sticky="w")

        ttk.Button(form, text="Guardar ajustes", bootstyle="info", command=self._save).grid(row=27, column=0, sticky="w", pady=10)

    def _gen_api_token(self) -> None:
        """Crea un token para la API REST (equivale a 'api tokens create')."""
        import hashlib
        import secrets as _sec

        token = _sec.token_urlsafe(32)
        scope = self.api_scope_var.get()
        try:
            self.ctx.metrics.add_token(
                hashlib.sha256(token.encode()).hexdigest(), scope, None,
                "generado desde Ajustes",
            )
        except Exception as e:  # noqa: BLE001
            messagebox.showerror("WSL Manager", f"No se pudo guardar el token: {e}")
            return
        self.ctx.metrics.log_event("api_token_created", message=f"token API creado (scope {scope})")
        messagebox.showinfo(
            "WSL Manager",
            "Token API generado (scope %s).\n\n%s\n\nGuardalo: NO se volvera a mostrar.\n"
            "Uso: Authorization: Bearer %s" % (scope, token, token),
        )

    def _save(self) -> None:
        cfg = self.ctx.store.get()
        cfg.ui.theme = self.theme_var.get()
        cfg.ui.start_minimized = self.min_var.get()
        cfg.ui.close_to_tray = self.tray_var.get()
        cfg.on_close.stop_distros = self.stop_var.get()

        try:
            web_port = int(self.web_port_var.get() or 8790)
            api_port = int(self.api_port_var.get() or 8791)
            mcp_port = int(self.mcp_port_var.get() or 8792)
        except ValueError:
            messagebox.showerror("WSL Manager", "Puertos invalidos")
            return

        # Panel web: la clave es OBLIGATORIA para habilitarlo.
        web_on = self.web_var.get()
        web_pw = self.web_pw_var.get()
        if web_on and not web_pw:
            messagebox.showerror(
                "WSL Manager",
                "El panel web debe tener una clave (es obligatoria).\n"
                "Escribela en 'Clave (obligatoria)' o desactiva el panel.",
            )
            return
        cfg.ui.web_panel_enabled = web_on
        cfg.ui.web_panel_port = web_port
        cfg.ui.web_panel_bind = self.web_bind_var.get().strip() or "127.0.0.1"
        if web_pw:
            # La clave se guarda SOLO en el SecretsStore (DPAPI), no en claro
            # en config.json. Si llego hasta aqui sin web_pw, se conserva la existente.
            from src.utils import secrets as sec

            sec.SecretsStore().set("web_panel_password", web_pw)
            cfg.ui.web_panel_password = ""

        # MCP: token obligatorio si se exige; si falta, generar uno.
        mcp_on = self.mcp_var.get()
        mcp_token = self.mcp_key_var.get()
        if mcp_on and self.mcp_token_var.get() and not mcp_token:
            import secrets

            mcp_token = secrets.token_urlsafe(24)
        cfg.mcp.enabled = mcp_on
        cfg.mcp.transport = self.mcp_transport_var.get()
        cfg.mcp.port = mcp_port
        cfg.mcp.token_required = self.mcp_token_var.get()
        if mcp_token:
            cfg.mcp.token = mcp_token

        cfg.api.enabled = self.api_var.get()
        cfg.api.port = api_port

        # Autoarranque con Windows (HKCU Run): en segundo plano via VBS.
        _set_autostart(self.auto_var.get())

        self.ctx.store.save(cfg)
        self.ctx.metrics.log_event("gui_settings", message="ajustes guardados")
        msg = "Ajustes guardados.\nEl tema se aplica al reiniciar."
        if mcp_on and self.mcp_token_var.get() and not self.mcp_key_var.get():
            msg += f"\n\nToken MCP generado: {mcp_token}"
        if self.auto_var.get():
            msg += "\n\nAutoarranque con Windows: ACTIVADO (inicia en segundo plano)."
        messagebox.showinfo("WSL Manager", msg)
