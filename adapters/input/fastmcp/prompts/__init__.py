"""MCP prompts."""

import fastmcp

from arclith import Arclith
from adapters.input.fastmcp.prompts.shopping_list_prompts import ShoppingListPrompts
from infrastructure.containers.shopping_list_container import build_shopping_list_service

__all__ = ["ShoppingListPrompts"]


def register_prompts(mcp: fastmcp.FastMCP, arclith: Arclith) -> None:
    service, logger = build_shopping_list_service(arclith)
    ShoppingListPrompts(service, logger, mcp)
