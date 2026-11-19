from typing import Annotated
from datetime import date
from uuid import UUID as StdUUID

import fastmcp
from pydantic import Field
from uuid6 import UUID

from adapters.input.fastmcp.dependencies import inject_tenant_uri, require_auth_mcp
from adapters.input.schemas.shopping_list_schema import ShoppingListSchema
from application.services.shopping_list_service import ShoppingListService
from arclith.domain.ports.logger import Logger
from domain.models.shopping_list import ShoppingItem, ShoppingList


class ShoppingListMCP:
    def __init__(self, service: ShoppingListService, logger: Logger, mcp: fastmcp.FastMCP) -> None:
        self._service = service
        self._logger = logger
        self._mcp = mcp
        self._register_tools()

    @staticmethod
    def _to_uuid6(uuid: StdUUID) -> UUID:
        return UUID(str(uuid))

    async def _expected_version(self, uuid: UUID, expected_version: int | None) -> int:
        if expected_version is not None:
            return expected_version
        current = await self._service.read(uuid)
        if current is None:
            raise ValueError(f"ShoppingList {uuid} not found")
        return current.version

    def _register_tools(self) -> None:
        service = self._service
        logger = self._logger
        to_uuid6 = self._to_uuid6
        expected_version_for = self._expected_version

        @self._mcp.tool
        async def create_shopping_list(
            name: Annotated[str, Field(description="Nom de la liste de courses.")],
            ctx: fastmcp.Context | None = None,
        ) -> dict:
            """Create an empty shopping list for manual use."""
            await require_auth_mcp(ctx)
            await inject_tenant_uri(ctx)
            result = await service.create(ShoppingList(name=name))
            logger.info("ShoppingList created via MCP", uuid=str(result.uuid), name=result.name)
            return ShoppingListSchema.model_validate(result).model_dump(mode="json")

        @self._mcp.tool
        async def generate_shopping_list_from_meal_plan(
            meal_plan_uuid: Annotated[str, Field(description="UUID du MealPlan confirmé.")],
            name: Annotated[str | None, Field(default=None, description="Nom optionnel de la liste.")] = None,
            ctx: fastmcp.Context | None = None,
        ) -> dict:
            """Generate a shopping list from a confirmed meal plan."""
            await require_auth_mcp(ctx)
            await inject_tenant_uri(ctx)
            result = await service.generate_from_meal_plan(StdUUID(meal_plan_uuid), name=name)
            logger.info("ShoppingList generated via MCP", uuid=str(result.uuid), meal_plan_uuid=meal_plan_uuid)
            return ShoppingListSchema.model_validate(result).model_dump(mode="json")

        @self._mcp.tool
        async def generate_shopping_list_from_period(
            date_start: Annotated[str, Field(description="Date de début ISO, incluse.")],
            date_end: Annotated[str, Field(description="Date de fin ISO, incluse.")],
            name: Annotated[str | None, Field(default=None, description="Nom optionnel de la liste.")] = None,
            ctx: fastmcp.Context | None = None,
        ) -> dict:
            """Generate a shopping list for a date period from confirmed meal plans."""
            await require_auth_mcp(ctx)
            await inject_tenant_uri(ctx)
            start = date.fromisoformat(date_start)
            end = date.fromisoformat(date_end)
            result = await service.generate_from_period(start, end, name=name)
            logger.info("ShoppingList generated from period via MCP", uuid=str(result.uuid), date_start=date_start, date_end=date_end)
            return ShoppingListSchema.model_validate(result).model_dump(mode="json")

        @self._mcp.tool
        async def get_shopping_list(
            uuid: Annotated[str, Field(description="UUID de la liste de courses.")],
            ctx: fastmcp.Context | None = None,
        ) -> dict | None:
            """Get a shopping list by UUID."""
            await inject_tenant_uri(ctx)
            result = await service.read(to_uuid6(StdUUID(uuid)))
            if result is None:
                logger.warning("ShoppingList not found via MCP", uuid=uuid)
                return None
            return ShoppingListSchema.model_validate(result).model_dump(mode="json")

        @self._mcp.tool
        async def update_shopping_list(
            uuid: Annotated[str, Field(description="UUID de la liste de courses.")],
            name: Annotated[str, Field(description="Nouveau nom.")],
            expected_version: Annotated[int | None, Field(default=None, description="Version attendue.")] = None,
            ctx: fastmcp.Context | None = None,
        ) -> dict:
            """Rename a shopping list."""
            await require_auth_mcp(ctx)
            await inject_tenant_uri(ctx)
            list_uuid = to_uuid6(StdUUID(uuid))
            version = await expected_version_for(list_uuid, expected_version)
            current = await service.read(list_uuid)
            if current is None:
                raise ValueError(f"ShoppingList {uuid} not found")
            result = await service.update_with_expected(list_uuid, current.model_copy(update={"name": name}), version)
            return ShoppingListSchema.model_validate(result).model_dump(mode="json")

        @self._mcp.tool
        async def add_manual_shopping_item(
            uuid: Annotated[str, Field(description="UUID de la liste de courses.")],
            name: Annotated[str, Field(description="Nom du produit.")],
            quantity: Annotated[float | None, Field(default=None, ge=0, description="Quantité optionnelle.")] = None,
            unit: Annotated[str | None, Field(default=None, description="Unité optionnelle.")] = None,
            rayon: Annotated[str | None, Field(default=None, description="Rayon optionnel.")] = None,
            expected_version: Annotated[int | None, Field(default=None, description="Version attendue.")] = None,
            ctx: fastmcp.Context | None = None,
        ) -> dict:
            """Add a manual product to a shopping list."""
            await require_auth_mcp(ctx)
            await inject_tenant_uri(ctx)
            list_uuid = to_uuid6(StdUUID(uuid))
            version = await expected_version_for(list_uuid, expected_version)
            result = await service.add_manual_item(
                list_uuid,
                ShoppingItem(name=name, quantity=quantity, unit=unit, rayon=rayon, manual=True, note=None),
                version,
            )
            return ShoppingListSchema.model_validate(result).model_dump(mode="json")

        @self._mcp.tool
        async def set_shopping_item_checked(
            uuid: Annotated[str, Field(description="UUID de la liste de courses.")],
            item_uuid: Annotated[str, Field(description="UUID de l'item à cocher/décocher.")],
            checked: Annotated[bool, Field(description="État de coche cible.")],
            expected_version: Annotated[int | None, Field(default=None, description="Version attendue.")] = None,
            ctx: fastmcp.Context | None = None,
        ) -> dict:
            """Check or uncheck a shopping item."""
            await require_auth_mcp(ctx)
            await inject_tenant_uri(ctx)
            list_uuid = to_uuid6(StdUUID(uuid))
            version = await expected_version_for(list_uuid, expected_version)
            result = await service.update_item(list_uuid, StdUUID(item_uuid), version, {"checked": checked})
            return ShoppingListSchema.model_validate(result).model_dump(mode="json")

        @self._mcp.tool
        async def delete_shopping_list(
            uuid: Annotated[str, Field(description="UUID de la liste de courses.")],
            expected_version: Annotated[int | None, Field(default=None, description="Version attendue.")] = None,
            ctx: fastmcp.Context | None = None,
        ) -> None:
            """Soft-delete a shopping list."""
            await require_auth_mcp(ctx)
            await inject_tenant_uri(ctx)
            list_uuid = to_uuid6(StdUUID(uuid))
            version = await expected_version_for(list_uuid, expected_version)
            await service.delete_with_expected(list_uuid, version)

        @self._mcp.tool
        async def list_shopping_lists(
            name: Annotated[str | None, Field(default=None, description="Filtre partiel sur le nom.")] = None,
            ctx: fastmcp.Context | None = None,
        ) -> list[dict]:
            """List active shopping lists."""
            await inject_tenant_uri(ctx)
            items = await service.find_by_name(name) if name else await service.find_all()
            return [ShoppingListSchema.model_validate(item).model_dump(mode="json") for item in items]

        @self._mcp.tool
        async def export_shopping_list_text(
            uuid: Annotated[str, Field(description="UUID de la liste de courses.")],
            include_checked: Annotated[bool, Field(description="Inclure les items déjà cochés.")] = True,
            rayon: Annotated[str | None, Field(default=None, description="Rayon à exporter.")] = None,
            ctx: fastmcp.Context | None = None,
        ) -> dict:
            """Export a filtered shopping list as plain text."""
            await inject_tenant_uri(ctx)
            return await service.export_text(to_uuid6(StdUUID(uuid)), rayon=rayon, include_checked=include_checked)

        @self._mcp.tool
        async def analyze_shopping_list(
            uuid: Annotated[str, Field(description="UUID de la liste de courses.")],
            ctx: fastmcp.Context | None = None,
        ) -> dict:
            """Analyze warnings, duplicate names and progress for a shopping list."""
            await inject_tenant_uri(ctx)
            return await service.analyze(to_uuid6(StdUUID(uuid)))

        @self._mcp.tool
        async def duplicate_shopping_list(
            uuid: Annotated[str, Field(description="UUID de la liste de courses à dupliquer.")],
            ctx: fastmcp.Context | None = None,
        ) -> dict:
            """Duplicate a shopping list."""
            await require_auth_mcp(ctx)
            await inject_tenant_uri(ctx)
            result = await service.duplicate(to_uuid6(StdUUID(uuid)))
            return ShoppingListSchema.model_validate(result).model_dump(mode="json")
