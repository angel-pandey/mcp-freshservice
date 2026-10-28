"""Asset management and canned responses."""

from __future__ import annotations

from typing import Annotated, Any, Literal

from mcp.server.fastmcp.exceptions import ToolError
from pydantic import Field

from ..client import clean, get_client, quote_query
from ._common import OrderType, Page, PerPage, Result, WorkspaceId
from ._registry import toolset

ts = toolset("assets", "Assets, asset types, and canned responses")

DisplayId = Annotated[int, Field(description="Asset display_id (the number shown as ASSET-<n>)")]
AssetTypeId = Annotated[int, Field(description="Asset type ID")]


@ts.tool("List asset types")
async def list_asset_types(page: Page = 1, per_page: PerPage = 30) -> Result:
    """List asset types (Hardware, Software, ...). Needed for create_asset."""
    return await get_client().list("/asset_types", "asset_types", page=page, per_page=per_page)


@ts.tool("Get asset type fields")
async def get_asset_type_fields(asset_type_id: AssetTypeId) -> Result:
    """List the fields (including type-specific ones) of an asset type; use their names in type_fields."""
    return await get_client().get(f"/asset_types/{asset_type_id}/fields")


@ts.tool("List assets")
async def get_assets(
    page: Page = 1,
    per_page: PerPage = 30,
    search: Annotated[
        str | None,
        Field(
            description="Quick search on ONE field: name, asset_tag, serial_number, mac_addresses, ip_addresses, "
            "uuid, item_id or imei_number, e.g. \"name:'dell'\". Escape apostrophes in values with a backslash. "
            "Cannot be sorted. Outer double quotes added for you"
        ),
    ] = None,
    filter: Annotated[
        str | None,
        Field(
            description="Query over: asset_type_id, department_id, location_id, asset_state (e.g. 'IN USE'), "
            "user_id, agent_id, name, asset_tag, serial_number, created_at/updated_at (YYYY-MM-DD), "
            "workspace_id, plus type fields. e.g. \"asset_state:'IN USE' AND created_at:>'2025-01-01'\". "
            "Max 512 characters, max 40 pages, 30 per page. Outer double quotes added for you"
        ),
    ] = None,
    include: Annotated[
        list[Literal["type_fields"]] | None,
        Field(description="'type_fields' adds asset-type specific fields"),
    ] = None,
    trashed: Annotated[bool | None, Field(description="true: list assets in trash")] = None,
    order_by: Annotated[Literal["id", "created_at", "updated_at"] | None, Field()] = None,
    order_type: OrderType = None,
    workspace_id: WorkspaceId = None,
) -> Result:
    """List assets, optionally searched or filtered. workspace_id 0 returns all workspaces (global fields only)."""
    client = get_client()
    params = {
        "search": quote_query(search) if search else None,
        "filter": quote_query(filter) if filter else None,
        "include": include,
        "trashed": trashed,
        "order_by": order_by,
        "order_type": order_type,
        "workspace_id": client.workspace(workspace_id),
    }
    return await client.list("/assets", "assets", page=page, per_page=per_page, params=params)


@ts.tool("Get asset")
async def get_asset(
    display_id: DisplayId,
    include: Annotated[
        list[Literal["type_fields"]] | None, Field(description="'type_fields' adds type fields")
    ] = None,
) -> Result:
    """Get an asset by display_id."""
    return await get_client().get(f"/assets/{display_id}", {"include": include})


