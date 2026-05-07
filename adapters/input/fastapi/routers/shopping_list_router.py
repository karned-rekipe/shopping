from typing import Annotated
from uuid import UUID as StdUUID

from fastapi import APIRouter, Depends, Header, HTTPException, Query, Request, Response
from uuid6 import UUID

from adapters.input.fastapi.dependencies import inject_tenant_uri
from adapters.input.schemas.shopping_list_schema import (
    ShoppingItemCreateSchema,
    ShoppingItemPatchSchema,
    ShoppingListAnalysisSchema,
    ShoppingListCreatedSchema,
    ShoppingListCreateSchema,
    ShoppingListExportResultSchema,
    ShoppingListExportSchema,
    ShoppingListFromMealPlanSchema,
    ShoppingListFromPeriodSchema,
    ShoppingListPatchSchema,
    ShoppingListSchema,
    ShoppingListUpdateSchema,
    shopping_list_create_payload_to_domain,
    shopping_list_update_payload_to_domain,
)
from application.services.shopping_list_service import ShoppingListService
from arclith.adapters.input.fastapi.dependencies import get_duration_ms
from arclith.adapters.input.schemas.response_wrapper import (
    ApiResponse,
    PaginatedResponse,
    ResponseMetadata,
    paginated_response,
    success_response,
)
from arclith.domain.ports.logger import Logger
from domain.exceptions import (
    MealPlanIntegrationError,
    MealPlanNotConfirmed,
    NoConfirmedMealPlanForPeriod,
    ShoppingItemNotFound,
    ShoppingListNotFound,
    VersionConflict,
)


