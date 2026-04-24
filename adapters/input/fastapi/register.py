from adapters.input.fastapi.routers import AdminRouter, ShoppingListRouter
from arclith import Arclith
from fastapi import FastAPI
from infrastructure.containers.shopping_list_container import build_shopping_list_service
from infrastructure.purge_registry import purge_registry


def register_routers(app: FastAPI, arclith: Arclith) -> None:
    service, logger = build_shopping_list_service(arclith)
    purge_registry.register("shopping_lists", service.purge)
    app.include_router(ShoppingListRouter(service, logger).router)
    app.include_router(AdminRouter(purge_registry).router)
