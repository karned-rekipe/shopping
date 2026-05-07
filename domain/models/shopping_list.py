from datetime import date, datetime
from uuid import UUID, uuid4

from pydantic import BaseModel, Field, field_validator

from arclith.domain.models.entity import Entity
from domain.models.enums import ShoppingListStatus, ShoppingWarningCode


class ShoppingSourceLine(BaseModel):
    source_type: str
    source_uuid: UUID
    slot_date: date | None = None
    slot_code: str | None = None
    scaled_quantity: float = Field(..., ge=0)
    unit: str
    scale_factor: float = Field(..., ge=0)


class ShoppingListWarning(BaseModel):
    code: ShoppingWarningCode | str
    ingredient_uuid: UUID | None = None
    details: str | None = None


class ShoppingItem(BaseModel):
    uuid: UUID = Field(default_factory=uuid4)
    name: str = Field(..., min_length=1, max_length=160)
    ingredient_uuid: UUID | None = None
    quantity: float | None = Field(None, ge=0)
    unit: str | None = None
    rayon: str | None = None
    group: str | None = None
    supplier_uuid: UUID | None = None
    checked: bool = False
    manual: bool = False
    note: str | None = Field(None, max_length=500)
    source_key: str | None = None
    lines: list[ShoppingSourceLine] = Field(default_factory=list)

    @field_validator("name", mode="before")
    @classmethod
    def strip_name(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("Shopping item name cannot be empty")
        return stripped

    @field_validator("unit", "rayon", "group", "note", mode="before")
    @classmethod
    def strip_optional_text(cls, value: str | None) -> str | None:
        if value is None:
            return None
        stripped = value.strip()
        return stripped or None


class ShoppingList(Entity):
    name: str = Field("Liste de courses", min_length=1, max_length=160)
    status: ShoppingListStatus = ShoppingListStatus.DRAFT
    meal_plan_uuid: UUID | None = None
    source_meal_plan_uuids: list[UUID] = Field(default_factory=list)
    period_start: date | None = None
    period_end: date | None = None
    generated_at: datetime | None = None
    items: list[ShoppingItem] = Field(default_factory=list)
    warnings: list[ShoppingListWarning] = Field(default_factory=list)

    @field_validator("name", mode="before")
    @classmethod
    def strip_name(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("ShoppingList name cannot be empty")
        return stripped
