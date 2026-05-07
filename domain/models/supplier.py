from pydantic import Field, field_validator

from arclith.domain.models.entity import Entity
from domain.models.enums import SupplierType


class Supplier(Entity):
    name: str = Field(..., min_length=1, max_length=120)
    supplier_type: SupplierType = SupplierType.STORE
    notes: str | None = Field(None, max_length=500)

    @field_validator("name", mode="before")
    @classmethod
    def strip_name(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("Supplier name cannot be empty")
        return stripped

    @field_validator("notes", mode="before")
    @classmethod
    def strip_notes(cls, value: str | None) -> str | None:
        if value is None:
            return None
        stripped = value.strip()
        return stripped or None
