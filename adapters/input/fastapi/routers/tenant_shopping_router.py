from datetime import UTC, datetime
from math import ceil
import re
from collections.abc import Callable
from typing import Any
from uuid import uuid4

from arclith.adapters.context import get_adapter_tenant_context
from fastapi import APIRouter, Depends, Header, HTTPException, Query, Response
from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorCollection, AsyncIOMotorDatabase
from uuid6 import uuid7

from adapters.input.fastapi.dependencies import inject_tenant_uri

Document = dict[str, Any]

_CLIENTS: dict[str, AsyncIOMotorClient] = {}
_LIST_STATUS_VALUES = {"draft", "to_check", "validated", "in_progress", "done"}
_SUPPLIER_TYPE_VALUES = {"store", "producer", "online", "other"}
_ITEM_PATCH_FIELDS = {
    "ingredient_uuid",
    "name",
    "quantity",
    "unit",
    "rayon",
    "group",
    "supplier_uuid",
    "checked",
    "note",
}


class TenantShoppingRouter:
    def __init__(self) -> None:
        self.router = APIRouter(
            prefix="/v1",
            tags=["tenant-shopping"],
            dependencies=[Depends(inject_tenant_uri)],
        )
        self._register_routes()

    def _register_routes(self) -> None:
        self.router.add_api_route(
            methods=["GET"],
            path="/shopping-lists/",
            endpoint=self.list_shopping_lists,
            status_code=200,
        )
        self.router.add_api_route(
            methods=["GET"],
            path="/shopping-lists/{uuid}",
            endpoint=self.get_shopping_list,
            status_code=200,
        )
        self.router.add_api_route(
            methods=["POST"],
            path="/shopping-lists/{uuid}/items",
            endpoint=self.add_item,
            status_code=200,
        )
        self.router.add_api_route(
            methods=["PATCH"],
            path="/shopping-lists/{uuid}/items/{item_uuid}",
            endpoint=self.patch_item,
            status_code=200,
        )
        self.router.add_api_route(
            methods=["POST"],
            path="/shopping-lists/{uuid}/export-text",
            endpoint=self.export_text,
            status_code=200,
        )
        self.router.add_api_route(
            methods=["GET"],
            path="/suppliers/",
            endpoint=self.list_suppliers,
            status_code=200,
        )
        self.router.add_api_route(
            methods=["POST"],
            path="/suppliers/",
            endpoint=self.create_supplier,
            status_code=201,
        )
        self.router.add_api_route(
            methods=["PATCH"],
            path="/suppliers/{uuid}",
            endpoint=self.patch_supplier,
            status_code=200,
        )

    async def list_shopping_lists(
        self,
        response: Response,
        page: int = Query(1, ge=1),
        per_page: int = Query(20, ge=1, le=100),
        name: str | None = Query(None, min_length=1),
    ) -> dict[str, Any]:
        query = _active_query(name)
        data, total = await _find_page(
            _shopping_lists(),
            query=query,
            page=page,
            per_page=per_page,
            sort=[("period_start", -1), ("created_at", -1), ("name", 1)],
        )
        response.headers["X-Total-Count"] = str(total)
        return _paginated([_shopping_list_payload(doc) for doc in data], total, page, per_page)

    async def get_shopping_list(self, uuid: str, response: Response) -> dict[str, Any]:
        doc = await _shopping_list_doc(uuid)
        response.headers["ETag"] = f'"{_version(doc)}"'
        return _success(_shopping_list_payload(doc))

    async def add_item(
        self,
        uuid: str,
        payload: Document,
        response: Response,
        if_match: str | None = Header(default=None),
    ) -> dict[str, Any]:
        doc = await _shopping_list_doc(uuid)
        _check_if_match(doc, if_match)

        item = _new_item_payload(payload)
        now = _now()
        result = await _shopping_lists().update_one(
            {"_id": uuid, "deleted_at": None},
            {"$push": {"items": item}, "$set": {"updated_at": now}, "$inc": {"version": 1}},
        )
        if result.modified_count != 1:
            raise HTTPException(status_code=409, detail="Ajout item impossible")

        updated = await _shopping_list_doc(uuid)
        response.headers["ETag"] = f'"{_version(updated)}"'
        return _success(_shopping_list_payload(updated))

    async def patch_item(
        self,
        uuid: str,
        item_uuid: str,
        payload: Document,
        response: Response,
        if_match: str | None = Header(default=None),
    ) -> dict[str, Any]:
        doc = await _shopping_list_doc(uuid)
        _check_if_match(doc, if_match)

        patch = {field: payload[field] for field in _ITEM_PATCH_FIELDS if field in payload}
        if not patch:
            response.headers["ETag"] = f'"{_version(doc)}"'
            return _success(_shopping_list_payload(doc))

        now = _now()
        update = {f"items.$[item].{field}": value for field, value in patch.items()}
        update["updated_at"] = now
        result = await _shopping_lists().update_one(
            {"_id": uuid, "deleted_at": None, "items.uuid": item_uuid},
            {"$set": update, "$inc": {"version": 1}},
            array_filters=[{"item.uuid": item_uuid}],
        )
        if result.matched_count != 1:
            raise HTTPException(status_code=404, detail="Shopping item not found")
        if result.modified_count != 1:
            raise HTTPException(status_code=409, detail="Modification item impossible")

        updated = await _shopping_list_doc(uuid)
        response.headers["ETag"] = f'"{_version(updated)}"'
        return _success(_shopping_list_payload(updated))

    async def export_text(self, uuid: str, payload: Document) -> dict[str, Any]:
        doc = await _shopping_list_doc(uuid)
        items = _export_items(doc, payload)
        lines = [_export_line(item) for item in items]
        return _success({"text": "\n".join(lines), "item_count": len(lines)})

    async def list_suppliers(
        self,
        response: Response,
        page: int = Query(1, ge=1),
        per_page: int = Query(20, ge=1, le=100),
        name: str | None = Query(None, min_length=1),
    ) -> dict[str, Any]:
        query = _active_query(name)
        data, total = await _find_page(
            _suppliers(),
            query=query,
            page=page,
            per_page=per_page,
            sort=[("name", 1), ("created_at", 1)],
        )
        response.headers["X-Total-Count"] = str(total)
        return _paginated([_supplier_payload(doc) for doc in data], total, page, per_page)

    async def create_supplier(self, payload: Document, response: Response) -> dict[str, Any]:
        name = _required_string(payload, "name")
        supplier_type = _supplier_type(payload.get("supplier_type"))
        now = _now()
        doc = {
            "_id": str(uuid7()),
            "created_at": now,
            "created_by": None,
            "updated_at": now,
            "updated_by": None,
            "deleted_at": None,
            "deleted_by": None,
            "version": 1,
            "name": name,
            "supplier_type": supplier_type,
            "notes": _nullable_string(payload.get("notes")),
        }
        await _suppliers().insert_one(doc)
        response.headers["Location"] = f"/v1/suppliers/{doc['_id']}"
        response.headers["ETag"] = '"1"'
        return _success({"uuid": doc["_id"]})

    async def patch_supplier(
        self,
        uuid: str,
        payload: Document,
        response: Response,
        if_match: str | None = Header(default=None),
    ) -> dict[str, Any]:
        doc = await _supplier_doc(uuid)
        _check_if_match(doc, if_match)

        update: Document = {}
        if "name" in payload:
            update["name"] = _required_string(payload, "name")
        if "supplier_type" in payload:
            update["supplier_type"] = _supplier_type(payload.get("supplier_type"))
        if "notes" in payload:
            update["notes"] = _nullable_string(payload.get("notes"))

        if not update:
            response.headers["ETag"] = f'"{_version(doc)}"'
            return _success(_supplier_payload(doc))

        update["updated_at"] = _now()
        result = await _suppliers().update_one(
            {"_id": uuid, "deleted_at": None},
            {"$set": update, "$inc": {"version": 1}},
        )
        if result.modified_count != 1:
            raise HTTPException(status_code=409, detail="Modification fournisseur impossible")

        updated = await _supplier_doc(uuid)
        response.headers["ETag"] = f'"{_version(updated)}"'
        return _success(_supplier_payload(updated))


