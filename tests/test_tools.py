"""Offline tests: every call goes through FastMCP's real call_tool path against a mocked Freshservice."""

from __future__ import annotations

import base64

import pytest
from mcp.server.fastmcp.exceptions import ToolError

pytestmark = pytest.mark.anyio

TICKET = {
    "ticket": {
        "id": 12031,
        "subject": "VPN down",
        "status": 4,
        "custom_fields": {"cf_resolution_note": "Rebooted the concentrator"},
        "planned_start_date": None,
        "attachments": [],
    }
}


@pytest.fixture(params=["asyncio"])
def anyio_backend(request):
    return request.param


async def call(server, name, args=None):
    """Return (content, structured) exactly as an MCP client would receive them."""
    content, structured = await server.call_tool(name, args or {})
    return content, structured


# --- Regression: get_ticket_by_id used to fail output validation ---------------------------------


async def test_get_ticket_by_id_returns_the_ticket_payload(server, api):
    api.reply(200, TICKET)
    _, structured = await call(server, "get_ticket_by_id", {"ticket_id": 12031})
    assert structured["ticket"]["id"] == 12031
    assert structured["ticket"]["custom_fields"]["cf_resolution_note"] == "Rebooted the concentrator"
    assert api.last.method == "GET" and api.last.url.path == "/api/v2/tickets/12031"


async def test_get_ticket_by_id_include_is_comma_joined(server, api):
    api.reply(200, TICKET)
    await call(server, "get_ticket_by_id", {"ticket_id": 1, "include": ["conversations", "stats"]})
    assert api.last.url.params["include"] == "conversations,stats"


async def test_get_ticket_by_id_rejects_unknown_include(server):
    with pytest.raises(ToolError):
        await call(server, "get_ticket_by_id", {"ticket_id": 1, "include": ["bogus"]})


@pytest.mark.parametrize(
    "name,args,path,key",
    [
        ("get_agent", {"agent_id": 5}, "/api/v2/agents/5", "agent"),
        ("get_requester", {"requester_id": 7}, "/api/v2/requesters/7", "requester"),
        ("get_agent_group", {"group_id": 3}, "/api/v2/groups/3", "group"),
        ("get_change_by_id", {"change_id": 9}, "/api/v2/changes/9", "change"),
        ("get_product", {"product_id": 2}, "/api/v2/products/2", "product"),
    ],
)
async def test_every_single_record_tool_returns_a_dict(server, api, name, args, path, key):
    api.reply(200, {key: {"id": 1}})
    _, structured = await call(server, name, args)
    assert structured[key]["id"] == 1
    assert api.last.url.path == path


# --- Errors surface as tool errors, never as fake successes -------------------------------------


async def test_api_error_becomes_tool_error_with_field_details(server, api):
    api.reply(
        400,
        {
            "description": "Validation failed",
            "errors": [{"field": "group_id", "message": "It should not be blank", "code": "missing_field"}],
        },
    )
    with pytest.raises(ToolError) as exc:
        await call(server, "create_ticket", {"subject": "s", "description": "d", "email": "a@b.co"})
    text = str(exc.value)
    assert "HTTP 400" in text and "group_id" in text and "missing_field" in text


@pytest.mark.parametrize(
    "status,hint", [(401, "FRESHSERVICE_APIKEY"), (404, "does not exist"), (429, "Rate limited")]
)
async def test_error_hints(server, api, status, hint):
    api.reply(status, {"description": "x"}, headers={"Retry-After": "12"})
    with pytest.raises(ToolError, match=hint):
        await call(server, "get_agent", {"agent_id": 1})


async def test_missing_configuration_is_explained(make_server):
    server = make_server(domain="", api_key="")
    with pytest.raises(ToolError, match="FRESHSERVICE_DOMAIN"):
        await call(server, "get_agent", {"agent_id": 1})


# --- Auth, pagination, queries ------------------------------------------------------------------


