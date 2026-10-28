"""Requesters (end users)."""

from __future__ import annotations

from typing import Annotated, Any

from mcp.server.fastmcp.exceptions import ToolError
from pydantic import Field

from ..client import clean, get_client, quote_query
from ._common import CustomFields, Page, PerPage, Result
from ._registry import toolset

ts = toolset("requesters", "Requesters (end users) and their fields", default=True)

RequesterId = Annotated[int, Field(description="Requester ID")]

REQUESTER_FIELDS = (
    "first_name last_name job_title primary_email secondary_emails work_phone_number mobile_phone_number "
    "department_ids can_see_all_tickets_from_associated_departments reporting_manager_id address time_zone "
    "time_format language location_id background_information custom_fields"
)


@ts.tool("List requester fields")
async def list_all_requester_fields() -> Result:
    """List requester fields, including custom fields and their API names."""
    return await get_client().get("/requester_fields")


@ts.tool("List requesters")
async def get_all_requesters(
    page: Page = 1,
    per_page: PerPage = 30,
    email: Annotated[str | None, Field(description="Exact primary or secondary email")] = None,
    mobile_phone_number: Annotated[str | None, Field(description="Exact mobile number")] = None,
    work_phone_number: Annotated[str | None, Field(description="Exact work number")] = None,
    active: Annotated[bool | None, Field(description="true: active only, false: deactivated only")] = None,
    include_agents: Annotated[bool, Field(description="Also return agents (who are requesters too)")] = False,
) -> Result:
    """List requesters, optionally looked up by email or phone."""
    params = {
        "email": email,
        "mobile_phone_number": mobile_phone_number,
        "work_phone_number": work_phone_number,
        "active": active,
        "include_agents": include_agents or None,
    }
    return await get_client().list("/requesters", "requesters", page=page, per_page=per_page, params=params)


@ts.tool("Filter requesters")
async def filter_requesters(
    query: Annotated[
        str,
        Field(
            description="Freshservice query, e.g. \"first_name:'Ada' AND job_title:'Engineer'\", "
            '"department_id:5", "created_at:>\'2025-01-01\'", or a prefix search '
            "\"~[first_name|last_name]:'ad'\" (starts-with on one or more attributes). Max 512 characters; "
            "outer double quotes are added for you."
        ),
    ],
    page: Annotated[int, Field(ge=1, le=40, description="Page (30 results per page, max 40 pages)")] = 1,
    include_agents: Annotated[
        bool, Field(description="Also match agents (needs Manage Agents permission)")
    ] = False,
) -> Result:
    """Search requesters (30 per page, newest first; results cannot be sorted).

    Fields: first_name, last_name, name, job_title, primary_email, work_phone_number, mobile_phone_number,
    department_id, reporting_manager_id, time_zone, language, location_id, created_at, updated_at,
    external_id and custom fields. The ~ operator does "starts with" on first_name, last_name, name,
    primary_email, mobile_phone_number and work_phone_number. Changes can take a few minutes to be indexed.
    """
    params = {"query": quote_query(query), "include_agents": include_agents or None}
    return await get_client().list(
        "/requesters", "requesters", page=page, per_page=None, params=params, max_page=40
    )


@ts.tool("Get requester")
async def get_requester(requester_id: RequesterId) -> Result:
    """Get a requester by ID."""
    return await get_client().get(f"/requesters/{requester_id}")


@ts.tool("Create requester", "create")
async def create_requester(
    first_name: Annotated[str, Field(min_length=1, description="First name")],
    last_name: Annotated[str | None, Field(description="Last name")] = None,
    primary_email: Annotated[
        str | None, Field(description="Primary email (or a phone number is required)")
    ] = None,
    secondary_emails: Annotated[list[str] | None, Field(description="Additional emails")] = None,
    job_title: Annotated[str | None, Field(description="Job title")] = None,
    work_phone_number: Annotated[str | None, Field(description="Work phone")] = None,
    mobile_phone_number: Annotated[str | None, Field(description="Mobile phone")] = None,
    department_ids: Annotated[list[int] | None, Field(description="Department IDs")] = None,
    can_see_all_tickets_from_associated_departments: Annotated[bool | None, Field()] = None,
    reporting_manager_id: Annotated[int | None, Field(description="Manager's user ID")] = None,
    address: Annotated[str | None, Field()] = None,
    time_zone: Annotated[str | None, Field(description="e.g. 'Sydney'")] = None,
    time_format: Annotated[str | None, Field(description="'12h' or '24h'")] = None,
    language: Annotated[str | None, Field(description="Language code, e.g. 'en'")] = None,
    location_id: Annotated[int | None, Field(description="Location ID")] = None,
    background_information: Annotated[str | None, Field()] = None,
    custom_fields: CustomFields = None,
) -> Result:
    """Create a requester. One of primary_email, work_phone_number or mobile_phone_number is required."""
    if not (primary_email or work_phone_number or mobile_phone_number):
        raise ToolError("One of primary_email, work_phone_number or mobile_phone_number is required")
    payload = clean(
        {
            "first_name": first_name.strip(),
            "last_name": last_name,
            "primary_email": primary_email,
            "secondary_emails": secondary_emails,
            "job_title": job_title,
            "work_phone_number": work_phone_number,
            "mobile_phone_number": mobile_phone_number,
            "department_ids": department_ids,
            "can_see_all_tickets_from_associated_departments": can_see_all_tickets_from_associated_departments,
            "reporting_manager_id": reporting_manager_id,
            "address": address,
            "time_zone": time_zone,
            "time_format": time_format,
            "language": language,
            "location_id": location_id,
            "background_information": background_information,
            "custom_fields": custom_fields,
        }
    )
    return await get_client().post("/requesters", payload)


@ts.tool("Update requester", "update")
async def update_requester(
    requester_id: RequesterId,
    requester_fields: Annotated[
        dict[str, Any], Field(description=f"Fields to change. Allowed: {REQUESTER_FIELDS}")
    ],
) -> Result:
    """Update a requester. Only the supplied fields change."""
    if not requester_fields:
        raise ToolError("No fields provided for update")
    return await get_client().put(f"/requesters/{requester_id}", clean(requester_fields))


@ts.tool("Deactivate requester", "delete")
async def deactivate_requester(requester_id: RequesterId) -> Result:
    """Deactivate a requester (reversible with reactivate_requester)."""
    return await get_client().delete(f"/requesters/{requester_id}")


@ts.tool("Reactivate requester", "update")
async def reactivate_requester(requester_id: RequesterId) -> Result:
    """Reactivate a deactivated requester."""
    return await get_client().put(f"/requesters/{requester_id}/reactivate")


@ts.tool("Convert requester to agent", "update")
async def convert_requester_to_agent(requester_id: RequesterId) -> Result:
    """Convert a requester into an occasional agent."""
    return await get_client().put(f"/requesters/{requester_id}/convert_to_agent")
