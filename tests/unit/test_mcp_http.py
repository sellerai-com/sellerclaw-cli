"""Unit tests for the hosted HTTP MCP server: OAuth resource-server wiring + per-request auth."""

from __future__ import annotations

import asyncio
import json
from typing import Any

import httpx
import pytest
import respx

from sellerclaw_cli._client import DEFAULT_TIMEOUT_SECONDS
from sellerclaw_cli._command_group import LONG_TIMEOUT_SECONDS
from sellerclaw_cli._errors import UserInputError
from sellerclaw_cli.mcp_server import (
    _LIST_CACHE_TTL_MS,
    SellerclawTokenVerifier,
    _client_for_tool,
    _http_transport_options,
    _request_token,
    build_http_server,
    create_http_app,
)

pytestmark = pytest.mark.unit

ISSUER = "https://api.sellerclaw.test"
RESOURCE = "https://mcp.sellerclaw.test"
API_URL = "https://api.sellerclaw.test"
# The container binds every interface, and that is not incidental to the test: on a loopback bind the
# SDK turns on DNS-rebinding protection and rejects any Host it was not told about.
BIND_HOST = "0.0.0.0"  # noqa: S104


def _server() -> Any:
    return build_http_server(issuer_url=ISSUER, resource_url=RESOURCE, api_url=API_URL)


def _app(server: Any | None = None) -> Any:
    return (server or _server()).streamable_http_app(stateless_http=True, host=BIND_HOST)


async def _request(method: str, path: str, **kwargs: Any) -> httpx.Response:
    transport = httpx.ASGITransport(app=_app())
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        return await client.request(method, path, **kwargs)


async def _live_request(method: str, path: str, **kwargs: Any) -> httpx.Response:
    """Like :func:`_request`, but with the app's lifespan running.

    The streamable-HTTP transport starts its task group in the lifespan, so a request that gets past
    the auth middleware needs it; without it the manager refuses with "task group is not initialized".
    """
    app = _app()
    async with app.router.lifespan_context(app):
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
            return await client.request(method, path, **kwargs)


def _rpc_result(resp: httpx.Response) -> dict[str, Any]:
    """The JSON-RPC result, whether the transport answered as JSON or as one SSE event."""
    if resp.headers.get("content-type", "").startswith("text/event-stream"):
        for line in resp.text.splitlines():
            if line.startswith("data:"):
                return json.loads(line[len("data:") :].strip())["result"]
        raise AssertionError(f"no SSE data frame in: {resp.text!r}")
    return resp.json()["result"]


def test_build_http_server_registers_the_same_tools_as_stdio() -> None:
    """The hosted server and the local one are two constructor calls, and only this keeps them
    equal — a tool or a screen added to one and not the other is a surface that differs by how it
    was started."""
    server = build_http_server(issuer_url=ISSUER, resource_url=RESOURCE, api_url=API_URL)
    tools = asyncio.run(server.list_tools())
    assert {t.name for t in tools} == {
        "sellerclaw_guide",
        "sellerclaw_groups",
        "sellerclaw_describe",
        "sellerclaw_run",
        "sellerclaw_store_summary",
        "sellerclaw_orders",
        "sellerclaw_approval",
        "sellerclaw_approval_decide",
        "sellerclaw_attention",
        "sellerclaw_listings",
        "sellerclaw_products",
        "sellerclaw_ads",
        "sellerclaw_connections",
    }


def test_protected_resource_metadata_points_at_issuer() -> None:
    """The path matters as much as the body: the deployment's health check probes exactly this URL.

    RFC 9728 appends the resource's own path to the well-known prefix, so a ``resource_url`` that
    grew a ``/mcp`` suffix would move the document out from under the Fly health check and the
    post-deploy verify step (``deploy/*/fly-mcp.toml``, both deploy workflows) without failing a
    single unit test. This is that test.
    """
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


