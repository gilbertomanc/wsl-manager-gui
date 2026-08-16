---
name: wsl-manager-cli
description: "Operar WSL Manager desde la terminal: ciclo de vida de distros WSL, IPs, limites de recursos, snapshots, programador, perfiles, monitor y diagnostico. Para gestionar distros WSL sin abrir la GUI."
---

# WSL Manager CLI — Guia para agentes LLM

## 1. Contexto y cuando usar

WSL Manager es una app de escritorio (system tray) para gestionar distros WSL en Windows. Su CLI (`wsl-manager`, o `python -m src.cli` desde el repo) tiene la **misma capacidad que la GUI** (paridad garantizada: ambos usan los mismos providers). Usa esta skill siempre que debas:

- Saber que distros existen, su estado, version o IP.
- Iniciar/detener/reiniciar distros (incluido arranque en cascada con dependencias).
- Limitar RAM/CPU/swap (global) o por distro (experimental).
- Crear snapshots, clonar, exportar/importar.
- Programar tareas o aplicar perfiles.
- Diagnosticar problemas (doctor, diag).

## 2. Requisitos previos

- Windows 10/11 con WSL 2 instalado (`wsl --version` responde).
- La app instalada y el binario `wsl-manager` en PATH (o `python -m src.cli` desde el repo).
- Para limites por distro: `systemd=true` en `wsl.conf` de la distro.

## 3. Convenciones

| Regla | Detalle |
|-------|---------|
| Salida | Humana por defecto; `--json` para parsear |
| Exit codes | `0` OK, `1` error funcional, `2` argumentos invalidos, `3` config invalida |
| Seguridad | No volcar contenido completo de config; resumir rutas sensibles |

## 4. Comandos

### Estado y consulta

```bash
wsl-manager list [--json] [--filter <texto>]
wsl-manager status [--json]
wsl-manager ips [--distro X] [--json]
wsl-manager monitor once [--json]
wsl-manager monitor metrics [--distro X] [--json] [--watch]
wsl-manager monitor events [--limit N] [--json]
wsl-manager monitor history [--distro X] [--limit N]
```

> Los mismos comandos de distros existen en el grupo `distros` (p.ej. `wsl-manager distros list`), con extras `vhd` y `rename`.

### Ciclo de vida

```bash
wsl-manager start <distro>
wsl-manager start --all | start --cascade   # todas / respetando dependencias
wsl-manager stop <distro>
wsl-manager restart <distro>
wsl-manager stop-all
wsl-manager group start|stop|list [grupo]
wsl-manager deps                             # dependencias de arranque
wsl-manager run <distro> <cmd>               # ejecuta un comando dentro de la distro
wsl-manager shell <distro>
wsl-manager explorer <distro>
```

### Backup / clonado

```bash
wsl-manager export <distro> <ruta.tar>
wsl-manager import <ruta.tar> <nombre> [--install-dir DIR]
wsl-manager snapshot <distro> [--retention N]
wsl-manager snapshots-list [--json]
wsl-manager snapshots-prune
wsl-manager clone <distro> <nuevo-nombre>
wsl-manager set-default <distro>
```

### Recursos

```bash
wsl-manager limits global [set|get] [--get] [--memory 8GB --processors 4 --swap 4GB] [--reclaim gradual|dropcache|disabled] [--sparse/--no-sparse]
wsl-manager limits distro set|get|clear <distro> [--memory-max 4G] [--cpu-quota 200%] [--tasks-max 512] [--scope all|user|service]
wsl-manager limits service set|clear <distro> --service myservice [--memory-max 2G] [--cpu-quota 100%]
```

> [!WARNING] Limites por distro
> Experimental (systemd/cgroups). `memory` global de `.wslconfig` es el techo real de la VM. Prefiere `--scope user` salvo que se pida otra cosa; `--scope all` es avanzado y requiere confirmacion.

### Autoarranque

