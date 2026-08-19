# Changelog

## v0.1.1 (2026-08-19) — clave del panel web con DPAPI

- La clave del panel web es **obligatoria** y se guarda cifrada con **DPAPI**
  (CurrentUser) en `%APPDATA%\WSLManager\secrets.json` (`SecretsStore`,
  autocontenido con ctypes, cero dependencias). Nunca queda en claro en
  `config.json`.
- `src/web/web_app.py`: `_web_panel_password()` resuelve la clave primero desde
  SecretsStore, con fallback a `cfg.ui.web_panel_password` (tests/legacy).
- `src/app.py`: `_web_key_configured()` valida la clave (secrets o legacy) antes
  de arrancar o sincronizar el panel web.
- Ajustes (GUI): al guardar, la clave se escribe en SecretsStore y se vacía el
  campo en claro de config.
- Fuera de Windows: fallback XOR solo para dev/test.

## v0.1.0 (2026-08-14) — primer release

### P0 (MVP)
- WslProvider: listar/estado/versión/IP/start/stop/restart/shutdown/export/import/set-default.
- Dashboard GUI con tabla de distros, filtro, ciclo de vida, terminal, explorador, exportar, snapshot, clonar.
- Watcher en segundo plano: estado + IPs + métricas + alertas de RAM y detención inesperada (SQLite).
- Límites globales vía `.wslconfig` con backup + validación INI + rollback (R2/R7).
- Autoarranque de distros con Windows (HKCU Run) con retraso configurable (W5).
- ConfigStore pydantic (schema completo del Anexo B), modo seguro ante config inválida.
- CLI operativo completo: paridad con la GUI (list/start/stop/ips/limits/status/doctor/diag...).

### P1
- Snapshots con retención y purga (W6), clonado (W7), grupos (W9), dependencias de arranque (W8).
- Scheduler (A2): distro_start/distro_stop/apply_profile/snapshot.
- Perfiles (A3): captura y aplicación con orden topológico.
- Monitor: métricas por distro (R3), umbrales configurables (M4), toasts (M5), historial SQLite (M3).
- Journal de acciones (U6), doctor (U8), bundle diag (U7), `supervise`/`watch` headless.
- API REST FastAPI con AuthService (tokens con scopes read/write/admin, rate limit, auditoría) (sección 21).
- Panel web local en 127.0.0.1:8790 (M7): dashboard con estado, métricas, alertas y acciones.
- Servidor MCP stdio (P1): 15 tools; requiere `pip install mcp`.

### Fixes de integración
- `sqlite3.row_factory` para acceso por nombre de columna.
- Formato de límites (`8GB`, no `8.0GB`).
- Comandos CLI con `typer.Context` (patrón soportado por typer moderno).
