from abc import ABC, abstractmethod
from datetime import date
from uuid import UUID

from domain.models.shopping_projection import ShoppingProjection


class MealPlanClient(ABC):
    @abstractmethod
    async def get_meal_plan(self, meal_plan_uuid: UUID, tenant_uri: str | None = None) -> dict[str, object]:
        pass

    @abstractmethod
    async def get_shopping_projection(
        self,
        meal_plan_uuid: UUID,
        tenant_uri: str | None = None,
    ) -> ShoppingProjection:
        pass

    @abstractmethod
    async def get_calendar_shopping_projection(
        self,
        date_start: date,
        date_end: date,
        tenant_uri: str | None = None,
    ) -> ShoppingProjection:
        pass

    @abstractmethod
    async def list_confirmed_meal_plans(
        self,
        date_start: date,
        date_end: date,
        tenant_uri: str | None = None,
    ) -> list[dict[str, object]]:
        pass
