"""Thin async HTTP client for the Freshservice REST API v2.

All tools go through :class:`FreshserviceClient`, which owns a single pooled
``httpx.AsyncClient``, applies authentication, normalises Freshservice error
payloads into :class:`~mcp.server.fastmcp.exceptions.ToolError` (so MCP clients
receive ``isError: true`` results instead of fake "success" payloads) and
exposes Link-header pagination in a consistent shape.
"""

from __future__ import annotations

import json
import mimetypes
import os
from pathlib import Path
from typing import Any
from urllib.parse import quote, urlencode

import httpx
from mcp.server.fastmcp.exceptions import ToolError

from . import __version__
from .config import Settings

MAX_PER_PAGE = 100
MAX_ATTACHMENTS = 15
MAX_ATTACHMENT_BYTES = 40 * 1024 * 1024


class FreshserviceError(ToolError):
    """Raised when Freshservice returns a non-2xx response."""

    def __init__(self, status_code: int, method: str, path: str, body: Any, retry_after: str | None = None):
        self.status_code = status_code
        self.body = body
        self.retry_after = retry_after
        super().__init__(self._format(status_code, method, path, body, retry_after))

    @staticmethod
    def _format(status: int, method: str, path: str, body: Any, retry_after: str | None) -> str:
        parts = [f"Freshservice API returned HTTP {status} for {method} {path}"]
        if isinstance(body, dict):
            summary = body.get("description") or body.get("message") or body.get("code")
            if summary:
                parts.append(str(summary))
            for err in body.get("errors") or []:
                if isinstance(err, dict):
                    field = err.get("field") or err.get("nested_field") or "request"
                    parts.append(f"{field}: {err.get('message')} ({err.get('code')})")
        elif body:
            parts.append(str(body)[:500])
        if status == 401:
            parts.append("Check FRESHSERVICE_APIKEY.")
        elif status == 403:
            parts.append(
                "The API key's agent lacks permission for this action, or the plan doesn't include it."
            )
        elif status == 404:
            parts.append("The resource does not exist (or is in a different workspace).")
        elif status == 429:
            parts.append(f"Rate limited; retry after {retry_after or 'a short while'} seconds.")
        return " | ".join(parts)


MAX_QUERY_LENGTH = 512


def quote_query(query: str) -> str:
    """Prepare a Freshservice filter query.

    The API needs the whole query enclosed in a pair of double quotes (without them it answers 500) and
    allows at most 512 characters. String and date literals inside use single quotes. Callers may pass the
    query with or without the outer double quotes; stray inner double quotes become single quotes.
    """
    q = query.strip()
    if len(q) >= 2 and q[0] == '"' and q[-1] == '"':
        q = q[1:-1].strip()
    if not q:
        raise ToolError("query must not be empty")
    q = q.replace('"', "'")
    if len(q) > MAX_QUERY_LENGTH:
        raise ToolError(f"query is {len(q)} characters; Freshservice allows at most {MAX_QUERY_LENGTH}")
    return f'"{q}"'


def clean(payload: dict[str, Any]) -> dict[str, Any]:
    """Drop keys whose value is ``None`` (Freshservice rejects explicit nulls on many fields)."""
    return {k: v for k, v in payload.items() if v is not None}


def _params(params: dict[str, Any] | None) -> dict[str, Any] | None:
    if not params:
        return None
    out: dict[str, Any] = {}
    for key, value in params.items():
        if value is None:
            continue
        if isinstance(value, bool):
            value = "true" if value else "false"
        elif isinstance(value, (list, tuple, set)):
            if not value:
                continue
            value = ",".join(str(v) for v in value)
        out[key] = value
    return out


def check_page(page: int, per_page: int) -> None:
    if page < 1:
        raise ToolError("page must be >= 1")
    if not 1 <= per_page <= MAX_PER_PAGE:
        raise ToolError(f"per_page must be between 1 and {MAX_PER_PAGE}")


def load_attachments(paths: list[str] | str | None) -> list[tuple[str, tuple[str, bytes, str]]]:
    """Read local files into httpx multipart tuples (``attachments[]`` parts)."""
    if not paths:
        return []
    if isinstance(paths, str):
        paths = [paths]
    if len(paths) > MAX_ATTACHMENTS:
        raise ToolError(f"At most {MAX_ATTACHMENTS} attachments are allowed")
    files, total = [], 0
    for raw in paths:
        path = Path(os.path.expanduser(raw))
        if not path.is_file():
            raise ToolError(f"Attachment not found: {raw}")
        content = path.read_bytes()
        total += len(content)
        if total > MAX_ATTACHMENT_BYTES:
            raise ToolError("Attachments exceed Freshservice's 40 MB total limit")
        ctype = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
        files.append(("attachments[]", (path.name, content, ctype)))
    return files


def _form_value(value: Any) -> str:
    if isinstance(value, bool):
        return "true" if value else "false"
    return str(value)


def to_form(payload: dict[str, Any]) -> dict[str, str | list[str]]:
    """Flatten a JSON payload into multipart form fields (``cc_emails[]``, ``custom_fields[x]``)."""
    fields: dict[str, str | list[str]] = {}
    for key, value in clean(payload).items():
        if isinstance(value, (list, tuple)):
            fields[f"{key}[]"] = [_form_value(v) for v in value]
        elif isinstance(value, dict):
            for sub, sub_value in clean(value).items():
                fields[f"{key}[{sub}]"] = _form_value(sub_value)
        else:
            fields[key] = _form_value(value)
    return fields


