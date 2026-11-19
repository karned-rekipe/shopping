from datetime import date, datetime, timezone
from uuid import UUID

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from adapters.input.fastapi.dependencies import inject_tenant_uri, require_auth
from adapters.input.fastapi.routers import AdminRouter, ShoppingListRouter
from application.services.shopping_list_service import ShoppingListService
from domain.models.shopping_projection import ShoppingProjection
from domain.ports.output.meal_plan_client import MealPlanClient
from infrastructure.purge_registry import PurgeRegistry

MEAL_PLAN_UUID = UUID("01951234-5678-7abc-def0-000000000111")
TOMATO_UUID = UUID("01951234-5678-7abc-def0-000000000001")
PASTA_UUID = UUID("01951234-5678-7abc-def0-000000000002")
SUPPLIER_UUID = UUID("01951234-5678-7abc-def0-000000000003")


class FakeMealPlanClient(MealPlanClient):
    def __init__(self, status: str = "confirmed") -> None:
        self.status = status
        self.tomato_quantity = 300.0

    async def get_meal_plan(self, meal_plan_uuid: UUID, tenant_uri: str | None = None) -> dict[str, object]:
        return {"uuid": str(meal_plan_uuid), "name": "Semaine test", "status": self.status}

    async def list_confirmed_meal_plans(
        self,
        date_start: date,
        date_end: date,
        tenant_uri: str | None = None,
    ) -> list[dict[str, object]]:
        if self.status != "confirmed":
            return []
        return [{"uuid": str(MEAL_PLAN_UUID), "name": "Semaine test", "status": "confirmed"}]

    async def get_shopping_projection(
        self,
        meal_plan_uuid: UUID,
        tenant_uri: str | None = None,
    ) -> ShoppingProjection:
        return self._projection(meal_plan_uuid)

    async def get_calendar_shopping_projection(
        self,
        date_start: date,
        date_end: date,
        tenant_uri: str | None = None,
    ) -> ShoppingProjection:
        return self._projection(MEAL_PLAN_UUID)

    def _projection(self, meal_plan_uuid: UUID) -> ShoppingProjection:
        return ShoppingProjection.model_validate(
            {
                "meal_plan_uuid": str(meal_plan_uuid),
                "period": {"start": "2026-04-27", "end": "2026-05-03"},
                "generated_at": datetime.now(timezone.utc).isoformat(),
                "totals": {"headcount_days": 8, "ingredients_count": 3, "groups_count": 2},
                "ingredients": [
                    {
                        "ingredient_uuid": str(TOMATO_UUID),
                        "name": "Tomates",
                        "group": "Légumes",
                        "rayon": "Primeur",
                        "supplier_uuid": str(SUPPLIER_UUID),
                        "season_months": [6, 7, 8],
                        "aggregated": {"quantity": self.tomato_quantity, "unit": "g"},
                        "lines": [
                            {
                                "source_type": "recipe",
                                "source_uuid": "01951234-5678-7abc-def0-000000001001",
                                "slot_date": "2026-04-27",
                                "slot_code": "dinner",
                                "scaled_quantity": self.tomato_quantity,
                                "unit": "g",
                                "scale_factor": 1.0,
                            }
                        ],
                    },
                    {
                        "ingredient_uuid": str(TOMATO_UUID),
                        "name": "Tomates",
                        "group": "Légumes",
                        "rayon": "Primeur",
                        "season_months": [6, 7, 8],
                        "aggregated": {"quantity": 2.0, "unit": "piece"},
                        "lines": [],
                    },
                    {
                        "ingredient_uuid": str(PASTA_UUID),
                        "name": "Pâtes",
                        "group": "Épicerie",
                        "rayon": "Sec",
                        "season_months": [],
                        "aggregated": {"quantity": 500.0, "unit": "g"},
                        "lines": [],
                    },
                ],
                "warnings": [
                    {
                        "code": "unit_mismatch",
                        "ingredient_uuid": str(TOMATO_UUID),
                        "details": "g vs piece",
                    }
                ],
            }
        )


def _payload(**kwargs) -> dict:
    return {"name": "Courses libres", **kwargs}


def _etag(response) -> str:
    return response.headers["etag"]


@pytest.fixture
def meal_plan_client() -> FakeMealPlanClient:
    return FakeMealPlanClient()


@pytest.fixture
def service(repo, logger, meal_plan_client):
    return ShoppingListService(repo, logger, meal_plan_client=meal_plan_client)


@pytest.fixture
def app(service, logger):
    fastapi_app = FastAPI()
    registry = PurgeRegistry()
    registry.register("shopping_lists", service.purge)
    fastapi_app.include_router(ShoppingListRouter(service, logger).router)
    fastapi_app.include_router(AdminRouter(registry).router)
    fastapi_app.dependency_overrides[inject_tenant_uri] = lambda: None
    fastapi_app.dependency_overrides[require_auth] = lambda: {"sub": "test-user"}
    return fastapi_app


