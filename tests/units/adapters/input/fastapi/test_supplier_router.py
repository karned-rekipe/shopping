import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from adapters.input.fastapi.dependencies import inject_tenant_uri
from adapters.input.fastapi.routers import SupplierRouter
from adapters.output.memory.repository import InMemorySupplierRepository
from application.services.supplier_service import SupplierService


@pytest.fixture
def supplier_service(logger):
    return SupplierService(InMemorySupplierRepository(), logger)


@pytest.fixture
def app(supplier_service, logger):
    fastapi_app = FastAPI()
    fastapi_app.include_router(SupplierRouter(supplier_service, logger).router)
    fastapi_app.dependency_overrides[inject_tenant_uri] = lambda: None
    return fastapi_app


@pytest.fixture
async def client(app):
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        yield c


async def test_create_and_get_supplier(client):
    created = await client.post("/v1/suppliers/", json={"name": "Marché", "supplier_type": "producer"})
    assert created.status_code == 201
    fetched = await client.get(f"/v1/suppliers/{created.json()['data']['uuid']}")
    assert fetched.json()["data"]["name"] == "Marché"
    assert fetched.json()["data"]["supplier_type"] == "producer"


async def test_patch_supplier_requires_if_match(client):
    created = await client.post("/v1/suppliers/", json={"name": "Biocoop"})
    response = await client.patch(f"/v1/suppliers/{created.json()['data']['uuid']}", json={"notes": "vrac"})
    assert response.status_code == 412


async def test_patch_supplier_updates_notes(client):
    created = await client.post("/v1/suppliers/", json={"name": "Biocoop"})
    fetched = await client.get(f"/v1/suppliers/{created.json()['data']['uuid']}")
    response = await client.patch(
        f"/v1/suppliers/{created.json()['data']['uuid']}",
        json={"notes": "vrac"},
        headers={"If-Match": fetched.headers["etag"]},
    )
    assert response.status_code == 200
    assert response.json()["data"]["notes"] == "vrac"


async def test_list_supplier_name_filter(client):
    await client.post("/v1/suppliers/", json={"name": "Marché"})
    await client.post("/v1/suppliers/", json={"name": "Super U"})
    response = await client.get("/v1/suppliers/", params={"name": "mar"})
    assert response.json()["pagination"]["total"] == 1
    assert response.json()["data"][0]["name"] == "Marché"
