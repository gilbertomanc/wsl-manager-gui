# Troubleshooting

## `wsl -l -v` falla o no aparecen distros

- Verifica WSL: `wsl --version` (necesita WSL 2.x).
- `wsl-manager doctor` te dice qué falla (wsl.exe, distros, config, DB, permisos).
- Si no hay distros instaladas: `wsl --install -d Ubuntu`.

## Los límites no surten efecto

- Los cambios en `.wslconfig` solo aplican tras `wsl --shutdown` (botón "Apagar todas" del Dashboard).
- Comprueba el backup previo en `%APPDATA%\WSLManager\backups\` si algo se rompió.

## Límites por distro (experimental) no aplican

- Requiere systemd en la distro (`wsl.conf` con `systemd=true`) y acceso root sin contraseña (`wsl -u root`).
- Revisa los drop-ins: `/etc/systemd/system.conf.d/99-wsl-manager.conf`.

## La GUI no abre / no hay tray

- Windows siempre tiene escritorio; si falla, mira el log en `%LOCALAPPDATA%\WSLManager\logs\wsl-manager.log`.
- `python src/app.py --validate-config` para descartar config inválida.
- La app sigue funcionando headless con `wsl-manager supervise`.

## API REST

- `wsl-manager api status` para ver configuración; `api enable` + reiniciar la app.
- Modo token: `wsl-manager api tokens create --scope write` y usa `Authorization: Bearer <token>`.
- Puertos por defecto: panel web 8790, API 8791, MCP 8792 (loopback).

## VHD resize (W12, P2)

Requiere PowerShell elevado:

```powershell
wsl --shutdown
diskpart
# select vdisk file="<ruta ext4.vhdx>"
# expand vdisk maximum=128000   (o compact vdisk)
```

Localiza el VHD con `wsl --shutdown` + `Get-ChildItem "$env:LOCALAPPDATA\Packages" -Recurse -Filter ext4.vhdx` (o `%USERPROFILE%\AppData\Local\Docker\wsl\data\ext4.vhdx` para Docker Desktop).

## Renombrar distro (W13, P2)

`wsl-manager rename <distro> <nuevo>` clona con el nombre nuevo; después borra la original:

```bash
wsl --unregister <distro-old>
```

## Diagnóstico completo

```bash
wsl-manager diag            # crea wsl-manager-diag-<ts>.zip con logs + config + estado
```