@pytest.fixture
async def client(app):
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        yield c


@pytest.fixture
async def created(client):
    response = await client.post("/v1/shopping-lists/", json=_payload())
    uuid = response.json()["data"]["uuid"]
    loaded = await client.get(f"/v1/shopping-lists/{uuid}")
    return loaded.json()["data"], _etag(loaded)


async def test_create_returns_201_and_uuid(client):
    response = await client.post("/v1/shopping-lists/", json=_payload())
    assert response.status_code == 201
    assert response.json()["status"] == "success"
    assert "uuid" in response.json()["data"]


async def test_get_found(client, created):
    data, _ = created
    response = await client.get(f"/v1/shopping-lists/{data['uuid']}")
    assert response.status_code == 200
    assert response.json()["data"]["name"] == "Courses libres"
    assert response.headers["etag"] == 'W/"1"'


async def test_get_not_found(client):
    response = await client.get("/v1/shopping-lists/01951234-5678-7abc-def0-000000000000")
    assert response.status_code == 404


async def test_update_requires_if_match(client, created):
    data, _ = created
    response = await client.put(f"/v1/shopping-lists/{data['uuid']}", json=_payload(name="Nouveau nom"))
    assert response.status_code == 412


async def test_update_reflects_on_get(client, created):
    data, etag = created
    response = await client.put(
        f"/v1/shopping-lists/{data['uuid']}",
        json={"name": "Nouveau nom", "status": "validated"},
        headers={"If-Match": etag},
    )
    assert response.status_code == 200
    assert response.json()["data"]["name"] == "Nouveau nom"
    assert response.headers["etag"] == 'W/"2"'


async def test_patch_updates_status(client, created):
    data, etag = created
    response = await client.patch(
        f"/v1/shopping-lists/{data['uuid']}",
        json={"status": "validated"},
        headers={"If-Match": etag},
    )
    assert response.status_code == 200
    assert response.json()["data"]["status"] == "validated"


async def test_delete_hides_from_get(client, created):
    data, etag = created
    response = await client.delete(f"/v1/shopping-lists/{data['uuid']}", headers={"If-Match": etag})
    assert response.status_code == 204
    response = await client.get(f"/v1/shopping-lists/{data['uuid']}")
    assert response.status_code == 404


async def test_list_returns_all(client):
    await client.post("/v1/shopping-lists/", json=_payload(name="Farine"))
    await client.post("/v1/shopping-lists/", json=_payload(name="Sel"))
    response = await client.get("/v1/shopping-lists/")
    assert response.status_code == 200
    assert len(response.json()["data"]) == 2
    assert response.headers.get("x-total-count") == "2"


async def test_list_filtered_by_name(client):
    await client.post("/v1/shopping-lists/", json=_payload(name="Farine de blé"))
    await client.post("/v1/shopping-lists/", json=_payload(name="Sel fin"))
    response = await client.get("/v1/shopping-lists/", params={"name": "farine"})
    assert len(response.json()["data"]) == 1
    assert response.json()["data"][0]["name"] == "Farine de blé"


async def test_create_from_confirmed_meal_plan_generates_items_and_warnings(client):
    response = await client.post(
        "/v1/shopping-lists/from-meal-plan",
        json={"meal_plan_uuid": str(MEAL_PLAN_UUID)},
    )
    data = response.json()["data"]
    assert response.status_code == 201
    assert data["status"] == "to_check"
    assert data["meal_plan_uuid"] == str(MEAL_PLAN_UUID)
    assert len(data["items"]) == 3
    assert data["warnings"][0]["code"] == "unit_mismatch"


async def test_create_from_draft_meal_plan_returns_422(client, meal_plan_client):
    meal_plan_client.status = "draft"
    response = await client.post(
        "/v1/shopping-lists/from-meal-plan",
        json={"meal_plan_uuid": str(MEAL_PLAN_UUID)},
    )
    assert response.status_code == 422


async def test_create_from_period_generates_period_list(client):
    response = await client.post(
        "/v1/shopping-lists/from-period",
        json={"date_start": "2026-04-27", "date_end": "2026-05-03"},
    )
    data = response.json()["data"]
    assert response.status_code == 201
    assert data["period_start"] == "2026-04-27"
    assert data["period_end"] == "2026-05-03"
    assert data["meal_plan_uuid"] is None
    assert data["source_meal_plan_uuids"] == [str(MEAL_PLAN_UUID)]
    assert len(data["items"]) == 3


