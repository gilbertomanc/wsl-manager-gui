"""Contexto compartido del CLI: construye los mismos providers que la GUI."""
from __future__ import annotations

import json
import sys

from src.core.config import ConfigError, ConfigStore
from src.core.event_bus import EventBus
from src.core.metrics_store import MetricsStore
from src.core.notifier import notify
from src.providers.autostart_provider import AutoStartProvider
from src.providers.resource_provider import ResourceProvider
from src.providers.wsl_config_provider import WslConfigProvider
from src.providers.wsl_provider import WslProvider

EXIT_OK = 0
EXIT_ERROR = 1
EXIT_ARGS = 2
EXIT_CONFIG = 3


class CliContext:
    def __init__(self, config_path: str | None = None) -> None:
        try:
            self.store = ConfigStore(config_path)
            self.config = self.store.load(create_if_missing=True)
        except ConfigError as e:
            print(f"ERROR DE CONFIG: {e}", file=sys.stderr)
            print("La app arranca en modo seguro (solo Logs/Ajustes). Corrige o borra el archivo.", file=sys.stderr)
            sys.exit(EXIT_CONFIG)
        self.bus = EventBus()
        self.metrics = MetricsStore()
        self.wsl = WslProvider(self.store, self.config.windows.wsl_exe)
        self.resources = ResourceProvider(self.store, self.wsl)
        self.autostart = AutoStartProvider()
        self.wsl_config = WslConfigProvider()

    def emit_json(self, data: object) -> None:
        print(json.dumps(data, indent=2, ensure_ascii=False, default=str))


def new_context(config_path: str | None = None) -> CliContext:
    return CliContext(config_path)
