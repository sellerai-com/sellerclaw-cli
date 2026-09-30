"""The server reports each call it served — names only — and a report never costs the caller its answer."""

from __future__ import annotations

import asyncio
import json
from collections.abc import Awaitable, Callable
from types import SimpleNamespace
from typing import Any

import httpx
import pytest
import respx
from mcp import Client
from mcp.types import Implementation

from sellerclaw_cli import mcp_usage

# Importing the CLI app registers every command group the proxy tools read.
from sellerclaw_cli.cli import app  # noqa: F401
from sellerclaw_cli.mcp_server import build_http_server, build_server

pytestmark = pytest.mark.unit


@pytest.fixture
def env_pointing_at_fake_api(
    monkeypatch: pytest.MonkeyPatch,
    fake_api_url: str,
    fake_token: str,
    isolated_config_home: Any,
) -> None:
    monkeypatch.setenv("SELLERCLAW_API_URL", fake_api_url)
    monkeypatch.setenv("SELLERCLAW_TOKEN", fake_token)


async def _reports_done() -> None:
    while mcp_usage._in_flight:
        await asyncio.gather(*list(mcp_usage._in_flight), return_exceptions=True)


def _drive(action: Callable[[Client], Awaitable[Any]], *, client_name: str = "claude-code") -> Any:
    """Talk to a freshly built stdio server in-process (through its middleware), then let reports land."""

    async def _run() -> Any:
        async with Client(
            build_server(), client_info=Implementation(name=client_name, version="1.2.3"), mode="legacy"
        ) as client:
            result = await action(client)
        await _reports_done()
        return result

    return asyncio.run(_run())


def _reports(route: respx.Route) -> list[dict[str, Any]]:
    return [json.loads(call.request.content) for call in route.calls]


@pytest.mark.usefixtures("env_pointing_at_fake_api")
@respx.mock
def test_a_command_run_is_reported_with_its_command_and_the_clients_name(fake_api_url: str, fake_token: str) -> None:
    respx.get(f"{fake_api_url}/agent/orders").mock(return_value=httpx.Response(200, json={"items": []}))
    reported = respx.post(f"{fake_api_url}/agent/mcp/calls").mock(return_value=httpx.Response(204))

    result = _drive(
        lambda c: c.call_tool(
            "sellerclaw_run",
            {"group": "orders", "command": "list", "flags": {"status": "owner-typed-filter"}},
        )
    )

    assert result.is_error is False
    [report] = _reports(reported)
    assert report.pop("duration_ms") >= 0
    assert report == {
        "kind": "tool",
        "name": "sellerclaw_run",
        "ok": True,
        "command": "orders list",
        "client_name": "claude-code",
    }
    # The owner's words in the arguments never leave: only names are reported.
    assert "owner-typed-filter" not in reported.calls[0].request.content.decode()
    assert reported.calls[0].request.headers["Authorization"] == f"Bearer {fake_token}"


@pytest.mark.parametrize(
    ("tool", "arguments", "expected"),
    [
        pytest.param(
            "sellerclaw_run",
            {"group": "no-such-group", "command": "list"},
            {"name": "sellerclaw_run", "ok": False, "command": "no-such-group list"},
            id="refused-command-is-a-failure",
        ),
        pytest.param("sellerclaw_groups", {}, {"name": "sellerclaw_groups", "ok": True}, id="discovery-tool"),
        pytest.param(
            "look up Jane Doe", {}, {"name": "unknown", "ok": False}, id="text-where-a-tool-name-goes-is-not-sent"
        ),
    ],
)
@pytest.mark.usefixtures("env_pointing_at_fake_api")
@respx.mock
def test_every_tool_call_is_reported_with_its_outcome(
    fake_api_url: str, tool: str, arguments: dict[str, Any], expected: dict[str, Any]
) -> None:
    reported = respx.post(f"{fake_api_url}/agent/mcp/calls").mock(return_value=httpx.Response(204))

    _drive(lambda c: c.call_tool(tool, arguments))

    [report] = _reports(reported)
    assert {k: v for k, v in report.items() if k in expected} == expected
    assert report["kind"] == "tool"
    assert ("command" in report) == ("command" in expected)


@pytest.mark.usefixtures("env_pointing_at_fake_api")
@respx.mock
def test_a_ready_made_command_is_reported_as_a_prompt(fake_api_url: str) -> None:
    reported = respx.post(f"{fake_api_url}/agent/mcp/calls").mock(return_value=httpx.Response(204))

    _drive(lambda c: c.get_prompt("orders"))

    [report] = _reports(reported)
    assert (report["kind"], report["name"], report["ok"]) == ("prompt", "orders", True)


@pytest.mark.usefixtures("env_pointing_at_fake_api")
@respx.mock
def test_the_clients_housekeeping_is_not_reported(fake_api_url: str) -> None:
    reported = respx.post(f"{fake_api_url}/agent/mcp/calls").mock(return_value=httpx.Response(204))

    async def _housekeeping(client: Client) -> None:
        await client.list_tools()
        await client.list_prompts()

    _drive(_housekeeping)

    assert reported.calls == []


