"""Ejecucion de subprocesos con timeout y captura limpia de stdout/stderr."""
from __future__ import annotations

import subprocess
import sys

from src.providers.base import CommandResult

_CREATE_NO_WINDOW = 0x08000000 if sys.platform == "win32" else 0


def run(args: list[str], timeout: float = 120.0, cwd: str | None = None) -> CommandResult:
    """Ejecuta un comando y devuelve CommandResult. Nunca lanza excepcion."""
    try:
        proc = subprocess.run(
            args,
            capture_output=True,
            timeout=timeout,
            cwd=cwd,
            creationflags=_CREATE_NO_WINDOW,
        )
        stdout = _decode(proc.stdout)
        stderr = _decode(proc.stderr)
        ok = proc.returncode == 0
        if not ok and not stderr and stdout:
            # wsl.exe escribe los errores en stdout (UTF-16) con rc != 0
            stderr, stdout = stdout, ""
        return CommandResult(
            ok=ok,
            output=stdout,
            error=stderr,
            exit_code=proc.returncode,
        )
    except FileNotFoundError as e:
        return CommandResult(ok=False, error=f"ejecutable no encontrado: {e}")
    except subprocess.TimeoutExpired as e:
        return CommandResult(ok=False, error=f"timeout tras {timeout}s", exit_code=-1)
    except OSError as e:
        return CommandResult(ok=False, error=str(e), exit_code=-1)


def _decode(data: bytes) -> str:
    """wsl.exe a veces escribe UTF-16-LE; intenta utf-8 primero y cae a utf-16."""
    if not data:
        return ""
    for enc in ("utf-8", "utf-16-le"):
        try:
            return data.decode(enc)
        except (UnicodeDecodeError, UnicodeError):
            continue
    return data.decode("utf-8", errors="replace")


def spawn_detached(args: list[str]) -> CommandResult:
    """Lanza un proceso sin esperarlo (terminal/explorer). En Windows abre consola nueva."""
    try:
        creationflags = 0
        if sys.platform == "win32":
            creationflags = _CREATE_NO_WINDOW | getattr(
                subprocess, "DETACHED_PROCESS", 0
            )
        subprocess.Popen(args, creationflags=creationflags, close_fds=True)
        return CommandResult(ok=True)
    except OSError as e:
        return CommandResult(ok=False, error=str(e))
