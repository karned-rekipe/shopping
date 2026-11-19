from datetime import date, datetime
from uuid import UUID

from pydantic import BaseModel, Field


class ShoppingProjectionPeriod(BaseModel):
    start: date
    end: date


class ShoppingProjectionTotals(BaseModel):
    headcount_days: int = 0
    ingredients_count: int = 0
    groups_count: int = 0


class ShoppingProjectionAggregatedQuantity(BaseModel):
    quantity: float = Field(..., ge=0)
    unit: str


class ShoppingProjectionLine(BaseModel):
    source_type: str
    source_uuid: UUID
    slot_date: date | None = None
    slot_code: str | None = None
    scaled_quantity: float = Field(..., ge=0)
    unit: str
    scale_factor: float = Field(..., ge=0)


class ShoppingProjectionIngredient(BaseModel):
    ingredient_uuid: UUID
    name: str | None = None
    group: str | None = None
    rayon: str | None = None
    supplier_uuid: UUID | None = None
    season_months: list[int] = Field(default_factory=list)
    lines: list[ShoppingProjectionLine] = Field(default_factory=list)
    aggregated: ShoppingProjectionAggregatedQuantity


class ShoppingProjectionWarning(BaseModel):
    code: str
    ingredient_uuid: UUID | None = None
    details: str | None = None


class ShoppingProjection(BaseModel):
    meal_plan_uuid: UUID
    period: ShoppingProjectionPeriod
    generated_at: datetime
    totals: ShoppingProjectionTotals
    ingredients: list[ShoppingProjectionIngredient] = Field(default_factory=list)
    warnings: list[ShoppingProjectionWarning] = Field(default_factory=list)
