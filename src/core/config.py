"""ConfigStore: validacion pydantic + persistencia JSON.

Schema completo segun Anexo B del plan. Ante config invalida se lanza
ConfigError; el arranque de la app entra en "modo seguro" (solo Logs/Ajustes).
"""
from __future__ import annotations

import json
import os
import threading
from pathlib import Path
from typing import Literal, Optional

from pydantic import BaseModel, Field, ValidationError

APP_NAME = "WSLManager"


class ConfigError(Exception):
    """Config inexistente, invalida o ilegible."""


def appdata_dir() -> Path:
    d = Path(os.environ.get("APPDATA", str(Path.home()))) / APP_NAME
    d.mkdir(parents=True, exist_ok=True)
    return d


def localappdata_dir() -> Path:
    d = Path(os.environ.get("LOCALAPPDATA", str(Path.home()))) / APP_NAME
    d.mkdir(parents=True, exist_ok=True)
    return d


def default_config_path() -> Path:
    return appdata_dir() / "config.json"


# --------------------------------------------------------------------------
# Modelos
# --------------------------------------------------------------------------

class WindowsCfg(BaseModel):
    wsl_exe: str = "wsl.exe"


class DependsOn(BaseModel):
    distro: str
    wait_port: Optional[int] = None
    timeout_s: int = 60


class QuickAction(BaseModel):
    name: str
    cmd: str


class DistroInstance(BaseModel):
    name: str
    group: str = ""
    auto_start: bool = False
    delay_s: int = 0
    depends_on: list[DependsOn] = Field(default_factory=list)
    quick_actions: list[QuickAction] = Field(default_factory=list)


class DistrosDefaults(BaseModel):
    auto_start: bool = False
    delay_s: int = 0


class DistrosCfg(BaseModel):
    defaults: DistrosDefaults = Field(default_factory=DistrosDefaults)
    instances: list[DistroInstance] = Field(default_factory=list)


class GlobalLimits(BaseModel):
    memory_gb: Optional[float] = None
    processors: Optional[int] = None
    swap_gb: Optional[float] = None
    auto_memory_reclaim: Optional[Literal["gradual", "dropcache", "disabled"]] = None
    sparse_vhd: Optional[bool] = None


class PerDistroLimits(BaseModel):
    distro: str
    memory_max: Optional[str] = None  # "4G"
    cpu_quota: Optional[str] = None   # "200%"
    tasks_max: Optional[int] = None
    enabled: bool = True
    scope: Literal["all", "user", "service"] = "all"
    service: Optional[str] = None


class ResourcesCfg(BaseModel):
    global_limits: GlobalLimits = Field(default_factory=GlobalLimits, alias="global")
    per_distro: list[PerDistroLimits] = Field(default_factory=list)

    model_config = {"populate_by_name": True}


class AlertsCfg(BaseModel):
    memory_percent: int = 85
    distro_stopped_unexpected: bool = True
    check_interval_seconds: int = 15


class SnapshotsCfg(BaseModel):
    enabled: bool = True
    retention_days: int = 14
    target_dir: Optional[str] = None


class ScheduleAction(BaseModel):
    type: Literal["distro_start", "distro_stop", "apply_profile", "snapshot"]
    distro: Optional[str] = None
    profile: Optional[str] = None


class ScheduleSpec(BaseModel):
    days: list[str] = Field(default_factory=lambda: ["mon", "tue", "wed", "thu", "fri"])
    time: str = "09:00"


class ScheduleTask(BaseModel):
    id: str
    name: str
    action: ScheduleAction
    schedule: ScheduleSpec
    enabled: bool = True


class SchedulerCfg(BaseModel):
    tasks: list[ScheduleTask] = Field(default_factory=list)


class ProfileItem(BaseModel):
    name: str
    description: str = ""
    distros_to_start: list[str] = Field(default_factory=list)


class ProfilesCfg(BaseModel):
    active: Optional[str] = None
    items: list[ProfileItem] = Field(default_factory=list)


