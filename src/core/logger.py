"""Logging rotado para WSL Manager."""
from __future__ import annotations

import logging
import os
from logging.handlers import RotatingFileHandler
from pathlib import Path


def logs_dir() -> Path:
    base = Path(os.environ.get("LOCALAPPDATA", Path.home())) / "WSLManager" / "logs"
    base.mkdir(parents=True, exist_ok=True)
    return base


def setup_logging(level: str = "INFO", log_file: str | None = None) -> logging.Logger:
    level = getattr(logging, str(level).upper(), logging.INFO)
    root = logging.getLogger("wslmanager")
    root.setLevel(level)
    root.handlers.clear()

    fmt = logging.Formatter("%(asctime)s %(levelname)-7s %(name)s: %(message)s")

    console = logging.StreamHandler()
    console.setFormatter(fmt)
    root.addHandler(console)

    target = Path(log_file) if log_file else (logs_dir() / "wsl-manager.log")
    target.parent.mkdir(parents=True, exist_ok=True)
    file_handler = RotatingFileHandler(target, maxBytes=1_000_000, backupCount=5, encoding="utf-8")
    file_handler.setFormatter(fmt)
    root.addHandler(file_handler)
    return root


def get_logger(name: str) -> logging.Logger:
    return logging.getLogger(f"wslmanager.{name}")
