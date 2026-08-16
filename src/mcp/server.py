"""Servidor MCP sobre stdio (seccion 21.4). Import lazy de 'mcp'."""
from __future__ import annotations

from src.cli.common import CliContext


def run_stdio(ctx: CliContext) -> None:
    if not ctx.config.mcp.enabled:
        print("MCP deshabilitado en Ajustes de WSL Manager (mcp.enabled=false).")
        raise SystemExit(3)

    mcp_cfg = ctx.config.mcp

    try:
        from mcp.server.fastmcp import FastMCP  # type: ignore
    except ImportError as e:
        raise RuntimeError("falta el paquete 'mcp'. Instala: pip install mcp") from e

    from src.mcp.tools import McpTools, get_tool_defs

    tools = McpTools(ctx)
    mcp = FastMCP("wsl-manager")

    def _authed(arguments: dict | None) -> None:
        """Valida el token si mcp.token_required esta activo (Ajustes)."""
        if not mcp_cfg.token_required or not mcp_cfg.token:
            return
        provided = (arguments or {}).get("token") or ((arguments or {}).get("_meta") or {}).get("token")
        if provided != mcp_cfg.token:
            raise PermissionError("token invalido (configura el token en Ajustes)")

    for definition in get_tool_defs():
        name = definition["name"]

        def make_tool(fn_name: str = name):
            def tool(arguments: dict | None = None) -> dict:
                _authed(arguments)
                return tools.call(fn_name, arguments)

            tool.__name__ = fn_name
            tool.__doc__ = definition["description"]
            return tool

        mcp.tool()(make_tool())

    mcp.run(transport="stdio")


def create_http_app(ctx: CliContext):
    """App ASGI para transporte HTTP (P2): usa FastMCP con streamable_http."""
    try:
        from mcp.server.fastmcp import FastMCP  # type: ignore
    except ImportError as e:
        raise RuntimeError("falta el paquete 'mcp'. Instala: pip install mcp") from e

    from src.mcp.tools import McpTools, get_tool_defs

    mcp_cfg = ctx.config.mcp
    tools = McpTools(ctx)
    mcp = FastMCP("wsl-manager")
    for definition in get_tool_defs():
        name = definition["name"]

        def make_tool(fn_name: str = name):
            def tool(arguments: dict | None = None) -> dict:
                if mcp_cfg.token_required and mcp_cfg.token:
                    provided = (arguments or {}).get("token") or ((arguments or {}).get("_meta") or {}).get("token")
                    if provided != mcp_cfg.token:
                        raise PermissionError("token invalido")
                return tools.call(fn_name, arguments)

            tool.__name__ = fn_name
            tool.__doc__ = definition["description"]
            return tool

        mcp.tool()(make_tool())
    return mcp.streamable_http_app()
