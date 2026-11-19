from typing import Annotated
from uuid import UUID as StdUUID

from fastapi import APIRouter, Depends, Header, HTTPException, Query, Request, Response
from uuid6 import UUID

from adapters.input.fastapi.dependencies import inject_tenant_uri
from adapters.input.schemas.supplier_schema import (
    SupplierCreatedSchema,
    SupplierCreateSchema,
    SupplierPatchSchema,
    SupplierSchema,
    SupplierUpdateSchema,
    supplier_create_payload_to_domain,
    supplier_update_payload_to_domain,
)
from application.services.supplier_service import SupplierService
from arclith.adapters.input.fastapi.dependencies import get_duration_ms
from arclith.adapters.input.schemas.response_wrapper import (
    ApiResponse,
    PaginatedResponse,
    ResponseMetadata,
    paginated_response,
    success_response,
)
from arclith.domain.ports.logger import Logger


class SupplierRouter:
    def __init__(self, service: SupplierService, logger: Logger) -> None:
        self._service = service
        self._logger = logger
        self.router = APIRouter(prefix="/v1/suppliers", tags=["suppliers"], dependencies=[Depends(inject_tenant_uri)])
        self._register_routes()

    def _register_routes(self) -> None:
        self.router.add_api_route("/", self.create_supplier, methods=["POST"], response_model=ApiResponse[SupplierCreatedSchema], status_code=201)
        self.router.add_api_route("/", self.list_suppliers, methods=["GET"], response_model=PaginatedResponse[SupplierSchema], status_code=200)
        self.router.add_api_route("/{uuid}", self.get_supplier, methods=["GET"], response_model=ApiResponse[SupplierSchema], status_code=200)
        self.router.add_api_route("/{uuid}", self.update_supplier, methods=["PUT"], response_model=ApiResponse[SupplierSchema], status_code=200)
        self.router.add_api_route("/{uuid}", self.patch_supplier, methods=["PATCH"], response_model=ApiResponse[SupplierSchema], status_code=200)
        self.router.add_api_route("/{uuid}", self.delete_supplier, methods=["DELETE"], status_code=204)

    @staticmethod
    def _to_uuid6(uuid: StdUUID) -> UUID:
        return UUID(str(uuid))

    async def create_supplier(
        self,
        payload: SupplierCreateSchema,
        response: Response,
        request: Request,
        duration_ms: Annotated[float, Depends(get_duration_ms)],
    ) -> ApiResponse[SupplierCreatedSchema]:
        result = await self._service.create(supplier_create_payload_to_domain(payload))
        response.headers["Location"] = f"{request.url.path.rstrip('/')}/{result.uuid}"
        response.headers["ETag"] = self._etag(result.version)
        return success_response(SupplierCreatedSchema(uuid=result.uuid), metadata=ResponseMetadata(duration_ms=int(duration_ms)))

    async def get_supplier(
        self,
        uuid: StdUUID,
        response: Response,
        duration_ms: Annotated[float, Depends(get_duration_ms)],
    ) -> ApiResponse[SupplierSchema]:
        result = await self._service.read(self._to_uuid6(uuid))
        if result is None:
            raise HTTPException(status_code=404, detail="Supplier not found")
        response.headers["ETag"] = self._etag(result.version)
        return success_response(SupplierSchema.model_validate(result, from_attributes=True), metadata=ResponseMetadata(duration_ms=int(duration_ms)))

    async def list_suppliers(
        self,
        response: Response,
        duration_ms: Annotated[float, Depends(get_duration_ms)],
        page: int = Query(1, ge=1),
        per_page: int = Query(20, ge=1, le=100),
        name: str | None = Query(None, min_length=1),
    ) -> PaginatedResponse[SupplierSchema]:
        offset = (page - 1) * per_page
        items, total = await self._service.find_page_filtered(name=name, offset=offset, limit=per_page)
        response.headers["X-Total-Count"] = str(total)
        return paginated_response(
            data=[SupplierSchema.model_validate(item, from_attributes=True) for item in items],
            total=total,
            page=page,
            per_page=per_page,
            metadata=ResponseMetadata(duration_ms=int(duration_ms)),
        )

    async def update_supplier(
        self,
        uuid: StdUUID,
        payload: SupplierUpdateSchema,
        response: Response,
        duration_ms: Annotated[float, Depends(get_duration_ms)],
        if_match: Annotated[str | None, Header(alias="If-Match")] = None,
    ) -> ApiResponse[SupplierSchema]:
        expected_version = self._parse_if_match(if_match)
        existing = await self._service.read(self._to_uuid6(uuid))
        if existing is None:
            raise HTTPException(status_code=404, detail="Supplier not found")
        if existing.version != expected_version:
            raise HTTPException(status_code=412, detail=f"expected version {expected_version}, current version {existing.version}")
        result = await self._service.update(supplier_update_payload_to_domain(existing, payload))
        response.headers["ETag"] = self._etag(result.version)
        return success_response(SupplierSchema.model_validate(result, from_attributes=True), metadata=ResponseMetadata(duration_ms=int(duration_ms)))

    async def patch_supplier(
        self,
        uuid: StdUUID,
        payload: SupplierPatchSchema,
        response: Response,
        duration_ms: Annotated[float, Depends(get_duration_ms)],
        if_match: Annotated[str | None, Header(alias="If-Match")] = None,
    ) -> ApiResponse[SupplierSchema]:
        expected_version = self._parse_if_match(if_match)
        existing = await self._service.read(self._to_uuid6(uuid))
        if existing is None:
            raise HTTPException(status_code=404, detail="Supplier not found")
        if existing.version != expected_version:
            raise HTTPException(status_code=412, detail=f"expected version {expected_version}, current version {existing.version}")
        result = await self._service.update(existing.model_copy(update=payload.model_dump(exclude_unset=True)))
        response.headers["ETag"] = self._etag(result.version)
        return success_response(SupplierSchema.model_validate(result, from_attributes=True), metadata=ResponseMetadata(duration_ms=int(duration_ms)))

    async def delete_supplier(
        self,
        uuid: StdUUID,
        if_match: Annotated[str | None, Header(alias="If-Match")] = None,
    ) -> None:
        expected_version = self._parse_if_match(if_match)
        existing = await self._service.read(self._to_uuid6(uuid))
        if existing is None:
            raise HTTPException(status_code=404, detail="Supplier not found")
        if existing.version != expected_version:
            raise HTTPException(status_code=412, detail=f"expected version {expected_version}, current version {existing.version}")
        await self._service.delete(existing.uuid)

    @staticmethod
    def _etag(version: int) -> str:
        return f'W/"{version}"'

    @staticmethod
    def _parse_if_match(value: str | None) -> int:
        if value is None:
            raise HTTPException(status_code=412, detail="If-Match header is required")
        cleaned = value.strip()
        if cleaned.startswith("W/"):
            cleaned = cleaned[2:]
        cleaned = cleaned.strip('"').lstrip("vV")
        if not cleaned.isdigit():
            raise HTTPException(status_code=412, detail="Invalid If-Match header")
        return int(cleaned)
