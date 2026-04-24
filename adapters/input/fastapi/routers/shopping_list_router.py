from typing import Annotated
from uuid import UUID as StdUUID

from fastapi import APIRouter, Depends, Header, HTTPException, Query, Request, Response
from uuid6 import UUID

from adapters.input.fastapi.dependencies import inject_tenant_uri, require_auth
from adapters.input.schemas.shopping_list_schema import (
    ShoppingListCreatedSchema,
    ShoppingListCreateSchema,
    ShoppingListPatchSchema,
    ShoppingListSchema,
    ShoppingListUpdateSchema,
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
from domain.models.shopping_list import ShoppingList


class ShoppingListRouter:
    def __init__(self, service: ShoppingListService, logger: Logger) -> None:
        self._service = service
        self._logger = logger
        self.router = APIRouter(prefix="/v1/shopping_lists", tags=["shopping_lists"], dependencies=[Depends(inject_tenant_uri)])
        self._register_routes()

    def _register_routes(self) -> None:
        self.router.add_api_route(
            methods=["POST"],
            path="/",
            endpoint=self.create_shopping_list,
            summary="Create shopping_list",
            response_model = ApiResponse[ShoppingListCreatedSchema],
            status_code=201,
            responses = {
                400: {"description": "Invalid payload"},
                422: {"description": "Validation failed"},
            },
        )
        self.router.add_api_route(
            methods=["GET"],
            path="/",
            endpoint=self.list_shopping_lists,
            summary="List shopping_lists",
            response_model=PaginatedResponse[ShoppingListSchema],
            status_code=200,
        )
        self.router.add_api_route(
            methods=["GET"],
            path="/{uuid}",
            endpoint=self.get_shopping_list,
            summary="Get shopping_list",
            response_model=ApiResponse[ShoppingListSchema],
            status_code=200,
            responses = {
                404: {"description": "ShoppingList not found"},
            },
        )
        self.router.add_api_route(
            methods=["PUT"],
            path="/{uuid}",
            endpoint=self.update_shopping_list,
            summary="Replace shopping_list",
            status_code=204,
            responses = {
                404: {"description": "ShoppingList not found"},
                412: {"description": "Precondition Failed (version mismatch via If-Match)"},
                422: {"description": "Validation failed"},
            },
        )
        self.router.add_api_route(
            methods=["PATCH"],
            path="/{uuid}",
            endpoint=self.patch_shopping_list,
            summary="Partially update shopping_list",
            status_code=204,
            responses = {
                404: {"description": "ShoppingList not found"},
                412: {"description": "Precondition Failed (version mismatch via If-Match)"},
                422: {"description": "Validation failed"},
            },
        )
        self.router.add_api_route(
            methods=["DELETE"],
            path="/{uuid}",
            endpoint=self.delete_shopping_list,
            summary="Delete shopping_list",
            status_code=204,
            responses = {
                404: {"description": "ShoppingList not found"},
            },
            dependencies=[Depends(require_auth)],
        )
        self.router.add_api_route(
            methods=["POST"],
            path="/{uuid}/duplicate",
            endpoint=self.duplicate_shopping_list,
            summary="Duplicate shopping_list",
            response_model = ApiResponse[ShoppingListCreatedSchema],
            status_code=201,
            responses = {
                404: {"description": "ShoppingList not found"},
            },
        )

    @staticmethod
    def _to_uuid6(uuid: StdUUID) -> UUID:
        return UUID(str(uuid))

    async def create_shopping_list(
        self,
        payload: ShoppingListCreateSchema,
            response: Response,
            request: Request,
        duration_ms: Annotated[float, Depends(get_duration_ms)],
            prefer: Annotated[str | None, Header()] = None,
    ) -> ApiResponse[ShoppingListCreatedSchema] | ApiResponse[ShoppingListSchema]:
        """Create a new reusable shopping_list.

        **SOTA REST Features:**
        - Returns 201 Created with UUID only (minimal response)
        - Location header points to the created resource
        - Supports `Prefer: return=representation` to get full object instead
        - Supports `Idempotency-Key` header to prevent duplicates (via middleware)
        - Returns 422 for validation errors (business logic)

        **Usage:**
        ```bash
        # Minimal response (default)
        curl -X POST /v1/shopping_lists \\
          -H "Content-Type: application/json" \\
          -H "Idempotency-Key: $(uuidgen)" \\
          -d '{"name": "Farine de blé"}'
        
        # Full representation
        curl -X POST /v1/shopping_lists \\
          -H "Prefer: return=representation" \\
          -d '{"name": "Farine de blé"}'
        ```
        """
        result = await self._service.create(ShoppingList(name=payload.name))

        # RFC 7231: Location header on 201 Created
        location = f"{request.url.path.rstrip('/')}/{result.uuid}"
        response.headers["Location"] = location

        # RFC 8288: Link header (HATEOAS)
        response.headers["Link"] = f'<{location}>; rel="self", <{location}/duplicate>; rel="duplicate"'

        # RFC 7240: Prefer header support
        if prefer and "return=representation" in prefer.lower():
            # Client wants full object
            return success_response(
                ShoppingListSchema.model_validate(result, from_attributes = True),
                metadata = ResponseMetadata(duration_ms = int(duration_ms)),
            )

        # Default: minimal response (UUID only)
        return success_response(
            ShoppingListCreatedSchema(uuid = result.uuid),
            metadata=ResponseMetadata(duration_ms=int(duration_ms)),
        )

    async def get_shopping_list(
        self,
        uuid: StdUUID,
            response: Response,
            request: Request,
        duration_ms: Annotated[float, Depends(get_duration_ms)],
    ) -> ApiResponse[ShoppingListSchema]:
        """Get an shopping_list by its UUID.

        **SOTA REST Features:**
        - ETag header based on entity version (for caching/concurrency)
        - Cache-Control: private, max-age=300 (via middleware)
        - Link header for HATEOAS navigation
        - Supports If-None-Match for conditional GET (304 Not Modified)

        **Usage:**
        ```bash
        # First request
        curl -i /v1/shopping_lists/01234...
        # Returns: ETag: "v1"
        
        # Subsequent request (cache validation)
        curl -H 'If-None-Match: "v1"' /v1/shopping_lists/01234...
        # Returns: 304 Not Modified (if unchanged)
        ```
        """
        result = await self._service.read(self._to_uuid6(uuid))
        if result is None:
            self._logger.warning("⚠️ ShoppingList not found via HTTP", uuid=str(uuid))
            raise HTTPException(status_code=404, detail="ShoppingList not found")

        # RFC 7232: ETag for optimistic locking
        response.headers["ETag"] = f'"{result.version}"'

        # RFC 8288: Link header (HATEOAS)
        base = f"{request.url.path.rstrip('/')}"
        response.headers[
            "Link"] = f'<{base}>; rel="self", <{base}/duplicate>; rel="duplicate", </v1/shopping_lists>; rel="collection"'
        
        return success_response(
            ShoppingListSchema.model_validate(result, from_attributes=True),
            metadata=ResponseMetadata(duration_ms=int(duration_ms)),
        )

    async def update_shopping_list(
            self,
            uuid: StdUUID,
            payload: ShoppingListUpdateSchema,
            response: Response,
            request: Request,
            if_match: Annotated[str | None, Header()] = None,
    ) -> None:
        """Replace name of an existing shopping_list (PUT semantics).

        **SOTA REST Features:**
        - Requires If-Match header for optimistic locking
        - Returns 412 Precondition Failed if version mismatch
        - Returns 204 No Content on success
        - Content-Location header points to updated resource
        - New ETag in response headers

        **Usage:**
        ```bash
        # Get current version
        curl -i /v1/shopping_lists/01234...
        # Returns: ETag: "v1"
        
        # Update with version check
        curl -X PUT /v1/shopping_lists/01234... \\
          -H 'If-Match: "v1"' \\
          -d '{"name": "Nouvelle farine"}'
        ```

        The field is fully overwritten.
        Note: changes do not propagate to recipes where this shopping_list is already linked (snapshot model).
        """
        existing = await self._service.read(self._to_uuid6(uuid))
        if existing is None:
            self._logger.warning("⚠️ ShoppingList not found via HTTP (PUT)", uuid = str(uuid))
            raise HTTPException(status_code = 404, detail = "ShoppingList not found")

        # RFC 7232: If-Match validation (optimistic locking)
        if if_match:
            expected_version = int(if_match.strip('"').lstrip('vV'))
            if existing.version != expected_version:
                self._logger.warning(
                    "⚠️ Version mismatch (optimistic lock failure)",
                    uuid = str(uuid),
                    expected = expected_version,
                    current = existing.version,
                )
                raise HTTPException(
                    status_code = 412,
                    detail = f"Version mismatch: expected v{expected_version}, current v{existing.version}",
                )

        updated = await self._service.update(ShoppingList(uuid = self._to_uuid6(uuid), name = payload.name))

        # RFC 7231: Content-Location header
        response.headers["Content-Location"] = f"/v1/shopping_lists/{uuid}"

        # New ETag after update
        response.headers["ETag"] = f'"{updated.version}"'

    async def patch_shopping_list(
            self,
            uuid: StdUUID,
            payload: ShoppingListPatchSchema,
            response: Response,
            request: Request,
            if_match: Annotated[str | None, Header()] = None,
    ) -> None:
        """Partially update an shopping_list (PATCH semantics).

        **SOTA REST Features:**
        - Requires If-Match header for optimistic locking
        - Returns 412 Precondition Failed if version mismatch
        - Returns 204 No Content on success
        - Content-Location header points to updated resource

        Only the fields provided in the body are updated; omitted fields keep their current value.
        Note: changes do not propagate to recipes where this shopping_list is already linked (snapshot model).
        """
        existing = await self._service.read(self._to_uuid6(uuid))
        if existing is None:
            self._logger.warning("⚠️ ShoppingList not found via HTTP (PATCH)", uuid = str(uuid))
            raise HTTPException(status_code=404, detail="ShoppingList not found")

        # RFC 7232: If-Match validation
        if if_match:
            expected_version = int(if_match.strip('"').lstrip('vV'))
            if existing.version != expected_version:
                self._logger.warning(
                    "⚠️ Version mismatch (optimistic lock failure)",
                    uuid = str(uuid),
                    expected = expected_version,
                    current = existing.version,
                )
                raise HTTPException(
                    status_code = 412,
                    detail = f"Version mismatch: expected v{expected_version}, current v{existing.version}",
                )

        updated = await self._service.update(
            ShoppingList(
                uuid = existing.uuid,
                name = payload.name if payload.name is not None else existing.name,
            )
        )

        # RFC 7231: Content-Location header
        response.headers["Content-Location"] = f"/v1/shopping_lists/{uuid}"

        # New ETag after update
        response.headers["ETag"] = f'"{updated.version}"'

    async def delete_shopping_list(self, uuid: StdUUID) -> None:
        """Soft-delete an shopping_list.

        **SOTA REST Features:**
        - Returns 204 No Content on success
        - Idempotent (deleting already-deleted resource returns 204)

        The shopping_list is marked as deleted and excluded from list results.
        It is retained until the purge retention period expires.
        Use `DELETE /admin/purge` to permanently remove all expired entities.
        """
        await self._service.delete(self._to_uuid6(uuid))

    async def list_shopping_lists(
        self,
        response: Response,
        duration_ms: Annotated[float, Depends(get_duration_ms)],
        page: int = Query(1, ge=1, description="Page number (1-indexed)"),
        per_page: int = Query(20, ge=1, le=100, description="Items per page"),
        name: str | None = Query(None, min_length=1, description="Filter by name (partial, case-insensitive)"),
    ) -> PaginatedResponse[ShoppingListSchema]:
        """List all active (non-deleted) shopping_lists.

        **SOTA REST Features:**
        - X-Total-Count header for total items (useful for pagination UI)
        - Cache-Control: private, max-age=60 (via middleware)
        - Always returns 200 OK, even if empty list

        Pass `name` for a partial, case-insensitive name filter.
        Each item: uuid, name, unit, created_at, updated_at, version.
        Use the returned UUIDs with `POST /v1/recipes/{uuid}/shopping_lists/{shopping_list_uuid}` to link them to a recipe.
        """
        offset = (page - 1) * per_page
        items, total = await self._service.find_page_filtered(name=name, offset=offset, limit=per_page)

        # X-Total-Count header (common practice for pagination)
        response.headers["X-Total-Count"] = str(total)

        return paginated_response(
            data=[ShoppingListSchema.model_validate(i, from_attributes=True) for i in items],
            total=total,
            page=page,
            per_page=per_page,
            metadata=ResponseMetadata(duration_ms=int(duration_ms)),
        )

    async def duplicate_shopping_list(
        self,
        uuid: StdUUID,
            response: Response,
            request: Request,
        duration_ms: Annotated[float, Depends(get_duration_ms)],
            prefer: Annotated[str | None, Header()] = None,
    ) -> ApiResponse[ShoppingListCreatedSchema] | ApiResponse[ShoppingListSchema]:
        """Duplicate an shopping_list, assigning it a new UUID.

        **SOTA REST Features:**
        - Returns 201 Created with UUID only (minimal response)
        - Location header points to the duplicated resource
        - Supports `Prefer: return=representation` to get full object

        Creates an independent copy with the same name and unit.
        Returns the UUID of the new shopping_list.
        """
        result = await self._service.duplicate(self._to_uuid6(uuid))

        # RFC 7231: Location header on 201 Created
        location = f"/v1/shopping_lists/{result.uuid}"
        response.headers["Location"] = location

        # RFC 8288: Link header
        response.headers["Link"] = f'<{location}>; rel="self", </v1/shopping_lists>; rel="collection"'

        # RFC 7240: Prefer header support
        if prefer and "return=representation" in prefer.lower():
            return success_response(
                ShoppingListSchema.model_validate(result, from_attributes = True),
                metadata = ResponseMetadata(duration_ms = int(duration_ms)),
            )

        # Default: minimal response (UUID only)
        return success_response(
            ShoppingListCreatedSchema(uuid = result.uuid),
            metadata=ResponseMetadata(duration_ms=int(duration_ms)),
        )

