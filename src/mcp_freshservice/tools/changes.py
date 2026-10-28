"""Change management: changes, notes, tasks, time entries and approvals."""

from __future__ import annotations

from typing import Annotated, Any

from mcp.server.fastmcp.exceptions import ToolError
from pydantic import Field

from ..client import clean, get_client, quote_query
from ._common import (
    CustomFields,
    Impact,
    OrderType,
    Page,
    PerPage,
    Priority,
    Query,
    Result,
    UpdatedSince,
    WorkspaceId,
    add_approvals,
    add_notes,
    add_tasks,
    add_time_entries,
)
from ._registry import toolset

ts = toolset("changes", "Change requests with planning fields")

ChangeId = Annotated[int, Field(description="Change ID")]
ChangeStatus = Annotated[
    int,
    Field(
        ge=1,
        le=6,
        description="1 Open, 2 Planning, 3 Awaiting Approval, 4 Pending Release, 5 Pending Review, 6 Closed",
    ),
]
Risk = Annotated[int, Field(ge=1, le=4, description="1 Low, 2 Medium, 3 High, 4 Very High")]
ChangeType = Annotated[int, Field(ge=1, le=4, description="1 Minor, 2 Standard, 3 Major, 4 Emergency")]
PLANNING_FIELDS = ("reason_for_change", "change_impact", "rollout_plan", "backout_plan")


def _planning(fields: dict[str, Any]) -> dict[str, Any] | None:
    """Planning fields are objects ({"description": "..."}); accept plain strings too."""
    out = {k: ({"description": v} if isinstance(v, str) else v) for k, v in fields.items() if v is not None}
    return out or None


@ts.tool("Get change form fields")
async def list_change_fields(workspace_id: WorkspaceId = None) -> Result:
    """List change form fields, including custom fields and allowed choices."""
    client = get_client()
    return await client.get("/change_form_fields", {"workspace_id": client.workspace(workspace_id)})


@ts.tool("List changes")
async def get_changes(
    page: Page = 1,
    per_page: PerPage = 30,
    view: Annotated[
        str | None,
        Field(
            description="Name of a default view (e.g. 'my_open', 'unassigned') or ID of a custom view. "
            "Cannot be combined with query"
        ),
    ] = None,
    query: Annotated[str | None, Field(description="Freshservice query (see filter_changes)")] = None,
    updated_since: UpdatedSince = None,
    order_by: Annotated[str | None, Field(description="Sort field, e.g. 'created_at', 'priority'")] = None,
    order_type: OrderType = None,
    workspace_id: WorkspaceId = None,
) -> Result:
    """List changes, optionally narrowed by a view or a query."""
    if view and query:
        raise ToolError("view and query cannot be used together")
    client = get_client()
    params = {
        "view": view,
        "query": quote_query(query) if query else None,
        "updated_since": updated_since,
        "order_by": order_by,
        "order_type": order_type,
        "workspace_id": client.workspace(workspace_id),
    }
    return await client.list("/changes", "changes", page=page, per_page=per_page, params=params)


@ts.tool("Filter changes")
async def filter_changes(
    query: Query,
    page: Page = 1,
    per_page: PerPage = 30,
    workspace_id: WorkspaceId = None,
) -> Result:
    """Search changes with the Freshservice query language.

    Use change field names in snake case (see list_change_fields; custom fields by API name). Examples:
    "status:3" (awaiting approval), "approval_status:1 AND status:<5" (approved, not closed),
    "priority:>2 AND group_id:11", "planned_start_date:>'2025-07-14'", "priority:4 OR priority:3".
    :> and :< are inclusive (>= and <=). approval_status: 0 Requested, 1 Approved, 2 Rejected, 3 Not requested.
    Cannot be combined with a view.
    """
    return await get_changes(page=page, per_page=per_page, query=query, workspace_id=workspace_id)


@ts.tool("Get change")
async def get_change_by_id(change_id: ChangeId) -> Result:
    """Get a change by ID, including planning fields and custom fields."""
    return await get_client().get(f"/changes/{change_id}")


