from __future__ import annotations

import os
from typing import cast

from application.services.shopping_list_service import ShoppingListService
from application.services.supplier_service import SupplierService
from arclith import Arclith, AdapterRegistry
from arclith.adapters.output.mongodb.config import MongoDBConfig
from arclith.domain.ports.logger import Logger
from arclith.domain.ports.repository import Repository
from arclith.infrastructure.config import AppConfig
from domain.models.shopping_list import ShoppingList
from domain.models.supplier import Supplier
from domain.ports.output.meal_plan_client import MealPlanClient
from domain.ports.output.shopping_list_repository import ShoppingListRepository
from domain.ports.output.supplier_repository import SupplierRepository


def _build_memory(cfg: AppConfig, log: Logger) -> Repository[ShoppingList]:
    from adapters.output.memory.repository import InMemoryShoppingListRepository
    return InMemoryShoppingListRepository()


def _build_mongodb(cfg: AppConfig, log: Logger) -> Repository[ShoppingList]:
    from adapters.output.mongodb.repository import MongoDBShoppingListRepository
    mongo = cfg.adapters.mongodb
    if mongo is None:
        raise RuntimeError("MongoDB settings are required when repository=mongodb")
    return MongoDBShoppingListRepository(
        MongoDBConfig(uri=mongo.uri, db_name=mongo.db_name, collection_name=getattr(mongo, "collection_name", None)),
        log,
    )


def _build_duckdb(cfg: AppConfig, log: Logger) -> Repository[ShoppingList]:
    from adapters.output.duckdb.repository import DuckDBShoppingListRepository
    duckdb = cfg.adapters.duckdb
    if duckdb is None:
        raise RuntimeError("DuckDB settings are required when repository=duckdb")
    return DuckDBShoppingListRepository(duckdb.path)


def _build_memory_supplier(cfg: AppConfig, log: Logger) -> Repository[Supplier]:
    from adapters.output.memory.repository import InMemorySupplierRepository

    return InMemorySupplierRepository()


def _build_mongodb_supplier(cfg: AppConfig, log: Logger) -> Repository[Supplier]:
    from adapters.output.mongodb.repository import MongoDBSupplierRepository

    mongo = cfg.adapters.mongodb
    if mongo is None:
        raise RuntimeError("MongoDB settings are required when repository=mongodb")
    return MongoDBSupplierRepository(
        MongoDBConfig(uri=mongo.uri, db_name=mongo.db_name, collection_name="suppliers"),
        log,
    )


def _build_duckdb_supplier(cfg: AppConfig, log: Logger) -> Repository[Supplier]:
    from adapters.output.duckdb.repository import DuckDBSupplierRepository

    duckdb = cfg.adapters.duckdb
    if duckdb is None:
        raise RuntimeError("DuckDB settings are required when repository=duckdb")
    return DuckDBSupplierRepository(duckdb.path)


_registry = cast(
    AdapterRegistry[ShoppingList],
    AdapterRegistry[ShoppingList]()
    .register("memory", _build_memory)  # type: ignore[arg-type]
    .register("mongodb", _build_mongodb)  # type: ignore[arg-type]
    .register("duckdb", _build_duckdb)  # type: ignore[arg-type]
)

_supplier_registry = cast(
    AdapterRegistry[Supplier],
    AdapterRegistry[Supplier]()
    .register("memory", _build_memory_supplier)  # type: ignore[arg-type]
    .register("mongodb", _build_mongodb_supplier)  # type: ignore[arg-type]
    .register("duckdb", _build_duckdb_supplier)  # type: ignore[arg-type]
)


def _build_meal_plan_client() -> MealPlanClient:
    from adapters.output.http.meal_plan_http_client import MealPlanHttpClient
    from adapters.output.http.static_meal_plan_client import StaticMealPlanClient

    base_url = os.getenv("MEAL_PLANNER_BASE_URL")
    if not base_url:
        return StaticMealPlanClient()
    return MealPlanHttpClient(base_url=base_url, api_token=os.getenv("MEAL_PLANNER_API_TOKEN"))


def build_shopping_list_service(arclith: Arclith) -> tuple[ShoppingListService, Logger]:
    arclith.logger.info("🗄️ Repository adapter selected", adapter=arclith.config.adapters.repository)
    repo: ShoppingListRepository = cast(ShoppingListRepository, _registry.build(arclith.config, arclith.logger))
    return (
        ShoppingListService(
            repo,
            arclith.logger,
            arclith.config.soft_delete.retention_days,
            meal_plan_client=_build_meal_plan_client(),
        ),
        arclith.logger,
    )


def build_supplier_service(arclith: Arclith) -> tuple[SupplierService, Logger]:
    arclith.logger.info("🗄️ Supplier repository adapter selected", adapter=arclith.config.adapters.repository)
    repo: SupplierRepository = cast(SupplierRepository, _supplier_registry.build(arclith.config, arclith.logger))
    return SupplierService(repo, arclith.logger, arclith.config.soft_delete.retention_days), arclith.logger
