"""Smoke-test mcp-freshservice against a real Freshservice account.

It starts the server exactly as an MCP client would (stdio), calls a set of tools and prints PASS/FAIL for each.
By default it is READ-ONLY: it cannot create, change or delete anything.

PowerShell:
    $env:FRESHSERVICE_DOMAIN = "yourcompany.freshservice.com"
    $env:FRESHSERVICE_APIKEY = "<your key>"
    uv run python scripts/live_check.py
    uv run python scripts/live_check.py --ticket-id 123          # use a specific ticket for the read checks

Write checks (optional) create ONE throwaway ticket, add a private note and delete it again. Freshservice may
email the requester, so use your own address:
    uv run python scripts/live_check.py --write --email you@yourcompany.com

The API key is read from the environment and is never printed.
"""

from __future__ import annotations

import argparse
import asyncio
import os
import sys
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Any

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

MISSING_TICKET_ID = 999_999_999


@dataclass
class Outcome:
    name: str
    ok: bool
    detail: str


async def call(session: ClientSession, tool: str, args: dict | None = None) -> tuple[bool, dict, str]:
    """Return (succeeded, structured result, text) for a tool call."""
    result = await session.call_tool(tool, args or {})
    text = " ".join(c.text for c in result.content if getattr(c, "type", "") == "text")
    return (not result.isError), dict(result.structuredContent or {}), text


class Runner:
    def __init__(self) -> None:
        self.outcomes: list[Outcome] = []

    async def check(self, name: str, fn: Callable[[], Awaitable[str]]) -> None:
        try:
            detail = await fn()
            outcome = Outcome(name, True, detail)
        except AssertionError as exc:
            outcome = Outcome(name, False, str(exc) or "assertion failed")
        except Exception as exc:  # noqa: BLE001 - any crash in a check must be reported, not abort the run
            outcome = Outcome(name, False, f"{type(exc).__name__}: {exc}")
        self.outcomes.append(outcome)
        print(
            f"{'PASS' if outcome.ok else 'FAIL'}  {name}"
            + (f"  -  {outcome.detail}" if outcome.detail else "")
        )


def short(text: str, limit: int = 300) -> str:
    return text if len(text) <= limit else text[: limit - 1] + "…"


