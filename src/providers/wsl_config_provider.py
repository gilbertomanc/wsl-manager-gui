"""WslConfigProvider: escritura segura de .wslconfig y wsl.conf.

Reglas del plan: backup previo a cada escritura, validacion INI antes de
guardar, rollback si falla (R2/R7).
"""
from __future__ import annotations

import configparser
import os
import time
from pathlib import Path
from typing import Optional

from src.core.config import backups_dir
from src.providers.base import CommandResult


class WslConfigProvider:
    def __init__(self, userprofile: str | None = None) -> None:
        self.userprofile = userprofile or os.environ.get("USERPROFILE") or str(Path.home())
        self.wslconfig_path = Path(self.userprofile) / ".wslconfig"

    # -- lectura -------------------------------------------------------------

    def read_wslconfig(self) -> dict[str, dict[str, str]]:
        """Devuelve el .wslconfig como dict seccion -> {clave: valor}."""
        if not self.wslconfig_path.exists():
            return {}
        parser = configparser.ConfigParser()
        parser.read(self.wslconfig_path, encoding="utf-8")
        return {s: dict(parser.items(s)) for s in parser.sections()}

    def read_wsl_conf(self, distro: str) -> Optional[str]:
        """wsl.conf de una distro via wsl.exe (puede no existir)."""
        from src.utils.subprocess_async import run

        r = run(["wsl.exe", "-d", distro, "--", "cat", "/etc/wsl.conf"], timeout=30)
        return r.output if r.ok else None

    # -- escritura segura -------------------------------------------------------

    def _backup(self) -> Path:
        stamp = time.strftime("%Y%m%d-%H%M%S")
        dest = backups_dir() / f"wslconfig-{stamp}.bak"
        if self.wslconfig_path.exists():
            dest.write_bytes(self.wslconfig_path.read_bytes())
        return dest

    @staticmethod
    def _validate_ini(text: str) -> bool:
        """True si el texto es un INI parseable con configparser."""
        try:
            parser = configparser.ConfigParser()
            parser.read_string(text)
            return True
        except configparser.Error:
            return False

    def write_wslconfig(self, sections: dict[str, dict[str, str]]) -> CommandResult:
        """Escribe .wslconfig a partir de secciones {nombre: {clave: valor}}."""
        lines = ["# Generado por WSL Manager", "# Ediciones manuales se detectan en el watcher", ""]
        for section, kv in sections.items():
            lines.append(f"[{section}]")
            for k, v in kv.items():
                lines.append(f"{k}={v}")
            lines.append("")
        text = "\n".join(lines) + "\n"

        if not self._validate_ini(text):
            return CommandResult(ok=False, error="INI generado no parseable; no se escribe")

        backup = self._backup()
        try:
            self.wslconfig_path.write_text(text, encoding="utf-8")
        except OSError as e:
            return CommandResult(ok=False, error=f"no se pudo escribir: {e}")

        # Validacion post-escritura + rollback (R2)
        if not self._validate_ini(self.wslconfig_path.read_text(encoding="utf-8")):
            if backup.exists():
                backup.replace(self.wslconfig_path)
            return CommandResult(ok=False, error="escritura invalida; rollback aplicado")
        return CommandResult(ok=True, output=str(self.wslconfig_path))

    def backup_now(self) -> Path:
        return self._backup()
