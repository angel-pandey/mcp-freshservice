"""Tickets, conversations, tasks, time entries and requested items."""

from __future__ import annotations

from typing import Annotated, Any, Literal

from mcp.server.fastmcp.exceptions import ToolError
from pydantic import Field

from ..client import clean, get_client, quote_query
from ._common import (
    Attachments,
    CustomFields,
    OrderType,
    Page,
    PerPage,
    Priority,
    Query,
    Result,
    UpdatedSince,
    WorkspaceId,
    add_approvals,
    add_tasks,
    add_time_entries,
)
from ._registry import toolset

ts = toolset("tickets", "Incidents and service requests, replies, notes, conversations", default=True)

TicketId = Annotated[int, Field(description="Ticket ID (the number shown as #INC-123 / #SR-123)")]
ConversationId = Annotated[int, Field(description="Conversation (reply/note) ID")]
TicketStatus = Annotated[int, Field(ge=2, le=5, description="2 Open, 3 Pending, 4 Resolved, 5 Closed")]
TicketSource = Annotated[
    int,
    Field(
        ge=1,
        description="1 Email, 2 Portal, 3 Phone, 4 Chat, 5 Feedback widget, 6 Yammer, 7 AWS Cloudwatch, "
        "8 Pagerduty, 9 Walkup, 10 Slack, 11 Chatbot, 12 Workplace, 13 Employee Onboarding, 14 Alerts, "
        "15 MS Teams, 18 Employee Offboarding (custom sources: see list_ticket_sources)",
    ),
]
TicketInclude = Literal[
    "conversations",
    "requester",
    "requested_for",
    "stats",
    "problem",
    "assets",
    "impacted_services",
    "change",
    "changes",
    "related_tickets",
    "tags",
    "department",
    "feedback",
    "onboarding_context",
    "offboarding_context",
    "ticket_attachments",
    "skill",
]
ListInclude = Literal[
    "requester", "stats", "requested_for", "tags", "department", "created_by", "onboarding_context"
]
Emails = Annotated[list[str] | None, Field(description="Email addresses")]


@ts.tool("Get ticket form fields")
async def get_ticket_fields(workspace_id: WorkspaceId = None) -> Result:
    """List ticket form fields, including custom fields, their API names and allowed choices."""
    client = get_client()
    return await client.get("/ticket_form_fields", {"workspace_id": client.workspace(workspace_id)})


@ts.tool("List ticket sources")
async def list_ticket_sources(workspace_id: WorkspaceId = None) -> Result:
    """List ticket sources (channels), built-in and custom, with the numeric IDs create_ticket expects.

    Returns {"sources": [{"id": 1, "value": "Email"}, ...]}. Freshservice has no endpoint that lists sources
    (/ticket_fields/sources only creates one), so they are read from the ticket form's "source" field.
    """
    client = get_client()
    data = await client.get("/ticket_form_fields", {"workspace_id": client.workspace(workspace_id)})
    for field in data.get("ticket_fields", []):
        if field.get("name") == "source":
            return {"sources": field.get("choices", [])}
    raise ToolError("The ticket form has no 'source' field to read sources from")


@ts.tool("List tickets")
async def get_tickets(
    page: Page = 1,
    per_page: PerPage = 30,
    filter: Annotated[
        Literal["new_and_my_open", "watching", "spam", "deleted"] | None,
        Field(description="Predefined filter. Default (none) returns tickets from the last 30 days"),
    ] = None,
    requester_id: Annotated[int | None, Field(description="Only tickets raised by this requester")] = None,
    email: Annotated[str | None, Field(description="Only tickets raised by this requester email")] = None,
    updated_since: UpdatedSince = None,
    type: Annotated[Literal["Incident", "Service Request"] | None, Field(description="Ticket type")] = None,
    order_type: OrderType = None,
    include: Annotated[list[ListInclude] | None, Field(description="Embed related data")] = None,
    workspace_id: WorkspaceId = None,
) -> Result:
    """List tickets (newest first). Without a filter or updated_since, only the last 30 days are returned.

    For arbitrary conditions (status, priority, agent, group, dates, custom fields) use filter_tickets.
    """
    client = get_client()
    params = {
        "filter": filter,
        "requester_id": requester_id,
        "email": email,
        "updated_since": updated_since,
        "type": type,
        "order_type": order_type,
        "include": include,
        "workspace_id": client.workspace(workspace_id),
    }
    return await client.list("/tickets", "tickets", page=page, per_page=per_page, params=params)


