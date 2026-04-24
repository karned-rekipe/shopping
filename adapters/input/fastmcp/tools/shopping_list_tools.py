import fastmcp
from pydantic import Field
from uuid6 import UUID

from adapters.input.fastmcp.dependencies import inject_tenant_uri, require_auth_mcp
from adapters.input.schemas.shopping_list_schema import ShoppingListSchema
from application.services.shopping_list_service import ShoppingListService
from arclith.domain.ports.logger import Logger
from domain.models.shopping_list import ShoppingList
from typing import Annotated
from uuid import UUID as StdUUID


class ShoppingListMCP:
    def __init__(self, service: ShoppingListService, logger: Logger, mcp: fastmcp.FastMCP) -> None:
        self._service = service
        self._logger = logger
        self._mcp = mcp
        self._register_tools()

    @staticmethod
    def _to_uuid6(uuid: StdUUID) -> UUID:
        return UUID(str(uuid))

    def _register_tools(self) -> None:
        service = self._service
        logger = self._logger
        to_uuid6 = self._to_uuid6

        @self._mcp.tool
        async def create_shopping_list(
                name: Annotated[str, Field(
                    description = "Nom de l'ingrédient (ex. 'Farine de blé', 'Sel fin'). Sera normalisé (espaces rognés).",
                    examples = ["Farine de blé", "Sel fin"])],
                ctx: fastmcp.Context | None = None,
        ) -> dict:
            """Create a new reusable shopping_list.

            Returns the created shopping_list with its generated UUID.
            Once created, use `link_shopping_list_to_recipe` to attach it to a recipe.
            Fields returned: uuid, name, created_at, updated_at, version.
            """
            await require_auth_mcp(ctx)
            await inject_tenant_uri(ctx)
            result = await service.create(ShoppingList(name = name))
            logger.info("✅ ShoppingList created via MCP", uuid = str(result.uuid), name = result.name)
            return ShoppingListSchema.model_validate(result).model_dump()

        @self._mcp.tool
        async def get_shopping_list(
                uuid: Annotated[str, Field(description = "UUID (UUIDv7) de l'ingrédient à récupérer.",
                                           examples = ["01951234-5678-7abc-def0-123456789abc"])],
                ctx: fastmcp.Context | None = None,
        ) -> dict | None:
            """Get an shopping_list by its UUID.

            Returns the full shopping_list object or null if not found.
            Fields: uuid, name, created_at, updated_at, version.
            """
            await inject_tenant_uri(ctx)
            result = await service.read(to_uuid6(StdUUID(uuid)))
            if result is None:
                logger.warning("⚠️ ShoppingList not found via MCP", uuid = uuid)
                return None
            logger.info("✅ ShoppingList fetched via MCP", uuid = uuid, name = result.name)
            return ShoppingListSchema.model_validate(result).model_dump()

        @self._mcp.tool
        async def update_shopping_list(
                uuid: Annotated[str, Field(description = "UUID (UUIDv7) de l'ingrédient à modifier.",
                                           examples = ["01951234-5678-7abc-def0-123456789abc"])],
                name: Annotated[str, Field(description = "Nouveau nom de l'ingrédient.",
                                           examples = ["Farine complète", "Gros sel"])],
                ctx: fastmcp.Context | None = None,
        ) -> dict:
            """Replace name of an existing shopping_list.

            Full replacement (PUT semantics): name is overwritten.
            Returns the updated shopping_list.
            Note: updating an shopping_list does not propagate to recipes where it is already linked (snapshot model).
            """
            await inject_tenant_uri(ctx)
            result = await service.update(ShoppingList(uuid = to_uuid6(StdUUID(uuid)), name = name))
            logger.info("✅ ShoppingList updated via MCP", uuid = uuid, name = result.name)
            return ShoppingListSchema.model_validate(result).model_dump()

        @self._mcp.tool
        async def delete_shopping_list(
                uuid: Annotated[str, Field(description = "UUID (UUIDv7) de l'ingrédient à supprimer.",
                                           examples = ["01951234-5678-7abc-def0-123456789abc"])],
                ctx: fastmcp.Context | None = None,
        ) -> None:
            """Soft-delete an shopping_list.

            The shopping_list is marked as deleted and excluded from list results.
            It is retained until the purge retention period expires.
            Use `purge_shopping_lists` to permanently remove expired entries.
            """
            await require_auth_mcp(ctx)
            await inject_tenant_uri(ctx)
            await service.delete(to_uuid6(StdUUID(uuid)))
            logger.info("✅ ShoppingList deleted via MCP", uuid = uuid)

        @self._mcp.tool
        async def list_shopping_lists(
                name: Annotated[str | None, Field(default = None,
                                                  description = "Filtre optionnel : recherche partielle sur le nom, insensible à la casse. Ex: 'far' retournera 'Farine de blé'.",
                                                  examples = ["farine", None])] = None,
                ctx: fastmcp.Context | None = None,
        ) -> list[dict]:
            """List all active (non-deleted) shopping_lists.

            Pass `name` for a partial, case-insensitive name filter.
            Each item: uuid, name, created_at, updated_at, version.
            Use these UUIDs with `link_shopping_list_to_recipe` to attach shopping_lists to a recipe.
            """
            await inject_tenant_uri(ctx)
            items = await service.find_by_name(name) if name else await service.find_all()
            logger.info("✅ ShoppingLists listed via MCP", count = len(items), filter = name)
            return [ShoppingListSchema.model_validate(i).model_dump() for i in items]

        @self._mcp.tool
        async def duplicate_shopping_list(
                uuid: Annotated[str, Field(description = "UUID (UUIDv7) de l'ingrédient à dupliquer.",
                                           examples = ["01951234-5678-7abc-def0-123456789abc"])],
                ctx: fastmcp.Context | None = None,
        ) -> dict:
            """Duplicate an shopping_list, assigning it a new UUID.

            Creates an independent copy with the same name.
            Returns the new shopping_list with its own UUID.
            """
            await inject_tenant_uri(ctx)
            result = await service.duplicate(to_uuid6(StdUUID(uuid)))
            logger.info("✅ ShoppingList duplicated via MCP", source_uuid = uuid, new_uuid = str(result.uuid))
            return ShoppingListSchema.model_validate(result).model_dump()