async def test_basic_auth_uses_api_key(server, api):
    api.reply(200, {"agent": {}})
    await call(server, "get_agent", {"agent_id": 1})
    expected = base64.b64encode(b"secret:X").decode()
    assert api.last.headers["authorization"] == f"Basic {expected}"
    assert api.last.url.host == "acme.freshservice.com"


async def test_list_reports_next_page_from_link_header(server, api):
    api.reply(
        200,
        {"tickets": [{"id": 1}]},
        headers={"Link": '<https://acme.freshservice.com/api/v2/tickets?page=3>; rel="next"'},
    )
    _, structured = await call(server, "get_tickets", {"page": 2, "per_page": 10})
    assert structured["pagination"] == {"page": 2, "per_page": 10, "next_page": 3, "has_more": True}
    assert dict(api.last.url.params) == {"page": "2", "per_page": "10"}


async def test_last_page_has_no_next(server, api):
    api.reply(200, {"tickets": []})
    _, structured = await call(server, "get_tickets")
    assert structured["pagination"]["has_more"] is False and structured["pagination"]["next_page"] is None


async def test_per_page_is_bounded(server):
    with pytest.raises(ToolError):
        await call(server, "get_tickets", {"per_page": 101})


@pytest.mark.parametrize("query", ["status:2 AND priority:4", '"status:2 AND priority:4"'])
async def test_filter_tickets_wraps_query_in_double_quotes_once(server, api, query):
    api.reply(200, {"tickets": [], "total": 0})
    await call(server, "filter_tickets", {"query": query})
    assert api.last.url.path == "/api/v2/tickets/filter"
    assert api.last.url.params["query"] == '"status:2 AND priority:4"'


async def test_filter_query_is_percent_encoded_like_the_docs(server, api):
    api.reply(200, {"tickets": []})
    await call(server, "filter_tickets", {"query": "status:2 AND tag:'vip'"})
    raw = str(api.last.url)
    assert (
        raw.endswith("query=%22status%3A2%20AND%20tag%3A%27vip%27%22")
        or "query=%22status%3A2%20AND%20tag%3A%27vip%27%22&" in raw
    )
    assert "+" not in api.last.url.query.decode()


async def test_filter_endpoints_do_not_send_per_page(server, api):
    api.reply(200, {"tickets": [], "agents": [], "requesters": []})
    for name, args in [
        ("filter_tickets", {"query": "status:2"}),
        ("filter_agents", {"query": "first_name:'a'"}),
        ("filter_requesters", {"query": "first_name:'a'"}),
    ]:
        _, structured = await call(server, name, args)
        assert "per_page" not in api.last.url.params, name
        assert structured["pagination"]["per_page"] == 30


@pytest.mark.parametrize("name", ["filter_agents", "filter_requesters"])
async def test_agent_and_requester_filters_cap_pages_at_40(server, api, name):
    with pytest.raises(ToolError):
        await call(server, name, {"query": "first_name:'a'", "page": 41})


@pytest.mark.parametrize("name", ["filter_agents", "filter_requesters"])
async def test_starts_with_operator_passes_through(server, api, name):
    api.reply(200, {"agents": [], "requesters": []})
    await call(server, name, {"query": "~[first_name|last_name]:'ad'"})
    assert api.last.url.params["query"] == "\"~[first_name|last_name]:'ad'\""


async def test_null_and_range_operators_pass_through(server, api):
    api.reply(200, {"tickets": []})
    await call(
        server, "filter_tickets", {"query": "agent_id:null AND priority:>2 AND created_at:<'2025-02-01'"}
    )
    assert api.last.url.params["query"] == "\"agent_id:null AND priority:>2 AND created_at:<'2025-02-01'\""


async def test_query_longer_than_512_characters_is_rejected_locally(server, api):
    with pytest.raises(ToolError, match="512"):
        await call(server, "filter_tickets", {"query": "tag:'" + "x" * 520 + "'"})
    assert api.requests == []


