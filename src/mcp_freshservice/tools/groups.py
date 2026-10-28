"""Agent groups and requester groups."""

from __future__ import annotations

from typing import Annotated, Any, Literal

from mcp.server.fastmcp.exceptions import ToolError
from pydantic import Field

from ..client import clean, get_client
from ._common import Page, PerPage, Result
from ._registry import toolset

ts = toolset("groups", "Agent groups and requester groups (with membership)", default=True)

GroupId = Annotated[int, Field(description="Agent group ID")]
RequesterGroupId = Annotated[int, Field(description="Requester group ID")]
UnassignedFor = Literal["30m", "1h", "2h", "4h", "8h", "12h", "1d", "2d", "3d"]


# --- Agent groups (/groups) ----------------------------------------------------------------------


@ts.tool("List agent groups")
async def get_all_agent_groups(page: Page = 1, per_page: PerPage = 30) -> Result:
    """List agent groups."""
    return await get_client().list("/groups", "groups", page=page, per_page=per_page)


@ts.tool("Get agent group")
async def get_agent_group(group_id: GroupId) -> Result:
    """Get an agent group by ID, including its members."""
    return await get_client().get(f"/groups/{group_id}")


@ts.tool("Create agent group", "create")
async def create_group(
    name: Annotated[str, Field(min_length=1, description="Group name")],
    description: Annotated[str | None, Field(description="Description")] = None,
    agent_ids: Annotated[list[int] | None, Field(description="Member agent IDs")] = None,
    observer_ids: Annotated[list[int] | None, Field(description="Observer agent IDs")] = None,
    members: Annotated[list[int] | None, Field(description="Alias of agent_ids on some accounts")] = None,
    auto_ticket_assign: Annotated[bool | None, Field(description="Automatically assign new tickets")] = None,
    escalate_to: Annotated[
        int | None, Field(description="Agent ID to escalate unassigned tickets to")
    ] = None,
    unassigned_for: Annotated[
        UnassignedFor | None, Field(description="Escalate after this idle time")
    ] = None,
    business_hours_id: Annotated[int | None, Field(description="Business hours ID")] = None,
    group_type: Annotated[
        str | None, Field(description="e.g. 'support_agent_group' or 'oncall_agents'")
    ] = None,
) -> Result:
    """Create an agent group."""
    payload = clean(
        {
            "name": name,
            "description": description,
            "agent_ids": agent_ids,
            "observer_ids": observer_ids,
            "members": members,
            "auto_ticket_assign": auto_ticket_assign,
            "escalate_to": escalate_to,
            "unassigned_for": unassigned_for,
            "business_hours_id": business_hours_id,
            "group_type": group_type,
        }
    )
    return await get_client().post("/groups", payload)


@ts.tool("Update agent group", "update")
async def update_group(
    group_id: GroupId,
    group_fields: Annotated[
        dict[str, Any],
        Field(
            description="Fields to change: name, description, agent_ids, observer_ids, auto_ticket_assign, "
            "escalate_to, unassigned_for, business_hours_id"
        ),
    ],
) -> Result:
    """Update an agent group. Only the supplied fields change."""
    if not group_fields:
        raise ToolError("No fields provided for update")
    return await get_client().put(f"/groups/{group_id}", clean(group_fields))


@ts.tool("Delete agent group", "delete")
async def delete_group(group_id: GroupId) -> Result:
    """Delete an agent group."""
    return await get_client().delete(f"/groups/{group_id}")


# --- Requester groups (/requester_groups) --------------------------------------------------------


@ts.tool("List requester groups")
async def get_all_requester_groups(page: Page = 1, per_page: PerPage = 30) -> Result:
    """List requester groups."""
    return await get_client().list("/requester_groups", "requester_groups", page=page, per_page=per_page)


@ts.tool("Get requester group")
async def get_requester_group(requester_group_id: RequesterGroupId) -> Result:
    """Get a requester group by ID."""
    return await get_client().get(f"/requester_groups/{requester_group_id}")


@ts.tool("Create requester group", "create")
async def create_requester_group(
    name: Annotated[str, Field(min_length=1, description="Group name")],
    description: Annotated[str | None, Field(description="Description")] = None,
    type: Annotated[
        Literal["manual", "rule_based"] | None, Field(description="Membership type (default manual)")
    ] = None,
    conditions: Annotated[
        list[dict[str, Any]] | None,
        Field(
            description="Rules for rule_based groups, e.g. [{'name': 'department_id', 'operator': 'is', "
            "'value': 5}]"
        ),
    ] = None,
) -> Result:
    """Create a requester group."""
    payload = clean({"name": name, "description": description, "type": type, "conditions": conditions})
    return await get_client().post("/requester_groups", payload)


@ts.tool("Update requester group", "update")
async def update_requester_group(
    requester_group_id: RequesterGroupId,
    name: Annotated[str | None, Field(description="New name")] = None,
    description: Annotated[str | None, Field(description="New description")] = None,
    conditions: Annotated[
        list[dict[str, Any]] | None, Field(description="New rules (rule_based groups)")
    ] = None,
) -> Result:
    """Update a requester group."""
    payload = clean({"name": name, "description": description, "conditions": conditions})
    if not payload:
        raise ToolError("Provide at least one of name, description or conditions")
    return await get_client().put(f"/requester_groups/{requester_group_id}", payload)


@ts.tool("Delete requester group", "delete")
async def delete_requester_group(requester_group_id: RequesterGroupId) -> Result:
    """Delete a requester group."""
    return await get_client().delete(f"/requester_groups/{requester_group_id}")


@ts.tool("List requester group members")
async def list_requester_group_members(
    requester_group_id: RequesterGroupId, page: Page = 1, per_page: PerPage = 30
) -> Result:
    """List the requesters in a requester group."""
    return await get_client().list(
        f"/requester_groups/{requester_group_id}/members", "requesters", page=page, per_page=per_page
    )


@ts.tool("Add requester to group", "update")
async def add_requester_to_group(
    requester_group_id: RequesterGroupId, requester_id: Annotated[int, Field(description="Requester ID")]
) -> Result:
    """Add a requester to a manual requester group."""
    return await get_client().post(f"/requester_groups/{requester_group_id}/members/{requester_id}")


@ts.tool("Remove requester from group", "update")
async def remove_requester_from_group(
    requester_group_id: RequesterGroupId, requester_id: Annotated[int, Field(description="Requester ID")]
) -> Result:
    """Remove a requester from a manual requester group."""
    return await get_client().delete(f"/requester_groups/{requester_group_id}/members/{requester_id}")
