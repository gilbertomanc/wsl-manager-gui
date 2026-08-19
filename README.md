# WSL Manager (GUI)

[![Licencia](https://img.shields.io/badge/Licencia-MIT-blue.svg)](LICENSE)
[![Python](https://img.shields.io/badge/Python-3.11%2B-3776AB?logo=python&logoColor=white)](https://www.python.org/)
[![Plataforma](https://img.shields.io/badge/Plataforma-Windows%2010%2F11-0078D6?logo=windows&logoColor=white)](#requisitos)
[![Tests](https://img.shields.io/badge/Tests-59%2F59%20passed-2ea44f)](#tests)

> Gestión de distros WSL2 con una sola aplicación: **GUI en system tray**, **CLI operativo**, **API REST segura**, **servidor MCP** para agentes LLM y **panel web local**. GUI, CLI, API y MCP comparten los mismos providers: lo que se puede hacer en una interfaz se puede hacer en todas.

**Proyecto hermano:** [port-forwarder-app](https://github.com/gilbertomanc/port-forwarder-app) — redirección de puertos Windows → WSL y túneles SSH hacia VPS. Ambas apps son **independientes y coexisten** en la misma máquina (puertos propios).

---

## Índice

- [Requisitos](#requisitos)
- [Instalación](#instalación)
- [Interfaz rápida](#interfaz-rápida)
- [Uso diario (CLI)](#uso-diario-cli)
- [Panel web](#panel-web)
- [API REST](#api-rest)
- [MCP (agentes LLM)](#mcp-agentes-llm)
- [Archivos](#archivos)
- [Seguridad](#seguridad)
- [Tests](#tests)
- [Estructura del proyecto](#estructura-del-proyecto)
- [Contribuir](#contribuir)
- [Licencia](#licencia)

## Requisitos

- **Windows 10/11** con WSL 2.x instalado y al menos una distro (ej. `ubuntu`).
- **Python 3.11+** (probado en 3.14).
- Conocimientos básicos de línea de comandos.

## Instalación

```bash
git clone https://github.com/gilbertomanc/wsl-manager-gui
cd wsl-manager-gui
python -m venv .venv
.venv\Scripts\activate

# Base (GUI + CLI): 
pip install -e .

# Con panel web + API REST (recomendado):
pip install -e ".[api]"

# Para desarrollo y tests (añade pytest):
pip install -e ".[api,dev]"
```

> **¿No quieres tocar código?** Usa los ejecutables ya compilados de la carpeta
> `ejecutables\wsl-manager\wsl-manager.exe` (ver la guía de uso en la raíz del
> workspace o las secciones de este README).

## Interfaz rápida

| Interfaz | Cómo se lanza |
|----------|---------------|
| GUI (tray + ventana) | `python src\app.py` o doble clic en `wsl-manager.exe` |
| CLI | `wsl-manager` (tras `pip install -e .`) |
| Panel web (M7) | `wsl-manager web serve` → http://127.0.0.1:8790 |
| API REST (P1) | `wsl-manager ux run-server` → http://127.0.0.1:8791 |
| Servidor MCP (P1) | `wsl-manager mcp serve` (requiere `pip install mcp`) |
| Watcher headless | `wsl-manager supervise` |

Flags de la GUI: `--minimized` (inicia al system tray), `--tray-only` (solo tray),
`--validate-config` (valida la configuración y sale).

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

## Panel web

```bash
wsl-manager web serve              # dashboard en http://127.0.0.1:8790
```

El panel requiere una **clave obligatoria** (se configura en Ajustes de la GUI o
con los comandos de `secrets`). La clave se guarda **cifrada con DPAPI** en
`secrets.json` — nunca en claro.

## API REST

```bash
wsl-manager ux run-server          # API en http://127.0.0.1:8791
```

- Solo loopback por defecto; modo token con scopes `read`/`write`/`admin`.
- Tokens guardados con hash SHA-256 en SQLite.
- Rate limit y auditoría de cada llamada.

## MCP (agentes LLM)

```bash
pip install mcp                     # dependencia opcional
wsl-manager mcp serve               # servidor stdio (JSON-RPC)
```

## Archivos

| Dato | Ubicación |
|------|-----------|
| config.json | `%APPDATA%\WSLManager\` |
| secrets.json (claves cifradas DPAPI) | `%APPDATA%\WSLManager\` |
| metrics.db (SQLite) | `%APPDATA%\WSLManager\` |
| snapshots/ | `%APPDATA%\WSLManager\snapshots\` |
| backups/ (.wslconfig) | `%APPDATA%\WSLManager\backups\` |
| logs/ | `%LOCALAPPDATA%\WSLManager\logs\` |

## Seguridad

- Escritura de `.wslconfig` con backup previo, validación INI y rollback.
- API solo loopback por defecto; modo token con scopes `read`/`write`/`admin`.
- Tokens guardados con hash SHA-256 en SQLite.
- Clave del panel web **obligatoria** y cifrada con **DPAPI** (CurrentUser) en
  `secrets.json` — nunca queda en claro en `config.json`. Fuera de Windows se
  usa un fallback XOR solo para dev/test.
- Headers de seguridad (nosniff, `X-Frame-Options`, CSP) en el panel web.
- **Coexistencia:** port-forwarder-app usa puertos propios (8794 web, 8795 API,
  8796 MCP), así que ambas apps pueden correr a la vez en la misma máquina.

## Tests

```bash
pip install -e ".[api,dev]"     # asegura pytest + dependencias de la API
.venv\Scripts\python -m pytest tests -q
```

Los tests unitarios usan mocks (no tocan WSL). Los smoke tests reales están en
`scripts\smoke_check.py`.

## Estructura del proyecto

```
src/
├── app.py                 # Entry GUI (tray + ventana)
├── core/                  # config (pydantic), watcher, scheduler, métricas, perfiles
├── providers/             # wsl, recursos, snapshots (paridad GUI/CLI/API/MCP)
├── cli/                   # wsl-manager (typer)
├── api/                   # REST FastAPI + AuthService (tokens, scopes, rate limit)
├── web/                   # panel web FastAPI en 127.0.0.1:8790
├── mcp/                   # servidor MCP stdio (JSON-RPC)
├── gui/                   # ventana tkinter + tray
└── utils/                 # subprocess, secrets DPAPI, paths
scripts/                   # smoke_check.py, check_environment.ps1, wsl-manager.spec
```

## Contribuir

1. Haz un fork del repositorio.
2. Crea una rama: `git checkout -b feature/mi-mejora`.
3. Haz tus cambios y asegúrate de que pasan los tests (`pytest tests -q`).
4. Envía un pull request describiendo el cambio.

Reporta bugs o pide funciones en
[Issues](https://github.com/gilbertomanc/wsl-manager-gui/issues).

## Licencia

[MIT](LICENSE) © 2026 — gilbertomanc. Ver también el [CHANGELOG](CHANGELOG.md).