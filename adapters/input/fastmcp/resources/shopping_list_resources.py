import json
from uuid import UUID as StdUUID

import fastmcp
from uuid6 import UUID

from adapters.input.fastmcp.dependencies import inject_tenant_uri
from adapters.input.schemas.shopping_list_schema import ShoppingListSchema
from application.services.shopping_list_service import ShoppingListService
from arclith.domain.ports.logger import Logger

_SAMPLE_LIMIT = 5
_RECENT_LIMIT = 10


class ShoppingListResources:
    def __init__(self, service: ShoppingListService, logger: Logger, mcp: fastmcp.FastMCP) -> None:
        self._service = service
        self._logger = logger
        self._mcp = mcp
        self._register_resources()

    @staticmethod
    def _to_uuid6(uuid: StdUUID) -> UUID:
        return UUID(str(uuid))

    def _register_resources(self) -> None:
        service = self._service
        logger = self._logger
        to_uuid6 = self._to_uuid6

        @self._mcp.resource("resource://shopping-lists/sample")
        async def sample_shopping_lists_resource(ctx: fastmcp.Context) -> str:
            """First 5 shopping_lists ordered by creation date — quick dataset preview."""
            await inject_tenant_uri(ctx)
            items = await service.find_all()
            sample = sorted(items, key=lambda i: i.created_at)[:_SAMPLE_LIMIT]
            return json.dumps([ShoppingListSchema.model_validate(i).model_dump(mode="json") for i in sample])

        @self._mcp.resource("resource://shopping-lists/recent")
        async def recent_shopping_lists_resource(ctx: fastmcp.Context) -> str:
            """Last 10 shopping_lists by creation date, newest first."""
            await inject_tenant_uri(ctx)
            items = await service.find_all()
            recent = sorted(items, key=lambda i: i.created_at, reverse=True)[:_RECENT_LIMIT]
            return json.dumps([ShoppingListSchema.model_validate(i).model_dump(mode="json") for i in recent])

        @self._mcp.resource("resource://shopping-list/{uuid}")
        async def get_shopping_list_resource(uuid: str, ctx: fastmcp.Context) -> str:
            """A single shopping_list by UUID."""
            await inject_tenant_uri(ctx)
            result = await service.read(to_uuid6(StdUUID(uuid)))
            if result is None:
                logger.warning("⚠️ ShoppingList not found via MCP resource", uuid=uuid)
                return json.dumps(None)
            return json.dumps(ShoppingListSchema.model_validate(result).model_dump(mode="json"))
