"""Agents and agent fields."""

from __future__ import annotations

from typing import Annotated, Any, Literal

from mcp.server.fastmcp.exceptions import ToolError
from pydantic import Field

from ..client import clean, get_client, quote_query
from ._common import Page, PerPage, Result
from ._registry import toolset

ts = toolset("agents", "Agents (helpdesk staff) and their fields", default=True)

AgentId = Annotated[int, Field(description="Agent ID")]

AGENT_FIELDS = (
    "first_name last_name occasional job_title email work_phone_number mobile_phone_number department_ids "
    "can_see_all_tickets_from_associated_departments reporting_manager_id address time_zone time_format "
    "language location_id background_information scoreboard_level_id member_of observer_of roles "
    "custom_fields"
)


@ts.tool("List agent fields")
async def get_agent_fields() -> Result:
    """List agent fields, including custom fields."""
    return await get_client().get("/agent_fields")


@ts.tool("List agents")
async def get_all_agents(
    page: Page = 1,
    per_page: PerPage = 30,
    email: Annotated[str | None, Field(description="Exact email")] = None,
    state: Annotated[Literal["fulltime", "occasional"] | None, Field(description="Agent type")] = None,
    active: Annotated[bool | None, Field(description="true: active only, false: deactivated only")] = None,
) -> Result:
    """List agents."""
    params = {"email": email, "state": state, "active": active}
    return await get_client().list("/agents", "agents", page=page, per_page=per_page, params=params)


@ts.tool("Filter agents")
async def filter_agents(
    query: Annotated[
        str,
        Field(
            description="Freshservice query, e.g. \"first_name:'Ada'\", \"department_id:5 AND job_title:'Lead'\", "
            "or a prefix search \"~[first_name|last_name]:'ad'\". Max 512 characters; outer double quotes "
            "are added for you."
        ),
    ],
    page: Annotated[int, Field(ge=1, le=40, description="Page (30 results per page, max 40 pages)")] = 1,
) -> Result:
    """Search agents (30 per page, newest first; results cannot be sorted).

    Fields: first_name, last_name, name, job_title, email, work_phone_number, mobile_phone_number,
    department_id, reporting_manager_id, time_zone, language, location_id, created_at, updated_at,
    external_id and custom fields. The ~ operator does "starts with" on first_name, last_name, name, email,
    mobile_phone_number and work_phone_number. Changes can take a few minutes to be indexed.
    """
    params = {"query": quote_query(query)}
    return await get_client().list("/agents", "agents", page=page, per_page=None, params=params, max_page=40)


@ts.tool("Get agent")
async def get_agent(agent_id: AgentId) -> Result:
    """Get an agent by ID, including roles and group memberships."""
    return await get_client().get(f"/agents/{agent_id}")


@ts.tool("Create agent", "create")
async def create_agent(
    first_name: Annotated[str, Field(min_length=1, description="First name")],
    email: Annotated[str, Field(description="Email address")],
    last_name: Annotated[str | None, Field(description="Last name")] = None,
    occasional: Annotated[bool, Field(description="true for an occasional (day-pass) agent")] = False,
    job_title: Annotated[str | None, Field()] = None,
    work_phone_number: Annotated[str | None, Field()] = None,
    mobile_phone_number: Annotated[str | None, Field()] = None,
    department_ids: Annotated[list[int] | None, Field()] = None,
    reporting_manager_id: Annotated[int | None, Field()] = None,
    location_id: Annotated[int | None, Field()] = None,
    member_of: Annotated[list[int] | None, Field(description="Group IDs the agent is a member of")] = None,
    observer_of: Annotated[list[int] | None, Field(description="Group IDs the agent observes")] = None,
    roles: Annotated[
        list[dict[str, Any]] | None,
        Field(description="Role assignments, e.g. [{'role_id': 3, 'assignment_scope': 'entire_helpdesk'}]"),
    ] = None,
    time_zone: Annotated[str | None, Field()] = None,
    language: Annotated[str | None, Field()] = None,
) -> Result:
    """Create an agent. Assign at least one role so the agent can sign in."""
    payload = clean(
        {
            "first_name": first_name,
            "last_name": last_name,
            "email": email,
            "occasional": occasional,
            "job_title": job_title,
            "work_phone_number": work_phone_number,
            "mobile_phone_number": mobile_phone_number,
            "department_ids": department_ids,
            "reporting_manager_id": reporting_manager_id,
            "location_id": location_id,
            "member_of": member_of,
            "observer_of": observer_of,
            "roles": roles,
            "time_zone": time_zone,
            "language": language,
        }
    )
    return await get_client().post("/agents", payload)


@ts.tool("Update agent", "update")
async def update_agent(
    agent_id: AgentId,
    agent_fields: Annotated[dict[str, Any], Field(description=f"Fields to change. Allowed: {AGENT_FIELDS}")],
) -> Result:
    """Update an agent. Only the supplied fields change."""
    if not agent_fields:
        raise ToolError("No fields provided for update")
    return await get_client().put(f"/agents/{agent_id}", clean(agent_fields))


@ts.tool("Deactivate agent", "delete")
async def deactivate_agent(agent_id: AgentId) -> Result:
    """Deactivate an agent (they become a requester; reversible with reactivate_agent)."""
    return await get_client().delete(f"/agents/{agent_id}")


@ts.tool("Reactivate agent", "update")
async def reactivate_agent(agent_id: AgentId) -> Result:
    """Reactivate a deactivated agent."""
    return await get_client().put(f"/agents/{agent_id}/reactivate")


@ts.tool("List agent roles")
async def list_roles(page: Page = 1, per_page: PerPage = 30) -> Result:
    """List agent roles (needed for create_agent's roles)."""
    return await get_client().list("/roles", "roles", page=page, per_page=per_page)
