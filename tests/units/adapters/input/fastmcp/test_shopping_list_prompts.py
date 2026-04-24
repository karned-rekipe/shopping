from unittest.mock import AsyncMock, patch

import fastmcp
import pytest

from adapters.input.fastmcp.prompts import ShoppingListPrompts
from application.services.shopping_list_service import ShoppingListService
from domain.models.shopping_list import ShoppingList


@pytest.fixture
def mcp_app():
    return fastmcp.FastMCP("test")


@pytest.fixture
def service(repo, logger):
    return ShoppingListService(repo, logger)


@pytest.fixture
async def client(service, logger, mcp_app):
    with patch("adapters.input.fastmcp.prompts.shopping_list_prompts.inject_tenant_uri", new=AsyncMock()):
        ShoppingListPrompts(service, logger, mcp_app)
        async with fastmcp.Client(mcp_app) as c:
            yield c


def _text(result) -> str:
    return result.messages[0].content.text


# --- check_duplicate ---

async def test_check_duplicate_contains_name(client):
    result = await client.get_prompt("check_duplicate", {"shopping_list_name": "Farine"})
    assert "Farine" in _text(result)


async def test_check_duplicate_mentions_list_tool(client):
    result = await client.get_prompt("check_duplicate", {"shopping_list_name": "Sel"})
    assert "list_shopping_lists" in _text(result)


# --- explore_shopping_lists ---

async def test_explore_empty_catalog(client):
    result = await client.get_prompt("explore_shopping_lists", {})
    assert "No shopping_lists available" in _text(result)


async def test_explore_lists_shopping_list_names(client, service):
    await service.create(ShoppingList(name="Farine"))
    await service.create(ShoppingList(name="Sel"))
    result = await client.get_prompt("explore_shopping_lists", {})
    text = _text(result)
    assert "Farine" in text
    assert "Sel" in text


async def test_explore_shows_total_count(client, service):
    for i in range(3):
        await service.create(ShoppingList(name=f"Item {i}"))
    result = await client.get_prompt("explore_shopping_lists", {})
    assert "3" in _text(result)


# --- mcp_help ---

async def test_mcp_help_lists_tools(client):
    text = _text(await client.get_prompt("mcp_help", {}))
    assert "create_shopping_list" in text
    assert "list_shopping_lists" in text
    assert "purge_shopping_lists" in text


async def test_mcp_help_lists_prompts(client):
    text = _text(await client.get_prompt("mcp_help", {}))
    assert "check_duplicate" in text
    assert "explore_shopping_lists" in text
    assert "mcp_help" in text


async def test_mcp_help_lists_resources(client):
    text = _text(await client.get_prompt("mcp_help", {}))
    assert "resource://shopping-lists/sample" in text
    assert "resource://shopping-lists/recent" in text
    assert "resource://shopping-list/{uuid}" in text
