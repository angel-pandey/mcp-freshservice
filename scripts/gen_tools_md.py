"""Regenerate TOOLS.md from the tool registry:  python scripts/gen_tools_md.py"""

from __future__ import annotations

import inspect
from pathlib import Path

from mcp_freshservice.tools import TOOLSETS, resolve_toolsets

TYPE = {"read": "read", "create": "write", "update": "write", "delete": "DELETE"}
HEADER = """\
# Tool catalogue

Generated from the code by `scripts/gen_tools_md.py` (a test fails if this file is stale).

- **read** = read-only, **write** = creates or changes data, **DELETE** = destructive.
- Toolsets marked **default** are on unless you choose otherwise. Pick toolsets with `FRESHSERVICE_TOOLSETS`
  or `--toolsets`: names, `default` (the core set) and `all`, e.g. `--toolsets default,changes,ticket_tasks`.
  `--list-toolsets` prints this index; `--read-only` drops every non-read tool.
"""


def first_sentence(fn) -> str:
    doc = (inspect.getdoc(fn) or "").split("\n\n")[0].replace("\n", " ").strip()
    doc = doc if len(doc) < 150 else doc[:147].rsplit(" ", 1)[0] + "…"
    return doc.replace("|", "\\|")


def render() -> str:
    total = sum(len(ts.tools) for ts in TOOLSETS.values())
    default_total = sum(len(TOOLSETS[n].tools) for n in resolve_toolsets())
    out = [HEADER, f"**{total} tools in {len(TOOLSETS)} toolsets; {default_total} in the default set.**", ""]
    out += ["| Toolset | Default | Tools | Read-only | Covers |", "|---|:-:|--:|--:|---|"]
    for ts in TOOLSETS.values():
        reads = sum(1 for t in ts.tools if t.kind == "read")
        mark = "yes" if ts.default else ""
        out.append(f"| [`{ts.name}`](#{ts.name}) | {mark} | {len(ts.tools)} | {reads} | {ts.description} |")
    out.append("")
    for ts in TOOLSETS.values():
        reads = sum(1 for t in ts.tools if t.kind == "read")
        flag = " — default" if ts.default else ""
        out += [f"## {ts.name}", "", f"{ts.description}. {len(ts.tools)} tools, {reads} read-only{flag}.", ""]
        out += ["| Tool | Type | What it does |", "|---|---|---|"]
        out += [f"| `{t.fn.__name__}` | {TYPE[t.kind]} | {first_sentence(t.fn)} |" for t in ts.tools]
        out.append("")
    return "\n".join(out)


if __name__ == "__main__":
    Path(__file__).resolve().parent.parent.joinpath("TOOLS.md").write_text(
        render(), encoding="utf-8", newline="\n"
    )
