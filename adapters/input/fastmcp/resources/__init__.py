"""MCP resources."""

import fastmcp

from arclith import Arclith
from adapters.input.fastmcp.resources.shopping_list_resources import ShoppingListResources
from infrastructure.containers.shopping_list_container import build_shopping_list_service

__all__ = ["ShoppingListResources"]


def register_resources(mcp: fastmcp.FastMCP, arclith: Arclith) -> None:
    service, logger = build_shopping_list_service(arclith)
    ShoppingListResources(service, logger, mcp)
