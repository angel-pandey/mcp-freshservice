"""FastMCP server entry point for ``mcp-freshservice``."""

from __future__ import annotations

import argparse
import logging
import os
import sys
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from dotenv import load_dotenv
from mcp.server.fastmcp import FastMCP

from . import __version__
from .client import FreshserviceClient, get_client, set_client
from .config import Settings
from .tools import TOOLSETS, register_all, resolve_toolsets

logger = logging.getLogger("mcp_freshservice")

INSTRUCTIONS = """\
Tools for the Freshservice ITSM REST API v2 (tickets, changes, problems, assets, requesters,
agents, groups, service catalog, knowledge base and more).

Conventions:
- Single-record tools return the Freshservice payload as-is, e.g. {"ticket": {...}}.
- List tools return one page plus {"pagination": {"page", "per_page", "next_page", "has_more"}};
  request the next page while has_more is true. per_page is at most 100.
- filter_* tools (and query/search/filter arguments) take Freshservice query language: field:value
  terms joined by AND / OR with (parentheses), max 512 characters. Numbers bare (priority:3), strings and
  dates in single quotes (tag:'vip', created_at:>'2025-01-01'), null for empty (agent_id:null). ':>' and
  ':<' are inclusive (>= and <=). Requester/agent queries also support prefix search "~[first_name|last_name]:'ad'".
  The outer double quotes the API requires are added for you. Filter results are 30 per page.
- Numeric codes: ticket status 2 Open, 3 Pending, 4 Resolved, 5 Closed; priority/urgency
  1 Low, 2 Medium, 3 High, 4 Urgent; impact 1 Low, 2 Medium, 3 High.
- Knowledge base: search_solution_articles and the list tools return article metadata; call
  get_solution_article with an id to read the full text.
- Failures are reported as tool errors containing Freshservice's own error description.
"""


@asynccontextmanager
async def lifespan(_: FastMCP) -> AsyncIterator[None]:
    try:
        yield
    finally:
        await get_client().aclose()


def build_server(settings: Settings, *, host: str = "127.0.0.1", port: int = 8000) -> FastMCP:
    set_client(FreshserviceClient(settings))
    mcp = FastMCP(
        "mcp-freshservice",
        instructions=INSTRUCTIONS,
        website_url="https://github.com/angel-pandey/mcp-freshservice",
        lifespan=lifespan,
        host=host,
        port=port,
        stateless_http=True,
        json_response=True,
    )
    names = register_all(mcp, enabled=settings.toolsets, read_only=settings.read_only)
    logger.info(
        "Registered %d Freshservice tools from toolsets: %s",
        len(names),
        ", ".join(sorted(resolve_toolsets(settings.toolsets))),
    )
    return mcp


def print_toolsets() -> None:
    width = max(len(name) for name in TOOLSETS)
    print("Toolsets (* = enabled by default). Select with --toolsets or FRESHSERVICE_TOOLSETS.\n")
    for ts in TOOLSETS.values():
        mark = "*" if ts.default else " "
        reads = sum(1 for t in ts.tools if t.kind == "read")
        print(f"{mark} {ts.name:<{width}}  {len(ts.tools):>3} tools ({reads:>2} read-only)  {ts.description}")
    enabled = resolve_toolsets()
    total = sum(len(TOOLSETS[n].tools) for n in enabled)
    print(
        f"\nDefault set: {total} tools. Use '--toolsets all' for all {sum(len(t.tools) for t in TOOLSETS.values())}."
    )


def main(argv: list[str] | None = None) -> None:
    load_dotenv()
    parser = argparse.ArgumentParser(prog="mcp-freshservice", description="Freshservice MCP server")
    parser.add_argument(
        "--transport",
        choices=["stdio", "streamable-http", "sse"],
        default=os.getenv("MCP_TRANSPORT", "stdio"),
        help="MCP transport (default: stdio, or $MCP_TRANSPORT)",
    )
    parser.add_argument("--host", default=os.getenv("MCP_HOST", "127.0.0.1"))
    parser.add_argument("--port", type=int, default=int(os.getenv("MCP_PORT", "8000")))
    parser.add_argument("--read-only", action="store_true", help="Only expose read-only tools")
    parser.add_argument(
        "--toolsets",
        help="Comma-separated toolsets to enable: names, 'default' (the core set) and/or 'all'. "
        "Default: the core set. Example: default,changes,ticket_tasks. Overrides $FRESHSERVICE_TOOLSETS",
    )
    parser.add_argument("--list-toolsets", action="store_true", help="Print the available toolsets and exit")
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    args = parser.parse_args(argv)

    if args.list_toolsets:
        print_toolsets()
        return

    # Logs go to stderr: stdout is the MCP stdio channel.
    logging.basicConfig(level=os.getenv("LOG_LEVEL", "INFO"), stream=sys.stderr)

    settings = Settings.from_env()
    overrides = {}
    if args.read_only:
        overrides["read_only"] = True
    if args.toolsets:
        overrides["toolsets"] = frozenset(t.strip().lower() for t in args.toolsets.split(",") if t.strip())
    if overrides:
        settings = Settings(**{**settings.__dict__, **overrides})
    if not settings.domain or not settings.api_key:
        logger.warning(
            "FRESHSERVICE_DOMAIN / FRESHSERVICE_APIKEY not set; tool calls will fail until configured"
        )

    try:
        server = build_server(settings, host=args.host, port=args.port)
    except ValueError as exc:  # unknown toolset name
        parser.error(str(exc))
    server.run(transport=args.transport)


if __name__ == "__main__":
    main()
