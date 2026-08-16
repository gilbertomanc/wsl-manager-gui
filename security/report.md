# Reporte de Seguridad — WSL Manager (v0.1.0)

- **Fecha:** 2026-08-14
- **Alcance:** `wsl-manager-gui/` (GUI tray + CLI + API REST FastAPI + panel web + MCP)
- **Metodología:** PTES — revisión de código (SAST), auditoría de dependencias, pruebas de AuthZ/endpoints con curl, búsqueda de secretos, hardening review
- **Entorno probado:** Windows 11, Python 3.14.6, WSL2 (docker-desktop/rancher-desktop), API y panel web en loopback (127.0.0.1:8791 / 8790)
- **Autorización:** pruebas autorizadas por el propietario del sistema (entorno local propio)

## Resumen ejecutivo

| Severidad | Hallazgos |
|-----------|-----------|
| Critical | 0 |
| High | 0 |
| Medium | 3 |
| Low | 4 |
| Info | 3 |

La aplicación es **segura para su modelo de despliegue actual (loopback)**. No se encontraron vulnerabilidades críticas explotables. Los tres hallazgos Medium dependen de exponer la API/panel a la red (o de un token comprometido) y tienen mitigaciones simples. El SAST (bandit) reporta 7 avisos LOW no explotables (uso intencional de subprocess y `except: pass` con propósito documentado). `pip-audit`: **0 vulnerabilidades conocidas** en las dependencias auditadas.

---

## 1. Hallazgos

### M1 — Arbitrary file write en `POST /api/v1/distros/{name}/export` (Medium)

- **CWE-22 / CWE-434 · OWASP A01 (Broken Access Control) · MITRE T1570**
- **Ubicación:** `src/api/routes.py` → `export()`; `src/providers/wsl_provider.py::export()`
- **Descripción:** el endpoint acepta una ruta de destino arbitraria del cliente y ejecuta `wsl --export <name> <path>` sobre ella, escribiendo el archivo donde el cliente indique (con los permisos del usuario que corre la app). No hay restricción de directorio.
- **Evidencia:**
  ```bash
  curl -i -X POST -H "Content-Type: application/json" \
    -d '{"path": "C:/Windows/Temp/wm-pentest.tar"}' \
    http://127.0.0.1:8791/api/v1/distros/docker-desktop/export
  # HTTP/1.1 200 OK  {"ok":true}
  # -> se escribieron 75,520,000 bytes en C:\Windows\Temp\wm-pentest.tar (verificado y eliminado)
  ```
- **Impacto:** en loopback, un proceso local ya puede escribir en `C:\Windows\Temp`; el riesgo real es si la API se publica (`--host 0.0.0.0`, VPN, port-forward) o si un token `write/admin` se filtra. El contenido es un tar de la distro (no código arbitrario), por lo que la explotación es limitada (relleno de disco, sobrescritura de archivos).
- **Reproducción:** arrancar la API, enviar el POST con `path` apuntando a cualquier directorio escribible.
- **Recomendación:** restringir el path al directorio de snapshots configurado:
  ```python
  from src.core.config import snapshot_dir
  base = Path(ctx.config.snapshots.target_dir or snapshot_dir()).resolve()
  target = Path(body.get("path", "")).resolve()
  if base not in target.parents:
      raise HTTPException(403, "ruta fuera del directorio de snapshots")
  ```

### M2 — Panel web sin autenticación (Medium, riesgo condicional)

