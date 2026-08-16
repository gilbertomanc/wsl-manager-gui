"""Servidor FastAPI: monta auth + rutas + headers de seguridad sobre el CliContext."""
from __future__ import annotations

from fastapi import FastAPI
from starlette.middleware.base import BaseHTTPMiddleware

from src.api.auth import AuthService
from src.api.routes import router
from src.cli.common import CliContext

SECURITY_HEADERS = {
    "X-Content-Type-Options": "nosniff",
    "X-Frame-Options": "DENY",
    "Referrer-Policy": "no-referrer",
    "Permissions-Policy": "geolocation=(), microphone=(), camera=()",
}


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        response = await call_next(request)
        for name, value in SECURITY_HEADERS.items():
            response.headers[name] = value
        return response


def apply_security_headers(app: FastAPI) -> None:
    app.add_middleware(SecurityHeadersMiddleware)


def create_app(ctx: CliContext) -> FastAPI:
    app = FastAPI(title="WSL Manager API", version="0.1.0")
    app.state.ctx = ctx  # type: ignore[attr-defined]
    app.state.auth = AuthService(ctx.config.api, ctx.metrics)  # type: ignore[attr-defined]
    app.include_router(router)
    apply_security_headers(app)
    return app
