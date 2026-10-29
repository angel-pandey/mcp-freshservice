"""Shared parameter types and builders for tools."""

from __future__ import annotations

import inspect
from collections.abc import Awaitable, Callable
from typing import Annotated, Any, Literal

from pydantic import Field

from ..client import clean, get_client
from ._registry import Kind, Toolset, toolset

Result = dict[str, Any]

Page = Annotated[int, Field(ge=1, description="Page number, starting at 1")]
PerPage = Annotated[int, Field(ge=1, le=100, description="Records per page (max 100)")]
WorkspaceId = Annotated[
    int | None,
    Field(
        description="Workspace ID (multi-workspace accounts). Defaults to $FRESHSERVICE_WORKSPACE_ID; "
        "0 means all workspaces where supported."
    ),
]
OrderType = Annotated[Literal["asc", "desc"] | None, Field(description="Sort direction")]
UpdatedSince = Annotated[
    str | None,
    Field(description="Only records updated at/after this ISO-8601 time, e.g. 2025-01-31T00:00:00Z"),
]
CustomFields = Annotated[
    dict[str, Any] | None,
    Field(description="Custom field values keyed by the field's API name (see *_fields tools)"),
]
Attachments = Annotated[
    list[str] | None,
    Field(
        description="Local file paths to attach (max 15 files / 40 MB total). Only files inside the folders in "
        "FRESHSERVICE_ATTACHMENT_DIRS are allowed; attachments are refused until that is set"
    ),
]
Priority = Annotated[int, Field(ge=1, le=4, description="1 Low, 2 Medium, 3 High, 4 Urgent")]
Impact = Annotated[int, Field(ge=1, le=3, description="1 Low, 2 Medium, 3 High")]
Query = Annotated[
    str,
    Field(
        description="Freshservice query: field:value terms joined by AND / OR with optional (parentheses). "
        "Numbers bare (priority:3); strings and dates in single quotes (tag:'vip', created_at:>'2025-01-01'); "
        "booleans bare; null for empty (agent_id:null). ':>' and ':<' mean greater/less than OR EQUAL. "
        "Max 512 characters. The outer double quotes the API requires are added for you."
    ),
]


def _p(name: str, annotation: Any, default: Any = inspect.Parameter.empty) -> inspect.Parameter:
    return inspect.Parameter(name, inspect.Parameter.KEYWORD_ONLY, annotation=annotation, default=default)


def _build(
    ts: Toolset,
    name: str,
    title: str,
    kind: Kind,
    doc: str,
    params: list[inspect.Parameter],
    impl: Callable[..., Awaitable[Result]],
) -> Callable[..., Awaitable[Result]]:
    async def tool(**kwargs: Any) -> Result:
        return await impl(**kwargs)

    tool.__name__ = tool.__qualname__ = name
    tool.__doc__ = doc
    tool.__signature__ = inspect.Signature(params, return_annotation=Result)  # type: ignore[attr-defined]
    tool.__annotations__ = {p.name: p.annotation for p in params} | {"return": Result}
    ts.tool(title, kind)(tool)
    return tool


def add_notes(*, singular: str, plural: str, id_name: str, default: bool = False) -> None:
    """Notes on changes, problems and releases: /{plural}/{id}/notes."""
    ts = toolset(f"{singular}_notes", f"Notes on {plural}", default)
    Id = Annotated[int, Field(description=f"{singular.capitalize()} ID")]
    NoteId = Annotated[int, Field(description="Note ID")]
    Body = Annotated[str, Field(description="Note body (HTML allowed)")]
    base = f"/{plural}/{{}}/notes"

    async def list_(**kw: Any) -> Result:
        return await get_client().list(
            base.format(kw[id_name]), "notes", page=kw["page"], per_page=kw["per_page"]
        )

    async def get_(**kw: Any) -> Result:
        return await get_client().get(f"{base.format(kw[id_name])}/{kw['note_id']}")

    async def create_(**kw: Any) -> Result:
        return await get_client().post(
            base.format(kw[id_name]), clean({"body": kw["body"], "notify_emails": kw["notify_emails"]})
        )

    async def update_(**kw: Any) -> Result:
        return await get_client().put(f"{base.format(kw[id_name])}/{kw['note_id']}", {"body": kw["body"]})

    async def delete_(**kw: Any) -> Result:
        return await get_client().delete(f"{base.format(kw[id_name])}/{kw['note_id']}")

    s = singular.replace(" ", "_")
    _build(
        ts,
        f"list_{s}_notes",
        f"List {singular} notes",
        "read",
        f"List notes on a {singular}.",
        [_p(id_name, Id), _p("page", Page, 1), _p("per_page", PerPage, 30)],
        list_,
    )
    _build(
        ts,
        f"view_{s}_note",
        f"View {singular} note",
        "read",
        f"Get one note on a {singular}.",
        [_p(id_name, Id), _p("note_id", NoteId)],
        get_,
    )
    _build(
        ts,
        f"create_{s}_note",
        f"Add {singular} note",
        "create",
        f"Add a note to a {singular}.",
        [
            _p(id_name, Id),
            _p("body", Body),
            _p("notify_emails", Annotated[list[str] | None, Field(description="Emails to notify")], None),
        ],
        create_,
    )
    _build(
        ts,
        f"update_{s}_note",
        f"Update {singular} note",
        "update",
        f"Edit a note on a {singular}.",
        [_p(id_name, Id), _p("note_id", NoteId), _p("body", Body)],
        update_,
    )
    _build(
        ts,
        f"delete_{s}_note",
        f"Delete {singular} note",
        "delete",
        f"Delete a note on a {singular}.",
        [_p(id_name, Id), _p("note_id", NoteId)],
        delete_,
    )


