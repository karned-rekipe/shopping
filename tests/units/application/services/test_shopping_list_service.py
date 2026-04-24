import pytest
from uuid6 import uuid7

from application.services.shopping_list_service import ShoppingListService
from domain.models.shopping_list import ShoppingList


@pytest.fixture
def service(repo, logger):
    return ShoppingListService(repo, logger)


async def test_create_and_read(service):
    shopping_list = await service.create(ShoppingList(name="Farine"))
    found = await service.read(shopping_list.uuid)
    assert found is not None
    assert found.name == "Farine"


async def test_update(service):
    shopping_list = await service.create(ShoppingList(name="Farine"))
    updated = await service.update(shopping_list.model_copy(update={"name": "Farine complète"}))
    assert updated.name == "Farine complète"
    assert updated.version == 2


async def test_delete_hides_from_read(service):
    shopping_list = await service.create(ShoppingList(name="Sel"))
    await service.delete(shopping_list.uuid)
    assert await service.read(shopping_list.uuid) is None


async def test_find_all(service):
    await service.create(ShoppingList(name="Farine"))
    await service.create(ShoppingList(name="Sel"))
    result = await service.find_all()
    assert len(result) == 2


async def test_find_by_name(service):
    await service.create(ShoppingList(name="Farine de blé"))
    await service.create(ShoppingList(name="Sel fin"))
    result = await service.find_by_name("farine")
    assert len(result) == 1
    assert result[0].name == "Farine de blé"


async def test_duplicate(service):
    shopping_list = await service.create(ShoppingList(name="Farine"))
    clone = await service.duplicate(shopping_list.uuid)
    assert clone.uuid != shopping_list.uuid
    assert clone.name == "Farine"


async def test_read_unknown_returns_none(service):
    assert await service.read(uuid7()) is None


async def test_find_by_name_no_results(service):
    await service.create(ShoppingList(name="Sel"))
    result = await service.find_by_name("farine")
    assert result == []