class FreshserviceClient:
    def __init__(self, settings: Settings, transport: httpx.AsyncBaseTransport | None = None):
        self.settings = settings
        self._transport = transport
        self._http: httpx.AsyncClient | None = None

    @property
    def http(self) -> httpx.AsyncClient:
        if not self.settings.domain or not self.settings.api_key:
            raise ToolError(
                "Freshservice is not configured: set FRESHSERVICE_DOMAIN (e.g. yourcompany.freshservice.com) "
                "and FRESHSERVICE_APIKEY in the MCP server's environment."
            )
        if self._http is None or self._http.is_closed:
            self._http = httpx.AsyncClient(
                base_url=f"https://{self.settings.domain}/api/v2",
                auth=(self.settings.api_key, "X"),
                headers={"Accept": "application/json", "User-Agent": f"mcp-freshservice/{__version__}"},
                timeout=self.settings.timeout,
                transport=self._transport,
            )
        return self._http

    async def aclose(self) -> None:
        if self._http is not None:
            await self._http.aclose()
            self._http = None

    def workspace(self, workspace_id: int | None) -> int | None:
        """Explicit workspace wins; otherwise fall back to FRESHSERVICE_WORKSPACE_ID."""
        return workspace_id if workspace_id is not None else self.settings.workspace_id

    async def send(
        self,
        method: str,
        path: str,
        *,
        params: dict[str, Any] | None = None,
        json_body: Any = None,
        form: dict[str, str | list[str]] | None = None,
        files: list | None = None,
    ) -> httpx.Response:
        query = _params(params)
        if query:
            # Percent-encode as the Freshservice docs show (%20, %22, %27) rather than httpx's '+' form.
            path = f"{path}?{urlencode(query, quote_via=quote, safe='')}"
        kwargs: dict[str, Any] = {}
        if files:
            kwargs["data"] = form or {}
            kwargs["files"] = files
        elif json_body is not None:
            kwargs["json"] = json_body
        try:
            response = await self.http.request(method, path, **kwargs)
        except httpx.TimeoutException as exc:
            raise ToolError(f"Timed out calling Freshservice {method} {path}") from exc
        except httpx.HTTPError as exc:
            raise ToolError(f"Could not reach Freshservice ({self.settings.domain}): {exc}") from exc
        if response.is_error:
            try:
                body: Any = response.json()
            except (json.JSONDecodeError, ValueError):
                body = response.text
            raise FreshserviceError(
                response.status_code, method, path, body, response.headers.get("Retry-After")
            )
        return response

    async def request(self, method: str, path: str, **kwargs: Any) -> dict[str, Any]:
        response = await self.send(method, path, **kwargs)
        if response.status_code == 204 or not response.content:
            return {"success": True, "status_code": response.status_code}
        data = response.json()
        return data if isinstance(data, dict) else {"data": data}

    async def get(self, path: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
        return await self.request("GET", path, params=params)

    async def post(self, path: str, body: Any = None, **kwargs: Any) -> dict[str, Any]:
        return await self.request("POST", path, json_body=body, **kwargs)

    async def put(self, path: str, body: Any = None, **kwargs: Any) -> dict[str, Any]:
        return await self.request("PUT", path, json_body=body, **kwargs)

    async def delete(self, path: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
        return await self.request("DELETE", path, params=params)

    async def write_with_attachments(
        self, method: str, path: str, payload: dict[str, Any], attachments: list[str] | str | None
    ) -> dict[str, Any]:
        """Send JSON, or multipart/form-data when there are attachments."""
        files = load_attachments(attachments)
        if files:
            return await self.request(method, path, form=to_form(payload), files=files)
        return await self.request(method, path, json_body=clean(payload))

    async def list(
        self,
        path: str,
        key: str,
        *,
        page: int = 1,
        per_page: int | None = 30,
        params: dict[str, Any] | None = None,
        max_page: int | None = None,
    ) -> dict[str, Any]:
        """Fetch one page of a list endpoint and describe where the next page is.

        Pass ``per_page=None`` for endpoints with a fixed page size (the ``filter`` family: 30 per page);
        ``max_page`` is the endpoint's documented page ceiling, if any.
        """
        check_page(page, per_page or 30)
        if max_page is not None and page > max_page:
            raise ToolError(f"page must be at most {max_page} for this endpoint")
        query = {**(params or {}), "page": page}
        if per_page is not None:
            query["per_page"] = per_page
        response = await self.send("GET", path, params=query)
        body = response.json() if response.content else {}
        result: dict[str, Any] = dict(body) if isinstance(body, dict) else {key: body}
        result.setdefault(key, [])
        meta = result.get("meta") if isinstance(result.get("meta"), dict) else {}
        if "total_pages" in meta:  # search endpoints report paging in the body, not a Link header
            has_more = page < int(meta["total_pages"])
        else:
            has_more = "next" in response.links
        has_more = has_more and (max_page is None or page < max_page)
        result["pagination"] = {
            "page": page,
            "per_page": per_page or 30,
            "next_page": page + 1 if has_more else None,
            "has_more": has_more,
        }
        if "total_items" in meta:
            result["pagination"]["total_items"] = meta["total_items"]
        return result


_client: FreshserviceClient | None = None


def get_client() -> FreshserviceClient:
    global _client
    if _client is None:
        _client = FreshserviceClient(Settings.from_env())
    return _client


def set_client(client: FreshserviceClient | None) -> None:
    """Install a client (used by the server at start-up and by tests)."""
    global _client
    _client = client