def _tenant_db() -> AsyncIOMotorDatabase:
    coords = get_adapter_tenant_context("mongodb")
    if coords is None:
        raise HTTPException(status_code=401, detail="Tenant MongoDB non résolu")

    uri = coords.get("uri")
    db_name = coords.get("shopping_db_name") or coords.get("db_name")
    if not uri or not db_name:
        raise HTTPException(status_code=500, detail="Coordonnées MongoDB tenant incomplètes")

    client = _CLIENTS.get(uri)
    if client is None:
        client = AsyncIOMotorClient(uri)
        _CLIENTS[uri] = client
    return client[db_name]


def _shopping_lists() -> AsyncIOMotorCollection:
    return _tenant_db().shopping_lists


def _suppliers() -> AsyncIOMotorCollection:
    return _tenant_db().suppliers


async def _find_page(
    collection: AsyncIOMotorCollection,
    *,
    query: Document,
    page: int,
    per_page: int,
    sort: list[tuple[str, int]],
) -> tuple[list[Document], int]:
    offset = (page - 1) * per_page
    total = await collection.count_documents(query)
    cursor = collection.find(query).sort(sort).skip(offset).limit(per_page)
    return await cursor.to_list(length=per_page), total


async def _shopping_list_doc(uuid: str) -> Document:
    doc = await _shopping_lists().find_one({"_id": uuid, "deleted_at": None})
    if doc is None:
        raise HTTPException(status_code=404, detail="Shopping list not found")
    return doc