def test_the_transport_is_stateless() -> None:
    """Sessions in this process would pin a conversation to one machine.

    The app auto-stops when idle and comes back elsewhere, so a session held here resurfaces as a
    client whose next call is refused. In the v2 SDK the flag lives at the call site rather than on
    the constructor, and there are two call sites, so it is worth pinning.
    """
    server = _server()
    _app(server)

    assert server.session_manager.stateless is True
    assert _http_transport_options()["stateless_http"] is True


@respx.mock
@pytest.mark.parametrize(
    ("revision", "expects_cache_fields"),
    [
        pytest.param("2026-07-28", True, id="current-revision"),
        pytest.param("2025-06-18", False, id="older-revision"),
    ],
)
def test_an_authenticated_client_can_list_the_tools_over_http(
    revision: str, expects_cache_fields: bool
) -> None:
    """The whole hosted path in one test: bearer → verifier → dispatcher → tools.

    Metadata and a 401 only prove the door is locked; this proves the key works, and it is what would
    catch the transport rewiring going wrong while every in-process test still passed.

    Both revisions are exercised because over HTTP the revision comes from the ``MCP-Protocol-Version``
    header, not from the body: the older one must still get its tools (that is what the published
    plugin and the desktop bridge speak), and only the current one carries the freshness hint.
    """
    respx.get(f"{API_URL}/agent/me").mock(return_value=httpx.Response(200, json={"id": "user-1"}))

    # The current revision is stateless and so carries its envelope on every request; the older one
    # established it once in `initialize`, which stateless mode does not need and does not keep.
    params: dict[str, Any] = {}
    if expects_cache_fields:
        params["_meta"] = {
            "io.modelcontextprotocol/protocolVersion": revision,
            "io.modelcontextprotocol/clientCapabilities": {},
            "io.modelcontextprotocol/clientInfo": {"name": "probe", "version": "1.0"},
        }

    resp = asyncio.run(
        _live_request(
            "POST",
            "/mcp",
            json={"jsonrpc": "2.0", "id": 1, "method": "tools/list", "params": params},
            headers={
                "Authorization": "Bearer sca_good",
                "Accept": "application/json, text/event-stream",
                "Content-Type": "application/json",
                "MCP-Protocol-Version": revision,
                "Mcp-Method": "tools/list",
            },
        )
    )

    assert resp.status_code == 200, resp.text
    result = _rpc_result(resp)
    assert {t["name"] for t in result["tools"]} == {
        "sellerclaw_guide",
        "sellerclaw_groups",
        "sellerclaw_describe",
        "sellerclaw_run",
        "sellerclaw_store_summary",
        "sellerclaw_orders",
        "sellerclaw_approval",
        "sellerclaw_approval_decide",
        "sellerclaw_attention",
        "sellerclaw_listings",
        "sellerclaw_products",
        "sellerclaw_ads",
        "sellerclaw_connections",
    }
    if expects_cache_fields:
        assert result["ttlMs"] == _LIST_CACHE_TTL_MS
        assert result["cacheScope"] == "public"
    else:
        # Fields the revision does not know must not be invented for it.
        assert "ttlMs" not in result
        assert "cacheScope" not in result


