from arclith.domain.ports.logger import Logger
from domain.models.shopping_list import ShoppingList
from domain.ports.output.shopping_list_repository import ShoppingListRepository


class FindByNameUseCase:
    def __init__(self, repository: ShoppingListRepository, logger: Logger) -> None:
        self._repository = repository
        self._logger = logger

    async def execute(self, name: str) -> list[ShoppingList]:
        self._logger.info("🔍 Finding shopping_lists by name", name=name)
        result = [i for i in await self._repository.find_by_name(name) if not i.is_deleted]
        self._logger.info("✅ ShoppingLists found", name=name, count=len(result))
        return result

