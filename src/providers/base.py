"""Interfaces de providers + tipos compartidos (CommandResult, Distro, DistroMetrics)."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional


@dataclass
class CommandResult:
    ok: bool
    output: str = ""
    error: str = ""
    exit_code: int = 0

    @property
    def stdout_lines(self) -> list[str]:
        return [l for l in self.output.splitlines() if l.strip()]

    def to_dict(self) -> dict:
        return {"ok": self.ok, "output": self.output, "error": self.error, "exit_code": self.exit_code}


@dataclass
class Distro:
    name: str
    state: str = "Stopped"          # Running / Stopped / (estado crudo de wsl)
    version: int = 0                # 1 o 2
    default: bool = False
    ip: Optional[str] = None        # cache del watcher
    group: str = ""

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "state": self.state,
            "running": self.state.lower() == "running",
            "version": self.version,
            "default": self.default,
            "ip": self.ip,
            "group": self.group,
        }


@dataclass
class DistroMetrics:
    name: str
    running: bool
    ip: Optional[str] = None
    ram_total_mb: Optional[int] = None
    ram_used_mb: Optional[int] = None
    ram_percent: Optional[float] = None
    cpus: Optional[int] = None
    uptime_s: Optional[int] = None

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "running": self.running,
            "ip": self.ip,
            "ram_total_mb": self.ram_total_mb,
            "ram_used_mb": self.ram_used_mb,
            "ram_percent": self.ram_percent,
            "cpus": self.cpus,
            "uptime_s": self.uptime_s,
        }
