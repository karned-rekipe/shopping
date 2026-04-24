"""MCP tools registration."""

import fastmcp
from adapters.input.fastmcp.tools import AdminMCP, ShoppingListMCP
from arclith import Arclith
from infrastructure.containers.shopping_list_container import build_shopping_list_service
from infrastructure.purge_registry import purge_registry


def register_tools(mcp: fastmcp.FastMCP, arclith: Arclith) -> None:
    """Register all MCP tools."""
    service, logger = build_shopping_list_service(arclith)
    purge_registry.register("shopping_lists", service.purge)
    ShoppingListMCP(service, logger, mcp)
    AdminMCP(purge_registry, logger, mcp)

