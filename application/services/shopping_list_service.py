from application.use_cases import FindByNameUseCase
from arclith import BaseService, Logger
from domain.models.shopping_list import ShoppingList
from domain.ports.output.shopping_list_repository import ShoppingListRepository


class ShoppingListService(BaseService[ShoppingList]):
    def __init__(self, repository: ShoppingListRepository, logger: Logger, retention_days: float | None = None) -> None:
        super().__init__(repository, logger, retention_days)
        self._shopping_list_repo = repository
        self._find_by_name_uc = FindByNameUseCase(repository, logger)

    async def find_by_name(self, name: str) -> list[ShoppingList]:
        return await self._find_by_name_uc.execute(name)

    async def find_page_filtered(self, name: str | None = None, offset: int = 0, limit: int | None = None) -> tuple[list[ShoppingList], int]:
        """Return a page of shopping_lists (optionally filtered by name) and total count."""
        if name:
            return await self._shopping_list_repo.find_page_by_name(name, offset, limit)
        return await self._shopping_list_repo.find_page(offset, limit)

