from datetime import date, datetime, timezone
from uuid import UUID as StdUUID

from uuid6 import UUID

from application.use_cases import FindByNameUseCase
from arclith import BaseService, Logger
from domain.exceptions import (
    MealPlanNotConfirmed,
    ShoppingItemNotFound,
    ShoppingListNotFound,
    VersionConflict,
)
from domain.models.enums import ShoppingListStatus, ShoppingWarningCode
from domain.models.shopping_list import ShoppingItem, ShoppingList, ShoppingListWarning, ShoppingSourceLine
from domain.models.shopping_projection import ShoppingProjection, ShoppingProjectionIngredient
from domain.ports.output.meal_plan_client import MealPlanClient
from domain.ports.output.shopping_list_repository import ShoppingListRepository


def _matches_item_filters(
    item: ShoppingItem,
    *,
    wanted: set[StdUUID] | None,
    normalized_rayon: str | None,
    supplier_uuid: StdUUID | None,
    include_checked: bool,
) -> bool:
    if wanted is not None and item.uuid not in wanted:
        return False
    if normalized_rayon is not None and (item.rayon or "").casefold() != normalized_rayon:
        return False
    if supplier_uuid is not None and item.supplier_uuid != supplier_uuid:
        return False
    return include_checked or not item.checked


class ShoppingListService(BaseService[ShoppingList]):
    def __init__(
        self,
        repository: ShoppingListRepository,
        logger: Logger,
        retention_days: float | None = None,
        meal_plan_client: MealPlanClient | None = None,
    ) -> None:
        super().__init__(repository, logger, retention_days)
        self._shopping_list_repo = repository
        self._find_by_name_uc = FindByNameUseCase(repository, logger)
        self._meal_plan_client = meal_plan_client

    async def find_by_name(self, name: str) -> list[ShoppingList]:
        return await self._find_by_name_uc.execute(name)

    async def find_page_filtered(
        self,
        name: str | None = None,
        offset: int = 0,
        limit: int | None = None,
    ) -> tuple[list[ShoppingList], int]:
        """Return a page of shopping_lists (optionally filtered by name) and total count."""
        if name:
            return await self._shopping_list_repo.find_page_by_name(name, offset, limit)
        return await self._shopping_list_repo.find_page(offset, limit)

    async def generate_from_meal_plan(
        self,
        meal_plan_uuid: StdUUID,
        name: str | None = None,
        tenant_uri: str | None = None,
    ) -> ShoppingList:
        if self._meal_plan_client is None:
            raise RuntimeError("MealPlanClient is required to generate a shopping list")
        meal_plan = await self._meal_plan_client.get_meal_plan(meal_plan_uuid, tenant_uri)
        status = meal_plan.get("status")
        if status != "confirmed":
            raise MealPlanNotConfirmed(meal_plan_uuid, str(status) if status is not None else None)
        projection = await self._meal_plan_client.get_shopping_projection(meal_plan_uuid, tenant_uri)
        generated = self._list_from_projection(projection, name=name or self._default_name(meal_plan, projection))
        return await self.create(generated)

    async def generate_from_period(
        self,
        date_start: date,
        date_end: date,
        name: str | None = None,
        tenant_uri: str | None = None,
    ) -> ShoppingList:
        if self._meal_plan_client is None:
            raise RuntimeError("MealPlanClient is required to generate a shopping list")
        projection = await self._meal_plan_client.get_calendar_shopping_projection(date_start, date_end, tenant_uri)
        generated = self._list_from_period_projection(
            [projection],
            date_start=date_start,
            date_end=date_end,
            name=name or f"Courses {date_start.isoformat()} - {date_end.isoformat()}",
        )
        return await self.create(generated)

    async def refresh_from_meal_plan(
        self,
        uuid: UUID,
        expected_version: int,
        tenant_uri: str | None = None,
    ) -> ShoppingList:
        existing = await self._get_existing(uuid)
        self._assert_version(existing, expected_version)
        if self._meal_plan_client is None:
            raise RuntimeError("MealPlanClient is required to refresh a shopping list")
        if existing.meal_plan_uuid is not None:
            projection = await self._meal_plan_client.get_shopping_projection(existing.meal_plan_uuid, tenant_uri)
            regenerated = self._list_from_projection(projection, name=existing.name)
        elif existing.period_start is not None and existing.period_end is not None:
            regenerated = await self._build_period_list(existing.period_start, existing.period_end, existing.name, tenant_uri)
        else:
            raise ValueError("Shopping list is not linked to a meal plan or period")
        return await self._merge_refresh(existing, regenerated)

    async def _merge_refresh(self, existing: ShoppingList, regenerated: ShoppingList) -> ShoppingList:
        previous_by_key = {
            item.source_key: item
            for item in existing.items
            if item.source_key is not None and not item.manual
        }
        merged_generated: list[ShoppingItem] = []
        for item in regenerated.items:
            previous = previous_by_key.get(item.source_key) if item.source_key is not None else None
            if previous is not None:
                item = item.model_copy(
                    update={
                        "uuid": previous.uuid,
                        "checked": previous.checked,
                        "supplier_uuid": previous.supplier_uuid,
                        "note": previous.note,
                    },
                )
            merged_generated.append(item)
        manual_items = [item for item in existing.items if item.manual]
        updated = existing.model_copy(
            update={
                "period_start": regenerated.period_start,
                "period_end": regenerated.period_end,
                "generated_at": regenerated.generated_at,
                "meal_plan_uuid": regenerated.meal_plan_uuid,
                "source_meal_plan_uuids": regenerated.source_meal_plan_uuids,
                "items": [*merged_generated, *manual_items],
                "warnings": regenerated.warnings,
            },
        )
        return await self.update(updated.model_copy(update={"status": self._status_after_items(updated)}))

    async def add_manual_item(self, uuid: UUID, item: ShoppingItem, expected_version: int) -> ShoppingList:
        existing = await self._get_existing(uuid)
        self._assert_version(existing, expected_version)
        manual = item.model_copy(update={"manual": True, "source_key": None, "lines": []})
        updated = existing.model_copy(update={"items": [*existing.items, manual]})
        return await self.update(updated.model_copy(update={"status": self._status_after_items(updated)}))

    async def update_item(
        self,
        uuid: UUID,
        item_uuid: StdUUID,
        expected_version: int,
        changes: dict[str, object],
    ) -> ShoppingList:
        existing = await self._get_existing(uuid)
        self._assert_version(existing, expected_version)
        updated_items: list[ShoppingItem] = []
        found = False
        for item in existing.items:
            if item.uuid == item_uuid:
                found = True
                candidate = item.model_copy(update=changes)
                updated_items.append(ShoppingItem.model_validate(candidate.model_dump()))
            else:
                updated_items.append(item)
        if not found:
            raise ShoppingItemNotFound(item_uuid)
        updated = existing.model_copy(update={"items": updated_items})
        return await self.update(updated.model_copy(update={"status": self._status_after_items(updated)}))

    async def remove_item(self, uuid: UUID, item_uuid: StdUUID, expected_version: int) -> ShoppingList:
        existing = await self._get_existing(uuid)
        self._assert_version(existing, expected_version)
        remaining = [item for item in existing.items if item.uuid != item_uuid]
        if len(remaining) == len(existing.items):
            raise ShoppingItemNotFound(item_uuid)
        updated = existing.model_copy(update={"items": remaining})
        return await self.update(updated.model_copy(update={"status": self._status_after_items(updated)}))

    async def update_with_expected(self, uuid: UUID, payload: ShoppingList, expected_version: int) -> ShoppingList:
        existing = await self._get_existing(uuid)
        self._assert_version(existing, expected_version)
        updated = payload.model_copy(
            update={
                "uuid": existing.uuid,
                "created_at": existing.created_at,
                "created_by": existing.created_by,
                "updated_at": existing.updated_at,
                "updated_by": existing.updated_by,
                "version": existing.version,
            },
        )
        return await self.update(updated)

    async def delete_with_expected(self, uuid: UUID, expected_version: int) -> None:
        existing = await self._get_existing(uuid)
        self._assert_version(existing, expected_version)
        await self.delete(existing.uuid)

    async def export_text(
        self,
        uuid: UUID,
        *,
        item_uuids: list[StdUUID] | None = None,
        rayon: str | None = None,
        supplier_uuid: StdUUID | None = None,
        include_checked: bool = True,
    ) -> dict[str, str | int]:
        shopping_list = await self._get_existing(uuid)
        selected = self._filter_items(
            shopping_list.items,
            item_uuids=item_uuids,
            rayon=rayon,
            supplier_uuid=supplier_uuid,
            include_checked=include_checked,
        )
        lines = [shopping_list.name, ""]
        current_group: tuple[str, str] | None = None
        for item in sorted(selected, key=lambda i: (str(i.supplier_uuid or ""), i.rayon or "", i.name.lower())):
            group = (str(item.supplier_uuid or "Sans fournisseur"), item.rayon or "Sans rayon")
            if group != current_group:
                current_group = group
                lines.extend([f"[{group[0]} / {group[1]}]"])
            marker = "x" if item.checked else " "
            quantity = self._format_quantity(item)
            lines.append(f"- [{marker}] {item.name}{quantity}")
        return {"text": "\n".join(lines).strip(), "item_count": len(selected)}

    async def analyze(self, uuid: UUID) -> dict[str, object]:
        shopping_list = await self._get_existing(uuid)
        names: dict[str, list[ShoppingItem]] = {}
        for item in shopping_list.items:
            names.setdefault(item.name.casefold(), []).append(item)
        duplicates = [
            {"name": items[0].name, "item_uuids": [str(item.uuid) for item in items]}
            for items in names.values()
            if len(items) > 1
        ]
        return {
            "warnings": [warning.model_dump(mode="json") for warning in shopping_list.warnings],
            "duplicates": duplicates,
            "checked_count": sum(1 for item in shopping_list.items if item.checked),
            "items_count": len(shopping_list.items),
        }

    async def _get_existing(self, uuid: UUID) -> ShoppingList:
        existing = await self.read(uuid)
        if existing is None:
            raise ShoppingListNotFound(uuid)
        return existing

    def _list_from_projection(self, projection: ShoppingProjection, name: str) -> ShoppingList:
        warnings = [
            ShoppingListWarning(
                code=warning.code,
                ingredient_uuid=warning.ingredient_uuid,
                details=warning.details,
            )
            for warning in projection.warnings
        ]
        if not projection.ingredients:
            warnings.append(ShoppingListWarning(code=ShoppingWarningCode.EMPTY_PROJECTION, details="No ingredient found"))
        return ShoppingList(
            name=name,
            status=self._status_after_generation(warnings),
            meal_plan_uuid=projection.meal_plan_uuid,
            source_meal_plan_uuids=[projection.meal_plan_uuid],
            period_start=projection.period.start,
            period_end=projection.period.end,
            generated_at=datetime.now(timezone.utc),
            items=[self._item_from_projection_ingredient(item) for item in projection.ingredients],
            warnings=warnings,
        )

    async def _build_period_list(
        self,
        date_start: date,
        date_end: date,
        name: str,
        tenant_uri: str | None,
    ) -> ShoppingList:
        if self._meal_plan_client is None:
            raise RuntimeError("MealPlanClient is required to generate a shopping list")
        projection = await self._meal_plan_client.get_calendar_shopping_projection(date_start, date_end, tenant_uri)
        return self._list_from_period_projection([projection], date_start=date_start, date_end=date_end, name=name)

    def _list_from_period_projection(
        self,
        projections: list[ShoppingProjection],
        *,
        date_start: date,
        date_end: date,
        name: str,
    ) -> ShoppingList:
        items_by_key: dict[str, ShoppingItem] = {}
        source_meal_plan_uuids: list[StdUUID] = []
        for projection in projections:
            source_meal_plan_uuids.append(projection.meal_plan_uuid)
            for ingredient in projection.ingredients:
                clipped = self._clip_projection_ingredient(ingredient, projection, date_start, date_end)
                if clipped is None:
                    continue
                item = self._item_from_projection_ingredient(clipped)
                if item.source_key is None or item.source_key not in items_by_key:
                    if item.source_key is not None:
                        items_by_key[item.source_key] = item
                    continue
                existing = items_by_key[item.source_key]
                items_by_key[item.source_key] = existing.model_copy(
                    update={
                        "quantity": (existing.quantity or 0) + (item.quantity or 0),
                        "lines": [*existing.lines, *item.lines],
                    },
                )
        items = list(items_by_key.values())
        warnings = self._warnings_for_items(items)
        if not items:
            warnings.append(ShoppingListWarning(code=ShoppingWarningCode.EMPTY_PROJECTION, details="No ingredient found"))
        return ShoppingList(
            name=name,
            status=self._status_after_generation(warnings),
            meal_plan_uuid=None,
            source_meal_plan_uuids=source_meal_plan_uuids,
            period_start=date_start,
            period_end=date_end,
            generated_at=datetime.now(timezone.utc),
            items=items,
            warnings=warnings,
        )

    @staticmethod
    def _clip_projection_ingredient(
        ingredient: ShoppingProjectionIngredient,
        projection: ShoppingProjection,
        date_start: date,
        date_end: date,
    ) -> ShoppingProjectionIngredient | None:
        lines = [
            line
            for line in ingredient.lines
            if line.slot_date is not None and date_start <= line.slot_date <= date_end
        ]
        if lines:
            quantity = sum(line.scaled_quantity for line in lines)
            return ingredient.model_copy(
                update={
                    "lines": lines,
                    "aggregated": ingredient.aggregated.model_copy(update={"quantity": quantity}),
                },
            )
        if not ingredient.lines and date_start <= projection.period.start and projection.period.end <= date_end:
            return ingredient
        return None

    @staticmethod
    def _warnings_for_items(items: list[ShoppingItem]) -> list[ShoppingListWarning]:
        units_by_ingredient: dict[StdUUID, set[str]] = {}
        for item in items:
            if item.ingredient_uuid is not None and item.unit:
                units_by_ingredient.setdefault(item.ingredient_uuid, set()).add(item.unit)
        return [
            ShoppingListWarning(
                code=ShoppingWarningCode.UNIT_MISMATCH,
                ingredient_uuid=ingredient_uuid,
                details=" vs ".join(sorted(units)),
            )
            for ingredient_uuid, units in units_by_ingredient.items()
            if len(units) > 1
        ]

    @staticmethod
    def _item_from_projection_ingredient(ingredient: ShoppingProjectionIngredient) -> ShoppingItem:
        unit = ingredient.aggregated.unit.strip()
        source_key = f"{ingredient.ingredient_uuid}:{unit.casefold()}"
        return ShoppingItem(
            name=ingredient.name or str(ingredient.ingredient_uuid),
            ingredient_uuid=ingredient.ingredient_uuid,
            quantity=ingredient.aggregated.quantity,
            unit=unit,
            rayon=ingredient.rayon,
            group=ingredient.group,
            supplier_uuid=ingredient.supplier_uuid,
            note=None,
            manual=False,
            source_key=source_key,
            lines=[
                ShoppingSourceLine(
                    source_type=line.source_type,
                    source_uuid=line.source_uuid,
                    slot_date=line.slot_date,
                    slot_code=line.slot_code,
                    scaled_quantity=line.scaled_quantity,
                    unit=line.unit,
                    scale_factor=line.scale_factor,
                )
                for line in ingredient.lines
            ],
        )

    @staticmethod
    def _status_after_generation(warnings: list[ShoppingListWarning]) -> ShoppingListStatus:
        return ShoppingListStatus.TO_CHECK if warnings else ShoppingListStatus.VALIDATED

    @staticmethod
    def _status_after_items(shopping_list: ShoppingList) -> ShoppingListStatus:
        if not shopping_list.items:
            return shopping_list.status
        if all(item.checked for item in shopping_list.items):
            return ShoppingListStatus.DONE
        if any(item.checked for item in shopping_list.items):
            return ShoppingListStatus.IN_PROGRESS
        if shopping_list.warnings:
            return ShoppingListStatus.TO_CHECK
        return ShoppingListStatus.VALIDATED

    @staticmethod
    def _assert_version(entity: ShoppingList, expected_version: int) -> None:
        if entity.version != expected_version:
            raise VersionConflict(expected_version, entity.version)

    @staticmethod
    def _default_name(meal_plan: dict[str, object], projection: ShoppingProjection) -> str:
        plan_name = meal_plan.get("name")
        if isinstance(plan_name, str) and plan_name.strip():
            return f"Courses - {plan_name.strip()}"
        return f"Courses {projection.period.start.isoformat()} - {projection.period.end.isoformat()}"

    @staticmethod
    def _filter_items(
        items: list[ShoppingItem],
        *,
        item_uuids: list[StdUUID] | None,
        rayon: str | None,
        supplier_uuid: StdUUID | None,
        include_checked: bool,
    ) -> list[ShoppingItem]:
        wanted = set(item_uuids) if item_uuids is not None else None
        normalized_rayon = rayon.casefold() if rayon else None
        return [
            item
            for item in items
            if _matches_item_filters(
                item,
                wanted=wanted,
                normalized_rayon=normalized_rayon,
                supplier_uuid=supplier_uuid,
                include_checked=include_checked,
            )
        ]

    @staticmethod
    def _format_quantity(item: ShoppingItem) -> str:
        if item.quantity is None:
            return ""
        quantity_value = float(item.quantity)
        quantity = int(quantity_value) if quantity_value.is_integer() else round(quantity_value, 2)
        unit = f" {item.unit}" if item.unit else ""
        return f" - {quantity}{unit}"