@ts.tool("Filter tickets")
async def filter_tickets(
    query: Query,
    page: Page = 1,
    workspace_id: WorkspaceId = None,
) -> Result:
    """Search tickets with the Freshservice query language (30 results per page).

    Filterable fields: requester_id, email, agent_id, group_id, priority, status, impact, urgency, tag,
    due_by and fr_due_by (YYYY-MM-DD), created_at and updated_at (YYYY-MM-DD or UTC datetime), workspace_id
    (0 = all workspaces) and custom fields by API name (see get_ticket_fields). Field names are
    case-sensitive snake_case. Examples: "status:2 AND priority:4", "agent_id:null AND created_at:>'2025-01-01'",
    "(group_id:12 OR group_id:15) AND status:3", "tag:'vip'". :> and :< are documented as inclusive (>= and <=).
    Values must be valid ones (status 2-5, priority 1-4, ...) or the API answers 400.
    The response includes "total" with the overall match count.
    """
    client = get_client()
    params = {"query": quote_query(query), "workspace_id": client.workspace(workspace_id)}
    return await client.list("/tickets/filter", "tickets", page=page, per_page=None, params=params)


@ts.tool("Get ticket")
async def get_ticket_by_id(
    ticket_id: TicketId,
    include: Annotated[
        list[TicketInclude] | None,
        Field(
            description="Embed related data, e.g. ['conversations', 'requester', 'stats']. "
            "conversations returns at most 10; use list_all_ticket_conversation for the full thread."
        ),
    ] = None,
) -> Result:
    """Get a ticket by ID. Returns {"ticket": {...}} with all standard fields, custom_fields,
    planned dates, SLA flags (is_escalated, fr_escalated), attachments and, when available, the
    resolution notes."""
    return await get_client().get(f"/tickets/{ticket_id}", {"include": include})


