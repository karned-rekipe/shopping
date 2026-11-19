from abc import abstractmethod

from arclith.domain.ports.repository import Repository
from domain.models.supplier import Supplier


class SupplierRepository(Repository[Supplier]):
    @abstractmethod
    async def find_by_name(self, name: str) -> list[Supplier]:
        pass

    @abstractmethod
    async def find_page_by_name(
        self,
        name: str,
        offset: int = 0,
        limit: int | None = None,
    ) -> tuple[list[Supplier], int]:
        pass