async def test_empty_query_is_rejected(server):
    with pytest.raises(ToolError, match="empty"):
        await call(server, "filter_tickets", {"query": '  ""  '})


async def test_releases_only_use_documented_filter_names(server, api):
    api.reply(200, {"releases": []})
    await call(server, "get_releases", {"filter_name": "my_open"})
    assert api.last.url.params["filter_name"] == "my_open"
    with pytest.raises(ToolError):
        await call(server, "get_releases", {"filter_name": "bogus"})
    assert "filter_releases" not in {t.name for t in await server.list_tools()}


async def test_filter_converts_inner_double_quotes_to_single(server, api):
    api.reply(200, {"agents": []})
    await call(server, "filter_agents", {"query": 'first_name:"Ada"'})
    assert api.last.url.params["query"] == "\"first_name:'Ada'\""


async def test_default_workspace_from_settings(make_server, api):
    server = make_server(workspace_id=2)
    api.reply(200, {"tickets": []})
    await call(server, "get_tickets")
    assert api.last.url.params["workspace_id"] == "2"
    await call(server, "get_tickets", {"workspace_id": 5})
    assert api.last.url.params["workspace_id"] == "5"


# --- Writes -------------------------------------------------------------------------------------


async def test_create_ticket_payload_and_ids(server, api):
    api.reply(201, TICKET)
    await call(
        server,
        "create_ticket",
        {
            "subject": "s",
            "description": "d",
            "email": "a@b.co",
            "priority": 3,
            "group_id": 11,
            "responder_id": 22,
            "custom_fields": {"cf_x": 1},
        },
    )
    body = api.last_json()
    assert body["group_id"] == 11 and body["responder_id"] == 22 and body["priority"] == 3
    assert body["status"] == 2 and body["source"] == 2 and body["custom_fields"] == {"cf_x": 1}
    assert "requester_id" not in body and "urgency" not in body


async def test_create_ticket_requires_a_requester(server):
    with pytest.raises(ToolError, match="requester"):
        await call(server, "create_ticket", {"subject": "s", "description": "d"})


async def test_reply_omits_from_email_unless_given(server, api):
    api.reply(201, {"conversation": {"id": 1}})
    await call(server, "send_ticket_reply", {"ticket_id": 5, "body": "hi"})
    assert api.last_json() == {"body": "hi"}
    assert api.last.url.path == "/api/v2/tickets/5/reply"


async def test_note_is_private_by_default_and_public_on_request(server, api):
    api.reply(201, {"conversation": {"id": 1}})
    await call(server, "create_ticket_note", {"ticket_id": 5, "body": "n"})
    assert api.last_json()["private"] is True
    await call(server, "create_ticket_note", {"ticket_id": 5, "body": "n", "private": False})
    assert api.last_json()["private"] is False


async def test_reply_with_attachment_uses_multipart(server, api, tmp_path):
    f = tmp_path / "log.txt"
    f.write_text("hello")
    api.reply(201, {"conversation": {"id": 1}})
    await call(
        server,
        "send_ticket_reply",
        {"ticket_id": 5, "body": "see log", "cc_emails": ["x@y.co"], "attachments": [str(f)]},
    )
    assert api.last.headers["content-type"].startswith("multipart/form-data")
    raw = api.last.content.decode()
    assert 'name="attachments[]"; filename="log.txt"' in raw and 'name="cc_emails[]"' in raw


async def test_missing_attachment_is_a_clear_error(server):
    with pytest.raises(ToolError, match="not found"):
        await call(server, "send_ticket_reply", {"ticket_id": 5, "body": "x", "attachments": ["/nope.txt"]})


async def test_delete_returns_success_marker(server, api):
    api.handler = lambda r: __import__("httpx").Response(204)
    _, structured = await call(server, "delete_ticket", {"ticket_id": 5})
    assert structured["success"] is True and api.last.method == "DELETE"