def add_tasks(*, singular: str, plural: str, id_name: str, default: bool = False) -> None:
    """Tasks on tickets, changes, problems and releases: /{plural}/{id}/tasks."""
    ts = toolset(f"{singular}_tasks", f"Tasks on {plural}", default)
    Id = Annotated[int, Field(description=f"{singular.capitalize()} ID")]
    TaskId = Annotated[int, Field(description="Task ID")]
    base = f"/{plural}/{{}}/tasks"
    fields_doc = (
        "Task fields: title, description, status (1 Open, 2 In Progress, 3 Completed), due_date (ISO-8601), "
        "notify_before (seconds), agent_id, group_id"
    )

    async def list_(**kw: Any) -> Result:
        return await get_client().list(
            base.format(kw[id_name]), "tasks", page=kw["page"], per_page=kw["per_page"]
        )

    async def get_(**kw: Any) -> Result:
        return await get_client().get(f"{base.format(kw[id_name])}/{kw['task_id']}")

    async def create_(**kw: Any) -> Result:
        payload = clean(
            {
                k: kw[k]
                for k in (
                    "title",
                    "description",
                    "status",
                    "due_date",
                    "notify_before",
                    "agent_id",
                    "group_id",
                )
            }
        )
        return await get_client().post(base.format(kw[id_name]), payload)

    async def update_(**kw: Any) -> Result:
        return await get_client().put(f"{base.format(kw[id_name])}/{kw['task_id']}", kw["task_fields"])

    async def delete_(**kw: Any) -> Result:
        return await get_client().delete(f"{base.format(kw[id_name])}/{kw['task_id']}")

    s = singular.replace(" ", "_")
    opt_int = lambda d: Annotated[int | None, Field(description=d)]
    opt_str = lambda d: Annotated[str | None, Field(description=d)]
    _build(
        ts,
        f"list_{s}_tasks",
        f"List {singular} tasks",
        "read",
        f"List tasks on a {singular}.",
        [_p(id_name, Id), _p("page", Page, 1), _p("per_page", PerPage, 30)],
        list_,
    )
    _build(
        ts,
        f"view_{s}_task",
        f"View {singular} task",
        "read",
        f"Get one task on a {singular}.",
        [_p(id_name, Id), _p("task_id", TaskId)],
        get_,
    )
    _build(
        ts,
        f"create_{s}_task",
        f"Create {singular} task",
        "create",
        f"Create a task on a {singular}.",
        [
            _p(id_name, Id),
            _p("title", Annotated[str, Field(description="Task title")]),
            _p("description", opt_str("Task description"), None),
            _p(
                "status",
                Annotated[int | None, Field(ge=1, le=3, description="1 Open, 2 In Progress, 3 Completed")],
                None,
            ),
            _p("due_date", opt_str("Due date, ISO-8601"), None),
            _p("notify_before", opt_int("Seconds before due_date to send a reminder"), None),
            _p("agent_id", opt_int("Assigned agent ID"), None),
            _p("group_id", opt_int("Assigned group ID"), None),
        ],
        create_,
    )
    _build(
        ts,
        f"update_{s}_task",
        f"Update {singular} task",
        "update",
        f"Update a task on a {singular}. {fields_doc}.",
        [
            _p(id_name, Id),
            _p("task_id", TaskId),
            _p("task_fields", Annotated[dict[str, Any], Field(description=fields_doc)]),
        ],
        update_,
    )
    _build(
        ts,
        f"delete_{s}_task",
        f"Delete {singular} task",
        "delete",
        f"Delete a task on a {singular}.",
        [_p(id_name, Id), _p("task_id", TaskId)],
        delete_,
    )