@ts.tool("Create ticket", "create")
async def create_ticket(
    subject: Annotated[str, Field(description="Ticket subject")],
    description: Annotated[str, Field(description="Ticket body (HTML allowed)")],
    email: Annotated[
        str | None, Field(description="Requester email (one of email/requester_id/phone needed)")
    ] = None,
    requester_id: Annotated[int | None, Field(description="Requester user ID")] = None,
    phone: Annotated[
        str | None, Field(description="Requester phone; creates the contact if new (needs name)")
    ] = None,
    name: Annotated[str | None, Field(description="Requester name, used with phone")] = None,
    status: TicketStatus = 2,
    priority: Priority = 1,
    source: TicketSource = 2,
    urgency: Annotated[int | None, Field(ge=1, le=3, description="1 Low, 2 Medium, 3 High")] = None,
    impact: Annotated[int | None, Field(ge=1, le=3, description="1 Low, 2 Medium, 3 High")] = None,
    type: Annotated[
        Literal["Incident", "Service Request"] | None, Field(description="Default Incident")
    ] = None,
    group_id: Annotated[int | None, Field(description="Agent group to assign")] = None,
    responder_id: Annotated[int | None, Field(description="Agent to assign")] = None,
    department_id: Annotated[int | None, Field(description="Department ID")] = None,
    category: Annotated[str | None, Field(description="Category")] = None,
    sub_category: Annotated[str | None, Field(description="Sub-category")] = None,
    item_category: Annotated[str | None, Field(description="Item category")] = None,
    due_by: Annotated[str | None, Field(description="Resolution due, ISO-8601")] = None,
    fr_due_by: Annotated[str | None, Field(description="First response due, ISO-8601")] = None,
    cc_emails: Emails = None,
    tags: Annotated[list[str] | None, Field(description="Tags")] = None,
    assets: Annotated[
        list[dict[str, Any]] | None, Field(description="Assets to link, e.g. [{'display_id': 14}]")
    ] = None,
    custom_fields: CustomFields = None,
    workspace_id: WorkspaceId = None,
    attachments: Attachments = None,
) -> Result:
    """Create an incident or service-request ticket. Some ticket forms make fields such as
    group_id, responder_id, category or custom fields mandatory; check get_ticket_fields when the API
    reports missing_field."""
    if not (email or requester_id or phone):
        raise ToolError("Provide one of email, requester_id or phone to identify the requester")
    client = get_client()
    payload = {
        "subject": subject,
        "description": description,
        "email": email,
        "requester_id": requester_id,
        "phone": phone,
        "name": name,
        "status": status,
        "priority": priority,
        "source": source,
        "urgency": urgency,
        "impact": impact,
        "type": type,
        "group_id": group_id,
        "responder_id": responder_id,
        "department_id": department_id,
        "category": category,
        "sub_category": sub_category,
        "item_category": item_category,
        "due_by": due_by,
        "fr_due_by": fr_due_by,
        "cc_emails": cc_emails,
        "tags": tags,
        "assets": assets,
        "custom_fields": custom_fields,
        "workspace_id": client.workspace(workspace_id),
    }
    return await client.write_with_attachments("POST", "/tickets", payload, attachments)


@ts.tool("Update ticket", "update")
async def update_ticket(
    ticket_id: TicketId,
    ticket_fields: Annotated[
        dict[str, Any],
        Field(
            description="Fields to change, e.g. {'status': 4, 'priority': 3, 'responder_id': 42, "
            "'custom_fields': {'cf_root_cause': 'Network'}}. Same fields as create_ticket."
        ),
    ],
    attachments: Attachments = None,
) -> Result:
    """Update a ticket. Only the supplied fields change."""
    if not ticket_fields and not attachments:
        raise ToolError("No fields provided for update")
    return await get_client().write_with_attachments(
        "PUT", f"/tickets/{ticket_id}", ticket_fields, attachments
    )


@ts.tool("Delete ticket", "delete")
async def delete_ticket(ticket_id: TicketId) -> Result:
    """Move a ticket to trash. It can be brought back with restore_ticket."""
    return await get_client().delete(f"/tickets/{ticket_id}")


@ts.tool("Restore ticket", "update")
async def restore_ticket(ticket_id: TicketId) -> Result:
    """Restore a deleted (trashed) ticket."""
    return await get_client().put(f"/tickets/{ticket_id}/restore")


@ts.tool("Create child ticket", "create")
async def create_child_ticket(
    ticket_id: Annotated[int, Field(description="Parent ticket ID")],
    subject: Annotated[str, Field(description="Child ticket subject")],
    description: Annotated[str, Field(description="Child ticket body (HTML allowed)")],
    email: Annotated[str | None, Field(description="Requester email")] = None,
    requester_id: Annotated[int | None, Field(description="Requester user ID")] = None,
    status: TicketStatus = 2,
    priority: Priority = 1,
    source: TicketSource = 2,
    group_id: Annotated[int | None, Field(description="Agent group")] = None,
    responder_id: Annotated[int | None, Field(description="Assigned agent")] = None,
    custom_fields: CustomFields = None,
) -> Result:
    """Create a child ticket under an existing parent ticket."""
    payload = clean(
        {
            "subject": subject,
            "description": description,
            "email": email,
            "requester_id": requester_id,
            "status": status,
            "priority": priority,
            "source": source,
            "group_id": group_id,
            "responder_id": responder_id,
            "custom_fields": custom_fields,
        }
    )
    return await get_client().post(f"/tickets/{ticket_id}/create_child_ticket", payload)