@respx.mock
def test_the_published_plugin_path_still_works_end_to_end() -> None:
    """What the shipped plugin and the desktop extension actually do, against this server.

    They handshake with the revision they were built for and then call a tool. Both requests are sent
    to freshly built apps, which is the stateless promise in miniature: the second call knows nothing
    of the first and must still be answered. A regression here breaks every installed client at once,
    and nothing else in this suite would notice.
    """
    respx.get(f"{API_URL}/agent/me").mock(return_value=httpx.Response(200, json={"id": "user-1"}))
    headers = {
        "Authorization": "Bearer sca_good",
        "Accept": "application/json, text/event-stream",
        "Content-Type": "application/json",
        "MCP-Protocol-Version": "2025-06-18",
    }

    handshake = asyncio.run(
        _live_request(
            "POST",
            "/mcp",
            json={
                "jsonrpc": "2.0",
                "id": 1,
                "method": "initialize",
                "params": {
                    "protocolVersion": "2025-06-18",
                    "capabilities": {},
                    "clientInfo": {"name": "sellerclaw-desktop-bridge", "version": "0.4.0"},
                },
            },
            headers=headers,
        )
    )

    assert handshake.status_code == 200, handshake.text
    # The client's own revision comes back, not ours: that is what keeps it talking to us.
    assert _rpc_result(handshake)["protocolVersion"] == "2025-06-18"

    called = asyncio.run(
        _live_request(
            "POST",
            "/mcp",
            json={
                "jsonrpc": "2.0",
                "id": 2,
                "method": "tools/call",
                "params": {
                    "name": "sellerclaw_describe",
                    "arguments": {"group": "listings", "command": "bulk-publish"},
                },
            },
            headers=headers,
        )
    )

    assert called.status_code == 200, called.text
    result = _rpc_result(called)
    assert result.get("isError") is not True
    described = result["structuredContent"]
    assert described["starts_background_job"] is True
    assert described["poll_with"]["command"] == "bulk-job"
    assert described["timeout_seconds"] == DEFAULT_TIMEOUT_SECONDS


@respx.mock
def test_token_verifier_ignores_socks_proxy_env(monkeypatch: pytest.MonkeyPatch) -> None:
    """A shell SOCKS proxy must not crash token verification (httpx needs socksio for socks://)."""
    monkeypatch.setenv("ALL_PROXY", "socks://127.0.0.1:10808/")
    monkeypatch.setenv("all_proxy", "socks://127.0.0.1:10808/")
    respx.get(f"{API_URL}/agent/me").mock(
        return_value=httpx.Response(200, json={"id": "user-1"})
    )
    verifier = SellerclawTokenVerifier(api_url=API_URL)

    access = asyncio.run(verifier.verify_token("sca_good"))

    assert access is not None
    assert access.token == "sca_good"


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


def test_the_shipped_app_factory_serves_the_same_wiring(monkeypatch: pytest.MonkeyPatch) -> None:
    """``create_http_app`` is what the hosted image runs, so the env contract is worth a test.

    It reads the issuer, the resource URL and the bind address from the environment; a typo in any of
    them is a server that starts and then refuses every request.
    """
    monkeypatch.setenv("SELLERCLAW_MCP_ISSUER_URL", ISSUER)
    monkeypatch.setenv("SELLERCLAW_MCP_RESOURCE_URL", RESOURCE)
    monkeypatch.setenv("SELLERCLAW_API_URL", API_URL)
    monkeypatch.setenv("HOST", BIND_HOST)
    monkeypatch.setenv("PORT", "8080")

    async def _get() -> httpx.Response:
        transport = httpx.ASGITransport(app=create_http_app())
        async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
            return await client.get("/.well-known/oauth-protected-resource")

    resp = asyncio.run(_get())

    assert resp.status_code == 200
    assert resp.json()["resource"].rstrip("/") == RESOURCE


def test_the_app_factory_refuses_without_an_issuer(monkeypatch: pytest.MonkeyPatch) -> None:
    """A missing issuer must fail loudly at startup, not answer 401 to everyone forever."""
    monkeypatch.delenv("SELLERCLAW_MCP_ISSUER_URL", raising=False)

    with pytest.raises(UserInputError, match="SELLERCLAW_MCP_ISSUER_URL"):
        create_http_app()


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

    client = _client_for_tool(LONG_TIMEOUT_SECONDS)

    assert client.base_url == fake_api_url
    assert client.token == fake_token
    # The command's budget travels with the client, so an MCP call waits as long as the CLI would.
    assert client.timeout == LONG_TIMEOUT_SECONDS