class ShoppingListRouter:
    def __init__(self, service: ShoppingListService, logger: Logger) -> None:
        self._service = service
        self._logger = logger
        self.router = APIRouter(
            prefix="/v1/shopping-lists",
            tags=["shopping-lists"],
            dependencies=[Depends(inject_tenant_uri)],
        )
        self._register_routes()

    def _register_routes(self) -> None:
        self.router.add_api_route("/", self.create_shopping_list, methods=["POST"], response_model=ApiResponse[ShoppingListCreatedSchema], status_code=201)
        self.router.add_api_route("/", self.list_shopping_lists, methods=["GET"], response_model=PaginatedResponse[ShoppingListSchema], status_code=200)
        self.router.add_api_route("/from-meal-plan", self.create_from_meal_plan, methods=["POST"], response_model=ApiResponse[ShoppingListSchema], status_code=201)
        self.router.add_api_route("/from-period", self.create_from_period, methods=["POST"], response_model=ApiResponse[ShoppingListSchema], status_code=201)
        self.router.add_api_route("/{uuid}", self.get_shopping_list, methods=["GET"], response_model=ApiResponse[ShoppingListSchema], status_code=200)
        self.router.add_api_route("/{uuid}", self.update_shopping_list, methods=["PUT"], response_model=ApiResponse[ShoppingListSchema], status_code=200)
        self.router.add_api_route("/{uuid}", self.patch_shopping_list, methods=["PATCH"], response_model=ApiResponse[ShoppingListSchema], status_code=200)
        self.router.add_api_route("/{uuid}", self.delete_shopping_list, methods=["DELETE"], status_code=204)
        self.router.add_api_route("/{uuid}/refresh", self.refresh_shopping_list, methods=["POST"], response_model=ApiResponse[ShoppingListSchema], status_code=200)
        self.router.add_api_route("/{uuid}/items", self.add_item, methods=["POST"], response_model=ApiResponse[ShoppingListSchema], status_code=200)
        self.router.add_api_route("/{uuid}/items/{item_uuid}", self.patch_item, methods=["PATCH"], response_model=ApiResponse[ShoppingListSchema], status_code=200)
        self.router.add_api_route("/{uuid}/items/{item_uuid}", self.delete_item, methods=["DELETE"], response_model=ApiResponse[ShoppingListSchema], status_code=200)
        self.router.add_api_route("/{uuid}/export-text", self.export_text, methods=["POST"], response_model=ApiResponse[ShoppingListExportResultSchema], status_code=200)
        self.router.add_api_route("/{uuid}/analysis", self.analyze, methods=["GET"], response_model=ApiResponse[ShoppingListAnalysisSchema], status_code=200)

    @staticmethod
    def _to_uuid6(uuid: StdUUID) -> UUID:
        return UUID(str(uuid))

    async def create_shopping_list(
        self,
        payload: ShoppingListCreateSchema,
        response: Response,
        request: Request,
        duration_ms: Annotated[float, Depends(get_duration_ms)],
    ) -> ApiResponse[ShoppingListCreatedSchema]:
        result = await self._service.create(shopping_list_create_payload_to_domain(payload))
        location = f"{request.url.path.rstrip('/')}/{result.uuid}"
        response.headers["Location"] = location
        response.headers["ETag"] = self._etag(result.version)
        return success_response(
            ShoppingListCreatedSchema(uuid=result.uuid),
            metadata=ResponseMetadata(duration_ms=int(duration_ms)),
        )

    async def create_from_meal_plan(
        self,
        payload: ShoppingListFromMealPlanSchema,
        response: Response,
        duration_ms: Annotated[float, Depends(get_duration_ms)],
        tenant_uri: Annotated[str | None, Header(alias="X-Tenant-URI")] = None,
    ) -> ApiResponse[ShoppingListSchema]:
        try:
            result = await self._service.generate_from_meal_plan(
                payload.meal_plan_uuid,
                name=payload.name,
                tenant_uri=tenant_uri,
            )
        except (MealPlanIntegrationError, MealPlanNotConfirmed) as exc:
            raise self._to_http_exception(exc) from exc
        response.headers["Location"] = f"/v1/shopping-lists/{result.uuid}"
        response.headers["ETag"] = self._etag(result.version)
        return success_response(
            ShoppingListSchema.model_validate(result, from_attributes=True),
            metadata=ResponseMetadata(duration_ms=int(duration_ms)),
        )

    async def create_from_period(
        self,
        payload: ShoppingListFromPeriodSchema,
        response: Response,
        duration_ms: Annotated[float, Depends(get_duration_ms)],
        tenant_uri: Annotated[str | None, Header(alias="X-Tenant-URI")] = None,
    ) -> ApiResponse[ShoppingListSchema]:
        try:
            result = await self._service.generate_from_period(
                payload.date_start,
                payload.date_end,
                name=payload.name,
                tenant_uri=tenant_uri,
            )
        except (MealPlanIntegrationError, NoConfirmedMealPlanForPeriod) as exc:
            raise self._to_http_exception(exc) from exc
        response.headers["Location"] = f"/v1/shopping-lists/{result.uuid}"
        response.headers["ETag"] = self._etag(result.version)
        return success_response(
            ShoppingListSchema.model_validate(result, from_attributes=True),
            metadata=ResponseMetadata(duration_ms=int(duration_ms)),
        )

    async def get_shopping_list(
        self,
        uuid: StdUUID,
        response: Response,
        duration_ms: Annotated[float, Depends(get_duration_ms)],
    ) -> ApiResponse[ShoppingListSchema]:
        result = await self._service.read(self._to_uuid6(uuid))
        if result is None:
            raise HTTPException(status_code=404, detail="ShoppingList not found")
        response.headers["ETag"] = self._etag(result.version)
        return success_response(
            ShoppingListSchema.model_validate(result, from_attributes=True),
            metadata=ResponseMetadata(duration_ms=int(duration_ms)),
        )

    async def list_shopping_lists(
        self,
        response: Response,
        duration_ms: Annotated[float, Depends(get_duration_ms)],
        page: int = Query(1, ge=1),
        per_page: int = Query(20, ge=1, le=100),
        name: str | None = Query(None, min_length=1),
    ) -> PaginatedResponse[ShoppingListSchema]:
        offset = (page - 1) * per_page
        items, total = await self._service.find_page_filtered(name=name, offset=offset, limit=per_page)
        response.headers["X-Total-Count"] = str(total)
        return paginated_response(
            data=[ShoppingListSchema.model_validate(item, from_attributes=True) for item in items],
            total=total,
            page=page,
            per_page=per_page,
            metadata=ResponseMetadata(duration_ms=int(duration_ms)),
        )

    async def update_shopping_list(
        self,
        uuid: StdUUID,
        payload: ShoppingListUpdateSchema,
        response: Response,
        duration_ms: Annotated[float, Depends(get_duration_ms)],
        if_match: Annotated[str | None, Header(alias="If-Match")] = None,
    ) -> ApiResponse[ShoppingListSchema]:
        expected_version = self._parse_if_match(if_match)
        existing = await self._service.read(self._to_uuid6(uuid))
        if existing is None:
            raise HTTPException(status_code=404, detail="ShoppingList not found")
        try:
            result = await self._service.update_with_expected(
                self._to_uuid6(uuid),
                shopping_list_update_payload_to_domain(existing, payload),
                expected_version,
            )
        except VersionConflict as exc:
            raise self._to_http_exception(exc) from exc
        response.headers["ETag"] = self._etag(result.version)
        return success_response(
            ShoppingListSchema.model_validate(result, from_attributes=True),
            metadata=ResponseMetadata(duration_ms=int(duration_ms)),
        )

    async def patch_shopping_list(
        self,
        uuid: StdUUID,
        payload: ShoppingListPatchSchema,
        response: Response,
        duration_ms: Annotated[float, Depends(get_duration_ms)],
        if_match: Annotated[str | None, Header(alias="If-Match")] = None,
    ) -> ApiResponse[ShoppingListSchema]:
        expected_version = self._parse_if_match(if_match)
        existing = await self._service.read(self._to_uuid6(uuid))
        if existing is None:
            raise HTTPException(status_code=404, detail="ShoppingList not found")
        update = payload.model_dump(exclude_unset=True)
        try:
            result = await self._service.update_with_expected(
                self._to_uuid6(uuid),
                existing.model_copy(update=update),
                expected_version,
            )
        except VersionConflict as exc:
            raise self._to_http_exception(exc) from exc
        response.headers["ETag"] = self._etag(result.version)
        return success_response(
            ShoppingListSchema.model_validate(result, from_attributes=True),
            metadata=ResponseMetadata(duration_ms=int(duration_ms)),
        )

    async def delete_shopping_list(
        self,
        uuid: StdUUID,
        if_match: Annotated[str | None, Header(alias="If-Match")] = None,
    ) -> None:
        expected_version = self._parse_if_match(if_match)
        try:
            await self._service.delete_with_expected(self._to_uuid6(uuid), expected_version)
        except (ShoppingListNotFound, VersionConflict) as exc:
            raise self._to_http_exception(exc) from exc

    async def refresh_shopping_list(
        self,
        uuid: StdUUID,
        response: Response,
        duration_ms: Annotated[float, Depends(get_duration_ms)],
        if_match: Annotated[str | None, Header(alias="If-Match")] = None,
        tenant_uri: Annotated[str | None, Header(alias="X-Tenant-URI")] = None,
    ) -> ApiResponse[ShoppingListSchema]:
        expected_version = self._parse_if_match(if_match)
        try:
            result = await self._service.refresh_from_meal_plan(self._to_uuid6(uuid), expected_version, tenant_uri)
        except (ShoppingListNotFound, VersionConflict, MealPlanIntegrationError, ValueError) as exc:
            raise self._to_http_exception(exc) from exc
        response.headers["ETag"] = self._etag(result.version)
        return success_response(
            ShoppingListSchema.model_validate(result, from_attributes=True),
            metadata=ResponseMetadata(duration_ms=int(duration_ms)),
        )

    async def add_item(
        self,
        uuid: StdUUID,
        payload: ShoppingItemCreateSchema,
        response: Response,
        duration_ms: Annotated[float, Depends(get_duration_ms)],
        if_match: Annotated[str | None, Header(alias="If-Match")] = None,
    ) -> ApiResponse[ShoppingListSchema]:
        expected_version = self._parse_if_match(if_match)
        try:
            result = await self._service.add_manual_item(self._to_uuid6(uuid), payload.to_domain(), expected_version)
        except (ShoppingListNotFound, VersionConflict) as exc:
            raise self._to_http_exception(exc) from exc
        response.headers["ETag"] = self._etag(result.version)
        return success_response(
            ShoppingListSchema.model_validate(result, from_attributes=True),
            metadata=ResponseMetadata(duration_ms=int(duration_ms)),
        )

    async def patch_item(
        self,
        uuid: StdUUID,
        item_uuid: StdUUID,
        payload: ShoppingItemPatchSchema,
        response: Response,
        duration_ms: Annotated[float, Depends(get_duration_ms)],
        if_match: Annotated[str | None, Header(alias="If-Match")] = None,
    ) -> ApiResponse[ShoppingListSchema]:
        expected_version = self._parse_if_match(if_match)
        try:
            result = await self._service.update_item(
                self._to_uuid6(uuid),
                item_uuid,
                expected_version,
                payload.to_changes(),
            )
        except (ShoppingListNotFound, ShoppingItemNotFound, VersionConflict) as exc:
            raise self._to_http_exception(exc) from exc
        response.headers["ETag"] = self._etag(result.version)
        return success_response(
            ShoppingListSchema.model_validate(result, from_attributes=True),
            metadata=ResponseMetadata(duration_ms=int(duration_ms)),
        )

    async def delete_item(
        self,
        uuid: StdUUID,
        item_uuid: StdUUID,
        response: Response,
        duration_ms: Annotated[float, Depends(get_duration_ms)],
        if_match: Annotated[str | None, Header(alias="If-Match")] = None,
    ) -> ApiResponse[ShoppingListSchema]:
        expected_version = self._parse_if_match(if_match)
        try:
            result = await self._service.remove_item(self._to_uuid6(uuid), item_uuid, expected_version)
        except (ShoppingListNotFound, ShoppingItemNotFound, VersionConflict) as exc:
            raise self._to_http_exception(exc) from exc
        response.headers["ETag"] = self._etag(result.version)
        return success_response(
            ShoppingListSchema.model_validate(result, from_attributes=True),
            metadata=ResponseMetadata(duration_ms=int(duration_ms)),
        )

    async def export_text(
        self,
        uuid: StdUUID,
        payload: ShoppingListExportSchema,
        duration_ms: Annotated[float, Depends(get_duration_ms)],
    ) -> ApiResponse[ShoppingListExportResultSchema]:
        try:
            result = await self._service.export_text(
                self._to_uuid6(uuid),
                item_uuids=payload.item_uuids,
                rayon=payload.rayon,
                supplier_uuid=payload.supplier_uuid,
                include_checked=payload.include_checked,
            )
        except ShoppingListNotFound as exc:
            raise self._to_http_exception(exc) from exc
        return success_response(
            ShoppingListExportResultSchema.model_validate(result),
            metadata=ResponseMetadata(duration_ms=int(duration_ms)),
        )

    async def analyze(
        self,
        uuid: StdUUID,
        duration_ms: Annotated[float, Depends(get_duration_ms)],
    ) -> ApiResponse[ShoppingListAnalysisSchema]:
        try:
            result = await self._service.analyze(self._to_uuid6(uuid))
        except ShoppingListNotFound as exc:
            raise self._to_http_exception(exc) from exc
        return success_response(
            ShoppingListAnalysisSchema.model_validate(result),
            metadata=ResponseMetadata(duration_ms=int(duration_ms)),
        )

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

    @staticmethod
    def _to_http_exception(exc: Exception) -> HTTPException:
        if isinstance(exc, (ShoppingListNotFound, ShoppingItemNotFound)):
            return HTTPException(status_code=404, detail=str(exc))
        if isinstance(exc, VersionConflict):
            return HTTPException(status_code=412, detail=str(exc))
        if isinstance(exc, (MealPlanIntegrationError, MealPlanNotConfirmed, NoConfirmedMealPlanForPeriod, ValueError)):
            return HTTPException(status_code=422, detail=str(exc))
        return HTTPException(status_code=500, detail="Unexpected shopping error")
