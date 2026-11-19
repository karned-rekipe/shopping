from uuid import UUID as StdUUID

from pydantic import BaseModel, Field, field_validator, model_validator

from arclith.adapters.input.schemas.base_schema import BaseSchema
from domain.models.enums import SupplierType
from domain.models.supplier import Supplier


class SupplierCreateSchema(BaseModel):
    name: str = Field(..., min_length=1, max_length=120)
    supplier_type: SupplierType = SupplierType.STORE
    notes: str | None = Field(None, max_length=500)

    @field_validator("name", mode="before")
    @classmethod
    def name_not_empty(cls, value: str) -> str:
        if isinstance(value, str) and not value.strip():
            raise ValueError("Name cannot be empty")
        return value


class SupplierUpdateSchema(SupplierCreateSchema):
    pass


class SupplierPatchSchema(BaseModel):
    name: str | None = Field(None, min_length=1, max_length=120)
    supplier_type: SupplierType | None = None
    notes: str | None = Field(None, max_length=500)

    @field_validator("name", mode="before")
    @classmethod
    def name_not_empty(cls, value: str | None) -> str | None:
        if isinstance(value, str) and not value.strip():
            raise ValueError("Name cannot be empty")
        return value

    @model_validator(mode="after")
    def reject_null_required_fields(self) -> "SupplierPatchSchema":
        for field_name in ("name", "supplier_type"):
            if field_name in self.model_fields_set and getattr(self, field_name) is None:
                raise ValueError(f"{field_name} cannot be null when provided")
        return self


class SupplierCreatedSchema(BaseModel):
    uuid: StdUUID


class SupplierSchema(BaseSchema):
    name: str
    supplier_type: SupplierType
    notes: str | None = None


def supplier_create_payload_to_domain(payload: SupplierCreateSchema) -> Supplier:
    return Supplier(name=payload.name, supplier_type=payload.supplier_type, notes=payload.notes)


def supplier_update_payload_to_domain(existing: Supplier, payload: SupplierUpdateSchema) -> Supplier:
    return existing.model_copy(
        update={
            "name": payload.name,
            "supplier_type": payload.supplier_type,
            "notes": payload.notes,
        },
    )
