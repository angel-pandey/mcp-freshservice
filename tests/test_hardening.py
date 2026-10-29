"""Attachment allowlist and retry behaviour."""

from __future__ import annotations

import os

import httpx
import pytest
from mcp.server.fastmcp.exceptions import ToolError

from mcp_freshservice.client import MAX_RETRY_WAIT, load_attachments
from mcp_freshservice.config import Settings

pytestmark = pytest.mark.anyio


@pytest.fixture(params=["asyncio"])
def anyio_backend(request):
    return request.param


async def call(server, name, args=None):
    return await server.call_tool(name, args or {})


REPLY = {"ticket_id": 5, "body": "see attached"}


# --- Attachment allowlist -----------------------------------------------------------------------


def test_attachments_are_off_by_default(tmp_path):
    f = tmp_path / "a.txt"
    f.write_text("x")
    with pytest.raises(ToolError, match="FRESHSERVICE_ATTACHMENT_DIRS"):
        load_attachments([str(f)])
    assert load_attachments(None) == [] and load_attachments([]) == []  # nothing to attach is fine


def test_a_file_inside_an_allowed_folder_is_read(tmp_path):
    (tmp_path / "sub").mkdir()
    f = tmp_path / "sub" / "log.txt"
    f.write_text("hello")
    [(field, (name, content, ctype))] = load_attachments([str(f)], (tmp_path.resolve(),))
    assert (field, name, content, ctype) == ("attachments[]", "log.txt", b"hello", "text/plain")


def test_a_file_outside_the_allowed_folders_is_refused(tmp_path):
    allowed = tmp_path / "allowed"
    allowed.mkdir()
    secret = tmp_path / "secret.txt"
    secret.write_text("do not upload")
    with pytest.raises(ToolError, match="outside the folders allowed"):
        load_attachments([str(secret)], (allowed.resolve(),))


def test_dot_dot_traversal_cannot_escape(tmp_path):
    allowed = tmp_path / "allowed"
    allowed.mkdir()
    (tmp_path / "secret.txt").write_text("do not upload")
    sneaky = str(allowed / ".." / "secret.txt")
    with pytest.raises(ToolError, match="outside the folders allowed"):
        load_attachments([sneaky], (allowed.resolve(),))


def test_a_symlink_pointing_outside_cannot_escape(tmp_path):
    allowed = tmp_path / "allowed"
    allowed.mkdir()
    secret = tmp_path / "secret.txt"
    secret.write_text("do not upload")
    link = allowed / "innocent.txt"
    try:
        link.symlink_to(secret)
    except (OSError, NotImplementedError):
        pytest.skip("this account cannot create symlinks")
    with pytest.raises(ToolError, match="outside the folders allowed"):
        load_attachments([str(link)], (allowed.resolve(),))


def test_outside_paths_give_the_same_answer_whether_or_not_they_exist(tmp_path):
    allowed = tmp_path / "allowed"
    allowed.mkdir()
    real = tmp_path / "real.txt"
    real.write_text("x")
    messages = set()
    for path in (real, tmp_path / "nope.txt"):
        with pytest.raises(ToolError) as exc:
            load_attachments([str(path)], (allowed.resolve(),))
        messages.add(str(exc.value).replace(str(path), "<path>"))
    assert len(messages) == 1  # no way to probe which files exist outside the allowed folders


def test_a_folder_is_not_an_attachment(tmp_path):
    with pytest.raises(ToolError, match="not found"):
        load_attachments([str(tmp_path)], (tmp_path.resolve(),))


def test_the_attachment_count_limit_still_applies(tmp_path):
    with pytest.raises(ToolError, match="At most"):
        load_attachments([str(tmp_path / f"{i}.txt") for i in range(16)], (tmp_path.resolve(),))


async def test_tools_refuse_attachments_until_a_folder_is_configured(server, api, tmp_path):
    f = tmp_path / "a.txt"
    f.write_text("x")
    with pytest.raises(ToolError, match="Attachments are disabled"):
        await call(server, "send_ticket_reply", {**REPLY, "attachments": [str(f)]})
    assert api.requests == []  # nothing was sent


async def test_tools_refuse_files_outside_the_configured_folder(make_server, api, tmp_path):
    allowed = tmp_path / "allowed"
    allowed.mkdir()
    secret = tmp_path / "secret.txt"
    secret.write_text("do not upload")
    server = make_server(attachment_dirs=(allowed.resolve(),))
    with pytest.raises(ToolError, match="outside the folders allowed"):
        await call(server, "create_ticket_note", {"ticket_id": 5, "body": "n", "attachments": [str(secret)]})
    assert api.requests == []