- **CWE-306 (Missing Auth) · OWASP A01 · MITRE T1110/T1078**
- **Ubicación:** `src/web/web_app.py`
- **Descripción:** el dashboard web (http://127.0.0.1:8790) permite `start`, `stop`, `restart`, `snapshot` y **`shutdown` de todas las distros sin autenticación**. Es aceptable por diseño (solo loopback, como el plan M7), pero es un vector de denegación de servicio trivial si cualquier proceso local alcanza el puerto — p. ej. DNS rebinding o una web maliciosa que haga `fetch` a `http://127.0.0.1:8790/api/shutdown` (no hay CORS, pero POST simples sin preflight sí se envían).
- **Evidencia:**
  ```bash
  curl -i -X POST http://127.0.0.1:8790/api/shutdown
  # HTTP/1.1 200 OK  {"ok":true}
  ```
- **Recomendación:** token estático opcional (`ui.web_panel_token`) y/o validar `Host` (rechazar cualquier Host ≠ `127.0.0.1:8790` para mitigar DNS rebinding). Documentar el riesgo si se mantiene sin auth.

### M3 — `mcp.token_required` configurado pero no implementado (Medium)

- **CWE-306 · OWASP A07 · MITRE T1078**
- **Ubicación:** `src/core/config.py` (`McpCfg.token_required`) vs `src/mcp/server.py`, `src/mcp/tools.py`
- **Descripción:** el schema expone `mcp.token_required` (default `false`) y la sección 21.5 del plan describe autenticación para el MCP, pero el servidor MCP (stdio/HTTP) **no valida ningún token**: el flag es decorativo.
- **Evidencia:** `grep -rn "token_required" src/mcp/` → sin resultados; el flag solo vive en el schema y en `config.example.json`.
- **Recomendación:** implementar el chequeo en `run_stdio()`/`create_http_app()` cuando `token_required` esté activo, o eliminar el flag hasta implementarlo.

### L1 — `/health` sin rate limit ni auth (Low)

- **CWE-799 · OWASP A05**
- **Evidencia:** con `rate_limit_per_minute: 5`, 8 peticiones a `/api/v1/health` → `200×8`; el mismo límite sobre `/api/v1/status` → `200×5, 429×3`.
- **Recomendación:** añadir `dependencies=[require("read")]` a `/health` o documentarlo explícitamente.

### L2 — Headers de seguridad ausentes en API y panel web (Low)

- **CWE-16 · OWASP A05 · MITRE T1190**
- **Evidencia:**
  ```
  HTTP/1.1 200 OK
  server: uvicorn          # revela el stack
  # sin: X-Content-Type-Options, X-Frame-Options, Referrer-Policy, Permissions-Policy, CSP
  ```
- **Recomendación:** middleware que fije `X-Content-Type-Options: nosniff`, `X-Frame-Options: DENY`, `Referrer-Policy: no-referrer`, `Permissions-Policy: geolocation=()` y oculte `server`. El XSS del panel está mitigado por `esc()` (textContent) — verificado.

### L3 — Errores de `wsl.exe` filtrados en respuestas 500 (Low)

- **CWE-209 · OWASP A05**
- **Evidencia:** `POST /api/v1/distros/no-existe/start` → `500` con el detalle crudo del error de wsl.exe en el body.
- **Recomendación:** mensaje genérico en la respuesta y detalle solo en logs.

### L4 — Tokens con SHA-256 sin salt (Low/Info)

- **CWE-760 · OWASP A02**
- **Ubicación:** `src/api/auth.py`, `src/core/metrics_store.py::add_token`
- **Descripción:** digest `sha256(token)` sin salt. Con tokens de 32 bytes aleatorios (`secrets.token_urlsafe(32)`, 256 bits de entropía) el ataque de diccionario es inviable; aceptable, pero `pbkdf2_hmac` con salt por token eleva el estándar.
- **Recomendación (mejora):** `hashlib.pbkdf2_hmac("sha256", token, salt, 100_000)`.

### I1 — `--host 0.0.0.0` permitido sin advertencia (Info)

- `wsl-manager web serve --host 0.0.0.0` / `ux run-server` exponen la API y el panel a la red sin aviso. Recomendación: advertencia en pantalla si `host != 127.0.0.1` y exigir modo token para la API.

### I2 — `allowed_ips` vacío desactiva el filtro (Info)

- En `auth.py::require()`, `if self._cfg.allowed_ips and ...` — lista vacía (config manual) salta el filtro. Recomendación: validar en carga que `mode=token` exija `allowed_ips` no vacío.

### I3 — Header `Date`/zona horaria del host en respuestas (Info)

- No es riesgo; se documenta por completitud.

---

## 2. Controles verificados (positivos)

| Control | Resultado |
|---------|-----------|
| Inyección SQL | **OK** — todas las queries de `metrics_store.py` usan parámetros `?`; sin f-strings en SQL |
| Inyección de comandos | **OK** — subprocess con listas (sin `shell=True`); nombres de distro como argumentos de `wsl.exe`; quoting correcto en drop-ins systemd (`_quote`) |
| XSS en panel web | **OK** — todo dato dinámico pasa por `esc()` (textContent) |
| Validación de entrada | **OK** — pydantic v2; `422` limpio con payload malformado |
| AuthZ de la API (modo token) | **OK** — sin token → 401; token `read` → 200 en GET; POST con `read` → 401; revocación inmediata |
| Rate limiting | **OK** en endpoints protegidos: `200×5 → 429×3` |
| Métodos HTTP | **OK** — `PUT`/`OPTIONS` → 405; sin CORS habilitado |
| Secretos hardcodeados | **OK** — grep sin coincidencias; token solo en stdout de `api tokens create` |
| Dependencias | **OK** — `pip-audit`: "No known vulnerabilities found" |
| SAST (bandit 1.9.4) | **7 LOW, 0 HIGH/MEDIUM** — B110/B404/B603 intencionales y revisados |
| Tokens en bundle `diag` | **OK** — `diag` incluye config/logs pero **no** `metrics.db` (donde viven los hashes) |
| Escritura de `.wslconfig` | **OK** — backup previo + validación INI + rollback (R2/R7) |
| Nombres de distro maliciosos (`..%2f`) | **OK** — 404 en routing (FastAPI los rechaza) |

Evidencia de validación:
```bash
curl -i -X POST -H "Content-Type: application/json" -d '{"id": 1, "name": 2}' \
  http://127.0.0.1:8791/api/v1/schedule
# HTTP/1.1 422  {"detail":[{"type":"...","loc":["body",...]}]}
```

---

## 3. Mapeo de frameworks

| Hallazgo | OWASP Top 10 | CWE | MITRE ATT&CK |
|----------|--------------|-----|--------------|
| M1 export path | A01 Broken Access Control | CWE-22, CWE-434 | T1570 Lateral Tool Transfer |
| M2 panel sin auth | A01 | CWE-306 | T1078 Valid Accounts / T1110 |
| M3 MCP token_required | A07 | CWE-306 | T1078 |
| L1 health sin rate limit | A05 | CWE-799 | — |
| L2 headers | A05 | CWE-16 | T1190 |
| L3 errores 500 | A05 | CWE-209 | — |
| L4 hash sin salt | A02 | CWE-760 | — |

---

## 4. Recomendaciones priorizadas

1. **(M1)** Restringir el path del export al directorio de snapshots — ~10 líneas en `routes.py`.
2. **(M3)** Implementar o eliminar `mcp.token_required`.
3. **(M2)** Token opcional + chequeo de `Host` en el panel web (mitiga DNS rebinding).
4. **(L1/L2/L3)** Middleware de headers + rate limit en `/health` + errores genéricos.
5. **(L4)** `pbkdf2_hmac` con salt para el digest de tokens.
6. **(I1/I2)** Advertencia al publicar fuera de loopback y validación de `allowed_ips`.

## 5. Herramientas y comandos

```bash
# SAST
.venv/Scripts/bandit -r src -f json -o bandit-report.json
# Dependencias
.venv/Scripts/python -m pip_audit
# Secretos
grep -riE "(api[_-]?key|secret|password)[=:][\"'][^\"']{8,}" src/
# AuthZ (evidencia de este reporte)
curl -i -X POST -H "Content-Type: application/json" -d '{"path":"C:/Windows/Temp/x.tar"}' \
  http://127.0.0.1:8791/api/v1/distros/docker-desktop/export
```

## 6. Estado final del sistema

Todas las pruebas fueron reversibles: distros restauradas a `Stopped`, `.wslconfig` original intacto, archivos de prueba eliminados (`C:\Windows\Temp\wm-pentest.tar`), configs temporales borradas, sin tokens residuales en la base.

## 7. Remediacion aplicada (2026-08-14)

Correcciones implementadas y verificadas tras la auditoria:

| Hallazgo | Estado | Verificacion post-fix |
|----------|--------|----------------------|
| M1 export path arbitrario | **CORREGIDO** — `routes.py::export()` valida que el destino este dentro de `snapshot_dir()`/`target_dir` | fuera → `403 ruta fuera del directorio de snapshots`; dentro → `200`; nada escrito fuera |
| L1 `/health` sin rate limit | **CORREGIDO** — `dependencies=[require("read")]` en `/health` | suite de tests verdes (el mecanismo 200x5/429x3 ya estaba probado en endpoints protegidos) |
| L2 headers ausentes | **CORREGIDO** — middleware `SecurityHeadersMiddleware` en API y panel web; `server_header=False` en uvicorn | `x-content-type-options: nosniff`, `x-frame-options: DENY`, `referrer-policy: no-referrer`, `permissions-policy: ...` presentes; sin `server: uvicorn` |
| L3 errores de wsl en 500 | **CORREGIDO** — `_fail()` loguea el detalle y devuelve `{"detail":"operacion fallida"}` | `POST .../distros/no-existe/start` → `500` generico (30 bytes) |
| M2 panel web sin auth | **PENDIENTE** — decision de diseno (loopback). Recomendado: token opcional + validacion de `Host` | — |
| M3 `mcp.token_required` sin implementar | **PENDIENTE** — implementar chequeo o eliminar el flag | — |
| L4 SHA-256 sin salt | **PENDIENTE (mejora)** — `pbkdf2_hmac` con salt | — |
| I1/I2 host/advertencias | **PENDIENTE (mejora)** | — |

Archivos tocados: `src/api/routes.py`, `src/api/server.py`, `src/web/web_app.py`, `src/cli/commands_ux.py`, `src/app.py`. Suite: **57/57 tests OK** tras los cambios.