def add_time_entries(*, singular: str, plural: str, id_name: str, default: bool = False) -> None:
    """Time entries on tickets, changes, problems and releases: /{plural}/{id}/time_entries."""
    ts = toolset(f"{singular}_time_entries", f"Time entries on {plural}", default)
    Id = Annotated[int, Field(description=f"{singular.capitalize()} ID")]
    EntryId = Annotated[int, Field(description="Time entry ID")]
    base = f"/{plural}/{{}}/time_entries"
    fields_doc = (
        "Time entry fields: time_spent ('hh:mm'), note, agent_id, billable, executed_at (ISO-8601), "
        "timer_running, task_id, custom_fields"
    )

    async def list_(**kw: Any) -> Result:
        return await get_client().list(
            base.format(kw[id_name]), "time_entries", page=kw["page"], per_page=kw["per_page"]
        )

    async def get_(**kw: Any) -> Result:
        return await get_client().get(f"{base.format(kw[id_name])}/{kw['time_entry_id']}")

    async def create_(**kw: Any) -> Result:
        payload = clean(
            {
                k: kw[k]
                for k in (
                    "agent_id",
                    "time_spent",
                    "note",
                    "billable",
                    "executed_at",
                    "timer_running",
                    "task_id",
                    "custom_fields",
                )
            }
        )
        return await get_client().post(base.format(kw[id_name]), payload)

    async def update_(**kw: Any) -> Result:
        return await get_client().put(
            f"{base.format(kw[id_name])}/{kw['time_entry_id']}", kw["time_entry_fields"]
        )

    async def delete_(**kw: Any) -> Result:
        return await get_client().delete(f"{base.format(kw[id_name])}/{kw['time_entry_id']}")

    s = singular.replace(" ", "_")
    _build(
        ts,
        f"list_{s}_time_entries",
        f"List {singular} time entries",
        "read",
        f"List time entries (time tracked by agents) on a {singular}.",
        [_p(id_name, Id), _p("page", Page, 1), _p("per_page", PerPage, 30)],
        list_,
    )
    _build(
        ts,
        f"view_{s}_time_entry",
        f"View {singular} time entry",
        "read",
        f"Get one time entry on a {singular}.",
        [_p(id_name, Id), _p("time_entry_id", EntryId)],
        get_,
    )
    _build(
        ts,
        f"create_{s}_time_entry",
        f"Log {singular} time",
        "create",
        f"Log time against a {singular}.",
        [
            _p(id_name, Id),
            _p("agent_id", Annotated[int, Field(description="Agent who did the work")]),
            _p(
                "time_spent",
                Annotated[
                    str | None,
                    Field(pattern=r"^\d{1,4}:[0-5]\d$", description="Duration as 'hh:mm', e.g. '01:30'"),
                ],
                None,
            ),
            _p("note", Annotated[str | None, Field(description="What was done")], None),
            _p("billable", Annotated[bool | None, Field(description="Billable (default true)")], None),
            _p(
                "executed_at",
                Annotated[str | None, Field(description="When the work happened, ISO-8601")],
                None,
            ),
            _p("timer_running", Annotated[bool | None, Field(description="Start a running timer")], None),
            _p("task_id", Annotated[int | None, Field(description="Associate with a task")], None),
            _p("custom_fields", CustomFields, None),
        ],
        create_,
    )
    _build(
        ts,
        f"update_{s}_time_entry",
        f"Update {singular} time entry",
        "update",
        f"Update a time entry on a {singular}. {fields_doc}.",
        [
            _p(id_name, Id),
            _p("time_entry_id", EntryId),
            _p("time_entry_fields", Annotated[dict[str, Any], Field(description=fields_doc)]),
        ],
        update_,
    )
    _build(
        ts,
        f"delete_{s}_time_entry",
        f"Delete {singular} time entry",
        "delete",
        f"Delete a time entry on a {singular}.",
        [_p(id_name, Id), _p("time_entry_id", EntryId)],
        delete_,
    )


APPROVAL_TYPE_DOC = "1 Everyone, 2 Anyone, 3 Majority, 4 First responder"


