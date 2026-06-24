"""Unit tests for the hosted HTTP MCP server: OAuth resource-server wiring + per-request auth."""

from __future__ import annotations

import asyncio
from typing import Any

import httpx
import pytest
import respx

from sellerclaw_cli.mcp_server import (
    SellerclawTokenVerifier,
    _client_for_tool,
    _request_token,
    build_http_server,
)

pytestmark = pytest.mark.unit

ISSUER = "https://api.sellerclaw.test"
RESOURCE = "https://mcp.sellerclaw.test"
API_URL = "https://api.sellerclaw.test"


def _app() -> Any:
    return build_http_server(
        issuer_url=ISSUER, resource_url=RESOURCE, api_url=API_URL
    ).streamable_http_app()


async def _request(method: str, path: str, **kwargs: Any) -> httpx.Response:
    transport = httpx.ASGITransport(app=_app())
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        return await client.request(method, path, **kwargs)


def test_build_http_server_registers_three_tools() -> None:
    server = build_http_server(issuer_url=ISSUER, resource_url=RESOURCE, api_url=API_URL)
    tools = asyncio.run(server.list_tools())
    assert {t.name for t in tools} == {"sellerclaw_groups", "sellerclaw_describe", "sellerclaw_run"}


def test_protected_resource_metadata_points_at_issuer() -> None:
    resp = asyncio.run(_request("GET", "/.well-known/oauth-protected-resource"))

    assert resp.status_code == 200
    body = resp.json()
    assert ISSUER in [s.rstrip("/") for s in body["authorization_servers"]]
    assert body["resource"].rstrip("/") == RESOURCE


def test_mcp_endpoint_challenges_unauthenticated_requests() -> None:
    resp = asyncio.run(
        _request(
            "POST",
            "/mcp",
            json={"jsonrpc": "2.0", "method": "tools/list", "id": 1},
            headers={"Accept": "application/json, text/event-stream"},
        )
    )

    assert resp.status_code == 401
    assert "www-authenticate" in {k.lower() for k in resp.headers}


@respx.mock
def test_token_verifier_accepts_token_the_agent_api_accepts() -> None:
    respx.get(f"{API_URL}/agent/me").mock(
        return_value=httpx.Response(200, json={"id": "user-1", "email": "a@b.c"})
    )
    verifier = SellerclawTokenVerifier(api_url=API_URL)

    access = asyncio.run(verifier.verify_token("sca_good"))

    assert access is not None
    assert access.token == "sca_good"
    assert access.subject == "user-1"


@respx.mock
@pytest.mark.parametrize("status", [401, 403, 500])
def test_token_verifier_rejects_token_the_agent_api_rejects(status: int) -> None:
    respx.get(f"{API_URL}/agent/me").mock(return_value=httpx.Response(status, json={"detail": "x"}))
    verifier = SellerclawTokenVerifier(api_url=API_URL)

    assert asyncio.run(verifier.verify_token("sca_bad")) is None


def test_request_token_is_none_outside_http_context() -> None:
    assert _request_token() is None


def test_client_for_tool_falls_back_to_config_token(
    monkeypatch: pytest.MonkeyPatch,
    fake_api_url: str,
    fake_token: str,
) -> None:
    # No request context (stdio) → the locally configured token is used.
    monkeypatch.setenv("SELLERCLAW_API_URL", fake_api_url)
    monkeypatch.setenv("SELLERCLAW_TOKEN", fake_token)

    client = _client_for_tool()

    assert client.base_url == fake_api_url
    assert client.token == fake_token
