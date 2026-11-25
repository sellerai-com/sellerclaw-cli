"""Unit tests for the hosted HTTP MCP server: OAuth resource-server wiring + per-request auth."""

from __future__ import annotations

import asyncio
import json
from typing import Any

import httpx
import pytest
import respx

from sellerclaw_cli import shortcuts
from sellerclaw_cli._client import DEFAULT_TIMEOUT_SECONDS
from sellerclaw_cli._command_group import LONG_TIMEOUT_SECONDS
from sellerclaw_cli._errors import UserInputError
from sellerclaw_cli.mcp_server import (
    _LIST_CACHE_TTL_MS,
    AuthCheckUnavailable,
    SellerclawTokenVerifier,
    _client_for_tool,
    _http_transport_options,
    _request_token,
    build_http_server,
    build_server,
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
        "sellerclaw_read",
        "sellerclaw_write",
        "sellerclaw_store_summary",
        "sellerclaw_orders",
        "sellerclaw_approval",
        "sellerclaw_approval_decide",
        "sellerclaw_attention",
        "sellerclaw_listings",
        "sellerclaw_products",
        "sellerclaw_ads",
        "sellerclaw_connections",
        "sellerclaw_billing",
        "sellerclaw_media",
        "sellerclaw_media_studio",
        "sellerclaw_media_set_default",
        "sellerclaw_media_upload_image",
        "sellerclaw_media_generate",
    }


def test_build_http_server_offers_the_same_ready_made_commands_as_stdio() -> None:
    """claude.ai reaches the shortcuts only through the hosted server, so it must not lose them."""
    hosted = build_http_server(issuer_url=ISSUER, resource_url=RESOURCE, api_url=API_URL)
    local = build_server()

    hosted_prompts = asyncio.run(hosted.list_prompts())
    assert [p.name for p in hosted_prompts] == list(shortcuts.names())
    assert hosted_prompts == asyncio.run(local.list_prompts())


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


@pytest.mark.parametrize(
    ("configured", "status", "body"),
    [
        pytest.param("tok_abc-123", 200, "tok_abc-123", id="configured"),
        pytest.param("  tok_abc-123\n", 200, "tok_abc-123", id="surrounding-whitespace-dropped"),
        pytest.param("", 404, None, id="empty"),
        pytest.param(None, 404, None, id="unset"),
    ],
)
def test_openai_domain_check_reads_the_token_from_the_environment(
    monkeypatch: pytest.MonkeyPatch, configured: str | None, status: int, body: str | None
) -> None:
    """OpenAI's plugin dashboard fetches this path without a token and compares the body as is."""
    monkeypatch.setenv("SELLERCLAW_MCP_ISSUER_URL", ISSUER)
    monkeypatch.setenv("SELLERCLAW_MCP_RESOURCE_URL", RESOURCE)
    monkeypatch.setenv("HOST", BIND_HOST)
    if configured is None:
        monkeypatch.delenv("SELLERCLAW_MCP_OPENAI_APPS_CHALLENGE", raising=False)
    else:
        monkeypatch.setenv("SELLERCLAW_MCP_OPENAI_APPS_CHALLENGE", configured)

    async def _get() -> httpx.Response:
        transport = httpx.ASGITransport(app=create_http_app())
        async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
            return await client.get("/.well-known/openai-apps-challenge")

    resp = asyncio.run(_get())

    assert resp.status_code == status
    if body is not None:
        assert resp.text == body
        assert resp.headers["content-type"].startswith("text/plain")


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
        "sellerclaw_read",
        "sellerclaw_write",
        "sellerclaw_store_summary",
        "sellerclaw_orders",
        "sellerclaw_approval",
        "sellerclaw_approval_decide",
        "sellerclaw_attention",
        "sellerclaw_listings",
        "sellerclaw_products",
        "sellerclaw_ads",
        "sellerclaw_connections",
        "sellerclaw_billing",
        "sellerclaw_media",
        "sellerclaw_media_studio",
        "sellerclaw_media_set_default",
        "sellerclaw_media_upload_image",
        "sellerclaw_media_generate",
    }
    if expects_cache_fields:
        assert result["ttlMs"] == _LIST_CACHE_TTL_MS
        assert result["cacheScope"] == "public"
    else:
        # Fields the revision does not know must not be invented for it.
        assert "ttlMs" not in result
        assert "cacheScope" not in result


_CARD_BUTTONS = {
    "sellerclaw_approval_decide",
    "sellerclaw_media_set_default",
    "sellerclaw_media_upload_image",
    "sellerclaw_media_generate",
}