async def test_create_from_period_uses_planning_calendar_even_when_plan_is_draft(client, meal_plan_client):
    meal_plan_client.status = "draft"
    response = await client.post(
        "/v1/shopping-lists/from-period",
        json={"date_start": "2026-04-27", "date_end": "2026-05-03"},
    )

    assert response.status_code == 201
    assert response.json()["data"]["source_meal_plan_uuids"] == [str(MEAL_PLAN_UUID)]


async def test_create_from_period_filters_outside_slot_lines(client):
    response = await client.post(
        "/v1/shopping-lists/from-period",
        json={"date_start": "2026-04-28", "date_end": "2026-04-28"},
    )
    data = response.json()["data"]
    assert response.status_code == 201
    assert all(item["name"] != "Tomates" or item["unit"] != "g" for item in data["items"])


async def test_add_manual_item(client, created):
    data, etag = created
    response = await client.post(
        f"/v1/shopping-lists/{data['uuid']}/items",
        json={"ingredient_uuid": str(PASTA_UUID), "name": "Torchons", "quantity": 2, "unit": "piece", "rayon": "Maison"},
        headers={"If-Match": etag},
    )
    item = response.json()["data"]["items"][0]
    assert response.status_code == 200
    assert item["manual"] is True
    assert item["ingredient_uuid"] == str(PASTA_UUID)
    assert item["name"] == "Torchons"


async def test_projection_supplier_is_applied_to_generated_item(client):
    response = await client.post(
        "/v1/shopping-lists/from-meal-plan",
        json={"meal_plan_uuid": str(MEAL_PLAN_UUID)},
    )
    item = next(item for item in response.json()["data"]["items"] if item["name"] == "Tomates" and item["unit"] == "g")
    assert item["supplier_uuid"] == str(SUPPLIER_UUID)


async def test_check_item_updates_status(client, meal_plan_client):
    generated = await client.post(
        "/v1/shopping-lists/from-meal-plan",
        json={"meal_plan_uuid": str(MEAL_PLAN_UUID)},
    )
    data = generated.json()["data"]
    item_uuid = data["items"][0]["uuid"]
    response = await client.patch(
        f"/v1/shopping-lists/{data['uuid']}/items/{item_uuid}",
        json={"checked": True},
        headers={"If-Match": _etag(generated)},
    )
    assert response.json()["data"]["items"][0]["checked"] is True
    assert response.json()["data"]["status"] == "in_progress"


async def test_refresh_preserves_checked_and_manual_items(client, meal_plan_client):
    generated = await client.post(
        "/v1/shopping-lists/from-meal-plan",
        json={"meal_plan_uuid": str(MEAL_PLAN_UUID)},
    )
    data = generated.json()["data"]
    first_uuid = data["items"][0]["uuid"]
    checked = await client.patch(
        f"/v1/shopping-lists/{data['uuid']}/items/{first_uuid}",
        json={"checked": True},
        headers={"If-Match": _etag(generated)},
    )
    manual = await client.post(
        f"/v1/shopping-lists/{data['uuid']}/items",
        json={"name": "Éponges"},
        headers={"If-Match": _etag(checked)},
    )
    meal_plan_client.tomato_quantity = 450.0
    refreshed = await client.post(
        f"/v1/shopping-lists/{data['uuid']}/refresh",
        headers={"If-Match": _etag(manual)},
    )
    items = refreshed.json()["data"]["items"]
    assert any(item["name"] == "Éponges" and item["manual"] for item in items)
    assert any(item["uuid"] == first_uuid and item["checked"] and item["quantity"] == 450.0 for item in items)


async def test_export_text_can_exclude_checked(client):
    generated = await client.post(
        "/v1/shopping-lists/from-meal-plan",
        json={"meal_plan_uuid": str(MEAL_PLAN_UUID)},
    )
    data = generated.json()["data"]
    first_uuid = data["items"][0]["uuid"]
    checked = await client.patch(
        f"/v1/shopping-lists/{data['uuid']}/items/{first_uuid}",
        json={"checked": True},
        headers={"If-Match": _etag(generated)},
    )
    response = await client.post(
        f"/v1/shopping-lists/{data['uuid']}/export-text",
        json={"include_checked": False},
    )
    text = response.json()["data"]["text"]
    assert "Tomates - 300 g" not in text
    assert "Pâtes - 500 g" in text
    assert checked.status_code == 200


async def test_analysis_reports_warnings(client):
    generated = await client.post(
        "/v1/shopping-lists/from-meal-plan",
        json={"meal_plan_uuid": str(MEAL_PLAN_UUID)},
    )
    response = await client.get(f"/v1/shopping-lists/{generated.json()['data']['uuid']}/analysis")
    assert response.json()["data"]["warnings"][0]["code"] == "unit_mismatch"


async def test_purge_returns_count(client):
    response = await client.delete("/admin/purge")
    assert response.status_code == 200
    assert "total" in response.json()