@respx.mock
def test_without_a_token_there_is_no_account_to_report_to(
    monkeypatch: pytest.MonkeyPatch, fake_api_url: str, isolated_config_home: Any
) -> None:
    monkeypatch.setenv("SELLERCLAW_API_URL", fake_api_url)
    monkeypatch.delenv("SELLERCLAW_TOKEN", raising=False)
    reported = respx.post(f"{fake_api_url}/agent/mcp/calls").mock(return_value=httpx.Response(204))

    result = _drive(lambda c: c.call_tool("sellerclaw_groups", {}))

    assert result.is_error is False
    assert reported.calls == []


@pytest.mark.parametrize(
    "failure",
    [
        pytest.param(httpx.Response(500), id="api-error"),
        pytest.param(httpx.Response(404), id="older-api-without-the-endpoint"),
        pytest.param(httpx.ConnectError("down"), id="api-unreachable"),
    ],
)
@pytest.mark.usefixtures("env_pointing_at_fake_api")
@respx.mock
def test_a_failed_report_never_costs_the_caller_its_answer(
    fake_api_url: str, failure: httpx.Response | Exception
) -> None:
    route = respx.post(f"{fake_api_url}/agent/mcp/calls")
    if isinstance(failure, Exception):
        route.mock(side_effect=failure)
    else:
        route.mock(return_value=failure)

    result = _drive(lambda c: c.call_tool("sellerclaw_groups", {}))

    assert result.is_error is False
    assert route.called


@respx.mock
def test_the_hosted_server_reports_under_the_requests_own_bearer() -> None:
    """On the hosted server each request carries its own OAuth bearer; the report goes out with it."""
    api_url = "https://api.sellerclaw.test"
    respx.get(f"{api_url}/agent/me").mock(return_value=httpx.Response(200, json={"id": "user-1"}))
    reported = respx.post(f"{api_url}/agent/mcp/calls").mock(return_value=httpx.Response(204))
    server = build_http_server(issuer_url=api_url, resource_url="https://mcp.sellerclaw.test", api_url=api_url)
    asgi_app = server.streamable_http_app(stateless_http=True, host="0.0.0.0")  # noqa: S104
    headers = {
        "Authorization": "Bearer sca_hosted",
        "Accept": "application/json, text/event-stream",
        "Content-Type": "application/json",
        "MCP-Protocol-Version": "2025-06-18",
    }

    async def _call() -> httpx.Response:
        async with asgi_app.router.lifespan_context(asgi_app):
            transport = httpx.ASGITransport(app=asgi_app)
            async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
                response = await client.post(
                    "/mcp",
                    json={
                        "jsonrpc": "2.0",
                        "id": 1,
                        "method": "tools/call",
                        "params": {"name": "sellerclaw_groups", "arguments": {}},
                    },
                    headers=headers,
                )
            await _reports_done()
            return response

    response = asyncio.run(_call())

    assert response.status_code == 200, response.text
    [report] = _reports(reported)
    assert (report["name"], report["ok"]) == ("sellerclaw_groups", True)
    # A stateless request carries no handshake, so the client is anonymous here; the cloud names it.
    assert "client_name" not in report
    assert reported.calls[0].request.headers["Authorization"] == "Bearer sca_hosted"


@pytest.mark.parametrize(
    ("name", "arguments", "expected"),
    [
        pytest.param("sellerclaw_run", {"group": " orders ", "command": "list"}, "orders list", id="runner"),
        pytest.param("sellerclaw_run", {"group": "orders"}, "orders", id="runner-without-command"),
        pytest.param("sellerclaw_run", {"group": "x" * 200, "command": "y"}, None, id="overlong-group-is-not-a-name"),
        pytest.param("sellerclaw_run", {"group": 5, "command": None}, None, id="garbage-dropped"),
        pytest.param(
            "sellerclaw_run",
            {"group": "orders", "command": "find order for Jane Doe, 12 Main St"},
            "orders",
            id="model-text-in-command-never-sent",
        ),
        pytest.param(
            "sellerclaw_run",
            {"group": "orders for jane@example.com", "command": "list"},
            None,
            id="model-text-in-group-drops-the-command",
        ),
        pytest.param("sellerclaw_orders", {"query": "1001"}, None, id="card-tool-has-no-command"),
    ],
)
def test_command_of(name: str, arguments: Any, expected: str | None) -> None:
    assert mcp_usage.command_of(name, arguments) == expected


@pytest.mark.parametrize(
    ("ctx", "expected"),
    [
        pytest.param(
            SimpleNamespace(
                session=SimpleNamespace(
                    client_params=SimpleNamespace(client_info=SimpleNamespace(name="claude-ai"))
                ),
                params={},
            ),
            "claude-ai",
            id="from-the-handshake",
        ),
        pytest.param(
            SimpleNamespace(
                session=SimpleNamespace(client_params=None),
                params={"_meta": {"io.modelcontextprotocol/clientInfo": {"name": "cursor", "version": "1"}}},
            ),
            "cursor",
            id="from-the-request-envelope",
        ),
        pytest.param(SimpleNamespace(session=SimpleNamespace(client_params=None), params={}), None, id="anonymous"),
    ],
)
def test_client_name_of(ctx: Any, expected: str | None) -> None:
    assert mcp_usage.client_name_of(ctx) == expected