def test_attachment_dirs_setting_is_parsed_from_the_environment(monkeypatch, tmp_path):
    other = tmp_path / "other"
    monkeypatch.setenv("FRESHSERVICE_ATTACHMENT_DIRS", f'{tmp_path}{os.pathsep} "{other}" {os.pathsep}')
    assert Settings.from_env().attachment_dirs == (tmp_path.resolve(), other.resolve())
    monkeypatch.delenv("FRESHSERVICE_ATTACHMENT_DIRS")
    assert Settings.from_env().attachment_dirs == ()


# --- Retry on rate limits and transient errors --------------------------------------------------


def sequence(api, *responses):
    """Serve the given responses in order, then keep repeating the last one."""
    queue = list(responses)

    def handler(request: httpx.Request) -> httpx.Response:
        return queue.pop(0) if len(queue) > 1 else queue[0]

    api.handler = handler


def rate_limited(retry_after: str | None = "3") -> httpx.Response:
    headers = {"Retry-After": retry_after} if retry_after else {}
    return httpx.Response(429, json={"description": "Too many requests"}, headers=headers)


async def test_a_rate_limited_request_is_retried_after_retry_after(server, api):
    sequence(api, rate_limited("3"), httpx.Response(200, json={"agent": {"id": 1}}))
    _, structured = await call(server, "get_agent", {"agent_id": 1})
    assert structured["agent"]["id"] == 1
    assert len(api.requests) == 2 and api.sleeps == [3.0]


async def test_without_retry_after_the_wait_grows(server, api):
    sequence(api, rate_limited(None), rate_limited(None), rate_limited(None), httpx.Response(200, json={}))
    await call(server, "get_agent", {"agent_id": 1})
    assert api.sleeps == [1.0, 2.0, 4.0]


async def test_gives_up_after_max_retries_with_the_rate_limit_error(server, api):
    sequence(api, rate_limited("1"))
    with pytest.raises(ToolError, match="Rate limited"):
        await call(server, "get_agent", {"agent_id": 1})
    assert len(api.requests) == 4 and len(api.sleeps) == 3  # one try + 3 retries


async def test_a_very_long_retry_after_is_surfaced_not_slept_through(server, api):
    api.handler = lambda r: rate_limited(str(int(MAX_RETRY_WAIT) + 40))
    with pytest.raises(ToolError, match="Rate limited"):
        await call(server, "get_agent", {"agent_id": 1})
    assert len(api.requests) == 1 and api.sleeps == []


async def test_retries_can_be_switched_off(make_server, api):
    server = make_server(max_retries=0)
    api.handler = lambda r: rate_limited("1")
    with pytest.raises(ToolError, match="Rate limited"):
        await call(server, "get_agent", {"agent_id": 1})
    assert len(api.requests) == 1 and api.sleeps == []


async def test_rate_limited_writes_are_retried_because_nothing_was_processed(server, api):
    sequence(api, rate_limited("2"), httpx.Response(201, json={"conversation": {"id": 9, "private": True}}))
    await call(server, "create_ticket_note", {"ticket_id": 5, "body": "n"})
    assert len(api.requests) == 2 and api.sleeps == [2.0]


async def test_gateway_errors_are_retried_for_reads_only(server, api):
    sequence(api, httpx.Response(503, json={}), httpx.Response(200, json={"agent": {"id": 1}}))
    await call(server, "get_agent", {"agent_id": 1})
    assert len(api.requests) == 2

    api.requests.clear()
    api.sleeps.clear()
    api.handler = lambda r: httpx.Response(503, json={"description": "unavailable"})
    with pytest.raises(ToolError, match="503"):
        await call(server, "create_ticket_note", {"ticket_id": 5, "body": "n"})
    assert len(api.requests) == 1 and api.sleeps == []  # a POST may have been processed: never resent


@pytest.mark.parametrize("status", [400, 401, 403, 404, 500])
async def test_other_errors_are_not_retried(server, api, status):
    api.handler = lambda r: httpx.Response(status, json={"description": "nope"})
    with pytest.raises(ToolError):
        await call(server, "get_agent", {"agent_id": 1})
    assert len(api.requests) == 1 and api.sleeps == []


def test_max_retries_setting_is_parsed_and_never_negative(monkeypatch):
    monkeypatch.setenv("FRESHSERVICE_MAX_RETRIES", "5")
    assert Settings.from_env().max_retries == 5
    monkeypatch.setenv("FRESHSERVICE_MAX_RETRIES", "-2")
    assert Settings.from_env().max_retries == 0
    monkeypatch.delenv("FRESHSERVICE_MAX_RETRIES")
    assert Settings.from_env().max_retries == 3