@ts.tool("Create asset", "create")
async def create_asset(
    name: Annotated[str, Field(min_length=1, description="Asset name")],
    asset_type_id: AssetTypeId,
    description: Annotated[str | None, Field()] = None,
    asset_tag: Annotated[str | None, Field()] = None,
    impact: Annotated[Literal["low", "medium", "high"] | None, Field()] = None,
    usage_type: Annotated[Literal["permanent", "loaner"] | None, Field()] = None,
    user_id: Annotated[int | None, Field(description="Used by (requester ID)")] = None,
    agent_id: Annotated[int | None, Field(description="Managed by (agent ID)")] = None,
    group_id: Annotated[int | None, Field(description="Managed by group")] = None,
    location_id: Annotated[int | None, Field()] = None,
    department_id: Annotated[int | None, Field()] = None,
    type_fields: Annotated[
        dict[str, Any] | None, Field(description="Asset-type specific fields (see get_asset_type_fields)")
    ] = None,
    workspace_id: WorkspaceId = None,
) -> Result:
    """Create an asset."""
    client = get_client()
    payload = clean(
        {
            "name": name,
            "asset_type_id": asset_type_id,
            "description": description,
            "asset_tag": asset_tag,
            "impact": impact,
            "usage_type": usage_type,
            "user_id": user_id,
            "agent_id": agent_id,
            "group_id": group_id,
            "location_id": location_id,
            "department_id": department_id,
            "type_fields": type_fields,
            "workspace_id": client.workspace(workspace_id),
        }
    )
    return await client.post("/assets", payload)


@ts.tool("Update asset", "update")
async def update_asset(
    display_id: DisplayId,
    asset_fields: Annotated[
        dict[str, Any], Field(description="Fields to change, same names as create_asset")
    ],
) -> Result:
    """Update an asset. Only the supplied fields change."""
    if not asset_fields:
        raise ToolError("No fields provided for update")
    return await get_client().put(f"/assets/{display_id}", clean(asset_fields))


@ts.tool("Delete asset", "delete")
async def delete_asset(display_id: DisplayId) -> Result:
    """Move an asset to trash (restorable with restore_asset)."""
    return await get_client().delete(f"/assets/{display_id}")


@ts.tool("Restore asset", "update")
async def restore_asset(display_id: DisplayId) -> Result:
    """Restore a trashed asset."""
    return await get_client().put(f"/assets/{display_id}/restore")


@ts.tool("List asset components")
async def list_asset_components(display_id: DisplayId) -> Result:
    """List an asset's components (processor, memory, disks, ...)."""
    return await get_client().get(f"/assets/{display_id}/components")


@ts.tool("List asset contracts")
async def list_asset_contracts(display_id: DisplayId) -> Result:
    """List contracts associated with an asset."""
    return await get_client().get(f"/assets/{display_id}/contracts")


@ts.tool("List asset requests")
async def list_asset_requests(display_id: DisplayId) -> Result:
    """List tickets, problems, changes and releases associated with an asset."""
    return await get_client().get(f"/assets/{display_id}/requests")


@ts.tool("List asset relationships")
async def list_asset_relationships(display_id: DisplayId) -> Result:
    """List relationships (depends on, used by, ...) of an asset."""
    return await get_client().get(f"/assets/{display_id}/relationships")


# --- Canned responses ----------------------------------------------------------------------------


@ts.tool("List canned responses")
async def get_all_canned_response(page: Page = 1, per_page: PerPage = 30) -> Result:
    """List canned (saved reply) responses."""
    return await get_client().list("/canned_responses", "canned_responses", page=page, per_page=per_page)


@ts.tool("Get canned response")
async def get_canned_response(
    canned_response_id: Annotated[int, Field(description="Canned response ID")],
) -> Result:
    """Get a canned response by ID, including its content."""
    return await get_client().get(f"/canned_responses/{canned_response_id}")


@ts.tool("List canned response folders")
async def list_all_canned_response_folder(page: Page = 1, per_page: PerPage = 30) -> Result:
    """List canned response folders."""
    return await get_client().list(
        "/canned_response_folders", "canned_response_folders", page=page, per_page=per_page
    )


@ts.tool("List canned responses in folder")
async def list_canned_response_folder(
    folder_id: Annotated[int, Field(description="Canned response folder ID")],
    page: Page = 1,
    per_page: PerPage = 30,
) -> Result:
    """List the canned responses inside a folder."""
    return await get_client().list(
        f"/canned_response_folders/{folder_id}/canned_responses",
        "canned_responses",
        page=page,
        per_page=per_page,
    )