@respx.mock
@pytest.mark.parametrize(
    ("user_agent", "revision", "client_name", "buttons_listed"),
    [
        pytest.param("Cursor/1.0.0", "2025-11-25", None, False, id="cursor-terminal-agent"),
        pytest.param("Cursor/2.1.50 (darwin arm64)", "2025-11-25", None, False, id="cursor-editor-with-its-platform"),
        pytest.param("python-httpx/0.28.1", "2026-07-28", "Cursor", False, id="cursor-named-in-the-envelope"),
        pytest.param("python-httpx/0.28.1", "2025-11-25", None, True, id="a-client-that-gives-no-name"),
        pytest.param("openai-mcp/1.0.0", "2026-07-28", "openai-mcp", True, id="a-client-that-keeps-them-for-the-card"),
    ],
)
def test_the_hosted_server_keeps_the_cards_buttons_from_cursor(
    user_agent: str, revision: str, client_name: str | None, buttons_listed: bool
) -> None:
    """Every request reaches a fresh connection, so the handshake's name is gone by the list:
    Cursor is known by the ``User-Agent`` it sends on each request, or by the name in the envelope
    the current revision carries."""
    respx.get(f"{API_URL}/agent/me").mock(return_value=httpx.Response(200, json={"id": "user-1"}))
    params: dict[str, Any] = {}
    if revision == "2026-07-28":
        params["_meta"] = {
            "io.modelcontextprotocol/protocolVersion": revision,
            "io.modelcontextprotocol/clientCapabilities": {},
            "io.modelcontextprotocol/clientInfo": {"name": client_name, "version": "1.0"},
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
                "User-Agent": user_agent,
            },
        )
    )

    assert resp.status_code == 200, resp.text
    listed = {tool["name"] for tool in _rpc_result(resp)["tools"]}
    assert (listed & _CARD_BUTTONS == _CARD_BUTTONS) is buttons_listed
    if not buttons_listed:
        assert listed.isdisjoint(_CARD_BUTTONS)
    assert {"sellerclaw_guide", "sellerclaw_read", "sellerclaw_write", "sellerclaw_approval"} <= listed


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
@pytest.mark.parametrize("status", [401, 403, 404])
def test_token_verifier_rejects_token_the_agent_api_rejects(status: int) -> None:
    respx.get(f"{API_URL}/agent/me").mock(return_value=httpx.Response(status, json={"detail": "x"}))
    verifier = SellerclawTokenVerifier(api_url=API_URL)

    assert asyncio.run(verifier.verify_token("sca_bad")) is None


@respx.mock
@pytest.mark.parametrize(
    ("answer", "reason"),
    [
        pytest.param(httpx.ConnectTimeout("slow"), "did not answer: ConnectTimeout", id="timed-out"),
        pytest.param(httpx.ConnectError("refused"), "did not answer: ConnectError", id="unreachable"),
        pytest.param(httpx.Response(500), "answered 500", id="failed"),
        pytest.param(httpx.Response(502), "answered 502", id="bad-gateway"),
        pytest.param(httpx.Response(503), "answered 503", id="unavailable"),
        pytest.param(httpx.Response(429), "answered 429", id="busy"),
        pytest.param(httpx.Response(520), "answered 520", id="any-server-error"),
    ],
)
def test_token_verifier_does_not_judge_a_token_the_api_could_not_check(
    answer: httpx.Response | Exception, reason: str
) -> None:
    """A stalled API is not a bad token: read as one, it signed claude.ai out (staging, 19.11.2026)."""
    route = respx.get(f"{API_URL}/agent/me")
    if isinstance(answer, Exception):
        route.mock(side_effect=answer)
    else:
        route.mock(return_value=answer)
    verifier = SellerclawTokenVerifier(api_url=API_URL)

    with pytest.raises(AuthCheckUnavailable, match=reason):
        asyncio.run(verifier.verify_token("sca_good"))


@respx.mock
@pytest.mark.parametrize("path", ["/mcp", "/chatgpt/mcp"])
@pytest.mark.parametrize(
    ("api_answer", "status", "retry_after", "error"),
    [
        pytest.param(httpx.ConnectTimeout("slow"), 503, "5", "temporarily_unavailable", id="api-stalled"),
        pytest.param(httpx.Response(502), 503, "5", "temporarily_unavailable", id="api-failed"),
        pytest.param(httpx.Response(401, json={"detail": "x"}), 401, None, None, id="token-refused"),
    ],
)
def test_the_hosted_app_asks_to_retry_when_the_sign_in_could_not_be_checked(
    monkeypatch: pytest.MonkeyPatch,
    path: str,
    api_answer: httpx.Response | Exception,
    status: int,
    retry_after: str | None,
    error: str | None,
) -> None:
    """OAuth clients sign in again only on a 401; a 503 with Retry-After keeps the owner signed in."""
    monkeypatch.setenv("SELLERCLAW_MCP_ISSUER_URL", ISSUER)
    monkeypatch.setenv("SELLERCLAW_MCP_RESOURCE_URL", RESOURCE)
    monkeypatch.setenv("SELLERCLAW_API_URL", API_URL)
    monkeypatch.setenv("HOST", BIND_HOST)
    route = respx.get(f"{API_URL}/agent/me")
    if isinstance(api_answer, Exception):
        route.mock(side_effect=api_answer)
    else:
        route.mock(return_value=api_answer)

    async def _post() -> httpx.Response:
        transport = httpx.ASGITransport(app=create_http_app())
        async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
            return await client.post(
                path,
                json={"jsonrpc": "2.0", "method": "tools/list", "id": 1},
                headers={"Authorization": "Bearer sca_owner", "Accept": "application/json, text/event-stream"},
            )

    resp = asyncio.run(_post())

    assert resp.status_code == status
    assert resp.headers.get("retry-after") == retry_after
    if error is not None:
        assert resp.json()["error"] == error
    else:
        assert "www-authenticate" in {k.lower() for k in resp.headers}


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
