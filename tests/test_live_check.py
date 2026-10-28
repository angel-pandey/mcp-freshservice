"""The live-check script must itself work: run it in-process against a mocked Freshservice."""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import httpx
import pytest
from mcp.shared.memory import create_connected_server_and_client_session

pytestmark = pytest.mark.anyio

ROOT = Path(__file__).resolve().parent.parent


@pytest.fixture(params=["asyncio"])
def anyio_backend(request):
    return request.param


@pytest.fixture
def live_check():
    spec = importlib.util.spec_from_file_location("live_check", ROOT / "scripts" / "live_check.py")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module  # dataclasses look the module up here
    spec.loader.exec_module(module)
    return module


def freshservice(request: httpx.Request) -> httpx.Response:
    """A tiny fake Freshservice good enough for the smoke checks."""
    path, method = request.url.path.removeprefix("/api/v2"), request.method
    page = int(request.url.params.get("page", "1"))
    if method == "GET" and path == "/tickets":
        ids = {1: [11, 12], 2: [13, 14]}.get(page, [])
        headers = {"Link": '<https://x/api/v2/tickets?page=2>; rel="next"'} if page == 1 else {}
        return httpx.Response(200, json={"tickets": [{"id": i} for i in ids]}, headers=headers)
    if method == "GET" and path == "/tickets/filter":
        return httpx.Response(200, json={"tickets": [{"id": 11}], "total": 1})
    if method == "GET" and path == "/tickets/999999999":
        return httpx.Response(404, json={"description": "Record not found"})
    if method == "GET" and path.startswith("/tickets/") and path.endswith("/time_entries"):
        return httpx.Response(200, json={"time_entries": []})
    if method == "GET" and path == "/tickets/11":
        return httpx.Response(
            200,
            json={
                "ticket": {"id": 11, "subject": "VPN down", "status": 2, "priority": 2, "requester_id": 77}
            },
        )
    if method == "GET" and path == "/agents":
        return httpx.Response(200, json={"agents": [{"id": 1, "first_name": "Angel"}]})
    if method == "GET" and path == "/requesters":
        return httpx.Response(200, json={"requesters": [{"id": 1, "first_name": "Ada"}]})
    if method == "GET" and path == "/ticket_form_fields":
        choices = [{"id": 1, "value": "Email"}, {"id": 2, "value": "Portal"}, {"id": 3, "value": "Phone"}]
        fields = [{"name": "status"}, {"name": "source", "choices": choices}]
        return httpx.Response(200, json={"ticket_fields": fields})
    if method == "GET" and path == "/solutions/articles/search":
        meta = {"total_items": 1, "total_pages": 1, "current_page": 1}
        return httpx.Response(
            200,
            json={"articles": [{"id": 2886, "title": "Printer", "description_text": "Steps"}], "meta": meta},
        )
    if method == "GET" and path == "/solutions/articles/2886":
        return httpx.Response(
            200, json={"article": {"id": 2886, "description": "<p>Steps</p>", "description_text": " Steps "}}
        )
    if method == "POST" and path == "/tickets":
        return httpx.Response(201, json={"ticket": {"id": 500}})
    if method == "POST" and path == "/tickets/500/notes":
        return httpx.Response(
            201, json={"conversation": {"id": 9, "private": json.loads(request.content)["private"]}}
        )
    if method == "DELETE" and path == "/tickets/500":
        return httpx.Response(204)
    return httpx.Response(500, json={"description": f"unmocked {method} {path}"})


async def run(live_check, make_server, **kwargs):
    server = make_server(toolsets=frozenset())
    async with create_connected_server_and_client_session(server) as session:
        return await live_check.run_checks(session, **kwargs)


async def test_read_checks_all_pass(live_check, make_server, api):
    api.handler = freshservice
    outcomes = await run(live_check, make_server)
    failed = [(o.name, o.detail) for o in outcomes if not o.ok]
    assert not failed, failed
    assert len(outcomes) == 14


