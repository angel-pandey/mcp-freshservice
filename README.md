# mcp-freshservice

A [Model Context Protocol](https://modelcontextprotocol.io/) server for the
[Freshservice REST API v2](https://api.freshservice.com/). It lets an AI assistant work with tickets,
changes, problems, releases, assets, requesters, agents, groups, the service catalog and the knowledge
base.

> Forked from [effytech/freshservice_mcp](https://github.com/effytech/freshservice_mcp) and reworked for
> v2 (see [CHANGELOG.md](CHANGELOG.md) for breaking changes).

## Quick start

You need a Freshservice API key (Profile Settings → API key) and your domain.

```bash
uvx mcp-freshservice --version
```

Claude Desktop / any MCP client (`claude_desktop_config.json`):

```json
{
  "mcpServers": {
    "freshservice": {
      "command": "uvx",
      "args": ["mcp-freshservice"],
      "env": {
        "FRESHSERVICE_DOMAIN": "yourcompany.freshservice.com",
        "FRESHSERVICE_APIKEY": "<your-api-key>"
      }
    }
  }
}
```

Claude Code: `claude mcp add freshservice -e FRESHSERVICE_DOMAIN=yourcompany.freshservice.com -e FRESHSERVICE_APIKEY=... -- uvx mcp-freshservice`

## Configuration

| Variable | Required | Description |
|---|---|---|
| `FRESHSERVICE_DOMAIN` | yes | `yourcompany.freshservice.com` (a bare `yourcompany` also works) |
| `FRESHSERVICE_APIKEY` | yes | API key of the agent the server acts as. Permissions follow that agent |
| `FRESHSERVICE_WORKSPACE_ID` | no | Default `workspace_id` for calls on multi-workspace accounts. A tool's own `workspace_id` argument wins |
| `FRESHSERVICE_READ_ONLY` | no | `1` exposes only read-only tools |
| `FRESHSERVICE_TOOLSETS` | no | Which toolsets to expose: names, `default` (the core set, used when unset) and/or `all`. See [Choosing tools](#choosing-tools) |
| `FRESHSERVICE_TIMEOUT` | no | HTTP timeout in seconds (default 30) |
| `FRESHSERVICE_ATTACHMENT_DIRS` | no | Folder(s) the server may read attachments from (`;` between several on Windows, `:` elsewhere). **Attachments are off until set** |
| `FRESHSERVICE_MAX_RETRIES` | no | Retries after a rate limit (429) or a transient 502/503/504 on reads (default 3, `0` disables) |
| `MCP_TRANSPORT`, `MCP_HOST`, `MCP_PORT` | no | `stdio` (default), `streamable-http` or `sse` |

The same switches exist as flags: `--read-only`, `--toolsets tickets,solutions`, `--transport`.

### Choosing tools

The server can expose 204 tools (full list in [TOOLS.md](TOOLS.md)), but some clients cap the tools per agent
(for example 128) and models choose better from a shorter list. So **by default only a 76-tool core set is
enabled**; everything else is opt-in by toolset.

```bash
uvx mcp-freshservice --list-toolsets                         # see what's available
uvx mcp-freshservice --toolsets default,changes,assets       # core set + changes + assets
uvx mcp-freshservice --toolsets all                          # everything
uvx mcp-freshservice --toolsets tickets,solutions --read-only
```

The same works with `FRESHSERVICE_TOOLSETS=default,changes` in the client's `env`. A list of plain names is
exact (only those toolsets); add `default` to keep the core set.

| Toolset | Default | Tools | Covers |
|---|:-:|---:|---|
| `tickets` | yes | 17 | tickets, replies and notes (with attachments), conversations, child tickets, requested items |
| `ticket_time_entries` | yes | 5 | time logged on tickets |
| `ticket_tasks` | | 5 | ticket tasks |
| `ticket_approvals` | | 9 | service-request approval groups and approvals |
| `requesters` | yes | 9 | requesters, fields, reactivate, convert to agent |
| `agents` | yes | 9 | agents, fields, roles |
| `groups` | yes | 13 | agent groups, requester groups and membership |
| `solutions` | yes | 18 | knowledge-base categories, folders, articles, search |
| `service_catalog` | yes | 5 | browse/search items, place service requests |
| `changes` | | 9 | change requests and planning fields |
| `change_notes`, `change_tasks`, `change_time_entries` | | 5 each | notes, tasks, time entries on changes |
| `change_approvals` | | 9 | change approval groups, chains, approvals |
| `problems`, `releases` | | 8, 7 | problem and release records |
| `problem_*`, `release_*` (`notes`, `tasks`, `time_entries`) | | 5 each | notes, tasks, time entries |
| `assets` | | 16 | assets, asset types, canned responses |
| `organisation` | | 20 | workspaces, departments, locations, vendors, products |

Every tool is annotated read-only / destructive so clients can auto-approve safely.

## Conventions

- **Single records** come back as Freshservice returns them: `{"ticket": {...}}`.
- **Lists** return one page plus `pagination: {page, per_page, next_page, has_more}`. `per_page` is at most 100.
- **Errors** are real MCP tool errors (`isError: true`) carrying Freshservice's message and field errors,
  with hints for 401/403/404/429.
- **Filtering**: see [Query syntax](#query-syntax).
- **Numeric codes**: ticket status 2 Open, 3 Pending, 4 Resolved, 5 Closed; priority 1 Low … 4 Urgent;
  source 1 Email, 2 Portal, 3 Phone, 4 Chat … (see `list_ticket_sources` for the full list).
- **Attachments**: `send_ticket_reply`, `create_ticket_note`, `create_ticket` and
  `update_ticket_conversation` accept local file paths (max 15 files / 40 MB), but only from folders listed in
  `FRESHSERVICE_ATTACHMENT_DIRS`. Until you set it, attachments are refused, so a prompt-injected path can't
  upload an arbitrary local file.

Example prompts: "Show ticket 12031 with its conversations and resolution notes", "How much time was
logged on ticket 8?", "List open P1 incidents unassigned for a day", "Search the KB for printer setup".

## Query syntax

`filter_tickets`, `filter_changes`, `filter_requesters`, `filter_agents` and the `query` / `filter` / `search`
arguments of the list tools use Freshservice's query language. Freshservice requires the whole query to be
**enclosed in a pair of double quotes** (without them the API answers `500`), so the server adds them for you;
you can pass `status:3` or `"status:3"` and get the same request.

| Rule | Example |
|---|---|
| Fields are snake_case and case-sensitive (custom fields by API name) | `status:3` |
| Numbers bare, strings and dates in **single** quotes | `tag:'vip'`, `planned_start_date:>'2025-07-14'` |
| `AND`, `OR` and parentheses | `(group_id:12 OR group_id:15) AND status:3` |
| `:>` / `:<` are **inclusive** (>= and <=), confirmed on a live account | `status:<5` means status 5 or lower |
| `null` finds empty values | `agent_id:null` |
| Starts-with (requesters and agents only) | `~[first_name\|last_name]:'ad'` |
| Max 512 characters (checked locally); filter results are 30 per page | |

Changes: `"status:3"` awaiting approval, `"approval_status:1"` approved,
`"approval_status:1 AND status:<5"` approved and not closed (status 6 is Closed, and `:<` includes its boundary, so `<6` would include closed changes), `"status:3 AND priority:1"`. `approval_status`
is 0 Requested, 1 Approved, 2 Rejected, 3 Not requested. A change `view` and `query` cannot be combined.

Not every endpoint supports every field: departments and locations filter on `name` only; asset `search`
takes one field (`name`, `asset_tag`, `serial_number`, ...); releases only have predefined `filter_name`
values. The per-tool descriptions list the supported fields. Filtered requester/agent pages are capped at 40;
changes to users can take a few minutes to be indexed.

## Rate limits

Freshservice limits requests per minute. When it answers HTTP 429 the server waits for the `Retry-After`
time (up to 20 seconds) and tries again, up to `FRESHSERVICE_MAX_RETRIES` times; transient 502/503/504 errors
on reads are retried the same way. If the wait would be longer than 20 seconds, or retries run out, the tool
reports the rate-limit error instead. Writes are only ever retried after a 429, because a request that was
rate-limited was not processed.

## Running remotely

```bash
MCP_TRANSPORT=streamable-http MCP_PORT=8000 uvx mcp-freshservice
```

The server is stateless over streamable HTTP and serves `/mcp`. It has **no authentication of its own**:
run it behind a gateway/reverse proxy that authenticates callers, because everyone who can reach it acts
with the configured API key.

## Development

```bash
uv sync
uv run pytest        # offline, mocks the Freshservice API
uv run ruff check .
```

To check the server against a real Freshservice account (read-only by default; never prints your key):

```bash
uv run python scripts/live_check.py            # the core tools, read-only
uv run python scripts/live_check.py --sweep    # every read-only tool of every toolset
```

The sweep calls each read-only tool once, using real IDs it finds along the way. A wrong endpoint shows up as
a failure; an empty list or a 403 (module not on your plan, or no permission) is a skip.

When you point an MCP client at a local checkout with `uvx --from <folder> mcp-freshservice`, uvx reuses a
cached build and will not notice your code changes (`--refresh` does not help). Add `--no-cache` to the uvx
arguments while developing, e.g. `"args": ["--no-cache", "--from", "G:/path/to/mcp-freshservice", "mcp-freshservice"]`.

Tests call tools through FastMCP's real `call_tool` path against a mocked API, so output-schema problems
(like the old `get_ticket_by_id` failure) are caught without credentials. Each tool module lives in
`src/mcp_freshservice/tools/`; add tools with `@ts.tool(title, kind)` and they are registered, filtered and
annotated automatically.

## Releasing

1. Bump `version` in `pyproject.toml` and add a `## <version>` section to `CHANGELOG.md`.
2. Merge to `main`, then create a GitHub release tagged `v<version>`.
3. The publish workflow first checks that the tag, the package version and the changelog agree, then runs
   lint and the tests, and only then uploads to PyPI (after your approval on the `pypi` environment).

`python scripts/check_release.py v<version>` runs the first check locally. PyPI never accepts a version twice,
so the check exists to fail before anything is uploaded.

## License

MIT, see [LICENSE](LICENSE).
