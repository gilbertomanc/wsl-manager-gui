# Schema config.json

Ubicación: `%APPDATA%\WSLManager\config.json` (ver `config/config.example.json`).

```jsonc
{
  "version": 1,
  "windows": { "wsl_exe": "wsl.exe" },

  "distros": {
    "defaults": { "auto_start": false, "delay_s": 0 },
    "instances": [{
      "name": "ubuntu-dev",
      "group": "dev",
      "auto_start": false,
      "delay_s": 5,
      "depends_on": [{ "distro": "ubuntu-db", "wait_port": 5432, "timeout_s": 60 }],
      "quick_actions": [{ "name": "build", "cmd": "make" }]
    }]
  },

  "resources": {
    "global": { "memory_gb": 8, "processors": 4, "swap_gb": 2,
                "auto_memory_reclaim": "gradual", "sparse_vhd": true },
    "per_distro": [{ "distro": "ubuntu-dev", "memory_max": "4G", "cpu_quota": "200%",
                     "tasks_max": 512, "enabled": true, "scope": "all", "service": null }]
  },

  "alerts": { "memory_percent": 85, "distro_stopped_unexpected": true, "check_interval_seconds": 15 },

  "snapshots": { "enabled": true, "retention_days": 14, "target_dir": null },

  "scheduler": { "tasks": [{
      "id": "tarea-abc", "name": "Iniciar dev",
      "action": { "type": "distro_start", "distro": "ubuntu-dev", "profile": null },
      "schedule": { "days": ["mon","tue","wed","thu","fri"], "time": "09:00" },
      "enabled": true }] },

  "profiles": { "active": "dev", "items": [{ "name": "dev", "description": "",
                  "distros_to_start": ["ubuntu-dev"] }] },

  "ui": { "start_minimized": false, "close_to_tray": true, "theme": "darkly",
          "language": "es", "log_level": "INFO", "logs_dir": null,
          "refresh_interval_seconds": 2, "metrics_retention_days": 30,
          "web_panel_enabled": false },

  "api": { "enabled": false, "host": "127.0.0.1", "port": 8791,
           "auth": { "mode": "none", "rate_limit_per_minute": 120 },
           "allowed_ips": ["127.0.0.1"] },

  "mcp": { "enabled": false, "transport": "stdio", "port": 8792, "token_required": false },

  "on_close": { "stop_distros": false }
}
```

## Notas

- `resources.global` se escribe en `~/.wslconfig` (`[wsl2]`): `memory`, `processors`, `swap`, `autoMemoryReclaim`, `sparseVhd`. Requiere `wsl --shutdown`.
- `resources.per_distro` es **experimental**: drop-ins de systemd escritos como root en la distro (`/etc/systemd/system.conf.d/99-wsl-manager.conf`, scope `user` → `user.conf.d`, scope `service` → override del servicio).
- `alerts.check_interval_seconds` también controla el intervalo del watcher (mínimo 2s).
- El panel web usa el puerto fijo 8790 (loopback).
