import pytest
from datetime import datetime, timezone

from adapters.input.schemas.shopping_list_schema import (
    ShoppingListCreateSchema,
    ShoppingListPatchSchema,
    ShoppingListSchema,
    ShoppingListUpdateSchema,
)
from domain.models.shopping_list import ShoppingList


# --- ShoppingListCreateSchema ---

def test_create_schema_valid():
    s = ShoppingListCreateSchema(name="Farine")
    assert s.name == "Farine"


def test_create_schema_empty_name_raises():
    with pytest.raises(Exception):
        ShoppingListCreateSchema(name="")


# --- ShoppingListPatchSchema ---

def test_patch_schema_all_none():
    s = ShoppingListPatchSchema()
    assert s.name is None


def test_patch_schema_partial():
    s = ShoppingListPatchSchema(name="Farine complète")
    assert s.name == "Farine complète"


def test_patch_schema_empty_name_raises():
    with pytest.raises(Exception):
        ShoppingListPatchSchema(name="")


# --- ShoppingListUpdateSchema ---

def test_update_schema_valid():
    s = ShoppingListUpdateSchema(name="Sel fin")
    assert s.name == "Sel fin"


def test_update_schema_empty_name_raises():
    with pytest.raises(Exception):
        ShoppingListUpdateSchema(name="")


# --- ShoppingListSchema (response) ---

def test_shopping_list_schema_from_entity():
    entity = ShoppingList(name="Farine")
    schema = ShoppingListSchema.model_validate(entity)
    assert schema.name == "Farine"
    assert schema.is_deleted is False
    assert schema.version == 1


def test_shopping_list_schema_deleted_entity():
    entity = ShoppingList(name="Sel", deleted_at=datetime.now(timezone.utc))
    schema = ShoppingListSchema.model_validate(entity)
    assert schema.is_deleted is True


def test_shopping_list_schema_uuid_serialized():
    entity = ShoppingList(name="Farine")
    schema = ShoppingListSchema.model_validate(entity)
    assert str(schema.uuid) == str(entity.uuid)

