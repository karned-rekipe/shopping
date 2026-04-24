from __future__ import annotations

from typing import cast

from application.services.shopping_list_service import ShoppingListService
from arclith import Arclith, AdapterRegistry
from arclith.adapters.output.mongodb.config import MongoDBConfig
from arclith.domain.ports.logger import Logger
from arclith.domain.ports.repository import Repository
from arclith.infrastructure.config import AppConfig
from domain.models.shopping_list import ShoppingList
from domain.ports.output.shopping_list_repository import ShoppingListRepository


def _build_memory(cfg: AppConfig, log: Logger) -> Repository[ShoppingList]:
    from adapters.output.memory.repository import InMemoryShoppingListRepository
    return InMemoryShoppingListRepository()


def _build_mongodb(cfg: AppConfig, log: Logger) -> Repository[ShoppingList]:
    from adapters.output.mongodb.repository import MongoDBShoppingListRepository
    mongo = cfg.adapters.mongodb
    if mongo is None:
        raise RuntimeError("MongoDB settings are required when repository=mongodb")
    return MongoDBShoppingListRepository(
        MongoDBConfig(uri=mongo.uri, db_name=mongo.db_name),
        log,
    )


def _build_duckdb(cfg: AppConfig, log: Logger) -> Repository[ShoppingList]:
    from adapters.output.duckdb.repository import DuckDBShoppingListRepository
    duckdb = cfg.adapters.duckdb
    if duckdb is None:
        raise RuntimeError("DuckDB settings are required when repository=duckdb")
    return DuckDBShoppingListRepository(duckdb.path)


_registry = cast(
    AdapterRegistry[ShoppingList],
    AdapterRegistry[ShoppingList]()
    .register("memory", _build_memory)  # type: ignore[arg-type]
    .register("mongodb", _build_mongodb)  # type: ignore[arg-type]
    .register("duckdb", _build_duckdb)  # type: ignore[arg-type]
)


def build_shopping_list_service(arclith: Arclith) -> tuple[ShoppingListService, Logger]:
    arclith.logger.info("🗄️ Repository adapter selected", adapter=arclith.config.adapters.repository)
    repo: ShoppingListRepository = cast(ShoppingListRepository, _registry.build(arclith.config, arclith.logger))
    return ShoppingListService(repo, arclith.logger, arclith.config.soft_delete.retention_days), arclith.logger