async def _supplier_doc(uuid: str) -> Document:
    doc = await _suppliers().find_one({"_id": uuid, "deleted_at": None})
    if doc is None:
        raise HTTPException(status_code=404, detail="Supplier not found")
    return doc


def _active_query(name: str | None = None) -> Document:
    query: Document = {"deleted_at": None}
    if name:
        query["name"] = {"$regex": re.escape(name), "$options": "i"}
    return query


def _shopping_list_payload(doc: Document) -> Document:
    return {
        "uuid": _document_uuid(doc),
        "version": _version(doc),
        "created_at": _timestamp(doc.get("created_at")),
        "updated_at": _timestamp(doc.get("updated_at")),
        "name": _string(doc.get("name"), "Liste de courses"),
        "status": _list_status(doc.get("status")),
        "meal_plan_uuid": _nullable_string(doc.get("meal_plan_uuid")),
        "source_meal_plan_uuids": _string_list(doc.get("source_meal_plan_uuids")),
        "period_start": _nullable_string(doc.get("period_start")),
        "period_end": _nullable_string(doc.get("period_end")),
        "generated_at": _nullable_timestamp(doc.get("generated_at")),
        "items": [_shopping_item_payload(item) for item in _documents(doc.get("items"))],
        "warnings": [_warning_payload(warning) for warning in _documents(doc.get("warnings"))],
    }


def _shopping_item_payload(doc: Document) -> Document:
    return {
        "uuid": _string(doc.get("uuid"), str(uuid4())),
        "name": _string(doc.get("name"), "Item"),
        "ingredient_uuid": _nullable_string(doc.get("ingredient_uuid")),
        "quantity": _number_or_none(doc.get("quantity")),
        "unit": _nullable_string(doc.get("unit")),
        "rayon": _nullable_string(doc.get("rayon")),
        "group": _nullable_string(doc.get("group")),
        "supplier_uuid": _nullable_string(doc.get("supplier_uuid")),
        "checked": bool(doc.get("checked", False)),
        "manual": bool(doc.get("manual", False)),
        "note": _nullable_string(doc.get("note")),
        "source_key": _nullable_string(doc.get("source_key")),
        "lines": [_line_payload(line) for line in _documents(doc.get("lines"))],
    }


def _line_payload(doc: Document) -> Document:
    return {
        "source_type": _string(doc.get("source_type"), "unknown"),
        "source_uuid": _string(doc.get("source_uuid"), ""),
        "slot_date": _nullable_string(doc.get("slot_date")),
        "slot_code": _nullable_string(doc.get("slot_code")),
        "scaled_quantity": _number(doc.get("scaled_quantity"), 0),
        "unit": _string(doc.get("unit"), ""),
        "scale_factor": _number(doc.get("scale_factor"), 1),
        "headcount": _number_or_none(doc.get("headcount")),
    }


def _warning_payload(doc: Document) -> Document:
    return {
        "code": _string(doc.get("code"), "warning"),
        "ingredient_uuid": _nullable_string(doc.get("ingredient_uuid")),
        "details": _nullable_string(doc.get("details")),
    }


def _supplier_payload(doc: Document) -> Document:
    return {
        "uuid": _document_uuid(doc),
        "version": _version(doc),
        "created_at": _timestamp(doc.get("created_at")),
        "updated_at": _timestamp(doc.get("updated_at")),
        "name": _string(doc.get("name"), "Fournisseur"),
        "supplier_type": _supplier_type(doc.get("supplier_type")),
        "notes": _nullable_string(doc.get("notes")),
    }


def _new_item_payload(payload: Document) -> Document:
    name = _required_string(payload, "name")
    return {
        "uuid": str(uuid4()),
        "name": name,
        "ingredient_uuid": _nullable_string(payload.get("ingredient_uuid")),
        "quantity": _number_or_none(payload.get("quantity")),
        "unit": _nullable_string(payload.get("unit")),
        "rayon": _nullable_string(payload.get("rayon")),
        "group": _nullable_string(payload.get("group")),
        "supplier_uuid": _nullable_string(payload.get("supplier_uuid")),
        "checked": bool(payload.get("checked", False)),
        "manual": True,
        "note": _nullable_string(payload.get("note")),
        "source_key": None,
        "lines": [],
    }


