"""Runtime configuration, read from environment variables (and a local ``.env``)."""

from __future__ import annotations

import os
from dataclasses import dataclass, field

TRUTHY = {"1", "true", "yes", "on"}


def normalize_domain(value: str) -> str:
    """Accept ``acme``, ``acme.freshservice.com`` or ``https://acme.freshservice.com/``."""
    domain = value.strip()
    for prefix in ("https://", "http://"):
        if domain.lower().startswith(prefix):
            domain = domain[len(prefix) :]
    domain = domain.split("/", 1)[0]
    if domain and "." not in domain:
        domain = f"{domain}.freshservice.com"
    return domain


def _split(value: str | None) -> frozenset[str]:
    if not value:
        return frozenset()
    return frozenset(part.strip().lower() for part in value.split(",") if part.strip())


@dataclass(frozen=True)
class Settings:
    domain: str
    api_key: str
    workspace_id: int | None = None
    timeout: float = 30.0
    read_only: bool = False
    toolsets: frozenset[str] = field(default_factory=frozenset)

    @classmethod
    def from_env(cls) -> Settings:
        workspace = os.getenv("FRESHSERVICE_WORKSPACE_ID", "").strip()
        return cls(
            domain=normalize_domain(os.getenv("FRESHSERVICE_DOMAIN", "")),
            api_key=os.getenv("FRESHSERVICE_APIKEY", os.getenv("FRESHSERVICE_API_KEY", "")).strip(),
            workspace_id=int(workspace) if workspace else None,
            timeout=float(os.getenv("FRESHSERVICE_TIMEOUT", "30")),
            read_only=os.getenv("FRESHSERVICE_READ_ONLY", "").strip().lower() in TRUTHY,
            toolsets=_split(os.getenv("FRESHSERVICE_TOOLSETS")),
        )