# --- Conversations ------------------------------------------------------------------------------


@ts.tool("List ticket conversations")
async def list_all_ticket_conversation(ticket_id: TicketId, page: Page = 1, per_page: PerPage = 30) -> Result:
    """List the replies and notes on a ticket, oldest first. Each has body/body_text, private,
    incoming, source, user_id, to/cc/bcc emails and attachments."""
    return await get_client().list(
        f"/tickets/{ticket_id}/conversations", "conversations", page=page, per_page=per_page
    )


@ts.tool("Reply to ticket", "create")
async def send_ticket_reply(
    ticket_id: TicketId,
    body: Annotated[str, Field(min_length=1, description="Reply content (HTML allowed)")],
    from_email: Annotated[
        str | None,
        Field(description="A configured support email to send from. Omit to use the account default"),
    ] = None,
    user_id: Annotated[int | None, Field(description="Agent ID to send the reply as")] = None,
    cc_emails: Emails = None,
    bcc_emails: Emails = None,
    attachments: Attachments = None,
) -> Result:
    """Send a public reply to the requester on a ticket."""
    payload = {
        "body": body,
        "from_email": from_email,
        "user_id": user_id,
        "cc_emails": cc_emails,
        "bcc_emails": bcc_emails,
    }
    return await get_client().write_with_attachments(
        "POST", f"/tickets/{ticket_id}/reply", payload, attachments
    )


@ts.tool("Add ticket note", "create")
async def create_ticket_note(
    ticket_id: TicketId,
    body: Annotated[str, Field(min_length=1, description="Note content (HTML allowed)")],
    private: Annotated[
        bool, Field(description="true (default): internal note for agents; false: visible to the requester")
    ] = True,
    incoming: Annotated[
        bool | None, Field(description="Mark as coming from outside (requester side)")
    ] = None,
    notify_emails: Annotated[list[str] | None, Field(description="Agent emails to notify")] = None,
    user_id: Annotated[int | None, Field(description="User ID to create the note as")] = None,
    attachments: Attachments = None,
) -> Result:
    """Add a note to a ticket (private by default)."""
    payload = {
        "body": body,
        "private": private,
        "incoming": incoming,
        "notify_emails": notify_emails,
        "user_id": user_id,
    }
    return await get_client().write_with_attachments(
        "POST", f"/tickets/{ticket_id}/notes", payload, attachments
    )


@ts.tool("Update ticket conversation", "update")
async def update_ticket_conversation(
    conversation_id: ConversationId,
    body: Annotated[str, Field(min_length=1, description="New content (HTML allowed)")],
    attachments: Attachments = None,
) -> Result:
    """Edit a note or reply. Only notes and replies created through the API/agents can be edited."""
    return await get_client().write_with_attachments(
        "PUT", f"/conversations/{conversation_id}", {"body": body}, attachments
    )


@ts.tool("Delete ticket conversation", "delete")
async def delete_ticket_conversation(conversation_id: ConversationId) -> Result:
    """Delete a note or reply from a ticket."""
    return await get_client().delete(f"/conversations/{conversation_id}")


@ts.tool("List ticket activities")
async def list_ticket_activities(ticket_id: TicketId) -> Result:
    """List the audit trail of a ticket (field changes, assignments, status changes)."""
    return await get_client().get(f"/tickets/{ticket_id}/activities")


# --- Service request items -----------------------------------------------------------------------


@ts.tool("Get requested items")
async def get_requested_items(ticket_id: TicketId) -> Result:
    """List the service catalog items requested on a service-request ticket."""
    return await get_client().get(f"/tickets/{ticket_id}/requested_items")


add_tasks(singular="ticket", plural="tickets", id_name="ticket_id")
add_time_entries(singular="ticket", plural="tickets", id_name="ticket_id", default=True)
add_approvals(singular="ticket", plural="tickets", id_name="ticket_id")