def _export_items(doc: Document, payload: Document) -> list[Document]:
    item_uuids = set(_string_list(payload.get("item_uuids")))
    rayon = _nullable_string(payload.get("rayon"))
    supplier_uuid = _nullable_string(payload.get("supplier_uuid"))
    include_checked = bool(payload.get("include_checked", True))

    predicates: list[Callable[[Document], bool]] = [
        lambda item: not item_uuids or item["uuid"] in item_uuids,
        lambda item: rayon is None or item["rayon"] == rayon,
        lambda item: supplier_uuid is None or item["supplier_uuid"] == supplier_uuid,
        lambda item: include_checked or not item["checked"],
    ]
    return [
        item
        for item in (_shopping_item_payload(raw) for raw in _documents(doc.get("items")))
        if all(predicate(item) for predicate in predicates)
    ]


def _export_line(item: Document) -> str:
    quantity = item.get("quantity")
    unit = item.get("unit")
    amount = ""
    if quantity is not None and unit:
        amount = f" : {quantity:g} {unit}"
    elif quantity is not None:
        amount = f" : {quantity:g}"
    return f"- {item['name']}{amount}"


def _check_if_match(doc: Document, if_match: str | None) -> None:
    if not if_match:
        return

    raw = if_match.strip().removeprefix("W/").strip('"')
    if raw.lower().startswith("v"):
        raw = raw[1:]
    if not raw.isdigit():
        raise HTTPException(status_code=400, detail="If-Match invalide")
    expected = int(raw)
    current = _version(doc)
    if current != expected:
        raise HTTPException(status_code=412, detail=f"Version mismatch: expected v{expected}, current v{current}")


def _paginated(data: list[Document], total: int, page: int, per_page: int) -> Document:
    pages = ceil(total / per_page) if total else 0
    return {
        "status": "success",
        "data": data,
        "pagination": {
            "total": total,
            "page": page,
            "per_page": per_page,
            "pages": pages,
            "has_next": page < pages,
            "has_prev": page > 1 and pages > 0,
            "next_page": page + 1 if page < pages else None,
            "prev_page": page - 1 if page > 1 and pages > 0 else None,
        },
        "metadata": _metadata(),
    }


def _success(data: Any) -> Document:
    return {"status": "success", "data": data, "metadata": _metadata()}


def _metadata() -> Document:
    return {"timestamp": _now(), "version": "v1"}


def _document_uuid(doc: Document) -> str:
    return _string(doc.get("_id") or doc.get("uuid"), str(uuid4()))


def _version(doc: Document) -> int:
    value = doc.get("version")
    if isinstance(value, int):
        return value
    if isinstance(value, str) and value.isdigit():
        return int(value)
    return 1


def _list_status(value: Any) -> str:
    status = _nullable_string(value)
    return status if status in _LIST_STATUS_VALUES else "draft"


def _supplier_type(value: Any) -> str:
    supplier_type = _nullable_string(value)
    return supplier_type if supplier_type in _SUPPLIER_TYPE_VALUES else "other"


def _documents(value: Any) -> list[Document]:
    if not isinstance(value, list):
        return []
    return [item for item in value if isinstance(item, dict)]


def _string_list(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    return [item for item in (_nullable_string(candidate) for candidate in value) if item]


def _required_string(payload: Document, key: str) -> str:
    value = _nullable_string(payload.get(key))
    if value is None:
        raise HTTPException(status_code=422, detail=f"{key} requis")
    return value


def _string(value: Any, fallback: str) -> str:
    text = _nullable_string(value)
    return text if text is not None else fallback


def _nullable_string(value: Any) -> str | None:
    if isinstance(value, str):
        stripped = value.strip()
        return stripped or None
    if value is None:
        return None
    return str(value)


def _number(value: Any, fallback: float) -> float:
    result = _number_or_none(value)
    return result if result is not None else fallback


def _number_or_none(value: Any) -> float | None:
    if isinstance(value, bool) or value is None:
        return None
    if isinstance(value, int | float):
        return float(value)
    if isinstance(value, str):
        stripped = value.strip().replace(",", ".")
        if not re.fullmatch(r"\d+(\.\d+)?", stripped):
            return None
        return float(stripped)
    return None


def _timestamp(value: Any) -> str:
    return _nullable_timestamp(value) or _now()


def _nullable_timestamp(value: Any) -> str | None:
    if isinstance(value, datetime):
        return value.astimezone(UTC).isoformat().replace("+00:00", "Z")
    return _nullable_string(value)


def _now() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")
