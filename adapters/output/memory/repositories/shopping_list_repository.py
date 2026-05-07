from uuid import UUID

from arclith.adapters.output.memory.repository import InMemoryRepository
from domain.models.shopping_list import ShoppingList
from domain.ports.output.shopping_list_repository import ShoppingListRepository


class InMemoryShoppingListRepository(InMemoryRepository[ShoppingList], ShoppingListRepository):
    async def find_page(self, offset: int = 0, limit: int | None = None) -> tuple[list[ShoppingList], int]:
        filtered = [item for item in self._store.values() if not item.is_deleted]
        filtered.sort(key=lambda item: (item.created_at, item.uuid), reverse=True)
        total = len(filtered)
        page = filtered[offset: offset + limit] if limit is not None else filtered[offset:]
        return page, total

    async def find_by_name(self, name: str) -> list[ShoppingList]:
        return [i for i in self._store.values() if name.lower() in i.name.lower() and not i.is_deleted]

    async def find_page_by_name(self, name: str, offset: int = 0, limit: int | None = None) -> tuple[list[ShoppingList], int]:
        filtered = [i for i in self._store.values() if name.lower() in i.name.lower() and not i.is_deleted]
        filtered.sort(key=lambda item: (item.created_at, item.uuid), reverse=True)
        total = len(filtered)
        page = filtered[offset: offset + limit] if limit is not None else filtered[offset:]
        return page, total

    async def find_by_meal_plan(self, meal_plan_uuid: UUID) -> list[ShoppingList]:
        return [item for item in self._store.values() if item.meal_plan_uuid == meal_plan_uuid and not item.is_deleted]