@ts.tool("Create change", "create")
async def create_change(
    requester_id: Annotated[int, Field(description="Initiator (requester or agent) user ID")],
    subject: Annotated[str, Field(description="Change subject")],
    description: Annotated[str, Field(description="Change description (HTML allowed)")],
    priority: Priority = 1,
    impact: Impact = 1,
    status: ChangeStatus = 1,
    risk: Risk = 1,
    change_type: ChangeType = 1,
    planned_start_date: Annotated[str | None, Field(description="ISO-8601")] = None,
    planned_end_date: Annotated[str | None, Field(description="ISO-8601")] = None,
    agent_id: Annotated[int | None, Field(description="Change owner agent ID")] = None,
    group_id: Annotated[int | None, Field(description="Agent group ID")] = None,
    department_id: Annotated[int | None, Field(description="Department ID")] = None,
    category: Annotated[str | None, Field(description="Category")] = None,
    sub_category: Annotated[str | None, Field(description="Sub-category")] = None,
    item_category: Annotated[str | None, Field(description="Item category")] = None,
    reason_for_change: Annotated[str | None, Field(description="Planning: reason for change")] = None,
    change_impact: Annotated[str | None, Field(description="Planning: impact")] = None,
    rollout_plan: Annotated[str | None, Field(description="Planning: rollout plan")] = None,
    backout_plan: Annotated[str | None, Field(description="Planning: backout plan")] = None,
    assets: Annotated[
        list[dict[str, Any]] | None, Field(description="Assets, e.g. [{'display_id': 14}]")
    ] = None,
    custom_fields: CustomFields = None,
    workspace_id: WorkspaceId = None,
) -> Result:
    """Create a change request."""
    client = get_client()
    payload = clean(
        {
            "requester_id": requester_id,
            "subject": subject,
            "description": description,
            "priority": priority,
            "impact": impact,
            "status": status,
            "risk": risk,
            "change_type": change_type,
            "planned_start_date": planned_start_date,
            "planned_end_date": planned_end_date,
            "agent_id": agent_id,
            "group_id": group_id,
            "department_id": department_id,
            "category": category,
            "sub_category": sub_category,
            "item_category": item_category,
            "assets": assets,
            "custom_fields": custom_fields,
            "workspace_id": client.workspace(workspace_id),
            "planning_fields": _planning(
                {
                    "reason_for_change": reason_for_change,
                    "change_impact": change_impact,
                    "rollout_plan": rollout_plan,
                    "backout_plan": backout_plan,
                }
            ),
        }
    )
    return await client.post("/changes", payload)


@ts.tool("Update change", "update")
async def update_change(
    change_id: ChangeId,
    change_fields: Annotated[
        dict[str, Any],
        Field(
            description="Fields to change, e.g. {'status': 6, 'custom_fields': {...}, "
            "'planning_fields': {'rollout_plan': 'text'}}. Planning fields may be plain strings."
        ),
    ],
) -> Result:
    """Update a change. Only the supplied fields change."""
    if not change_fields:
        raise ToolError("No fields provided for update")
    payload = dict(change_fields)
    if "planning_fields" in payload:
        payload["planning_fields"] = _planning(payload["planning_fields"] or {})
    return await get_client().put(f"/changes/{change_id}", clean(payload))


@ts.tool("Close change", "update")
async def close_change(
    change_id: ChangeId,
    change_result_explanation: Annotated[str, Field(description="Outcome of the change")],
    custom_fields: CustomFields = None,
) -> Result:
    """Close a change (status 6) and record the result explanation custom field."""
    fields = {"change_result_explanation": change_result_explanation, **(custom_fields or {})}
    return await update_change(change_id, {"status": 6, "custom_fields": fields})


@ts.tool("Delete change", "delete")
async def delete_change(change_id: ChangeId) -> Result:
    """Delete a change."""
    return await get_client().delete(f"/changes/{change_id}")


@ts.tool("Move change to workspace", "update")
async def move_change(
    change_id: ChangeId, workspace_id: Annotated[int, Field(description="Target workspace")]
) -> Result:
    """Move a change to another workspace."""
    return await get_client().put(f"/changes/{change_id}/move_workspace", {"workspace_id": workspace_id})


add_notes(singular="change", plural="changes", id_name="change_id")
add_tasks(singular="change", plural="changes", id_name="change_id")
add_time_entries(singular="change", plural="changes", id_name="change_id")
add_approvals(singular="change", plural="changes", id_name="change_id")
