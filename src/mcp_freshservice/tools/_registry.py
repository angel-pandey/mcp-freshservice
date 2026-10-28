"""Toolset registry.

Each module declares its tools with ``@toolset.tool(...)``. Functions stay plain
async callables (handy for tests); they are only attached to a FastMCP server by
:func:`register_all`, which honours ``FRESHSERVICE_TOOLSETS`` and
``FRESHSERVICE_READ_ONLY``.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any, Literal

from mcp.server.fastmcp import FastMCP
from mcp.types import ToolAnnotations

Kind = Literal["read", "create", "update", "delete"]

_ANNOTATIONS: dict[Kind, dict[str, bool]] = {
    "read": {"readOnlyHint": True, "destructiveHint": False, "idempotentHint": True},
    "create": {"readOnlyHint": False, "destructiveHint": False, "idempotentHint": False},
    "update": {"readOnlyHint": False, "destructiveHint": False, "idempotentHint": True},
    "delete": {"readOnlyHint": False, "destructiveHint": True, "idempotentHint": True},
}


@dataclass
class ToolSpec:
    fn: Callable[..., Any]
    title: str
    kind: Kind


@dataclass
class Toolset:
    name: str
    description: str
    default: bool = False
    tools: list[ToolSpec] = field(default_factory=list)

    def tool(self, title: str, kind: Kind = "read") -> Callable[[Callable[..., Any]], Callable[..., Any]]:
        def decorator(fn: Callable[..., Any]) -> Callable[..., Any]:
            self.tools.append(ToolSpec(fn=fn, title=title, kind=kind))
            return fn

        return decorator


TOOLSETS: dict[str, Toolset] = {}

ALL = "all"
DEFAULT = "default"


def toolset(name: str, description: str, default: bool = False) -> Toolset:
    """Get or create a toolset. ``default`` toolsets are exposed unless the user chooses otherwise."""
    ts = TOOLSETS.setdefault(name, Toolset(name, description, default))
    return ts


def resolve_toolsets(requested: frozenset[str] = frozenset()) -> frozenset[str]:
    """Turn ``FRESHSERVICE_TOOLSETS`` into concrete toolset names.

    Nothing requested -> the default set. ``all`` -> everything. ``default`` expands to the default set so
    it can be combined: ``default,changes``. Anything else must be a toolset name.
    """
    if not requested:
        requested = frozenset({DEFAULT})
    unknown = requested - TOOLSETS.keys() - {ALL, DEFAULT}
    if unknown:
        raise ValueError(
            f"Unknown toolset(s): {', '.join(sorted(unknown))}. "
            f"Available: all, default, {', '.join(TOOLSETS)}"
        )
    if ALL in requested:
        return frozenset(TOOLSETS)
    names = set(requested) - {DEFAULT}
    if DEFAULT in requested:
        names |= {ts.name for ts in TOOLSETS.values() if ts.default}
    return frozenset(names)


def register_all(
    mcp: FastMCP, *, enabled: frozenset[str] = frozenset(), read_only: bool = False
) -> list[str]:
    selected = resolve_toolsets(enabled)
    registered = []
    for ts in TOOLSETS.values():
        if ts.name not in selected:
            continue
        for spec in ts.tools:
            if read_only and spec.kind != "read":
                continue
            mcp.add_tool(
                spec.fn,
                title=spec.title,
                annotations=ToolAnnotations(title=spec.title, openWorldHint=True, **_ANNOTATIONS[spec.kind]),
                structured_output=True,
            )
            registered.append(spec.fn.__name__)
    return registered
