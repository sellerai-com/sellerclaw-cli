"""Tell SellerClaw which calls this MCP server served, so the owner's use of it can be seen at all.

An assistant never tells us what the owner asked it; the one trace that reaches us is the call itself.
Until this existed even that was invisible: a guide read, a card opened and the handshake every
client makes all looked the same from the API's side — a token check and nothing else.

So after every ``tools/call`` and ``prompts/get`` the server reports, with the caller's own token:
which tool or prompt (and, for ``sellerclaw_read``/``sellerclaw_write``, which command), whether it
worked — and when it did not, the refusal's code and HTTP status, never its message — how long it
took, and the name the client gave itself when the protocol carried one. **Never the arguments** —
they carry the owner's own words, and so does any name that is not shaped like one of ours. The cloud
decides which app it was: from the connection the token belongs to, and only failing that from the
name the client gave.

The report is sent after the answer, off the request path, and every failure of it is swallowed: a
slow or broken report must never delay or fail a tool. An API that does not know the endpoint yet
(an older deployment) answers 404, which is expected and not worth a warning.
"""

from __future__ import annotations

import asyncio
import json
import logging
import re
import time
from collections.abc import Callable, Mapping
from typing import Any, Final

import httpx

_logger = logging.getLogger(__name__)

USAGE_PATH: Final[str] = "/agent/mcp/calls"
#: A report is a nicety: give up quickly rather than hold a connection open for it.
USAGE_TIMEOUT_SECONDS: Final[float] = 5.0
#: The MCP methods that are a use of SellerClaw, and the kind each is reported as. Listing tools,
#: reading a card's document and the handshake are the client's housekeeping, not the owner's use.
RECORDED_METHODS: Final[Mapping[str, str]] = {"tools/call": "tool", "prompts/get": "prompt"}
#: The two tools that front every command — one for reads, one for changes: their reports name the
#: command too.
COMMAND_RUNNERS: Final[frozenset[str]] = frozenset({"sellerclaw_read", "sellerclaw_write"})
_CLIENT_INFO_META_KEY: Final[str] = "io.modelcontextprotocol/clientInfo"
_MAX_COMMAND_CHARS: Final[int] = 128
#: What a tool, prompt, group or command name looks like. The model writes these fields, so anything
#: else — a sentence, an address — is its text, not our name, and is never sent.
_NAME_SHAPE: Final[re.Pattern[str]] = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.:-]{0,63}$")

#: A refusal as the report carries it: ``(code, HTTP status)``, either unknown.
Failure = tuple[str | None, int | None]

#: Reports in flight. The event loop keeps only weak references to tasks, and the request's own task
#: group is torn down when the request ends — so the reports are held here until they finish.
_in_flight: set[asyncio.Task[None]] = set()


class UsageReporter:
    """Server middleware that reports each tool call and prompt it lets through.

    ``token_for_request`` answers "whose call is this": the request's OAuth bearer on the hosted
    server, the locally configured token over stdio. No token, no report — there is no account to
    file it under.
    """

    def __init__(self, *, api_url: Callable[[], str], token_for_request: Callable[[], str | None]) -> None:
        self._api_url = api_url
        self._token_for_request = token_for_request

    async def __call__(self, ctx: Any, call_next: Callable[[Any], Any]) -> Any:
        kind = RECORDED_METHODS.get(ctx.method)
        if kind is None or ctx.request_id is None:
            return await call_next(ctx)
        started = time.monotonic()
        ok = False
        failure: Failure = (None, None)
        try:
            result = await call_next(ctx)
            ok = not _is_error(result)
            if not ok:
                failure = failure_of(result)
            return result
        except Exception as exc:
            failure = (_exception_code(exc), None)
            raise
        finally:
            self._schedule(
                ctx, kind=kind, ok=ok, failure=failure, duration_ms=int((time.monotonic() - started) * 1000)
            )

    def _schedule(self, ctx: Any, *, kind: str, ok: bool, failure: Failure, duration_ms: int) -> None:
        try:
            token = self._token_for_request()
            params = ctx.params if isinstance(ctx.params, Mapping) else {}
            name = params.get("name")
            if not token or not isinstance(name, str) or not name.strip():
                return
            if not _NAME_SHAPE.match(name.strip()):
                name = "unknown"
            body: dict[str, Any] = {"kind": kind, "name": name, "ok": ok, "duration_ms": max(0, duration_ms)}
            command = command_of(name, params.get("arguments"))
            if command is not None:
                body["command"] = command
            client_name = client_name_of(ctx)
            if client_name is not None:
                body["client_name"] = client_name
            error_code, error_status = failure
            if error_code is not None:
                body["error_code"] = error_code
            if error_status is not None:
                body["error_status"] = error_status
            task = asyncio.get_running_loop().create_task(send_usage_report(self._api_url(), token, body))
        except Exception:  # a report must never cost the caller its answer
            _logger.warning("mcp_usage_report_not_scheduled", exc_info=True)
            return
        _in_flight.add(task)
        task.add_done_callback(_in_flight.discard)