# --- Endpoints that were wrong or missing before ------------------------------------------------


async def test_ticket_time_entries_can_be_listed(server, api):
    api.reply(200, {"time_entries": [{"id": 1, "time_spent": "01:30"}]})
    _, structured = await call(server, "list_ticket_time_entries", {"ticket_id": 8})
    assert structured["time_entries"][0]["time_spent"] == "01:30"
    assert api.last.url.path == "/api/v2/tickets/8/time_entries"


async def test_time_spent_format_is_validated(server):
    with pytest.raises(ToolError):
        await call(server, "create_ticket_time_entry", {"ticket_id": 1, "agent_id": 2, "time_spent": "90"})


async def test_change_approval_paths_match_the_api(server, api):
    api.reply(200, {"approval_group": {}})
    await call(server, "list_change_approval_groups", {"change_id": 20})
    assert api.last.url.path == "/api/v2/changes/20/approval-groups"
    await call(server, "update_change_approval_chain_rule", {"change_id": 20, "rule": 1})
    assert api.last.url.path == "/api/v2/changes/20/approval-chain-rule" and api.last_json() == {"rule": 1}
    await call(server, "send_change_approval_reminder", {"change_id": 20, "approval_id": 9})
    assert api.last.method == "PUT" and api.last.url.path == "/api/v2/changes/20/approvals/9/remind"
    await call(server, "cancel_change_approval", {"change_id": 20, "approval_id": 9})
    assert api.last_json() == {"approval_status": {"id": 3}}


async def test_changes_query_is_quoted_and_not_combined_with_view(server, api):
    api.reply(200, {"changes": []})
    await call(server, "filter_changes", {"query": "approval_status:1 AND status:<5"})
    assert api.last.url.params["query"] == '"approval_status:1 AND status:<5"'
    with pytest.raises(ToolError, match="together"):
        await call(server, "get_changes", {"query": "status:1", "view": "my_open"})


async def test_close_change_sets_status_6_and_explanation(server, api):
    api.reply(200, {"change": {}})
    await call(server, "close_change", {"change_id": 4, "change_result_explanation": "done"})
    body = api.last_json()
    assert body["status"] == 6 and body["custom_fields"]["change_result_explanation"] == "done"


async def test_planning_fields_accept_plain_strings(server, api):
    api.reply(200, {"change": {}})
    await call(
        server,
        "update_change",
        {"change_id": 4, "change_fields": {"planning_fields": {"rollout_plan": "go"}}},
    )
    assert api.last_json()["planning_fields"] == {"rollout_plan": {"description": "go"}}


async def test_requester_group_members(server, api):
    api.reply(200, {"requesters": []})
    await call(server, "add_requester_to_group", {"requester_group_id": 1, "requester_id": 77})
    assert api.last.method == "POST" and api.last.url.path == "/api/v2/requester_groups/1/members/77"
    await call(server, "remove_requester_from_group", {"requester_group_id": 1, "requester_id": 77})
    assert api.last.method == "DELETE"


async def test_solution_article_search_and_folder_visibility_rule(server, api):
    api.reply(200, {"articles": []})
    await call(server, "search_solution_articles", {"search_term": "printer"})
    assert api.last.url.path == "/api/v2/solutions/articles/search"
    assert api.last.url.params["search_term"] == "printer"
    with pytest.raises(ToolError, match="department_ids"):
        await call(server, "create_solution_folder", {"name": "f", "category_id": 1, "visibility": 4})


async def test_service_request_places_on_the_catalog_item(server, api):
    api.reply(201, {"service_request": {}})
    await call(server, "create_service_request", {"display_id": 10, "email": "a@b.co", "quantity": 2})
    assert api.last.url.path == "/api/v2/service_catalog/items/10/place_request"
    assert api.last_json() == {"email": "a@b.co", "quantity": 2}


