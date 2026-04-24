import fastmcp

from adapters.input.fastmcp.dependencies import inject_tenant_uri
from application.services.shopping_list_service import ShoppingListService
from arclith.domain.ports.logger import Logger

_EXPLORE_PREVIEW_LIMIT = 20


class ShoppingListPrompts:
    def __init__(self, service: ShoppingListService, logger: Logger, mcp: fastmcp.FastMCP) -> None:
        self._service = service
        self._logger = logger
        self._mcp = mcp
        self._register_prompts()

    def _register_prompts(self) -> None:
        service = self._service

        @self._mcp.prompt
        def check_duplicate(shopping_list_name: str) -> str:
            """Check for duplicates before creating a new shopping_list.

            Use this prompt before calling create_shopping_list.
            The LLM will guide you to call list_shopping_lists with a partial
            name filter to surface any existing match.
            """
            return (
                f"Before creating the shopping_list '{shopping_list_name}', "
                "call list_shopping_lists with a partial name filter to check for existing similar entries. "
                "If a match is found, suggest using the existing one instead of creating a duplicate."
            )

        @self._mcp.prompt
        async def explore_shopping_lists(ctx: fastmcp.Context) -> str:
            """Explore and discover available shopping_lists.

            Loads the current catalog and guides the LLM to help the user
            search by name or identify what is available.
            """
            await inject_tenant_uri(ctx)
            items = await service.find_all()
            if not items:
                snapshot = "No shopping_lists available yet. Use create_shopping_list to add the first one."
            else:
                names = ", ".join(i.name for i in items[:_EXPLORE_PREVIEW_LIMIT])
                total = len(items)
                snapshot = f"{total} shopping_list(s) available: {names}{'...' if total > _EXPLORE_PREVIEW_LIMIT else '.'}"
            return (
                f"{snapshot}\n\n"
                "Help me explore these shopping_lists: search by name, "
                "or suggest which ones to use for a given dish."
            )

        @self._mcp.prompt
        def mcp_help() -> str:
            """Overview of all MCP capabilities exposed by this server.

            Lists every tool, prompt, and resource with a short description.
            Use this as a starting point when discovering what this server can do.
            """
            return (
                "Here are all the capabilities exposed by this MCP server:\n\n"
                "**Tools** (actions):\n"
                "- create_shopping_list(name) — create a new shopping_list\n"
                "- get_shopping_list(uuid) — retrieve by UUID\n"
                "- update_shopping_list(uuid, name) — full replacement (PUT semantics)\n"
                "- delete_shopping_list(uuid) — soft-delete\n"
                "- list_shopping_lists(name?) — list all active, optional partial name filter\n"
                "- duplicate_shopping_list(uuid) — clone with a new UUID\n"
                "- purge_shopping_lists() — permanently remove expired soft-deleted entries\n\n"
                "**Prompts** (LLM guidance):\n"
                "- check_duplicate(shopping_list_name) — avoid duplicates before creating\n"
                "- explore_shopping_lists — discover and filter available shopping_lists\n"
                "- mcp_help — this overview\n\n"
                "**Resources** (read-only data):\n"
                "- resource://shopping-lists/sample — first 5 shopping_lists (quick dataset preview)\n"
                "- resource://shopping-lists/recent — last 10 shopping_lists by creation date, newest first\n"
                "- resource://shopping-list/{uuid} — single shopping_list by UUID\n"
            )
