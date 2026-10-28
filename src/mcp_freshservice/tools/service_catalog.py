"""Service catalog: browse items and place service requests."""

from __future__ import annotations

from typing import Annotated, Any

from mcp.server.fastmcp.exceptions import ToolError
from pydantic import Field

from ..client import clean, get_client
from ._common import CustomFields, Page, Result, WorkspaceId
from ._registry import toolset

ts = toolset("service_catalog", "Service catalog items and service requests", default=True)

DisplayId = Annotated[int, Field(description="Service item display_id")]


@ts.tool("List service catalog categories")
async def list_service_catalog_categories(workspace_id: WorkspaceId = None) -> Result:
    """List service catalog categories."""
    client = get_client()
    return await client.get("/service_catalog/categories", {"workspace_id": client.workspace(workspace_id)})


@ts.tool("List service items")
async def list_service_items(
    page: Page = 1,
    per_page: Annotated[
        int, Field(ge=1, le=30, description="Records per page (max 30 for this endpoint)")
    ] = 30,
    category_id: Annotated[int | None, Field(description="Only items in this category")] = None,
    workspace_id: WorkspaceId = None,
) -> Result:
    """List one page of service catalog items."""
    client = get_client()
    params = {"category_id": category_id, "workspace_id": client.workspace(workspace_id)}
    return await client.list(
        "/service_catalog/items", "service_items", page=page, per_page=per_page, params=params
    )


@ts.tool("Search service items")
async def search_service_items(
    search_term: Annotated[str, Field(min_length=1, description="e.g. 'vpn access'")],
    page: Page = 1,
    per_page: Annotated[int, Field(ge=1, le=30, description="Records per page")] = 30,
    user_email: Annotated[str | None, Field(description="Search on behalf of this user")] = None,
    workspace_id: WorkspaceId = None,
) -> Result:
    """Search service catalog items by keyword."""
    client = get_client()
    params = {
        "search_term": search_term,
        "user_email": user_email,
        "workspace_id": client.workspace(workspace_id),
    }
    return await client.list(
        "/service_catalog/items/search", "service_items", page=page, per_page=per_page, params=params
    )


@ts.tool("Get service item")
async def get_service_item(display_id: DisplayId) -> Result:
    """Get a service item, including its form fields (custom_fields names to use when placing a request)."""
    return await get_client().get(f"/service_catalog/items/{display_id}")


@ts.tool("Create service request", "create")
async def create_service_request(
    display_id: DisplayId,
    email: Annotated[str, Field(description="Email of the requester placing the request")],
    quantity: Annotated[int, Field(ge=1, description="Quantity")] = 1,
    requested_for: Annotated[str | None, Field(description="Email of the user the request is for")] = None,
    custom_fields: CustomFields = None,
    child_items: Annotated[
        list[dict[str, Any]] | None, Field(description="Child items: [{'display_id': 12, 'quantity': 1}]")
    ] = None,
) -> Result:
    """Place a service request for a catalog item."""
    if requested_for and "@" not in requested_for:
        raise ToolError("requested_for must be an email address")
    payload = clean(
        {
            "email": email,
            "quantity": quantity,
            "requested_for": requested_for,
            "custom_fields": custom_fields,
            "child_items": child_items,
        }
    )
    return await get_client().post(f"/service_catalog/items/{display_id}/place_request", payload)
