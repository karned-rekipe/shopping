"""FastAPI routers."""

from adapters.input.fastapi.routers.admin_router import AdminRouter
from adapters.input.fastapi.routers.shopping_list_router import ShoppingListRouter
from adapters.input.fastapi.routers.tenant_shopping_router import TenantShoppingRouter

__all__ = ["AdminRouter", "ShoppingListRouter", "TenantShoppingRouter"]
