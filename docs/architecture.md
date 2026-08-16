# Arquitectura

## Capas

```
GUI (tray + ventana) ─┐
CLI (typer) ──────────┼──► Service/Provider Layer ──► Infra Layer ──► OS
API REST (FastAPI) ───┤       WslProvider                  ConfigStore (JSON)
MCP (stdio/HTTP) ─────┘       ResourceProvider             MetricsStore (SQLite)
Panel web ─────────────────── WslConfigProvider            Notifier (toasts)
                              AutoStartProvider            Scheduler / Watcher / PowerWatcher
```

## Patrones

- **Provider pattern**: cada backend detrás de una interfaz; `CommandResult` tipado para todo.
- **CLI first-class**: el CLI usa los mismos providers que la GUI (paridad garantizada).
- **Event bus**: `state-changed` / `power-resume` / `scheduler-run`; la UI y `watch` los consumen.
- **Single instance**: mutex `WSLManager-SingleInstance`.
- **El watcher nunca muere**: excepciones capturadas en el loop.

## Modelo de threads

- UI thread (tkinter) nunca ejecuta subprocesos directamente: los workers (watcher, scheduler, power) corren en threads daemon y reportan por el bus.
- SQLite con `check_same_thread=False` + lock interno.

## Manejo de errores

- Config inválida → `ConfigError` → modo seguro (la GUI solo muestra Logs/Ajustes; el CLI sale con código 3).
- Escritura de `.wslconfig`: backup previo, validación INI pre y post, rollback si falla.
- `wsl.exe` ausente → `doctor` lo detecta con guía.
