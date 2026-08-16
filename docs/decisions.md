# Decisiones (Fase 0 del plan)

| Decisión | Elección | Motivo |
|----------|----------|--------|
| Lenguaje | Python 3.11+ (probado en 3.14) | Rápido de iterar, empaquetable con PyInstaller |
| GUI | ttkbootstrap (theme darkly) + pystray | Tema moderno con dark mode; tray nativo de Windows |
| Config | JSON + pydantic v2 | Validación en carga, schema tipado (Anexo B) |
| Métricas | sqlite3 (stdlib) | Cero dependencias, retención configurable |
| Toasts | winotify | Notificaciones nativas de Windows |
| CLI | typer | Paridad GUI/CLI con los mismos providers |
| API REST | FastAPI + uvicorn (loopback) | AuthService con tokens/scopes/rate limit |
| Panel web | FastAPI en 127.0.0.1:8790 | M7: dashboard consultable desde el móvil |
| MCP | mcp SDK (stdio), import lazy | Tools mapeadas al catálogo; opcional `pip install mcp` |
| Límites por distro | systemd drop-ins (experimental) | Scope all/user/service según el plan 9.3 |
| Autoarranque de distros | HKCU Run → app con `--autostart-distro --delay` | Retraso evita competencia con el login |
| Single instance | Mutex global (ctypes CreateMutexW) | Evita dobles watchers |

## Scope P0 entregado

Dashboard, ciclo de vida, IPs, export/import, autoarranque, límites globales, watcher, CLI completo, config segura con backup. P1 mayor entregado (snapshots, scheduler, perfiles, monitor, API, panel web, MCP).