async def test_operator_semantics_reports_inclusive(live_check, make_server, api):
    api.handler = freshservice
    outcomes = await run(live_check, make_server)
    semantics = next(o for o in outcomes if "inclusive or strict" in o.name)
    assert semantics.ok and "INCLUSIVE" in semantics.detail


async def test_operator_semantics_detects_strict_behaviour(live_check, make_server, api):
    def strict(request: httpx.Request) -> httpx.Response:
        query = request.url.params.get("query", "")
        if request.url.path.endswith("/tickets/filter") and ("status:>" in query or "status:<" in query):
            return httpx.Response(200, json={"tickets": [], "total": 0})
        return freshservice(request)

    api.handler = strict
    outcomes = await run(live_check, make_server)
    semantics = next(o for o in outcomes if "inclusive or strict" in o.name)
    assert semantics.ok and "STRICT" in semantics.detail


async def test_invalid_filter_values_are_reported_clearly(live_check, make_server, api):
    # what Freshservice really answered when we sent status:>1
    def rejecting(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("/tickets/filter") and "status:>1" in request.url.params.get(
            "query", ""
        ):
            return httpx.Response(
                400,
                json={
                    "description": "Validation failed",
                    "errors": [
                        {
                            "field": "status",
                            "message": "It should be one of these values: '2,3,4,5'",
                            "code": "invalid_value",
                        }
                    ],
                },
            )
        return freshservice(request)

    api.handler = rejecting
    server = make_server(toolsets=frozenset())
    async with create_connected_server_and_client_session(server) as session:
        ok, _, text = await live_check.call(session, "filter_tickets", {"query": "status:>1"})
    assert not ok and "invalid_value" in text and "2,3,4,5" in text


async def test_prefix_check_fails_when_the_real_person_is_not_found(live_check, make_server, api):
    def empty_search(request: httpx.Request) -> httpx.Response:
        if request.url.path in ("/api/v2/agents", "/api/v2/requesters") and "query" in request.url.params:
            return httpx.Response(200, json={"agents": [], "requesters": []})
        return freshservice(request)

    api.handler = empty_search
    outcomes = await run(live_check, make_server)
    failed = {o.name: o.detail for o in outcomes if not o.ok}
    assert len(failed) == 2 and all("was not returned" in d for d in failed.values()), failed
    assert any("~[first_name|last_name]:'Ang'" in d for d in failed.values())  # searched by real name prefix


async def test_kb_check_confirms_compact_search_and_reads_the_article(live_check, make_server, api):
    api.handler = freshservice
    outcomes = await run(live_check, make_server)
    kb = next(o for o in outcomes if o.name.startswith("knowledge base"))
    assert kb.ok and "compact results" in kb.detail and "returned 5 characters" in kb.detail

    def empty_article(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/api/v2/solutions/articles/2886":
            return httpx.Response(
                200, json={"article": {"id": 2886, "description": "", "description_text": ""}}
            )
        return freshservice(request)

    api.handler = empty_article
    outcomes = await run(live_check, make_server)
    kb = next(o for o in outcomes if o.name.startswith("knowledge base"))
    assert not kb.ok and "no body text" in kb.detail


async def test_write_checks_create_annotate_and_delete(live_check, make_server, api):
    api.handler = freshservice
    outcomes = await run(live_check, make_server, write_email="me@example.com")
    assert all(o.ok for o in outcomes), [(o.name, o.detail) for o in outcomes if not o.ok]
    assert [r.method for r in api.requests[-3:]] == ["POST", "POST", "DELETE"]
    assert json.loads(api.requests[-3].content)["email"] == "me@example.com"


async def test_failures_are_reported_not_raised(live_check, make_server, api):
    api.reply(401, {"description": "Invalid credentials"})
    outcomes = await run(live_check, make_server)
    assert outcomes[0].ok  # tools are listed without calling the API
    failing = [o for o in outcomes if not o.ok]
    assert len(failing) >= 8
    assert any("401" in o.detail for o in failing)


def test_summary_exit_codes(live_check):
    ok, bad = live_check.Outcome("a", True, ""), live_check.Outcome("b", False, "boom")
    assert live_check.summarise([ok]) == 0
    assert live_check.summarise([ok, bad]) == 1
