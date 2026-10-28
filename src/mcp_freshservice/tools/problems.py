"""Problem management and release management."""

from __future__ import annotations

from typing import Annotated, Any, Literal

from mcp.server.fastmcp.exceptions import ToolError
from pydantic import Field

from ..client import clean, get_client
from ._common import (
    CustomFields,
    Impact,
    OrderType,
    Page,
    PerPage,
    Priority,
    Result,
    UpdatedSince,
    WorkspaceId,
    add_notes,
    add_tasks,
    add_time_entries,
)
from ._registry import toolset

ts = toolset("problems", "Problems (root-cause investigations)")
releases = toolset("releases", "Releases")

ProblemId = Annotated[int, Field(description="Problem ID")]
ReleaseId = Annotated[int, Field(description="Release ID")]
Html = Annotated[str, Field(description="HTML content")]


# --- Problems ------------------------------------------------------------------------------------


@ts.tool("List problem fields")
async def list_problem_fields(workspace_id: WorkspaceId = None) -> Result:
    """List problem form fields, including custom fields."""
    client = get_client()
    return await client.get("/problem_form_fields", {"workspace_id": client.workspace(workspace_id)})


@ts.tool("List problems")
async def get_problems(
    page: Page = 1,
    per_page: PerPage = 30,
    updated_since: UpdatedSince = None,
    order_type: OrderType = None,
    workspace_id: WorkspaceId = None,
) -> Result:
    """List problems. Without workspace_id only the primary workspace is returned (0 means all)."""
    client = get_client()
    params = {
        "updated_since": updated_since,
        "order_type": order_type,
        "workspace_id": client.workspace(workspace_id),
    }
    return await client.list("/problems", "problems", page=page, per_page=per_page, params=params)


@ts.tool("Get problem")
async def get_problem(problem_id: ProblemId) -> Result:
    """Get a problem by ID, including analysis_fields (cause, symptom, impact)."""
    return await get_client().get(f"/problems/{problem_id}")


@ts.tool("Create problem", "create")
async def create_problem(
    requester_id: Annotated[int, Field(description="Initiator user ID")],
    subject: Annotated[str, Field(min_length=1)],
    description: Html,
    due_by: Annotated[str, Field(description="Due date, ISO-8601")],
    priority: Priority = 1,
    impact: Impact = 1,
    status: Annotated[int, Field(ge=1, le=3, description="1 Open, 2 Change Requested, 3 Closed")] = 1,
    known_error: Annotated[bool | None, Field(description="Mark as a known error")] = None,
    agent_id: Annotated[int | None, Field()] = None,
    group_id: Annotated[int | None, Field()] = None,
    department_id: Annotated[int | None, Field()] = None,
    category: Annotated[str | None, Field()] = None,
    sub_category: Annotated[str | None, Field()] = None,
    item_category: Annotated[str | None, Field()] = None,
    analysis_fields: Annotated[
        dict[str, Any] | None,
        Field(
            description="{'problem_cause': {'description': '...'}, 'problem_symptom': {...}, "
            "'problem_impact': {...}}"
        ),
    ] = None,
    assets: Annotated[list[dict[str, Any]] | None, Field(description="[{'display_id': 14}]")] = None,
    custom_fields: CustomFields = None,
    workspace_id: WorkspaceId = None,
) -> Result:
    """Create a problem record."""
    client = get_client()
    payload = clean(
        {
            "requester_id": requester_id,
            "subject": subject,
            "description": description,
            "due_by": due_by,
            "priority": priority,
            "impact": impact,
            "status": status,
            "known_error": known_error,
            "agent_id": agent_id,
            "group_id": group_id,
            "department_id": department_id,
            "category": category,
            "sub_category": sub_category,
            "item_category": item_category,
            "analysis_fields": analysis_fields,
            "assets": assets,
            "custom_fields": custom_fields,
            "workspace_id": client.workspace(workspace_id),
        }
    )
    return await client.post("/problems", payload)


@ts.tool("Update problem", "update")
async def update_problem(
    problem_id: ProblemId,
    problem_fields: Annotated[
        dict[str, Any], Field(description="Fields to change, same names as create_problem")
    ],
) -> Result:
    """Update a problem. Only the supplied fields change."""
    if not problem_fields:
        raise ToolError("No fields provided for update")
    return await get_client().put(f"/problems/{problem_id}", clean(problem_fields))


@ts.tool("Delete problem", "delete")
async def delete_problem(problem_id: ProblemId) -> Result:
    """Move a problem to trash (restorable)."""
    return await get_client().delete(f"/problems/{problem_id}")


