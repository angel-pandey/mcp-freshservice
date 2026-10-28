# Changelog

## 2.0.0

Published as **`mcp-freshservice`** (was `freshservice-mcp`); run it with `uvx mcp-freshservice`.

### Fixed
- `get_ticket_by_id` returned a pydantic output-validation error instead of the ticket.
  Single-record tools now return their `{"ticket": {...}}` payload with a proper output schema, and
  `include=` (conversations, requester, stats, …) is supported.
- Tools that returned an error *string* from a `dict`-typed function and the `${…}` typo in
  those messages. Every failure is now a tool error with Freshservice's description and field errors.
- `send_ticket_reply` no longer sends a made-up `from_email` that Freshservice rejected with 400.
- Wrong ticket source IDs (Chat was 7, is 4) and missing ones (Chatbot, Workplace, Alerts, MS Teams, …).
- Change approvals used paths that don't exist (`approval_groups`, `approval_chain`, `resend_approval`);
  they now use `approval-groups`, `approval-chain-rule` and `approvals/{id}/remind`.
- Docs/examples that treated `:<` as strict (e.g. `status:<6` for "not closed" changes). `:>`/`:<` are inclusive,
  confirmed against a live account, so "not closed" is `status:<5`.
- Knowledge-base search and folder listings return a short `snippet` instead of every article's full HTML and
  text body (Freshservice sends full bodies for all 30 results, which is large enough for clients to truncate);
  pass `include_body=true` for the full text or read one article with `get_solution_article`.
- Change `query` and `view` can't be combined (the API rejects it); the server says so up front.
- Filter syntax checked against the official docs: `:>`/`:<` are documented as inclusive; query length limit
  (512) enforced locally; filter endpoints no longer send `per_page` (fixed 30); page caps (40) for
  requester/agent filters; queries are percent-encoded as in the docs; departments/locations/asset-search/
  release filters describe only their documented fields. Releases take the documented `filter_name` values
  only (there is no free-form release query).
- `filter_requesters` now quotes its query like the other filters (the API requires it); all filters use one code path.

### Added
- Ticket, change, problem and release time entries, tasks and notes; ticket approvals,
  child tickets, restore, activities, ticket sources.
- Problems, releases, assets and asset types, departments, locations, vendors, roles, service catalog
  search, solution search and sub-folders, requester-group member removal, agent/requester deactivate and
  reactivate.
- Attachments on replies, notes and tickets; `private` flag on notes; `group_id` /
  `responder_id` on `create_ticket`.
- `FRESHSERVICE_WORKSPACE_ID` default workspace, `FRESHSERVICE_READ_ONLY`,
  `FRESHSERVICE_TOOLSETS`, streamable-HTTP/SSE transports, `--version`.
- Read-only / destructive / idempotent annotations on every tool, titles, typed and described parameters.

### Changed (breaking)
- **Only a core set of 76 tools is enabled by default** (tickets, ticket time entries, requesters, agents,
  groups, solutions, service catalog). Everything else is opt-in: `--toolsets default,changes,assets` or
  `--toolsets all`; `--list-toolsets` shows the options. Notes, tasks, time entries and approvals for each
  record type are separate toolsets (e.g. `change_notes`).
- Requires `mcp>=1.30,<2` (MCP SDK v1 line); still Python 3.13+.
- Package/module renamed `freshservice_mcp` → `mcp_freshservice`; console script `mcp-freshservice`.
- `server.py` split into `client.py`, `config.py` and `tools/<area>.py`.
- Renamed tools: `get_requester_id` → `get_requester`, `getAgentGroupById` → `get_agent_group`,
  `get_requester_groups_by_id` → `get_requester_group`, `get_products_by_id` → `get_product`,
  `get_change_tasks` → `list_change_tasks`, `update_approval_chain_rule_change` →
  `update_change_approval_chain_rule`.
- Renamed parameters: generic `id` arguments are now explicit (`product_id`, `requester_group_id`,
  `canned_response_id`, `workspace_id`, `folder_id`, `category_id`); `get_list_of_solution_folder` takes
  `category_id` and `get_list_of_solution_article` takes `folder_id`.
- `update_agent`, `update_requester`, `update_group` and `update_*_task` take a fields object; `update_product`
  and `update_solution_category` no longer require every field.
- `list_canned_response_folder` now lists the responses *in* a folder (`/canned_response_folders/{id}/canned_responses`).
- List tools return the API's own wrapper once (`{"tickets": [...]}`, not nested twice) plus
  `pagination: {page, per_page, next_page, has_more}`; `current_page`/`prev_page` are gone.
  `list_service_items` returns one page instead of fetching every page; `filter_agents` returns one page.
- `send_ticket_reply` takes lists for `cc_emails`/`bcc_emails` (JSON strings are no longer parsed).
- `get_requested_items` no longer pre-fetches the ticket to check its type; the API's own error is returned.
- Failures raise tool errors rather than returning `{"error": ...}` dictionaries or strings.
- Removed `smithery.yaml` and the Smithery-generated `Dockerfile` (distribution is via PyPI/`uvx`).
- Dropped the `build` runtime dependency and the live-API script `tests/test-fs-mcp.py` (replaced by offline tests).