async def test_product_status_code_is_translated(server, api):
    api.reply(201, {"product": {}})
    await call(server, "create_product", {"name": "p", "asset_type_id": 1, "status": 3})
    assert api.last_json()["status"] == "Retired"


async def test_asset_filter_is_quoted(server, api):
    api.reply(200, {"assets": []})
    await call(server, "get_assets", {"filter": "asset_state:'IN USE'", "include": ["type_fields"]})
    assert api.last.url.params["filter"] == "\"asset_state:'IN USE'\""
    assert api.last.url.params["include"] == "type_fields"


# --- Ticket sources and KB search/read (found by testing in the chat app) -----------------------


async def test_ticket_sources_come_from_the_ticket_form_not_a_missing_endpoint(server, api):
    api.reply(
        200,
        {
            "ticket_fields": [
                {"name": "status", "choices": {"2": ["Open", 1]}},
                {"name": "source", "choices": [{"id": 1, "value": "Email"}, {"id": 1001, "value": "iPhone"}]},
            ]
        },
    )
    _, structured = await call(server, "list_ticket_sources")
    assert structured["sources"] == [{"id": 1, "value": "Email"}, {"id": 1001, "value": "iPhone"}]
    assert api.last.url.path == "/api/v2/ticket_form_fields"  # /ticket_fields/sources is create-only


async def test_ticket_sources_error_when_form_has_no_source_field(server, api):
    api.reply(200, {"ticket_fields": [{"name": "status"}]})
    with pytest.raises(ToolError, match="source"):
        await call(server, "list_ticket_sources")


async def test_search_pagination_uses_the_meta_block(server, api):
    api.reply(
        200,
        {
            "articles": [{"id": 1, "title": "a"}],
            "meta": {"total_items": 75, "total_pages": 3, "current_page": 1},
        },
    )
    _, structured = await call(server, "search_solution_articles", {"search_term": "printer", "per_page": 30})
    assert structured["pagination"] == {
        "page": 1,
        "per_page": 30,
        "next_page": 2,
        "has_more": True,
        "total_items": 75,
    }
    api.reply(200, {"articles": [], "meta": {"total_items": 75, "total_pages": 3, "current_page": 3}})
    _, structured = await call(server, "search_solution_articles", {"search_term": "printer", "page": 3})
    assert structured["pagination"]["has_more"] is False and structured["pagination"]["next_page"] is None


def _long_articles():
    html = "<p>" + "Reset your password. " * 100 + "</p>"
    text = "Reset your password. " * 100
    return [
        {
            "id": i,
            "title": f"Article {i}",
            "folder_id": 7,
            "status": 2,
            "description": html,
            "description_text": text,
        }
        for i in (1, 2)
    ]


@pytest.mark.parametrize(
    "tool,args",
    [
        ("search_solution_articles", {"search_term": "password"}),
        ("get_list_of_solution_article", {"folder_id": 7}),
    ],
)
async def test_kb_listings_are_compact_by_default(server, api, tool, args):
    api.reply(200, {"articles": _long_articles()})
    _, structured = await call(server, tool, args)
    for article in structured["articles"]:
        assert "description" not in article and "description_text" not in article
        assert article["id"] in (1, 2) and article["folder_id"] == 7  # metadata is kept
        assert 0 < len(article["snippet"]) <= 301 and article["snippet"].endswith("…")

    api.reply(200, {"articles": _long_articles()})
    _, structured = await call(server, tool, {**args, "include_body": True})
    assert structured["articles"][0]["description"].startswith("<p>Reset")
    assert "snippet" not in structured["articles"][0]


async def test_short_articles_get_their_whole_text_as_the_snippet(server, api):
    api.reply(200, {"articles": [{"id": 1, "description": "<p>Hi</p>", "description_text": " Hi there "}]})
    _, structured = await call(server, "search_solution_articles", {"search_term": "hi"})
    assert structured["articles"][0]["snippet"] == "Hi there"


