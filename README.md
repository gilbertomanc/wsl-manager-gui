# WSL Manager (GUI)

Gestión de distros WSL2 con una sola aplicación: **GUI en system tray**, **CLI operativo**, **API REST segura**, **servidor MCP** para agentes LLM y **panel web local**. GUI, CLI, API y MCP comparten los mismos providers: lo que se puede hacer en una interfaz se puede hacer en todas.

Implementación del plan [PLAN-WSL.md](../PLAN-WSL.md) (v2.3).

## Instalación

```bash
python -m venv .venv
.venv\Scripts\pip install -e .
```

Requiere Python 3.11+, WSL 2.x con al menos una distro.

## Interfaz rápida

| Interfaz | Cómo se lanza |
|----------|---------------|
| GUI (tray + ventana) | `python src\app.py` (flags: `--minimized`, `--tray-only`, `--validate-config`) |
| CLI | `python -m src.cli` o `wsl-manager` (tras `pip install -e .`) |
| Panel web (M7) | `wsl-manager web serve` → http://127.0.0.1:8790 |
| API REST (P1) | `wsl-manager ux run-server` → http://127.0.0.1:8791 |
| Servidor MCP (P1) | `wsl-manager mcp serve` (requiere `pip install mcp`) |
| Watcher headless | `wsl-manager supervise` |

## Uso diario (CLI)

```bash
wsl-manager list --json            # estado de distros (W1)
wsl-manager start ubuntu-dev       # ciclo de vida (W2)
wsl-manager ips                    # IPs (W3)
wsl-manager snapshot ubuntu-dev    # snapshot con retención (W6)
wsl-manager limits global set --memory 8GB --processors 4   # R1
wsl-manager autostart set ubuntu-dev --delay 5              # W5
wsl-manager schedule add --name "Iniciar dev" --type distro_start --distro ubuntu-dev --time 09:00
wsl-manager profile capture dev    # A3
wsl-manager status --json
wsl-manager doctor                 # U8
```

Exit codes: `0` OK · `1` error funcional · `2` argumentos · `3` config inválida.

## Archivos

| Dato | Ubicación |
|------|-----------|
| config.json | `%APPDATA%\WSLManager\` |
| metrics.db (SQLite) | `%APPDATA%\WSLManager\` |
| snapshots/ | `%APPDATA%\WSLManager\snapshots\` |
| backups/ (.wslconfig) | `%APPDATA%\WSLManager\backups\` |
| logs/ | `%LOCALAPPDATA%\WSLManager\logs\` |

## Tests

```bash
.venv\Scripts\python -m pytest tests -q
```

Los tests unitarios usan mocks (no tocan WSL). Los smoke tests reales están en `scripts\smoke_check.py`.

## Seguridad

- Escritura de `.wslconfig` con backup previo, validación INI y rollback.
- API solo loopback por defecto; modo token con scopes `read`/`write`/`admin`:
  `wsl-manager api tokens create --scope write`.
- Tokens guardados con hash SHA-256 en SQLite.

## Estado del plan

- **P0 completo**: dashboard, ciclo de vida, IPs, export/import, autoarranque, límites globales, watcher, CLI.
- **P1 mayor**: snapshots, clonar, grupos, dependencias, scheduler, perfiles, monitor/alertas, journal, doctor/diag, API REST + tokens, panel web, MCP (si `mcp` instalado).
- **P2 parcial**: vhd resize (stub con guía), rename (vía clonado).

Ver `CHANGELOG.md` y `docs/`.
