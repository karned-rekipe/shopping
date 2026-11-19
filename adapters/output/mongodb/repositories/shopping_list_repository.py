import re
from collections.abc import Mapping, Sequence
from typing import Any, cast
from uuid import UUID

from arclith.adapters.output.mongodb.config import MongoDBConfig
from arclith.adapters.output.mongodb.repository import MongoDBRepository
from arclith.domain.ports.logger import Logger
from domain.models.shopping_list import ShoppingList
from domain.ports.output.shopping_list_repository import ShoppingListRepository


class MongoDBShoppingListRepository(MongoDBRepository[ShoppingList], ShoppingListRepository):
    def __init__(self, config: MongoDBConfig, logger: Logger) -> None:
        super().__init__(config, ShoppingList, logger)

    def _to_doc(self, entity: ShoppingList) -> dict[str, Any]:
        doc = entity.model_dump(mode="json")
        doc["_id"] = str(doc.pop("uuid"))
        return doc

    async def find_page(self, offset: int = 0, limit: int | None = None) -> tuple[list[ShoppingList], int]:
        return await self._find_page_by_match({"deleted_at": None}, offset, limit)

    async def find_by_name(self, name: str) -> list[ShoppingList]:
        async with self._collection() as col:
            escaped_name = re.escape(name)
            return [
                self._from_doc(doc)
                async for doc in col.find(
                    {"name": {"$regex": escaped_name, "$options": "i"}, "deleted_at": None}
                )
            ]

    async def find_page_by_name(self, name: str, offset: int = 0, limit: int | None = None) -> tuple[list[ShoppingList], int]:
        """Single-query pagination with name filter via $facet."""
        escaped_name = re.escape(name)
        return await self._find_page_by_match(
            {"name": {"$regex": escaped_name, "$options": "i"}, "deleted_at": None},
            offset,
            limit,
        )

    async def _find_page_by_match(
        self,
        match: dict[str, Any],
        offset: int = 0,
        limit: int | None = None,
    ) -> tuple[list[ShoppingList], int]:
        data_pipeline: list[dict[str, int]] = [{"$skip": offset}]
        if limit is not None:
            data_pipeline.append({"$limit": limit})
        pipeline: Sequence[Mapping[str, Any]] = cast(
            Sequence[Mapping[str, Any]],
            [
                {"$match": match},
                {"$sort": {"created_at": -1, "_id": -1}},
                {
                    "$facet": {
                        "data": data_pipeline,
                        "total": [{"$count": "count"}],
                    },
                },
            ],
        )
        async with self._collection() as col:
            result = await col.aggregate(pipeline).to_list(length=1)
        if not result:
            return [], 0
        facet = result[0]
        items = [self._from_doc(doc) for doc in facet.get("data", [])]
        total = facet["total"][0]["count"] if facet.get("total") else 0
        return items, total

    async def find_by_meal_plan(self, meal_plan_uuid: UUID) -> list[ShoppingList]:
        async with self._collection() as col:
            return [
                self._from_doc(doc)
                async for doc in col.find({"meal_plan_uuid": str(meal_plan_uuid), "deleted_at": None})
            ]
