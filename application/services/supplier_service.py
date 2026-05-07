from arclith import BaseService, Logger
from domain.models.supplier import Supplier
from domain.ports.output.supplier_repository import SupplierRepository


class SupplierService(BaseService[Supplier]):
    def __init__(self, repository: SupplierRepository, logger: Logger, retention_days: float | None = None) -> None:
        super().__init__(repository, logger, retention_days)
        self._supplier_repo = repository

    async def find_by_name(self, name: str) -> list[Supplier]:
        self._logger.info("Finding suppliers by name", name=name)
        return [supplier for supplier in await self._supplier_repo.find_by_name(name) if not supplier.is_deleted]

    async def find_page_filtered(
        self,
        name: str | None = None,
        offset: int = 0,
        limit: int | None = None,
    ) -> tuple[list[Supplier], int]:
        if name:
            return await self._supplier_repo.find_page_by_name(name, offset, limit)
        return await self._supplier_repo.find_page(offset, limit)
