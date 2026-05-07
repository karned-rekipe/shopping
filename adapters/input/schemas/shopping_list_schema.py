from datetime import date, datetime
from uuid import UUID as StdUUID

from pydantic import BaseModel, ConfigDict, Field, field_validator
from pydantic import model_validator

from arclith.adapters.input.schemas.base_schema import BaseSchema
from domain.models.enums import ShoppingListStatus
from domain.models.shopping_list import ShoppingItem, ShoppingList


class ShoppingSourceLineSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    source_type: str
    source_uuid: StdUUID
    slot_date: date | None = None
    slot_code: str | None = None
    scaled_quantity: float
    unit: str
    scale_factor: float


class ShoppingListWarningSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    code: str
    ingredient_uuid: StdUUID | None = None
    details: str | None = None


class ShoppingItemSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    uuid: StdUUID
    name: str
    ingredient_uuid: StdUUID | None = None
    quantity: float | None = None
    unit: str | None = None
    rayon: str | None = None
    group: str | None = None
    supplier_uuid: StdUUID | None = None
    checked: bool = False
    manual: bool = False
    note: str | None = None
    source_key: str | None = None
    lines: list[ShoppingSourceLineSchema] = Field(default_factory=list)


class ShoppingItemCreateSchema(BaseModel):
    ingredient_uuid: StdUUID | None = None
    name: str = Field(..., min_length=1, max_length=160)
    quantity: float | None = Field(None, ge=0)
    unit: str | None = None
    rayon: str | None = None
    group: str | None = None
    supplier_uuid: StdUUID | None = None
    checked: bool = False
    note: str | None = Field(None, max_length=500)

    @field_validator("name", mode="before")
    @classmethod
    def name_not_empty(cls, value: str) -> str:
        if isinstance(value, str) and not value.strip():
            raise ValueError("Name cannot be empty")
        return value

    def to_domain(self) -> ShoppingItem:
        return ShoppingItem.model_validate(self.model_dump())


class ShoppingItemPatchSchema(BaseModel):
    ingredient_uuid: StdUUID | None = None
    name: str | None = Field(None, min_length=1, max_length=160)
    quantity: float | None = Field(None, ge=0)
    unit: str | None = None
    rayon: str | None = None
    group: str | None = None
    supplier_uuid: StdUUID | None = None
    checked: bool | None = None
    note: str | None = Field(None, max_length=500)

    @field_validator("name", mode="before")
    @classmethod
    def name_not_empty(cls, value: str | None) -> str | None:
        if isinstance(value, str) and not value.strip():
            raise ValueError("Name cannot be empty")
        return value

    def to_changes(self) -> dict[str, object]:
        return self.model_dump(exclude_unset=True)


class ShoppingListCreateSchema(BaseModel):
    name: str = Field("Liste de courses", min_length=1, max_length=160)

    @field_validator("name", mode="before")
    @classmethod
    def name_not_empty(cls, value: str) -> str:
        if isinstance(value, str) and not value.strip():
            raise ValueError("Name cannot be empty")
        return value


class ShoppingListPatchSchema(BaseModel):
    name: str | None = Field(None, min_length=1, max_length=160)
    status: ShoppingListStatus | None = None

    @field_validator("name", mode="before")
    @classmethod
    def name_not_empty(cls, value: str | None) -> str | None:
        if isinstance(value, str) and not value.strip():
            raise ValueError("Name cannot be empty")
        return value


class ShoppingListUpdateSchema(BaseModel):
    name: str = Field(..., min_length=1, max_length=160)
    status: ShoppingListStatus = ShoppingListStatus.DRAFT


class ShoppingListFromMealPlanSchema(BaseModel):
    meal_plan_uuid: StdUUID
    name: str | None = Field(None, min_length=1, max_length=160)


class ShoppingListFromPeriodSchema(BaseModel):
    date_start: date
    date_end: date
    name: str | None = Field(None, min_length=1, max_length=160)

    @model_validator(mode="after")
    def check_period(self) -> "ShoppingListFromPeriodSchema":
        if self.date_end < self.date_start:
            raise ValueError("date_end must be greater than or equal to date_start")
        return self


class ShoppingListExportSchema(BaseModel):
    item_uuids: list[StdUUID] | None = None
    rayon: str | None = None
    supplier_uuid: StdUUID | None = None
    include_checked: bool = True


class ShoppingListExportResultSchema(BaseModel):
    text: str
    item_count: int


class ShoppingListCreatedSchema(BaseModel):
    uuid: StdUUID


class ShoppingListAnalysisSchema(BaseModel):
    warnings: list[dict]
    duplicates: list[dict]
    checked_count: int
    items_count: int


class ShoppingListSchema(BaseSchema):
    name: str
    status: ShoppingListStatus
    meal_plan_uuid: StdUUID | None = None
    source_meal_plan_uuids: list[StdUUID] = Field(default_factory=list)
    period_start: date | None = None
    period_end: date | None = None
    generated_at: datetime | None = None
    items: list[ShoppingItemSchema] = Field(default_factory=list)
    warnings: list[ShoppingListWarningSchema] = Field(default_factory=list)


def shopping_list_create_payload_to_domain(payload: ShoppingListCreateSchema) -> ShoppingList:
    return ShoppingList(name=payload.name)


def shopping_list_update_payload_to_domain(existing: ShoppingList, payload: ShoppingListUpdateSchema) -> ShoppingList:
    return existing.model_copy(update={"name": payload.name, "status": payload.status})