async def run_checks(
    session: ClientSession, *, ticket_id: int | None = None, write_email: str | None = None
) -> list[Outcome]:
    run = Runner()
    state: dict[str, Any] = {"ticket_id": ticket_id, "ticket": None}

    async def tools_listed() -> str:
        names = {t.name for t in (await session.list_tools()).tools}
        missing = {"get_ticket_by_id", "filter_tickets", "get_tickets", "get_agent"} - names
        assert not missing, f"missing tools: {sorted(missing)}"
        return f"{len(names)} tools exposed"

    async def list_tickets() -> str:
        ok, data, text = await call(session, "get_tickets", {"per_page": 3})
        assert ok, short(text)
        tickets = data.get("tickets", [])
        assert isinstance(tickets, list), "response has no 'tickets' list"
        if not tickets:
            return "reachable, but the account has no tickets in the default window"
        if state["ticket_id"] is None:
            state["ticket_id"] = tickets[0]["id"]
        return f"{len(tickets)} tickets, using #{state['ticket_id']} for the next checks"

    async def get_ticket() -> str:
        assert state["ticket_id"], "no ticket to fetch (pass --ticket-id)"
        ok, data, text = await call(session, "get_ticket_by_id", {"ticket_id": state["ticket_id"]})
        assert ok, short(text)
        ticket = data.get("ticket")
        assert isinstance(ticket, dict), f"expected {{'ticket': {{...}}}}, got keys {sorted(data)}"
        assert ticket.get("id") == state["ticket_id"], "returned a different ticket"
        state["ticket"] = ticket
        return f"subject={short(str(ticket.get('subject')), 60)!r} status={ticket.get('status')}"

    async def get_ticket_include() -> str:
        assert state["ticket_id"], "no ticket to fetch"
        args = {"ticket_id": state["ticket_id"], "include": ["stats", "requester"]}
        ok, data, text = await call(session, "get_ticket_by_id", args)
        assert ok, short(text)
        assert "ticket" in data, "no 'ticket' in response"
        return "include=stats,requester accepted"

    async def paging() -> str:
        ok, first, text = await call(session, "get_tickets", {"per_page": 2, "page": 1})
        assert ok, short(text)
        page = first.get("pagination", {})
        assert page.get("page") == 1 and "has_more" in page, f"bad pagination block: {page}"
        if not page["has_more"]:
            return "only one page of tickets, nothing to compare"
        ok, second, text = await call(session, "get_tickets", {"per_page": 2, "page": page["next_page"]})
        assert ok, short(text)
        ids_1 = {t["id"] for t in first["tickets"]}
        ids_2 = {t["id"] for t in second["tickets"]}
        assert ids_1 and ids_2 and not ids_1 & ids_2, "page 2 repeated page 1"
        return f"page 1 {sorted(ids_1)} / page 2 {sorted(ids_2)}"

    async def filter_open() -> str:
        ok, data, text = await call(session, "filter_tickets", {"query": "status:2"})
        assert ok, short(text)
        assert isinstance(data.get("tickets"), list), "no 'tickets' list"
        return f"{len(data['tickets'])} on page 1, total={data.get('total')}"

    async def filter_operators() -> str:
        query = "status:>2 AND priority:>1 AND agent_id:null"  # values must be real statuses/priorities
        ok, data, text = await call(session, "filter_tickets", {"query": query})
        assert ok, short(text)
        return f"{len(data.get('tickets', []))} unassigned matches (query accepted)"

    async def operator_semantics() -> str:
        """Is ':>' / ':<' inclusive (>=, <=) as documented, or strict? Test it on the ticket we already fetched."""
        ticket = state["ticket"]
        assert ticket, "needs the ticket from the get_ticket_by_id check"
        rid, status, priority, tid = (
            ticket["requester_id"],
            ticket["status"],
            ticket["priority"],
            ticket["id"],
        )

        async def appears(query: str) -> bool:
            for page in range(1, 4):
                ok, data, text = await call(session, "filter_tickets", {"query": query, "page": page})
                assert ok, short(text)
                if tid in {t["id"] for t in data.get("tickets", [])}:
                    return True
                if not data.get("pagination", {}).get("has_more"):
                    return False
            return False

        base = f"requester_id:{rid}"
        ge = await appears(f"{base} AND status:>{status} AND priority:>{priority}")
        le = await appears(f"{base} AND status:<{status} AND priority:<{priority}")
        if ge and le:
            return f"':>' and ':<' are INCLUSIVE (>= and <=), as documented (ticket #{tid} matched both)"
        if not ge and not le:
            return f"NOTE: ':>' and ':<' are STRICT (> and <) here, unlike the docs (ticket #{tid} matched neither)"
        return f"NOTE: mixed behaviour: ':>' inclusive={ge}, ':<' inclusive={le}"

    async def not_found() -> str:
        ok, _, text = await call(session, "get_ticket_by_id", {"ticket_id": MISSING_TICKET_ID})
        assert not ok, "a missing ticket should be an error"
        assert "404" in text, f"expected a 404 explanation, got: {short(text)}"
        return "clear 404 error"

    async def time_entries() -> str:
        assert state["ticket_id"], "no ticket to query"
        ok, data, text = await call(session, "list_ticket_time_entries", {"ticket_id": state["ticket_id"]})
        assert ok, short(text)
        return f"{len(data.get('time_entries', []))} time entries"

    async def prefix_roundtrip(list_tool: str, filter_tool: str, key: str, label: str) -> str:
        """Take a real person, search for the start of their first name, and require them in the results."""
        ok, data, text = await call(session, list_tool, {"per_page": 1})
        assert ok, short(text)
        people = data.get(key, [])
        assert people, f"the account has no {key} to search for"
        person = people[0]
        name = (person.get("first_name") or "").strip()
        assert name, f"{label} #{person.get('id')} has no first_name to search for"
        prefix = name[:3]
        query = f"~[first_name|last_name]:'{prefix}'"
        ok, found, text = await call(session, filter_tool, {"query": query})
        assert ok, short(text)
        ids = {p["id"] for p in found.get(key, [])}
        assert person["id"] in ids, (
            f"searched {query} but {label} #{person['id']} ({name!r}) was not returned "
            f"({len(ids)} results); the API may need time to index, or the starts-with syntax differs"
        )
        return f"{query} found {label} #{person['id']} among {len(ids)} result(s)"

    async def agents_prefix() -> str:
        return await prefix_roundtrip("get_all_agents", "filter_agents", "agents", "agent")

    async def requesters_prefix() -> str:
        return await prefix_roundtrip("get_all_requesters", "filter_requesters", "requesters", "requester")

    async def knowledge_base() -> str:
        """Search (compact results), then read the first hit in full."""
        ok, data, text = await call(session, "search_solution_articles", {"search_term": "the"})
        assert ok, short(text)
        articles = data.get("articles", [])
        if not articles:
            return "search worked but found no articles for 'the', so nothing to read"
        first = articles[0]
        assert "snippet" in first, "search results should carry a short snippet"
        assert "description" not in first and "description_text" not in first, (
            "search results still carry full article bodies"
        )
        search_kb = len(text) // 1000
        ok, full, text = await call(session, "get_solution_article", {"article_id": first["id"]})
        assert ok, short(text)
        article = full.get("article", {})
        body = (article.get("description_text") or article.get("description") or "").strip()
        assert body, f"article #{first['id']} came back with no body text"
        return (
            f"{len(articles)} compact results (~{search_kb} KB, snippet {len(first['snippet'])} chars); "
            f"get_solution_article #{first['id']} returned {len(body)} characters"
        )

    async def ticket_sources() -> str:
        ok, data, text = await call(session, "list_ticket_sources")
        assert ok, short(text)
        sources = data.get("sources", [])
        ids = {src.get("id") for src in sources}
        assert {1, 2, 3} <= ids, f"expected the built-in Email/Portal/Phone sources, got {sources}"
        names = ", ".join(str(src.get("value")) for src in sources[:8])
        return f"{len(sources)} sources: {names}" + (", ..." if len(sources) > 8 else "")

    await run.check("server exposes the core tools", tools_listed)
    await run.check("list tickets", list_tickets)
    await run.check("get_ticket_by_id returns the ticket", get_ticket)
    await run.check("get_ticket_by_id with include=", get_ticket_include)
    await run.check("pagination: page 2 differs from page 1", paging)
    await run.check("filter_tickets  status:2", filter_open)
    await run.check("filter_tickets  :>, AND and null", filter_operators)
    await run.check("filter_tickets  :> and :< inclusive or strict?", operator_semantics)
    await run.check("missing ticket gives a clear error", not_found)
    await run.check("list ticket time entries", time_entries)
    await run.check("list ticket sources (built-in and custom)", ticket_sources)
    await run.check("filter_agents starts-with (~) finds a real agent", agents_prefix)
    await run.check("filter_requesters starts-with (~) finds a real requester", requesters_prefix)
    await run.check("knowledge base: search, then read the article", knowledge_base)

    if write_email:
        created: dict[str, int | None] = {"id": None}

        async def create() -> str:
            args = {
                "subject": "[mcp-freshservice test] safe to delete",
                "description": "Created by scripts/live_check.py. Safe to delete.",
                "email": write_email,
                "priority": 1,
                "status": 2,
            }
            ok, data, text = await call(session, "create_ticket", args)
            assert ok, short(text)
            created["id"] = data["ticket"]["id"]
            return f"created ticket #{created['id']}"

        async def note() -> str:
            assert created["id"], "no test ticket was created"
            ok, data, text = await call(
                session, "create_ticket_note", {"ticket_id": created["id"], "body": "private test note"}
            )
            assert ok, short(text)
            assert data["conversation"]["private"] is True, "note should be private by default"
            return "private note added"

        async def delete() -> str:
            assert created["id"], "no test ticket was created"
            ok, _, text = await call(session, "delete_ticket", {"ticket_id": created["id"]})
            assert ok, short(text)
            return f"ticket #{created['id']} moved to trash"

        await run.check("WRITE: create a test ticket", create)
        await run.check("WRITE: add a private note", note)
        await run.check("WRITE: delete the test ticket", delete)

    return run.outcomes


