"""FastAPI routers."""

from adapters.input.fastapi.routers.admin_router import AdminRouter
from adapters.input.fastapi.routers.shopping_list_router import ShoppingListRouter

__all__ = ["AdminRouter", "ShoppingListRouter"]

