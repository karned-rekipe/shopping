from typing import Any
from datetime import date
from uuid import UUID

import httpx

from domain.exceptions import MealPlanIntegrationError
from domain.models.shopping_projection import ShoppingProjection
from domain.ports.output.meal_plan_client import MealPlanClient


class MealPlanHttpClient(MealPlanClient):
    def __init__(self, base_url: str, api_token: str | None = None) -> None:
        normalized = base_url.rstrip("/")
        self._base_url = normalized if normalized.endswith("/v1") else f"{normalized}/v1"
        self._api_token = api_token

    async def get_meal_plan(self, meal_plan_uuid: UUID, tenant_uri: str | None = None) -> dict[str, object]:
        payload = await self._get_json(f"/meal-plans/{meal_plan_uuid}", tenant_uri)
        data = payload.get("data")
        if not isinstance(data, dict):
            raise MealPlanIntegrationError(f"MealPlan {meal_plan_uuid} response is invalid")
        return data

    async def get_shopping_projection(
        self,
        meal_plan_uuid: UUID,
        tenant_uri: str | None = None,
    ) -> ShoppingProjection:
        payload = await self._get_json(f"/meal-plans/{meal_plan_uuid}/shopping-projection", tenant_uri)
        data = payload.get("data")
        if not isinstance(data, dict):
            raise MealPlanIntegrationError(f"Shopping projection for MealPlan {meal_plan_uuid} is invalid")
        return ShoppingProjection.model_validate(data)

    async def get_calendar_shopping_projection(
        self,
        date_start: date,
        date_end: date,
        tenant_uri: str | None = None,
    ) -> ShoppingProjection:
        payload = await self._get_json(
            f"/meal-plans/calendar/shopping-projection?date_from={date_start.isoformat()}&date_to={date_end.isoformat()}",
            tenant_uri,
        )
        data = payload.get("data")
        if not isinstance(data, dict):
            raise MealPlanIntegrationError("Calendar shopping projection response is invalid")
        return ShoppingProjection.model_validate(data)

    async def list_confirmed_meal_plans(
        self,
        date_start: date,
        date_end: date,
        tenant_uri: str | None = None,
    ) -> list[dict[str, object]]:
        payload = await self._get_json(
            f"/meal-plans/?status=confirmed&date_from={date_start.isoformat()}&date_to={date_end.isoformat()}&page_size=100",
            tenant_uri,
        )
        data = payload.get("data")
        if not isinstance(data, list):
            raise MealPlanIntegrationError("Confirmed meal plan list response is invalid")
        return [item for item in data if isinstance(item, dict)]

    async def _get_json(self, path: str, tenant_uri: str | None) -> dict[str, Any]:
        async with httpx.AsyncClient(timeout=8.0) as client:
            response = await client.get(f"{self._base_url}{path}", headers=self._headers(tenant_uri))
        if response.status_code == 404:
            raise MealPlanIntegrationError(f"Meal-planner resource not found at {path}")
        if response.status_code >= 400:
            raise MealPlanIntegrationError(f"Meal-planner returned HTTP {response.status_code} at {path}")
        payload = response.json()
        if not isinstance(payload, dict):
            raise MealPlanIntegrationError(f"Meal-planner response at {path} is invalid")
        return payload

    def _headers(self, tenant_uri: str | None) -> dict[str, str]:
        headers: dict[str, str] = {}
        if tenant_uri:
            headers["X-Tenant-URI"] = tenant_uri
        if self._api_token:
            headers["Authorization"] = f"Bearer {self._api_token}"
        return headers