def summarise(outcomes: list[Outcome]) -> int:
    failed = [o for o in outcomes if not o.ok]
    print(f"\n{len(outcomes) - len(failed)}/{len(outcomes)} checks passed")
    if failed:
        print("Failed: " + "; ".join(o.name for o in failed))
        print("Send me the FAIL lines above (never your API key).")
    return 1 if failed else 0


async def main(args: argparse.Namespace) -> int:
    env = dict(os.environ)
    if args.write:
        env.pop("FRESHSERVICE_READ_ONLY", None)
    else:
        env["FRESHSERVICE_READ_ONLY"] = "1"
    env.pop("FRESHSERVICE_TOOLSETS", None)  # test the default set
    params = StdioServerParameters(command=sys.executable, args=["-m", "mcp_freshservice"], env=env)
    print(f"Testing {env['FRESHSERVICE_DOMAIN']} ({'read/write' if args.write else 'read-only'})\n")
    async with stdio_client(params) as (read, write), ClientSession(read, write) as session:
        await session.initialize()
        outcomes = await run_checks(
            session, ticket_id=args.ticket_id, write_email=args.email if args.write else None
        )
    return summarise(outcomes)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("--ticket-id", type=int, help="ticket to use for the read checks (default: newest)")
    parser.add_argument(
        "--write", action="store_true", help="also create, annotate and delete one test ticket"
    )
    parser.add_argument("--email", help="requester email for the test ticket (required with --write)")
    args = parser.parse_args()
    if args.write and not args.email:
        parser.error("--write needs --email (the test ticket's requester; use your own address)")
    for var in ("FRESHSERVICE_DOMAIN", "FRESHSERVICE_APIKEY"):
        if not os.environ.get(var):
            parser.error(f"set {var} in the environment first (see the examples at the top of this file)")
    return args


if __name__ == "__main__":
    sys.exit(asyncio.run(main(parse_args())))
