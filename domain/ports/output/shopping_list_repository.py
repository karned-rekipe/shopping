from abc import abstractmethod
from uuid import UUID

from arclith.domain.ports.repository import Repository
from domain.models.shopping_list import ShoppingList


class ShoppingListRepository(Repository[ShoppingList]):
    @abstractmethod
    async def find_by_name(self, name: str) -> list[ShoppingList]:
        pass

    @abstractmethod
    async def find_page_by_name(self, name: str, offset: int = 0, limit: int | None = None) -> tuple[list[ShoppingList], int]:
        """Return a page of shopping_lists matching name filter and the total count."""
        pass

    @abstractmethod
    async def find_by_meal_plan(self, meal_plan_uuid: UUID) -> list[ShoppingList]:
        pass