class UiCfg(BaseModel):
    start_minimized: bool = False
    close_to_tray: bool = True
    theme: str = "darkly"
    language: str = "es"
    log_level: str = "INFO"
    logs_dir: Optional[str] = None
    refresh_interval_seconds: int = 2
    metrics_retention_days: int = 30
    web_panel_enabled: bool = False
    web_panel_port: int = 8790
    web_panel_bind: str = "127.0.0.1"
    web_panel_password: str = ""


class AuthCfg(BaseModel):
    mode: Literal["none", "token"] = "none"
    rate_limit_per_minute: int = 120


class ApiCfg(BaseModel):
    enabled: bool = False
    host: str = "127.0.0.1"
    port: int = 8791
    auth: AuthCfg = Field(default_factory=AuthCfg)
    allowed_ips: list[str] = Field(default_factory=lambda: ["127.0.0.1"])


class McpCfg(BaseModel):
    enabled: bool = False
    transport: Literal["stdio", "http"] = "stdio"
    port: int = 8792
    token_required: bool = False
    token: str = ""


class OnCloseCfg(BaseModel):
    stop_distros: bool = False


class AppConfig(BaseModel):
    version: int = 1
    windows: WindowsCfg = Field(default_factory=WindowsCfg)
    distros: DistrosCfg = Field(default_factory=DistrosCfg)
    resources: ResourcesCfg = Field(default_factory=ResourcesCfg)
    alerts: AlertsCfg = Field(default_factory=AlertsCfg)
    snapshots: SnapshotsCfg = Field(default_factory=SnapshotsCfg)
    scheduler: SchedulerCfg = Field(default_factory=SchedulerCfg)
    profiles: ProfilesCfg = Field(default_factory=ProfilesCfg)
    ui: UiCfg = Field(default_factory=UiCfg)
    api: ApiCfg = Field(default_factory=ApiCfg)
    mcp: McpCfg = Field(default_factory=McpCfg)
    on_close: OnCloseCfg = Field(default_factory=OnCloseCfg)


def snapshot_dir() -> Path:
    p = appdata_dir() / "snapshots"
    p.mkdir(parents=True, exist_ok=True)
    return p


def backups_dir() -> Path:
    p = appdata_dir() / "backups"
    p.mkdir(parents=True, exist_ok=True)
    return p


# --------------------------------------------------------------------------
# Store
# --------------------------------------------------------------------------

class ConfigStore:
    """Carga/guarda la config en %APPDATA%/WSLManager/config.json (thread-safe)."""

    def __init__(self, path: str | Path | None = None) -> None:
        self.path = Path(path) if path else default_config_path()
        self._lock = threading.RLock()
        self._cfg: AppConfig | None = None

    def load(self, create_if_missing: bool = True) -> AppConfig:
        with self._lock:
            if self.path.exists():
                try:
                    data = json.loads(self.path.read_text(encoding="utf-8"))
                    self._cfg = AppConfig.model_validate(data)
                except (json.JSONDecodeError, ValidationError, OSError) as e:
                    raise ConfigError(f"config invalida en {self.path}: {e}") from e
            else:
                self._cfg = AppConfig()
                if create_if_missing:
                    self.save()
            return self._cfg

    def get(self) -> AppConfig:
        if self._cfg is None:
            return self.load()
        return self._cfg

    def save(self, cfg: AppConfig | None = None) -> None:
        with self._lock:
            if cfg is not None:
                self._cfg = cfg
            if self._cfg is None:
                raise ConfigError("nada que guardar")
            self.path.parent.mkdir(parents=True, exist_ok=True)
            data = self._cfg.model_dump(by_alias=True, exclude_none=True)
            tmp = self.path.with_suffix(".json.tmp")
            tmp.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
            tmp.replace(self.path)

    @staticmethod
    def validate_file(path: str | Path) -> AppConfig:
        """Valida un archivo JSON sin tocarlo; devuelve la config o lanza ConfigError."""
        p = Path(path)
        try:
            data = json.loads(p.read_text(encoding="utf-8"))
            return AppConfig.model_validate(data)
        except (json.JSONDecodeError, ValidationError, OSError) as e:
            raise ConfigError(f"config invalida en {p}: {e}") from e
