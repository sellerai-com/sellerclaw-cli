from __future__ import annotations

import random
import time
from dataclasses import dataclass, field
from typing import Any

import httpx

from sellerclaw_cli._agent_id import resolve_agent_id
from sellerclaw_cli._errors import ApiError, AuthError, NetworkError, ServerError

DEFAULT_TIMEOUT_SECONDS = 30.0
RETRY_STATUS_CODES = frozenset({429, 502, 503, 504})
MAX_RETRIES = 3
_BACKOFF_CAP_SECONDS = 10.0
_BACKOFF_JITTER_MAX = 0.25


@dataclass
class Client:
    """Thin HTTP client for the SellerClaw Agent API. Shared between CLI and (future) MCP server."""

    base_url: str
    token: str | None
    timeout: float = DEFAULT_TIMEOUT_SECONDS
    _http: httpx.Client | None = field(default=None, init=False, repr=False)

    def __post_init__(self) -> None:
        headers = {"Accept": "application/json"}
        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"
        agent_id = resolve_agent_id()
        if agent_id is not None:
            headers["X-Agent-Id"] = agent_id
        self._http = httpx.Client(
            base_url=self.base_url,
            headers=headers,
            timeout=self.timeout,
        )

    @classmethod
    def from_env(cls) -> Client:
        """Build a Client from Config.load() results."""
        from sellerclaw_cli import _config

        cfg = _config.load()
        return cls(base_url=cfg.api_url, token=cfg.token)

    def request(
        self,
        method: str,
        path: str,
        *,
        params: dict[str, Any] | None = None,
        json: Any = None,
        files: dict[str, Any] | None = None,
        data: dict[str, Any] | None = None,
    ) -> Any:
        """Execute an HTTP request and return the parsed JSON body.

        Raises AuthError (401/403), ApiError (other 4xx), ServerError (5xx after retries),
        NetworkError (timeout/connection) — never raises httpx exceptions directly.

        ``files``/``data`` enable multipart uploads; pass them mutually exclusively with ``json``.
        """
        assert self._http is not None  # noqa: S101 — invariant from __post_init__
        last_transport_error: httpx.HTTPError | None = None

        for attempt in range(MAX_RETRIES):
            is_last = attempt == MAX_RETRIES - 1
            try:
                response = self._http.request(
                    method,
                    path,
                    params=params,
                    json=json,
                    files=files,
                    data=data,
                )
            except (httpx.ConnectError, httpx.TimeoutException, httpx.ReadError, httpx.WriteError) as exc:
                last_transport_error = exc
                if is_last:
                    raise NetworkError(str(exc) or exc.__class__.__name__) from exc
                time.sleep(_backoff_seconds(attempt))
                continue
            except httpx.HTTPError as exc:
                # Anything else from httpx we consider a network-ish failure, but don't retry — it's unknown.
                raise NetworkError(str(exc) or exc.__class__.__name__) from exc

            status = response.status_code

            if 200 <= status < 300:
                return _decode_body(response)

            if status in RETRY_STATUS_CODES and not is_last:
                time.sleep(_retry_delay(response, attempt))
                continue

            raise _error_for_response(response)

        # Loop exhausted only via transport errors; the `raise NetworkError` above should have fired.
        raise NetworkError(str(last_transport_error) if last_transport_error else "exhausted retries")

    def close(self) -> None:
        if self._http is not None:
            self._http.close()
            self._http = None

    def __enter__(self) -> Client:
        return self

    def __exit__(self, *_: object) -> None:
        self.close()


def _decode_body(response: httpx.Response) -> Any:
    if not response.content:
        return None
    try:
        return response.json()
    except ValueError:
        return response.text


def _error_for_response(response: httpx.Response) -> Exception:
    status = response.status_code
    message, details = _parse_error_body(response)

    if status in (401, 403):
        return AuthError(message, status=status, details=details)
    if 400 <= status < 500:
        return ApiError(message, status=status, details=details)
    if 500 <= status < 600:
        return ServerError(message, status=status, details=details)
    return ApiError(message or f"unexpected status {status}", status=status, details=details)


def _format_validation_error_item(item: object) -> str | None:
    """Format one FastAPI/Pydantic validation error object into a short human-readable line."""
    if not isinstance(item, dict):
        return None
    msg = item.get("msg")
    if not isinstance(msg, str) or not msg:
        return None
    loc = item.get("loc")
    field: str | None = None
    if isinstance(loc, (list, tuple)):
        parts = [str(part) for part in loc if part not in ("body", "query", "path", "header")]
        if parts:
            field = parts[-1]
    input_val = item.get("input")
    if field is not None:
        if input_val is not None:
            return f"{field}: {msg} (got {input_val!r})"
        return f"{field}: {msg}"
    if input_val is not None:
        return f"{msg} (got {input_val!r})"
    return msg


def _format_validation_detail(detail: list[object]) -> str:
    parts = [formatted for item in detail if (formatted := _format_validation_error_item(item))]
    return "; ".join(parts)


def _parse_error_body(response: httpx.Response) -> tuple[str, dict | None]:
    if not response.content:
        return f"HTTP {response.status_code}", None
    try:
        body = response.json()
    except ValueError:
        return response.text or f"HTTP {response.status_code}", None

    if isinstance(body, dict):
        message = body.get("message")
        if isinstance(message, str) and message:
            return message, body

        detail = body.get("detail")
        if isinstance(detail, str) and detail:
            return detail, body
        if isinstance(detail, dict):
            # FastAPI wraps a domain error's structured detail here: {"code", "message", "hint"?}.
            # Surface the human message (plus an actionable hint) instead of an opaque "HTTP 400".
            inner = detail.get("message") or detail.get("code")
            if isinstance(inner, str) and inner:
                hint = detail.get("hint")
                return (f"{inner} {hint}" if isinstance(hint, str) and hint else inner), body
        if isinstance(detail, list):
            formatted = _format_validation_detail(detail)
            if formatted:
                return formatted, body

        error = body.get("error")
        if isinstance(error, str) and error:
            return error, body

        return f"HTTP {response.status_code}", body
    return f"HTTP {response.status_code}", {"body": body}


def _retry_delay(response: httpx.Response, attempt: int) -> float:
    retry_after = response.headers.get("Retry-After")
    if retry_after is not None:
        try:
            return float(retry_after)
        except ValueError:
            pass
    return _backoff_seconds(attempt)


def _backoff_seconds(attempt: int) -> float:
    base = min(2.0**attempt, _BACKOFF_CAP_SECONDS)
    return base + random.uniform(0, _BACKOFF_JITTER_MAX)
