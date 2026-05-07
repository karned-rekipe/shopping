from uuid import UUID


class ShoppingError(Exception):
    """Base error for shopping domain use cases."""


class ShoppingListNotFound(ShoppingError):
    def __init__(self, uuid: UUID) -> None:
        super().__init__(f"ShoppingList {uuid} not found")


class ShoppingItemNotFound(ShoppingError):
    def __init__(self, uuid: UUID) -> None:
        super().__init__(f"Shopping item {uuid} not found")


class VersionConflict(ShoppingError):
    def __init__(self, expected_version: int, current_version: int) -> None:
        super().__init__(f"expected version {expected_version}, current version {current_version}")


class MealPlanNotConfirmed(ShoppingError):
    def __init__(self, meal_plan_uuid: UUID, status: str | None) -> None:
        super().__init__(f"MealPlan {meal_plan_uuid} must be confirmed before shopping generation, got {status!r}")


class NoConfirmedMealPlanForPeriod(ShoppingError):
    def __init__(self, date_start: str, date_end: str) -> None:
        super().__init__(f"No confirmed meal plan found between {date_start} and {date_end}")


class MealPlanIntegrationError(ShoppingError):
    pass
