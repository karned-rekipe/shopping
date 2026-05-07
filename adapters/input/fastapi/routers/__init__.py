"""FastAPI routers."""

from adapters.input.fastapi.routers.admin_router import AdminRouter
from adapters.input.fastapi.routers.shopping_list_router import ShoppingListRouter
from adapters.input.fastapi.routers.supplier_router import SupplierRouter

__all__ = ["AdminRouter", "ShoppingListRouter", "SupplierRouter"]
