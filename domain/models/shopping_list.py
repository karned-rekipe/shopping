from pydantic import Field, field_validator

from arclith.domain.models.entity import Entity


class ShoppingList(Entity):
    name: str = Field(
        ...,
        description="Nom de l'ingrédient",
        examples = ["Ingrédient 1", "Ingrédient 2"],
    )

    @field_validator("name", mode="before")
    @classmethod
    def strip_name(cls, v: str) -> str:
        stripped = v.strip()
        if not stripped:
            raise ValueError("ShoppingList name cannot be empty")
        return stripped

