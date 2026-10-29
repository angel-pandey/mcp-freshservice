from __future__ import annotations

import json
from collections.abc import Callable

import httpx
import pytest

from mcp_freshservice.client import FreshserviceClient, set_client
from mcp_freshservice.config import Settings
from mcp_freshservice.server import build_server


class Recorder:
    """Captures requests and serves canned responses through httpx.MockTransport."""

    def __init__(self) -> None:
        self.requests: list[httpx.Request] = []
        self.sleeps: list[float] = []  # what the client asked to wait between retries
        self.handler: Callable[[httpx.Request], httpx.Response] = lambda r: httpx.Response(200, json={})

    def __call__(self, request: httpx.Request) -> httpx.Response:
        self.requests.append(request)
        return self.handler(request)

    async def sleep(self, seconds: float) -> None:
        self.sleeps.append(seconds)

    @property
    def last(self) -> httpx.Request:
        return self.requests[-1]

    def last_json(self):
        return json.loads(self.last.content)

    def reply(self, status: int = 200, body=None, headers: dict | None = None) -> None:
        self.handler = lambda r: httpx.Response(status, json=body, headers=headers)


@pytest.fixture
def api() -> Recorder:
    return Recorder()


@pytest.fixture
def make_server(api: Recorder):
    def factory(**settings) -> object:
        # tests exercise every tool, so enable them all unless a test narrows it
        base = {"domain": "acme.freshservice.com", "api_key": "secret", "toolsets": frozenset({"all"})}
        server = build_server(Settings(**{**base, **settings}))
        # swap the real transport for the mock one
        set_client(
            FreshserviceClient(
                Settings(**{**base, **settings}), transport=httpx.MockTransport(api), sleep=api.sleep
            )
        )
        return server

    yield factory
    set_client(None)


@pytest.fixture
def server(make_server):
    return make_server()
