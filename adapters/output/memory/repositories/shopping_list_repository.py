from arclith.adapters.output.memory.repository import InMemoryRepository
from domain.models.shopping_list import ShoppingList
from domain.ports.output.shopping_list_repository import ShoppingListRepository


class InMemoryShoppingListRepository(InMemoryRepository[ShoppingList], ShoppingListRepository):
    async def find_by_name(self, name: str) -> list[ShoppingList]:
        return [i for i in self._store.values() if name.lower() in i.name.lower() and not i.is_deleted]

    async def find_page_by_name(self, name: str, offset: int = 0, limit: int | None = None) -> tuple[list[ShoppingList], int]:
        filtered = [i for i in self._store.values() if name.lower() in i.name.lower() and not i.is_deleted]
        total = len(filtered)
        page = filtered[offset: offset + limit] if limit is not None else filtered[offset:]
        return page, total