async def test_kb_tool_descriptions_point_from_search_to_the_article_reader(server):
    tools = {t.name: t for t in await server.list_tools()}
    assert "get_solution_article" in tools["search_solution_articles"].description
    assert "get_solution_article" in tools["get_list_of_solution_article"].description
    assert "description_text" in tools["get_solution_article"].description


# --- Server surface -----------------------------------------------------------------------------


async def test_every_tool_has_schema_description_and_annotations(server):
    tools = await server.list_tools()
    assert len({t.name for t in tools}) == len(tools) > 150
    for t in tools:
        assert t.description, t.name
        assert t.outputSchema, t.name
        assert t.annotations is not None and t.annotations.openWorldHint, t.name


async def test_read_only_mode_exposes_only_read_tools(make_server):
    server = make_server(read_only=True)
    tools = await server.list_tools()
    assert tools and all(t.annotations.readOnlyHint for t in tools)
    assert "get_ticket_by_id" in {t.name for t in tools}
    assert "delete_ticket" not in {t.name for t in tools}


async def test_toolset_selection(make_server):
    server = make_server(toolsets=frozenset({"solutions"}))
    names = {t.name for t in await server.list_tools()}
    assert "search_solution_articles" in names and "get_ticket_by_id" not in names


async def test_default_set_is_the_core_tools_only(make_server):
    server = make_server(toolsets=frozenset())  # nothing chosen -> defaults
    names = {t.name for t in await server.list_tools()}
    assert {"get_ticket_by_id", "filter_tickets", "send_ticket_reply", "create_ticket_note"} <= names
    assert {"list_ticket_time_entries", "search_solution_articles", "get_requester", "get_agent"} <= names
    assert {"create_service_request", "get_all_agent_groups"} <= names
    # everything else is opt-in
    assert not names & {"get_changes", "get_problems", "get_releases", "get_assets", "list_departments"}
    assert not names & {"list_ticket_tasks", "list_ticket_approval_groups", "list_change_notes"}
    assert 50 < len(names) < 100


async def test_all_and_default_tokens(make_server):
    everything = {t.name for t in await make_server(toolsets=frozenset({"all"})).list_tools()}
    default = {t.name for t in await make_server(toolsets=frozenset()).list_tools()}
    combined = {t.name for t in await make_server(toolsets=frozenset({"default", "changes"})).list_tools()}
    assert default < combined < everything
    assert {"get_changes", "close_change"} <= combined - default
    assert "list_change_notes" not in combined  # change notes are their own toolset


async def test_explicit_toolsets_are_exclusive(make_server):
    names = {t.name for t in await make_server(toolsets=frozenset({"ticket_tasks"})).list_tools()}
    assert names == {
        "list_ticket_tasks",
        "view_ticket_task",
        "create_ticket_task",
        "update_ticket_task",
        "delete_ticket_task",
    }


def test_catalogue_file_is_up_to_date():
    import importlib.util
    from pathlib import Path

    root = Path(__file__).resolve().parent.parent
    spec = importlib.util.spec_from_file_location("gen_tools_md", root / "scripts" / "gen_tools_md.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    current = (root / "TOOLS.md").read_text(encoding="utf-8").replace("\r\n", "\n")
    assert current == module.render(), "TOOLS.md is stale: run `python scripts/gen_tools_md.py`"


def test_unknown_toolset_is_rejected(make_server):
    with pytest.raises(ValueError, match="Unknown toolset"):
        make_server(toolsets=frozenset({"nope"}))


def test_domain_normalisation():
    from mcp_freshservice.config import normalize_domain

    assert normalize_domain("acme") == "acme.freshservice.com"
    assert normalize_domain("https://acme.freshservice.com/") == "acme.freshservice.com"
    assert normalize_domain("helpdesk.example.com") == "helpdesk.example.com"
