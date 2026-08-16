"""AuthService: tokens con scopes (read/write/admin), rate limit y auditoria (seccion 21).

- Modo 'none': sin auth (solo loopback recomendado).
- Modo 'token': Authorization: Bearer <token> (hash en SQLite).
Scopes: read (GET), write (acciones), admin (config).
"""
from __future__ import annotations

import hashlib
import threading
import time

from fastapi import Header, HTTPException, Request

from src.core.config import ApiCfg
from src.core.metrics_store import MetricsStore

_SCOPE_ORDER = {"read": 1, "write": 2, "admin": 3}


class AuthService:
    def __init__(self, cfg: ApiCfg, metrics: MetricsStore) -> None:
        self._cfg = cfg
        self._metrics = metrics
        self._hits: dict[str, list[float]] = {}
        self._lock = threading.RLock()

    # -- rate limit ---------------------------------------------------------

    def _check_rate(self, client_ip: str) -> None:
        limit = self._cfg.auth.rate_limit_per_minute
        if limit <= 0:
            return
        with self._lock:
            now = time.time()
            hits = [t for t in self._hits.get(client_ip, []) if now - t < 60]
            hits.append(now)
            self._hits[client_ip] = hits
        if len(hits) > limit:
            raise HTTPException(status_code=429, detail="rate limit excedido")

    # -- auth ---------------------------------------------------------------

    def _verify_token(self, token: str, required_scope: str) -> bool:
        if not token:
            return False
        digest = hashlib.sha256(token.encode()).hexdigest()
        row = self._metrics.token_exists(digest)
        if row is None:
            return False
        if row["expires"] and row["expires"] < time.time():
            return False
        return _SCOPE_ORDER.get(row["scope"], 0) >= _SCOPE_ORDER.get(required_scope, 99)

    def require(self, request: Request, scope: str) -> None:
        """Dependency de FastAPI. Lanza 401/403/429."""
        client_ip = request.client.host if request.client else "?"
        if self._cfg.allowed_ips and client_ip not in self._cfg.allowed_ips:
            raise HTTPException(status_code=403, detail=f"IP no permitida: {client_ip}")
        self._check_rate(client_ip)
        if self._cfg.auth.mode == "none":
            return
        token = request.headers.get("Authorization", "")
        if token.lower().startswith("bearer "):
            token = token[7:].strip()
        if not token:
            token = request.headers.get("X-API-Key", "")
        if not self._verify_token(token, scope):
            self._metrics.log_event("api_denied", message=f"403 para {client_ip} scope={scope}")
            raise HTTPException(status_code=401, detail="token invalido o scope insuficiente")