```bash
wsl-manager autostart set <distro> [--delay N]
wsl-manager autostart unset <distro>
wsl-manager autostart list [--json]
```

### Monitor y umbrales

```bash
wsl-manager monitor thresholds [--get] [--memory-percent 85] [--check-interval N] [--json]
wsl-manager monitor alerts [--json]
```

### Programacion y perfiles

```bash
wsl-manager schedule list [--json]
wsl-manager schedule add --name X --type distro_start|distro_stop|apply_profile|snapshot --distro Y --time 09:00 --days mon,tue,wed,thu,fri
wsl-manager schedule remove <id>
wsl-manager schedule enable <id> [--enabled/--disabled]
wsl-manager schedule profile list|capture|apply        # subgrupo de perfiles
wsl-manager profile-list [--json]                      # tambien en root
wsl-manager profile-capture <nombre> [--desc "..."]
wsl-manager profile-apply <nombre>
```

### Configuracion y diagnostico

```bash
wsl-manager config validate [--path R]
wsl-manager config show [--json]
wsl-manager config export <ruta>
wsl-manager config import <ruta>
wsl-manager doctor [--json]
wsl-manager diag [--out ruta.zip]
wsl-manager version
```

### Modos operativos

```bash
wsl-manager supervise              # watcher headless (Ctrl+C para salir)
wsl-manager watch [--json]         # eventos en vivo estilo tail
wsl-manager gui show|hide|quit     # control de la GUI via IPC (stub)
```

### API, MCP y panel web

```bash
wsl-manager api enable [--port 8791] | disable | status [--json]
wsl-manager api tokens create --scope read|write|admin [--expires N] [--note "..."] | list | revoke --id N
wsl-manager mcp serve | test               # servidor MCP stdio (requiere pip install mcp)
wsl-manager web serve [--port 8790] [--host 127.0.0.1] | enable | disable
wsl-manager ux run-server [--port N]       # API en foreground
wsl-manager ux test-notify                 # toast de prueba
```

- API REST en `http://127.0.0.1:8791/api/v1/*`; `Authorization: Bearer <token>` (o `X-API-Key`).
- Scopes: read < write < admin; el token se muestra **una sola vez** al crearlo.
- Panel web en `http://127.0.0.1:8790` (estado read-only; `enable` lo arranca con la app, `serve` en foreground).

## 5. Flujo recomendado

1. `wsl-manager doctor` → confirmar entorno sano (si falla, resolver antes de seguir).
2. `wsl-manager status --json` → estado actual.
3. Ejecutar la accion pedida.
4. Verificar: `wsl-manager list --json` o el comando de consulta correspondiente.
5. Si algo falla: ejecutar de nuevo y reportar el exit code + salida relevante.

## 6. Reglas para agentes

- **Nunca** ejecutar acciones destructivas (`stop-all`, import sobre nombre existente, `limits distro clear`, `snapshots-prune`) sin confirmacion explicita del usuario.
- Usar `--json` y validar el exit code antes de interpretar la salida.
- Si `wsl-manager doctor` reporta problemas, corregirlos antes de operar.
- Respetar la advertencia de experimental en `limits distro`.
- No editar `.wslconfig` a mano: usar `limits global` (la app hace backup y valida).
- Salida final al usuario: resumen breve con estado antes/despues, sin volcar logs completos.

## 7. Troubleshooting

| Sintoma | Causa probable | Accion |
|---------|----------------|--------|
| exit 3 | config.json invalida | `config validate`, revisar schema, `config export` para inspeccion |
| IP vacia para una distro | distro detenida | `start <distro>` primero, luego `ips --distro X` |
| `limits distro` falla | systemd no habilitado | verificar `systemd=true` en wsl.conf y `wsl --shutdown` |
| binario no encontrado | no esta en PATH | usar `python -m src.cli` desde el repo o reinstalar |
| `watch` no muestra nada | la app no esta corriendo | usar `supervise` o abrir la GUI |
