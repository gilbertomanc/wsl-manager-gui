"""AutoStartProvider: autoarranque de distros con Windows (W5).

Mecanica: entrada en HKCU\\Software\\Microsoft\\Windows\\CurrentVersion\\Run
que lanza la app con --autostart-distro <name> --delay <N>; la app espera
el delay y arranca la distro (evita que la VM compita con el login).
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path
from typing import Optional

from src.providers.base import CommandResult

_RUN_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"
_PREFIX = "WSLManager-"

try:
    import winreg
except ImportError:  # pragma: no cover - solo Windows
    winreg = None


def _app_launch_command(distro: str, delay_s: int) -> str:
    """Comando que se guarda en Run. Apunta al ejecutable actual + flags."""
    exe = Path(sys.executable)
    if exe.name.lower() in ("pythonw.exe", "python.exe"):
        app = Path(__file__).resolve().parents[1] / "app.py"  # src/app.py
        cmd = f'"{exe}" "{app}" --autostart-distro {distro} --delay {delay_s} --minimized'
    else:
        cmd = f'"{exe}" --autostart-distro {distro} --delay {delay_s} --minimized'
    return cmd


class AutoStartProvider:
    def set_autostart(self, distro: str, enabled: bool, delay_s: int = 0) -> CommandResult:
        if winreg is None:
            return CommandResult(ok=False, error="winreg no disponible (solo Windows)")
        try:
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, _RUN_KEY, 0, winreg.KEY_SET_VALUE) as key:
                name = f"{_PREFIX}{distro}"
                if enabled:
                    winreg.SetValueEx(key, name, 0, winreg.REG_SZ, _app_launch_command(distro, delay_s))
                else:
                    try:
                        winreg.DeleteValue(key, name)
                    except FileNotFoundError:
                        pass
            return CommandResult(ok=True, output=f"autostart {'activado' if enabled else 'desactivado'} para {distro}")
        except OSError as e:
            return CommandResult(ok=False, error=str(e))

    def list_autostart(self) -> dict[str, dict]:
        if winreg is None:
            return {}
        out: dict[str, dict] = {}
        try:
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, _RUN_KEY, 0, winreg.KEY_READ) as key:
                i = 0
                while True:
                    try:
                        name, value, _ = winreg.EnumValue(key, i)
                        i += 1
                    except OSError:
                        break
                    if name.startswith(_PREFIX):
                        distro = name[len(_PREFIX):]
                        out[distro] = {"command": value, "delay_s": 0}
            return out
        except OSError:
            return {}

    def clear_all(self) -> CommandResult:
        for distro in self.list_autostart():
            self.set_autostart(distro, False)
        return CommandResult(ok=True, output="autostart limpiado")
