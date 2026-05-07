from uuid import UUID
from datetime import date

from domain.exceptions import MealPlanIntegrationError
from domain.models.shopping_projection import ShoppingProjection
from domain.ports.output.meal_plan_client import MealPlanClient


class StaticMealPlanClient(MealPlanClient):
    async def get_meal_plan(self, meal_plan_uuid: UUID, tenant_uri: str | None = None) -> dict[str, object]:
        raise MealPlanIntegrationError("MEAL_PLANNER_BASE_URL is required to generate shopping lists")

    async def get_shopping_projection(
        self,
        meal_plan_uuid: UUID,
        tenant_uri: str | None = None,
    ) -> ShoppingProjection:
        raise MealPlanIntegrationError("MEAL_PLANNER_BASE_URL is required to generate shopping lists")

    async def get_calendar_shopping_projection(
        self,
        date_start: date,
        date_end: date,
        tenant_uri: str | None = None,
    ) -> ShoppingProjection:
        raise MealPlanIntegrationError("MEAL_PLANNER_BASE_URL is required to generate shopping lists")

    async def list_confirmed_meal_plans(
        self,
        date_start: date,
        date_end: date,
        tenant_uri: str | None = None,
    ) -> list[dict[str, object]]:
        raise MealPlanIntegrationError("MEAL_PLANNER_BASE_URL is required to generate shopping lists")
