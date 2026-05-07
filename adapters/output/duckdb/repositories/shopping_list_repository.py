import json
from datetime import date, datetime
from typing import Any
from uuid import UUID

from arclith.adapters.output.duckdb.repository import DuckDBRepository
from domain.models.shopping_list import ShoppingList
from domain.ports.output.shopping_list_repository import ShoppingListRepository


class DuckDBShoppingListRepository(DuckDBRepository[ShoppingList], ShoppingListRepository):
    def __init__(self, path: str) -> None:
        super().__init__(path, ShoppingList)

    def _row_to_entity(self, row: dict[str, Any]) -> ShoppingList:
        decoded = dict(row)
        for key in ("items", "warnings"):
            value = decoded.get(key)
            if isinstance(value, str) and value:
                decoded[key] = json.loads(value)
            elif value in (None, ""):
                decoded[key] = []
        return super()._row_to_entity(decoded)

    def _entity_to_row(self, entity: ShoppingList) -> dict[str, Any]:
        row = entity.model_dump(mode="json")
        for key in ("items", "warnings"):
            row[key] = json.dumps(row[key], ensure_ascii=False)
        for key, value in row.items():
            if isinstance(value, UUID):
                row[key] = str(value)
            elif isinstance(value, (datetime, date)):
                row[key] = value.isoformat()
        return row

    # noinspection SqlNoDataSourceInspection
    async def find_page(self, offset: int = 0, limit: int | None = None) -> tuple[list[ShoppingList], int]:
        limit_clause = f"LIMIT {limit}" if limit is not None else ""
        rows = self._fetch(
            f"SELECT *, COUNT(*) OVER () AS __total FROM {self._table} "  # nosec B608
            f"WHERE deleted_at IS NULL "
            f"ORDER BY created_at DESC OFFSET {offset} {limit_clause}",
            [],
        )
        total = int(rows[0]["__total"]) if rows else 0
        return [self._row_to_entity({k: v for k, v in row.items() if k != "__total"}) for row in rows], total

    # noinspection SqlNoDataSourceInspection
    async def find_by_name(self, name: str) -> list[ShoppingList]:
        rows = self._fetch(
            f"SELECT * FROM {self._table} WHERE deleted_at IS NULL AND lower(name) LIKE ?",  # nosec B608
            [f"%{name.lower()}%"],
        )
        return [self._row_to_entity(r) for r in rows]

    # noinspection SqlNoDataSourceInspection
    async def find_page_by_name(self, name: str, offset: int = 0, limit: int | None = None) -> tuple[list[ShoppingList], int]:
        """Single-query pagination with name filter via window function."""
        limit_clause = f"LIMIT {limit}" if limit is not None else ""
        rows = self._fetch(
            f"SELECT *, COUNT(*) OVER () AS __total FROM {self._table} "  # nosec B608
            f"WHERE deleted_at IS NULL AND lower(name) LIKE ? "
            f"ORDER BY created_at DESC OFFSET {offset} {limit_clause}",
            [f"%{name.lower()}%"],
        )
        total = int(rows[0]["__total"]) if rows else 0
        return [self._row_to_entity({k: v for k, v in r.items() if k != "__total"}) for r in rows], total

    async def find_by_meal_plan(self, meal_plan_uuid: UUID) -> list[ShoppingList]:
        rows = self._fetch(
            f"SELECT * FROM {self._table} WHERE deleted_at IS NULL AND meal_plan_uuid = ?",  # nosec B608
            [str(meal_plan_uuid)],
        )
        return [self._row_to_entity(row) for row in rows]
