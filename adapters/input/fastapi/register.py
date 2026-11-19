from adapters.input.fastapi.routers import AdminRouter, ShoppingListRouter, SupplierRouter
from arclith import Arclith
from fastapi import FastAPI
from infrastructure.containers.shopping_list_container import build_shopping_list_service, build_supplier_service
from infrastructure.purge_registry import purge_registry


def register_routers(app: FastAPI, arclith: Arclith) -> None:
    service, logger = build_shopping_list_service(arclith)
    supplier_service, _ = build_supplier_service(arclith)
    purge_registry.register("shopping_lists", service.purge)
    purge_registry.register("suppliers", supplier_service.purge)
    app.include_router(ShoppingListRouter(service, logger).router)
    app.include_router(SupplierRouter(supplier_service, logger).router)
    app.include_router(AdminRouter(purge_registry).router)
