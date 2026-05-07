from arclith.adapters.output.memory.repository import InMemoryRepository
from domain.models.supplier import Supplier
from domain.ports.output.supplier_repository import SupplierRepository


class InMemorySupplierRepository(InMemoryRepository[Supplier], SupplierRepository):
    async def find_by_name(self, name: str) -> list[Supplier]:
        return [item for item in self._store.values() if name.lower() in item.name.lower() and not item.is_deleted]

    async def find_page_by_name(
        self,
        name: str,
        offset: int = 0,
        limit: int | None = None,
    ) -> tuple[list[Supplier], int]:
        filtered = [item for item in self._store.values() if name.lower() in item.name.lower() and not item.is_deleted]
        total = len(filtered)
        page = filtered[offset: offset + limit] if limit is not None else filtered[offset:]
        return page, total