@ts.tool("Restore problem", "update")
async def restore_problem(problem_id: ProblemId) -> Result:
    """Restore a trashed problem."""
    return await get_client().put(f"/problems/{problem_id}/restore")


@ts.tool("Move problem to workspace", "update")
async def move_problem(
    problem_id: ProblemId, workspace_id: Annotated[int, Field(description="Target")]
) -> Result:
    """Move a problem to another workspace."""
    return await get_client().put(f"/problems/{problem_id}/move_workspace", {"workspace_id": workspace_id})


add_notes(singular="problem", plural="problems", id_name="problem_id")
add_tasks(singular="problem", plural="problems", id_name="problem_id")
add_time_entries(singular="problem", plural="problems", id_name="problem_id")


# --- Releases ------------------------------------------------------------------------------------


@releases.tool("List release fields")
async def list_release_fields(workspace_id: WorkspaceId = None) -> Result:
    """List release form fields, including custom fields."""
    client = get_client()
    return await client.get("/release_form_fields", {"workspace_id": client.workspace(workspace_id)})


@releases.tool("List releases")
async def get_releases(
    page: Page = 1,
    per_page: PerPage = 30,
    filter_name: Annotated[
        Literal["all", "my_open", "unassigned", "completed", "incompleted", "deleted"] | None,
        Field(description="Predefined filter"),
    ] = None,
    workspace_id: WorkspaceId = None,
) -> Result:
    """List releases, optionally using a predefined filter (the API has no free-form release query)."""
    client = get_client()
    params = {"filter_name": filter_name, "workspace_id": client.workspace(workspace_id)}
    return await client.list("/releases", "releases", page=page, per_page=per_page, params=params)


@releases.tool("Get release")
async def get_release(release_id: ReleaseId) -> Result:
    """Get a release by ID."""
    return await get_client().get(f"/releases/{release_id}")


@releases.tool("Create release", "create")
async def create_release(
    subject: Annotated[str, Field(min_length=1)],
    description: Html,
    planned_start_date: Annotated[str, Field(description="ISO-8601")],
    planned_end_date: Annotated[str, Field(description="ISO-8601")],
    priority: Priority = 1,
    status: Annotated[
        int, Field(ge=1, le=5, description="1 Open, 2 On hold, 3 In Progress, 4 Incomplete, 5 Completed")
    ] = 1,
    release_type: Annotated[
        int, Field(ge=1, le=4, description="1 Minor, 2 Standard, 3 Major, 4 Emergency")
    ] = 2,
    agent_id: Annotated[int | None, Field()] = None,
    group_id: Annotated[int | None, Field()] = None,
    department_id: Annotated[int | None, Field()] = None,
    category: Annotated[str | None, Field()] = None,
    planning_fields: Annotated[
        dict[str, Any] | None,
        Field(
            description="{'build_plan': {'description': '...'}, 'test_plan': {...}} per your account's fields"
        ),
    ] = None,
    custom_fields: CustomFields = None,
    workspace_id: WorkspaceId = None,
) -> Result:
    """Create a release."""
    client = get_client()
    payload = clean(
        {
            "subject": subject,
            "description": description,
            "planned_start_date": planned_start_date,
            "planned_end_date": planned_end_date,
            "priority": priority,
            "status": status,
            "release_type": release_type,
            "agent_id": agent_id,
            "group_id": group_id,
            "department_id": department_id,
            "category": category,
            "planning_fields": planning_fields,
            "custom_fields": custom_fields,
            "workspace_id": client.workspace(workspace_id),
        }
    )
    return await client.post("/releases", payload)


@releases.tool("Update release", "update")
async def update_release(
    release_id: ReleaseId,
    release_fields: Annotated[
        dict[str, Any], Field(description="Fields to change, same names as create_release")
    ],
) -> Result:
    """Update a release. Only the supplied fields change."""
    if not release_fields:
        raise ToolError("No fields provided for update")
    return await get_client().put(f"/releases/{release_id}", clean(release_fields))


@releases.tool("Delete release", "delete")
async def delete_release(release_id: ReleaseId) -> Result:
    """Move a release to trash (restorable)."""
    return await get_client().delete(f"/releases/{release_id}")


@releases.tool("Restore release", "update")
async def restore_release(release_id: ReleaseId) -> Result:
    """Restore a trashed release."""
    return await get_client().put(f"/releases/{release_id}/restore")


add_notes(singular="release", plural="releases", id_name="release_id")
add_tasks(singular="release", plural="releases", id_name="release_id")
add_time_entries(singular="release", plural="releases", id_name="release_id")