#: What a failure that never produced a result is filed under: the request itself was wrong (an
#: unknown tool or prompt, arguments that do not fit), or something broke on our side.
_REQUEST_ERRORS: Final[frozenset[str]] = frozenset({"MCPError", "ValidationError", "ValueError", "KeyError"})


def failure_of(result: Any) -> Failure:
    """The code and HTTP status of a refused tool call — only when the tool answered with our error JSON.

    The command runner answers a refusal with ``{"error": {"code", "status", "details"}}`` (behind the
    SDK's "Error executing tool …:" prefix). The API's own code (``order_not_found``) says more than the
    CLI's class of error (``api_error``), so it wins when there is one. The message is never read: it
    can quote what the owner asked for. A refusal in any other shape — a card's plain sentence — has
    no code to give, and says so by giving none.
    """
    text = _first_text(result)
    start = text.find("{") if text else -1
    if text is None or start < 0:
        return None, None
    try:
        payload, _ = json.JSONDecoder().raw_decode(text[start:])
    except ValueError:
        return None, None
    error = payload.get("error") if isinstance(payload, Mapping) else None
    if not isinstance(error, Mapping):
        return None, None
    details = error.get("details")
    detail = details.get("detail") if isinstance(details, Mapping) else None
    api_code = detail.get("code") if isinstance(detail, Mapping) else None
    code = _shaped_name(api_code) or _shaped_name(error.get("code"))
    status = error.get("status")
    valid_status = status if isinstance(status, int) and not isinstance(status, bool) and 100 <= status <= 599 else None
    return code, valid_status


def _first_text(result: Any) -> str | None:
    content = result.get("content") if isinstance(result, Mapping) else getattr(result, "content", None)
    for item in content if isinstance(content, list) else []:
        text = item.get("text") if isinstance(item, Mapping) else getattr(item, "text", None)
        if isinstance(text, str):
            return text
    return None


def _exception_code(exc: BaseException) -> str:
    return "invalid_request" if type(exc).__name__ in _REQUEST_ERRORS else "internal_error"


def _is_error(result: Any) -> bool:
    """Whether a served ``tools/call`` came back as a failure (the SDK hands errors back as results)."""
    if isinstance(result, Mapping):
        return result.get("isError") is True
    return getattr(result, "is_error", False) is True


def command_of(name: str, arguments: Any) -> str | None:
    """``"<group> <command>"`` for a command runner — its names only, never its payload.

    A group that is not shaped like a name drops the whole command; a command that is not keeps the
    group alone.
    """
    if name not in COMMAND_RUNNERS or not isinstance(arguments, Mapping):
        return None
    group, command = (_shaped_name(arguments.get(key)) for key in ("group", "command"))
    if group is None:
        return None
    return (group if command is None else f"{group} {command}")[:_MAX_COMMAND_CHARS]


def _shaped_name(value: Any) -> str | None:
    text = value.strip() if isinstance(value, str) else ""
    return text if _NAME_SHAPE.match(text) else None


def client_name_of(ctx: Any) -> str | None:
    """The name the client gave itself: from the handshake, else from this request's ``_meta``.

    The hosted server answers each request on a fresh connection, so a client that introduced itself
    only at the handshake is anonymous here — the cloud names it by its connection instead.
    """
    session = getattr(ctx, "session", None)
    client_params = getattr(session, "client_params", None)
    info = getattr(client_params, "client_info", None)
    name = getattr(info, "name", None)
    if isinstance(name, str) and name.strip():
        return name
    params = ctx.params if isinstance(getattr(ctx, "params", None), Mapping) else {}
    meta = params.get("_meta")
    announced = meta.get(_CLIENT_INFO_META_KEY) if isinstance(meta, Mapping) else None
    name = announced.get("name") if isinstance(announced, Mapping) else None
    return name if isinstance(name, str) and name.strip() else None


async def send_usage_report(api_url: str, token: str, body: dict[str, Any]) -> None:
    """POST one report; log what went wrong, never raise."""
    try:
        async with httpx.AsyncClient(
            base_url=api_url, timeout=USAGE_TIMEOUT_SECONDS, trust_env=False
        ) as client:
            response = await client.post(USAGE_PATH, json=body, headers={"Authorization": f"Bearer {token}"})
    except httpx.HTTPError as exc:
        _logger.warning("mcp_usage_report_failed error=%s", type(exc).__name__)
        return
    if response.status_code == 404:
        _logger.debug("mcp_usage_report_endpoint_missing")
    elif response.status_code >= 400:
        _logger.warning("mcp_usage_report_refused status=%s", response.status_code)
