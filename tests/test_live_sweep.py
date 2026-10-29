"""The sweep must itself be right: run it in-process against a fake Freshservice."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import httpx
import pytest
from mcp.shared.memory import create_connected_server_and_client_session

pytestmark = pytest.mark.anyio

ROOT = Path(__file__).resolve().parent.parent

LIST_KEYS = [
    "tickets",
    "changes",
    "problems",
    "releases",
    "assets",
    "asset_types",
    "departments",
    "locations",
    "vendors",
    "products",
    "workspaces",
    "groups",
    "requester_groups",
    "agents",
    "requesters",
    "canned_responses",
    "canned_response_folders",
    "categories",
    "folders",
    "articles",
    "service_items",
    "notes",
    "tasks",
    "time_entries",
    "approval_groups",
    "approvals",
    "conversations",
    "roles",
]


@pytest.fixture(params=["asyncio"])
def anyio_backend(request):
    return request.param


@pytest.fixture
def live_check():
    spec = importlib.util.spec_from_file_location("live_check", ROOT / "scripts" / "live_check.py")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def full_account(request: httpx.Request) -> httpx.Response:
    """Every list has one record (id 7), and the ticket form has a 'source' field."""
    item = {"id": 7, "display_id": 7, "first_name": "Ada", "title": "x"}
    body = {key: [item] for key in LIST_KEYS}
    body["ticket_fields"] = [{"name": "source", "choices": [{"id": 1, "value": "Email"}]}]
    return httpx.Response(200, json=body)


async def sweep(live_check, make_server, **kwargs):
    server = make_server(read_only=True)  # the sweep only ever sees read-only tools
    async with create_connected_server_and_client_session(server) as session:
        tool_names = {t.name for t in (await session.list_tools()).tools}
        return tool_names, await live_check.run_sweep(session, pause=0, **kwargs)


async def test_every_read_only_tool_is_called_with_real_ids(live_check, make_server, api):
    api.handler = full_account
    tool_names, outcomes = await sweep(live_check, make_server)
    assert {o.name for o in outcomes} == tool_names  # nothing forgotten
    assert len(tool_names) > 80
    bad = [(o.name, o.detail) for o in outcomes if not o.ok or o.skipped]
    assert not bad, bad  # every parameter could be satisfied from the fake account
    paths = {r.url.path for r in api.requests}
    for expected in (
        "/api/v2/changes/7/approval-groups",
        "/api/v2/changes/7/notes/7",
        "/api/v2/problems/7/time_entries/7",
        "/api/v2/releases/7/tasks/7",
        "/api/v2/tickets/7/approvals/7",
        "/api/v2/solutions/folders/7/sub-folders",
        "/api/v2/solutions/articles/7",
        "/api/v2/canned_response_folders/7/canned_responses",
        "/api/v2/assets/7/components",
        "/api/v2/service_catalog/items/7",
        "/api/v2/requester_groups/7/members",
    ):
        assert expected in paths, expected


async def test_each_id_goes_to_the_right_resource(live_check, make_server, api):
    """display_id means an asset for asset tools but a service item for the catalogue; folders differ too."""

    def distinct_ids(request: httpx.Request) -> httpx.Response:
        ids = {
            "assets": 11,
            "service_items": 22,
            "folders": 33,
            "canned_response_folders": 44,
            "categories": 55,
        }
        body = {key: [{"id": 1, "display_id": 1}] for key in LIST_KEYS}
        for key, value in ids.items():
            body[key] = [{"id": value, "display_id": value}]
        body["ticket_fields"] = [{"name": "source", "choices": [{"id": 1, "value": "Email"}]}]
        return httpx.Response(200, json=body)

    api.handler = distinct_ids
    await sweep(live_check, make_server)
    paths = {r.url.path for r in api.requests}
    assert "/api/v2/assets/11/components" in paths and "/api/v2/service_catalog/items/22" in paths
    assert "/api/v2/solutions/folders/33/sub-folders" in paths
    assert "/api/v2/canned_response_folders/44/canned_responses" in paths


async def test_a_wrong_endpoint_is_reported_as_a_failure(live_check, make_server, api):
    def missing_route(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("/approval-groups"):
            return httpx.Response(404, json={"description": "Record not found"})
        return full_account(request)

    api.handler = missing_route
    _, outcomes = await sweep(live_check, make_server)
    failed = {o.name: o.detail for o in outcomes if not o.ok}
    assert set(failed) == {
        "list_change_approval_groups",
        "list_ticket_approval_groups",
    }
    assert all("HTTP 404" in detail for detail in failed.values())


async def test_forbidden_modules_are_skipped_not_failed(live_check, make_server, api):
    def no_releases(request: httpx.Request) -> httpx.Response:
        if "/releases" in request.url.path:
            return httpx.Response(403, json={"description": "Access denied"})
        return full_account(request)

    api.handler = no_releases
    _, outcomes = await sweep(live_check, make_server)
    assert all(o.ok for o in outcomes)  # no failures
    skipped = {o.name for o in outcomes if o.skipped}
    assert "get_releases" in skipped and "get_release" in skipped  # the dependent tool is skipped too
    assert live_check.summarise(outcomes) == 0


async def test_an_empty_account_skips_what_needs_data(live_check, make_server, api, capsys):
    def empty(request: httpx.Request) -> httpx.Response:
        body = {key: [] for key in LIST_KEYS}
        body["ticket_fields"] = [{"name": "source", "choices": [{"id": 1, "value": "Email"}]}]
        return httpx.Response(200, json=body)

    api.handler = empty
    _, outcomes = await sweep(live_check, make_server)
    assert all(o.ok for o in outcomes)
    skipped = {o.name: o.detail for o in outcomes if o.skipped}
    assert "get_change_by_id" in skipped and "change_id" in skipped["get_change_by_id"]
    assert "get_tickets" not in skipped  # a plain list works on an empty account
    capsys.readouterr()
    assert live_check.summarise(outcomes) == 0
    assert "skipped" in capsys.readouterr().out


async def test_lists_are_kept_small(live_check, make_server, api):
    api.handler = full_account
    await sweep(live_check, make_server)
    listings = [r for r in api.requests if r.url.path == "/api/v2/tickets"]
    assert listings and listings[0].url.params["per_page"] == "1"


def test_sweep_cannot_be_combined_with_write(live_check, monkeypatch, capsys):
    monkeypatch.setenv("FRESHSERVICE_DOMAIN", "x.freshservice.com")
    monkeypatch.setenv("FRESHSERVICE_APIKEY", "k")
    monkeypatch.setattr(sys, "argv", ["live_check.py", "--sweep", "--write", "--email", "a@b.co"])
    with pytest.raises(SystemExit):
        live_check.parse_args()
    assert "read-only" in capsys.readouterr().err
