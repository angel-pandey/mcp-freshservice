# Tool catalogue

Generated from the code by `scripts/gen_tools_md.py` (a test fails if this file is stale).

- **read** = read-only, **write** = creates or changes data, **DELETE** = destructive.
- Toolsets marked **default** are on unless you choose otherwise. Pick toolsets with `FRESHSERVICE_TOOLSETS`
  or `--toolsets`: names, `default` (the core set) and `all`, e.g. `--toolsets default,changes,ticket_tasks`.
  `--list-toolsets` prints this index; `--read-only` drops every non-read tool.

**204 tools in 24 toolsets; 76 in the default set.**

| Toolset | Default | Tools | Read-only | Covers |
|---|:-:|--:|--:|---|
| [`agents`](#agents) | yes | 9 | 5 | Agents (helpdesk staff) and their fields |
| [`assets`](#assets) |  | 16 | 12 | Assets, asset types, and canned responses |
| [`changes`](#changes) |  | 9 | 4 | Change requests with planning fields |
| [`change_notes`](#change_notes) |  | 5 | 2 | Notes on changes |
| [`change_tasks`](#change_tasks) |  | 5 | 2 | Tasks on changes |
| [`change_time_entries`](#change_time_entries) |  | 5 | 2 | Time entries on changes |
| [`change_approvals`](#change_approvals) |  | 9 | 3 | Approval groups and approvals on changes |
| [`groups`](#groups) | yes | 13 | 5 | Agent groups and requester groups (with membership) |
| [`organisation`](#organisation) |  | 20 | 11 | Workspaces, departments, locations, vendors and products |
| [`problems`](#problems) |  | 8 | 3 | Problems (root-cause investigations) |
| [`releases`](#releases) |  | 7 | 3 | Releases |
| [`problem_notes`](#problem_notes) |  | 5 | 2 | Notes on problems |
| [`problem_tasks`](#problem_tasks) |  | 5 | 2 | Tasks on problems |
| [`problem_time_entries`](#problem_time_entries) |  | 5 | 2 | Time entries on problems |
| [`release_notes`](#release_notes) |  | 5 | 2 | Notes on releases |
| [`release_tasks`](#release_tasks) |  | 5 | 2 | Tasks on releases |
| [`release_time_entries`](#release_time_entries) |  | 5 | 2 | Time entries on releases |
| [`requesters`](#requesters) | yes | 9 | 4 | Requesters (end users) and their fields |
| [`service_catalog`](#service_catalog) | yes | 5 | 4 | Service catalog items and service requests |
| [`solutions`](#solutions) | yes | 18 | 8 | Knowledge base categories, folders and articles |
| [`tickets`](#tickets) | yes | 17 | 8 | Incidents and service requests, replies, notes, conversations |
| [`ticket_tasks`](#ticket_tasks) |  | 5 | 2 | Tasks on tickets |
| [`ticket_time_entries`](#ticket_time_entries) | yes | 5 | 2 | Time entries on tickets |
| [`ticket_approvals`](#ticket_approvals) |  | 9 | 3 | Approval groups and approvals on tickets |

## agents

Agents (helpdesk staff) and their fields. 9 tools, 5 read-only — default.

| Tool | Type | What it does |
|---|---|---|
| `get_agent_fields` | read | List agent fields, including custom fields. |
| `get_all_agents` | read | List agents. |
| `filter_agents` | read | Search agents (30 per page, newest first; results cannot be sorted). |
| `get_agent` | read | Get an agent by ID, including roles and group memberships. |
| `create_agent` | write | Create an agent. Assign at least one role so the agent can sign in. |
| `update_agent` | write | Update an agent. Only the supplied fields change. |
| `deactivate_agent` | DELETE | Deactivate an agent (they become a requester; reversible with reactivate_agent). |
| `reactivate_agent` | write | Reactivate a deactivated agent. |
| `list_roles` | read | List agent roles (needed for create_agent's roles). |

## assets

Assets, asset types, and canned responses. 16 tools, 12 read-only.

| Tool | Type | What it does |
|---|---|---|
| `list_asset_types` | read | List asset types (Hardware, Software, ...). Needed for create_asset. |
| `get_asset_type_fields` | read | List the fields (including type-specific ones) of an asset type; use their names in type_fields. |
| `get_assets` | read | List assets, optionally searched or filtered. workspace_id 0 returns all workspaces (global fields only). |
| `get_asset` | read | Get an asset by display_id. |
| `create_asset` | write | Create an asset. |
| `update_asset` | write | Update an asset. Only the supplied fields change. |
| `delete_asset` | DELETE | Move an asset to trash (restorable with restore_asset). |
| `restore_asset` | write | Restore a trashed asset. |
| `list_asset_components` | read | List an asset's components (processor, memory, disks, ...). |
| `list_asset_contracts` | read | List contracts associated with an asset. |
| `list_asset_requests` | read | List tickets, problems, changes and releases associated with an asset. |
| `list_asset_relationships` | read | List relationships (depends on, used by, ...) of an asset. |
| `get_all_canned_response` | read | List canned (saved reply) responses. |
| `get_canned_response` | read | Get a canned response by ID, including its content. |
| `list_all_canned_response_folder` | read | List canned response folders. |
| `list_canned_response_folder` | read | List the canned responses inside a folder. |

## changes

Change requests with planning fields. 9 tools, 4 read-only.

| Tool | Type | What it does |
|---|---|---|
| `list_change_fields` | read | List change form fields, including custom fields and allowed choices. |
| `get_changes` | read | List changes, optionally narrowed by a view or a query. |
| `filter_changes` | read | Search changes with the Freshservice query language. |
| `get_change_by_id` | read | Get a change by ID, including planning fields and custom fields. |
| `create_change` | write | Create a change request. |
| `update_change` | write | Update a change. Only the supplied fields change. |
| `close_change` | write | Close a change (status 6) and record the result explanation custom field. |
| `delete_change` | DELETE | Delete a change. |
| `move_change` | write | Move a change to another workspace. |

## change_notes

Notes on changes. 5 tools, 2 read-only.

| Tool | Type | What it does |
|---|---|---|
| `list_change_notes` | read | List notes on a change. |
| `view_change_note` | read | Get one note on a change. |
| `create_change_note` | write | Add a note to a change. |
| `update_change_note` | write | Edit a note on a change. |
| `delete_change_note` | DELETE | Delete a note on a change. |

## change_tasks

Tasks on changes. 5 tools, 2 read-only.

| Tool | Type | What it does |
|---|---|---|
| `list_change_tasks` | read | List tasks on a change. |
| `view_change_task` | read | Get one task on a change. |
| `create_change_task` | write | Create a task on a change. |
| `update_change_task` | write | Update a task on a change. Task fields: title, description, status (1 Open, 2 In Progress, 3 Completed), due_date (ISO-8601), notify_before… |
| `delete_change_task` | DELETE | Delete a task on a change. |

## change_time_entries

Time entries on changes. 5 tools, 2 read-only.

| Tool | Type | What it does |
|---|---|---|
| `list_change_time_entries` | read | List time entries (time tracked by agents) on a change. |
| `view_change_time_entry` | read | Get one time entry on a change. |
| `create_change_time_entry` | write | Log time against a change. |
| `update_change_time_entry` | write | Update a time entry on a change. Time entry fields: time_spent ('hh:mm'), note, agent_id, billable, executed_at (ISO-8601), timer_running,… |
| `delete_change_time_entry` | DELETE | Delete a time entry on a change. |

## change_approvals

Approval groups and approvals on changes. 9 tools, 3 read-only.

| Tool | Type | What it does |
|---|---|---|
| `list_change_approval_groups` | read | List approval groups (with their approvals and statuses) on a change. |
| `create_change_approval_group` | write | Create an approval group on a change, which sends approval requests to the approvers. |
| `update_change_approval_group` | write | Update an approval group on a change. |
| `cancel_change_approval_group` | write | Cancel an approval group on a change. |
| `update_change_approval_chain_rule` | write | Set how multiple approval groups on a change combine. |
| `list_change_approvals` | read | List individual approvals on a change. |
| `view_change_approval` | read | Get one approval on a change. |
| `send_change_approval_reminder` | write | Re-send the approval request email for an approval on a change. |
| `cancel_change_approval` | write | Cancel a pending approval on a change. |

## groups

Agent groups and requester groups (with membership). 13 tools, 5 read-only — default.

| Tool | Type | What it does |
|---|---|---|
| `get_all_agent_groups` | read | List agent groups. |
| `get_agent_group` | read | Get an agent group by ID, including its members. |
| `create_group` | write | Create an agent group. |
| `update_group` | write | Update an agent group. Only the supplied fields change. |
| `delete_group` | DELETE | Delete an agent group. |
| `get_all_requester_groups` | read | List requester groups. |
| `get_requester_group` | read | Get a requester group by ID. |
| `create_requester_group` | write | Create a requester group. |
| `update_requester_group` | write | Update a requester group. |
| `delete_requester_group` | DELETE | Delete a requester group. |
| `list_requester_group_members` | read | List the requesters in a requester group. |
| `add_requester_to_group` | write | Add a requester to a manual requester group. |
| `remove_requester_from_group` | write | Remove a requester from a manual requester group. |

## organisation

Workspaces, departments, locations, vendors and products. 20 tools, 11 read-only.

| Tool | Type | What it does |
|---|---|---|
| `list_all_workspaces` | read | List workspaces (use their IDs as workspace_id elsewhere). |
| `get_workspace` | read | Get a workspace by ID. |
| `list_department_fields` | read | List department fields, including custom fields. |
| `list_departments` | read | List departments, optionally filtered by query. |
| `get_department` | read | Get a department by ID. |
| `create_department` | write | Create a department. |
| `update_department` | write | Update a department. |
| `delete_department` | DELETE | Delete a department. |
| `list_locations` | read | List locations, optionally filtered by query. |
| `get_location` | read | Get a location by ID. |
| `create_location` | write | Create a location. |
| `update_location` | write | Update a location. |
| `delete_location` | DELETE | Delete a location. |
| `list_vendors` | read | List vendors. |
| `get_vendor` | read | Get a vendor by ID. |
| `get_all_products` | read | List catalogue products. |
| `get_product` | read | Get a product by ID. |
| `create_product` | write | Create a product. |
| `update_product` | write | Update a product. Only the supplied fields change. |
| `delete_product` | DELETE | Delete a product. |

## problems

Problems (root-cause investigations). 8 tools, 3 read-only.

| Tool | Type | What it does |
|---|---|---|
| `list_problem_fields` | read | List problem form fields, including custom fields. |
| `get_problems` | read | List problems. Without workspace_id only the primary workspace is returned (0 means all). |
| `get_problem` | read | Get a problem by ID, including analysis_fields (cause, symptom, impact). |
| `create_problem` | write | Create a problem record. |
| `update_problem` | write | Update a problem. Only the supplied fields change. |
| `delete_problem` | DELETE | Move a problem to trash (restorable). |
| `restore_problem` | write | Restore a trashed problem. |
| `move_problem` | write | Move a problem to another workspace. |

## releases

Releases. 7 tools, 3 read-only.

| Tool | Type | What it does |
|---|---|---|
| `list_release_fields` | read | List release form fields, including custom fields. |
| `get_releases` | read | List releases, optionally using a predefined filter (the API has no free-form release query). |
| `get_release` | read | Get a release by ID. |
| `create_release` | write | Create a release. |
| `update_release` | write | Update a release. Only the supplied fields change. |
| `delete_release` | DELETE | Move a release to trash (restorable). |
| `restore_release` | write | Restore a trashed release. |

## problem_notes

Notes on problems. 5 tools, 2 read-only.

| Tool | Type | What it does |
|---|---|---|
| `list_problem_notes` | read | List notes on a problem. |
| `view_problem_note` | read | Get one note on a problem. |
| `create_problem_note` | write | Add a note to a problem. |
| `update_problem_note` | write | Edit a note on a problem. |
| `delete_problem_note` | DELETE | Delete a note on a problem. |

## problem_tasks

Tasks on problems. 5 tools, 2 read-only.

| Tool | Type | What it does |
|---|---|---|
| `list_problem_tasks` | read | List tasks on a problem. |
| `view_problem_task` | read | Get one task on a problem. |
| `create_problem_task` | write | Create a task on a problem. |
| `update_problem_task` | write | Update a task on a problem. Task fields: title, description, status (1 Open, 2 In Progress, 3 Completed), due_date (ISO-8601), notify_before… |
| `delete_problem_task` | DELETE | Delete a task on a problem. |

## problem_time_entries

Time entries on problems. 5 tools, 2 read-only.

| Tool | Type | What it does |
|---|---|---|
| `list_problem_time_entries` | read | List time entries (time tracked by agents) on a problem. |
| `view_problem_time_entry` | read | Get one time entry on a problem. |
| `create_problem_time_entry` | write | Log time against a problem. |
| `update_problem_time_entry` | write | Update a time entry on a problem. Time entry fields: time_spent ('hh:mm'), note, agent_id, billable, executed_at (ISO-8601), timer_running,… |
| `delete_problem_time_entry` | DELETE | Delete a time entry on a problem. |

## release_notes

Notes on releases. 5 tools, 2 read-only.

| Tool | Type | What it does |
|---|---|---|
| `list_release_notes` | read | List notes on a release. |
| `view_release_note` | read | Get one note on a release. |
| `create_release_note` | write | Add a note to a release. |
| `update_release_note` | write | Edit a note on a release. |
| `delete_release_note` | DELETE | Delete a note on a release. |

## release_tasks

Tasks on releases. 5 tools, 2 read-only.

| Tool | Type | What it does |
|---|---|---|
| `list_release_tasks` | read | List tasks on a release. |
| `view_release_task` | read | Get one task on a release. |
| `create_release_task` | write | Create a task on a release. |
| `update_release_task` | write | Update a task on a release. Task fields: title, description, status (1 Open, 2 In Progress, 3 Completed), due_date (ISO-8601), notify_before… |
| `delete_release_task` | DELETE | Delete a task on a release. |

## release_time_entries

Time entries on releases. 5 tools, 2 read-only.

| Tool | Type | What it does |
|---|---|---|
| `list_release_time_entries` | read | List time entries (time tracked by agents) on a release. |
| `view_release_time_entry` | read | Get one time entry on a release. |
| `create_release_time_entry` | write | Log time against a release. |
| `update_release_time_entry` | write | Update a time entry on a release. Time entry fields: time_spent ('hh:mm'), note, agent_id, billable, executed_at (ISO-8601), timer_running,… |
| `delete_release_time_entry` | DELETE | Delete a time entry on a release. |

## requesters

Requesters (end users) and their fields. 9 tools, 4 read-only — default.

| Tool | Type | What it does |
|---|---|---|
| `list_all_requester_fields` | read | List requester fields, including custom fields and their API names. |
| `get_all_requesters` | read | List requesters, optionally looked up by email or phone. |
| `filter_requesters` | read | Search requesters (30 per page, newest first; results cannot be sorted). |
| `get_requester` | read | Get a requester by ID. |
| `create_requester` | write | Create a requester. One of primary_email, work_phone_number or mobile_phone_number is required. |
| `update_requester` | write | Update a requester. Only the supplied fields change. |
| `deactivate_requester` | DELETE | Deactivate a requester (reversible with reactivate_requester). |
| `reactivate_requester` | write | Reactivate a deactivated requester. |
| `convert_requester_to_agent` | write | Convert a requester into an occasional agent. |

## service_catalog

Service catalog items and service requests. 5 tools, 4 read-only — default.

| Tool | Type | What it does |
|---|---|---|
| `list_service_catalog_categories` | read | List service catalog categories. |
| `list_service_items` | read | List one page of service catalog items. |
| `search_service_items` | read | Search service catalog items by keyword. |
| `get_service_item` | read | Get a service item, including its form fields (custom_fields names to use when placing a request). |
| `create_service_request` | write | Place a service request for a catalog item. |

## solutions

Knowledge base categories, folders and articles. 18 tools, 8 read-only — default.

| Tool | Type | What it does |
|---|---|---|
| `get_all_solution_category` | read | List knowledge-base categories. |
| `get_solution_category` | read | Get a knowledge-base category by ID. |
| `create_solution_category` | write | Create a knowledge-base category. |
| `update_solution_category` | write | Update a knowledge-base category. |
| `delete_solution_category` | DELETE | Move a category (and its folders and articles) to trash. |
| `get_list_of_solution_folder` | read | List the folders in a category. |
| `list_solution_subfolders` | read | List the sub-folders of a folder. |
| `get_solution_folder` | read | Get a knowledge-base folder by ID. |
| `create_solution_folder` | write | Create a knowledge-base folder. |
| `update_solution_folder` | write | Update a knowledge-base folder. |
| `delete_solution_folder` | DELETE | Move a folder (and its articles) to trash. |
| `get_list_of_solution_article` | read | List the articles in a folder: metadata plus a short plain-text `snippet`, not the full body. |
| `search_solution_articles` | read | Full-text search across published knowledge-base articles. |
| `get_solution_article` | read | Read a knowledge-base article by ID: the full HTML in description and plain text in description_text. |
| `create_solution_article` | write | Create a knowledge-base article (a draft unless status is 2). |
| `update_solution_article` | write | Update a knowledge-base article. |
| `publish_solution_article` | write | Publish a draft article (sets status to 2). |
| `delete_solution_article` | DELETE | Move an article to trash. |

## tickets

Incidents and service requests, replies, notes, conversations. 17 tools, 8 read-only — default.

| Tool | Type | What it does |
|---|---|---|
| `get_ticket_fields` | read | List ticket form fields, including custom fields, their API names and allowed choices. |
| `list_ticket_sources` | read | List ticket sources (channels), built-in and custom, with the numeric IDs create_ticket expects. |
| `get_tickets` | read | List tickets (newest first). Without a filter or updated_since, only the last 30 days are returned. |
| `filter_tickets` | read | Search tickets with the Freshservice query language (30 results per page). |
| `get_ticket_by_id` | read | Get a ticket by ID. Returns {"ticket": {...}} with all standard fields, custom_fields, planned dates, SLA flags (is_escalated, fr_escalated),… |
| `create_ticket` | write | Create an incident or service-request ticket. Some ticket forms make fields such as group_id, responder_id, category or custom fields mandatory;… |
| `update_ticket` | write | Update a ticket. Only the supplied fields change. |
| `delete_ticket` | DELETE | Move a ticket to trash. It can be brought back with restore_ticket. |
| `restore_ticket` | write | Restore a deleted (trashed) ticket. |
| `create_child_ticket` | write | Create a child ticket under an existing parent ticket. |
| `list_all_ticket_conversation` | read | List the replies and notes on a ticket, oldest first. Each has body/body_text, private, incoming, source, user_id, to/cc/bcc emails and attachments. |
| `send_ticket_reply` | write | Send a public reply to the requester on a ticket. |
| `create_ticket_note` | write | Add a note to a ticket (private by default). |
| `update_ticket_conversation` | write | Edit a note or reply. Only notes and replies created through the API/agents can be edited. |
| `delete_ticket_conversation` | DELETE | Delete a note or reply from a ticket. |
| `list_ticket_activities` | read | List the audit trail of a ticket (field changes, assignments, status changes). |
| `get_requested_items` | read | List the service catalog items requested on a service-request ticket. |

## ticket_tasks

Tasks on tickets. 5 tools, 2 read-only.

| Tool | Type | What it does |
|---|---|---|
| `list_ticket_tasks` | read | List tasks on a ticket. |
| `view_ticket_task` | read | Get one task on a ticket. |
| `create_ticket_task` | write | Create a task on a ticket. |
| `update_ticket_task` | write | Update a task on a ticket. Task fields: title, description, status (1 Open, 2 In Progress, 3 Completed), due_date (ISO-8601), notify_before… |
| `delete_ticket_task` | DELETE | Delete a task on a ticket. |

## ticket_time_entries

Time entries on tickets. 5 tools, 2 read-only — default.

| Tool | Type | What it does |
|---|---|---|
| `list_ticket_time_entries` | read | List time entries (time tracked by agents) on a ticket. |
| `view_ticket_time_entry` | read | Get one time entry on a ticket. |
| `create_ticket_time_entry` | write | Log time against a ticket. |
| `update_ticket_time_entry` | write | Update a time entry on a ticket. Time entry fields: time_spent ('hh:mm'), note, agent_id, billable, executed_at (ISO-8601), timer_running,… |
| `delete_ticket_time_entry` | DELETE | Delete a time entry on a ticket. |

## ticket_approvals

Approval groups and approvals on tickets. 9 tools, 3 read-only.

| Tool | Type | What it does |
|---|---|---|
| `list_ticket_approval_groups` | read | List approval groups (with their approvals and statuses) on a ticket. |
| `create_ticket_approval_group` | write | Create an approval group on a ticket, which sends approval requests to the approvers. |
| `update_ticket_approval_group` | write | Update an approval group on a ticket. |
| `cancel_ticket_approval_group` | write | Cancel an approval group on a ticket. |
| `update_ticket_approval_chain_rule` | write | Set how multiple approval groups on a ticket combine. |
| `list_ticket_approvals` | read | List individual approvals on a ticket. |
| `view_ticket_approval` | read | Get one approval on a ticket. |
| `send_ticket_approval_reminder` | write | Re-send the approval request email for an approval on a ticket. |
| `cancel_ticket_approval` | write | Cancel a pending approval on a ticket. |