def add_approvals(*, singular: str, plural: str, id_name: str, default: bool = False) -> None:
    """Approval groups / approvals on service requests and changes.

    /{plural}/{id}/approval-groups, /approval-chain-rule and /approvals. Approval status values:
    0 Requested, 1 Approved, 2 Rejected, 3 Cancelled. Only cancelling is possible through the API.
    """
    ts = toolset(f"{singular}_approvals", f"Approval groups and approvals on {plural}", default)
    Id = Annotated[int, Field(description=f"{singular.capitalize()} ID")]
    GroupId = Annotated[int, Field(description="Approval group ID")]
    ApprovalId = Annotated[int, Field(description="Approval ID")]
    ApprovalType = Annotated[int, Field(ge=1, le=4, description=APPROVAL_TYPE_DOC)]
    base = f"/{plural}/{{}}"
    cancelled = {"approval_status": {"id": 3}}

    async def list_groups(**kw: Any) -> Result:
        return await get_client().get(f"{base.format(kw[id_name])}/approval-groups")

    async def create_group(**kw: Any) -> Result:
        payload = clean(
            {
                "name": kw["name"],
                "approval_type": kw["approval_type"],
                "approver_ids": kw["approver_ids"],
                "email_content": kw["email_content"],
            }
        )
        return await get_client().post(f"{base.format(kw[id_name])}/approval-groups", payload)

    async def update_group(**kw: Any) -> Result:
        payload = clean(
            {
                "name": kw["name"],
                "approval_type": kw["approval_type"],
                "approver_ids": kw["approver_ids"],
                "email_content": kw["email_content"],
            }
        )
        return await get_client().put(
            f"{base.format(kw[id_name])}/approval-groups/{kw['approval_group_id']}", payload
        )

    async def cancel_group(**kw: Any) -> Result:
        return await get_client().put(
            f"{base.format(kw[id_name])}/approval-groups/{kw['approval_group_id']}", cancelled
        )

    async def chain_rule(**kw: Any) -> Result:
        return await get_client().put(f"{base.format(kw[id_name])}/approval-chain-rule", {"rule": kw["rule"]})

    async def list_approvals(**kw: Any) -> Result:
        return await get_client().get(f"{base.format(kw[id_name])}/approvals")

    async def view_approval(**kw: Any) -> Result:
        return await get_client().get(f"{base.format(kw[id_name])}/approvals/{kw['approval_id']}")

    async def remind(**kw: Any) -> Result:
        return await get_client().put(f"{base.format(kw[id_name])}/approvals/{kw['approval_id']}/remind")

    async def cancel_approval(**kw: Any) -> Result:
        return await get_client().put(f"{base.format(kw[id_name])}/approvals/{kw['approval_id']}", cancelled)

    s = singular.replace(" ", "_")
    group_params = [
        _p("approval_type", ApprovalType),
        _p("approver_ids", Annotated[list[int], Field(min_length=1, description="Approver user IDs")]),
    ]
    email = _p(
        "email_content", Annotated[str | None, Field(description="Custom approval email (HTML)")], None
    )
    _build(
        ts,
        f"list_{s}_approval_groups",
        f"List {singular} approval groups",
        "read",
        f"List approval groups (with their approvals and statuses) on a {singular}.",
        [_p(id_name, Id)],
        list_groups,
    )
    _build(
        ts,
        f"create_{s}_approval_group",
        f"Request {singular} approval",
        "create",
        f"Create an approval group on a {singular}, which sends approval requests to the approvers.",
        [_p(id_name, Id), _p("name", Annotated[str, Field(description="Group name")]), *group_params, email],
        create_group,
    )
    _build(
        ts,
        f"update_{s}_approval_group",
        f"Update {singular} approval group",
        "update",
        f"Update an approval group on a {singular}.",
        [
            _p(id_name, Id),
            _p("approval_group_id", GroupId),
            _p("name", Annotated[str | None, Field(description="Group name")], None),
            _p(
                "approval_type", Annotated[int | None, Field(ge=1, le=4, description=APPROVAL_TYPE_DOC)], None
            ),
            _p("approver_ids", Annotated[list[int] | None, Field(description="Approver user IDs")], None),
            email,
        ],
        update_group,
    )
    _build(
        ts,
        f"cancel_{s}_approval_group",
        f"Cancel {singular} approval group",
        "update",
        f"Cancel an approval group on a {singular}.",
        [_p(id_name, Id), _p("approval_group_id", GroupId)],
        cancel_group,
    )
    _build(
        ts,
        f"update_{s}_approval_chain_rule",
        f"Set {singular} approval chain rule",
        "update",
        f"Set how multiple approval groups on a {singular} combine.",
        [_p(id_name, Id), _p("rule", Annotated[int, Field(ge=1, le=4, description=APPROVAL_TYPE_DOC)])],
        chain_rule,
    )
    _build(
        ts,
        f"list_{s}_approvals",
        f"List {singular} approvals",
        "read",
        f"List individual approvals on a {singular}.",
        [_p(id_name, Id)],
        list_approvals,
    )
    _build(
        ts,
        f"view_{s}_approval",
        f"View {singular} approval",
        "read",
        f"Get one approval on a {singular}.",
        [_p(id_name, Id), _p("approval_id", ApprovalId)],
        view_approval,
    )
    _build(
        ts,
        f"send_{s}_approval_reminder",
        f"Remind {singular} approver",
        "update",
        f"Re-send the approval request email for an approval on a {singular}.",
        [_p(id_name, Id), _p("approval_id", ApprovalId)],
        remind,
    )
    _build(
        ts,
        f"cancel_{s}_approval",
        f"Cancel {singular} approval",
        "update",
        f"Cancel a pending approval on a {singular}.",
        [_p(id_name, Id), _p("approval_id", ApprovalId)],
        cancel_approval,
    )
