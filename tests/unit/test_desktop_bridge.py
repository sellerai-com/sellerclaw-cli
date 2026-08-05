"""The Claude Desktop bundle: manifest guards + the Node bridge driven end to end.

The bundle no longer launches the Python CLI through ``uvx`` — Claude Desktop blocks the install
outright when a manifest declares a Python runtime and the machine has none, which is exactly the
complaint this replaced. It now ships a dependency-free Node script that forwards MCP traffic to the
hosted server, so the two things worth guarding are:

* the manifest keeps declaring a *node* runtime whose entry point is actually in the bundle (a
  regression here is invisible in code review and only shows up as "extension incompatible"), and
* the bridge behaves like an MCP server for a user who has never signed in — answers the handshake,
  offers ``sellerclaw_login``, completes the browser device flow and only then exposes the hosted
  tools.

The tests below run the real ``node`` process against a fake that plays both hosted halves (the MCP
server and the Agent API), so nothing here mocks the bridge's own logic.
"""

from __future__ import annotations

import json
import os
import queue
import shutil
import subprocess
import threading
import time
from collections.abc import Callable, Iterator
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any

import pytest

from scripts.build_plugin import assemble

pytestmark = pytest.mark.unit

REPO_ROOT = Path(__file__).resolve().parents[2]
PLUGIN_SRC = REPO_ROOT / "plugin"
TARGET_DIR = PLUGIN_SRC / "targets" / "claude-desktop"
BRIDGE_JS = TARGET_DIR / "server" / "index.js"
MANIFEST: dict[str, Any] = json.loads((TARGET_DIR / "manifest.json").read_text())

NODE = shutil.which("node")
requires_node = pytest.mark.skipif(NODE is None, reason="the Desktop bridge is a Node script")

HOSTED_INSTRUCTIONS = "Hosted SellerClaw instructions."
HOSTED_TOOLS: list[dict[str, Any]] = [
    {"name": "sellerclaw_groups", "description": "groups", "inputSchema": {"type": "object"}},
    {"name": "sellerclaw_describe", "description": "describe", "inputSchema": {"type": "object"}},
    {"name": "sellerclaw_run", "description": "run", "inputSchema": {"type": "object"}},
]
VALID_TOKEN = "sca_" + "a" * 32
USER_NAME = "Test Seller"
VERIFICATION_URI = "https://app.sellerclaw.test/device"
USER_CODE = "WXYZ-1234"


# --------------------------------------------------------------------------------------------- #
# Manifest guards (no Node required)


def test_manifest_declares_a_node_runtime_and_no_python() -> None:
    server = MANIFEST["server"]

    assert server["type"] == "node"
    assert server["entry_point"] == "server/index.js"
    assert server["mcp_config"]["command"] == "node"
    assert server["mcp_config"]["args"] == ["${__dirname}/server/index.js"]
    # A declared python runtime is what made Claude Desktop refuse to install the extension on a
    # machine without Python, whatever the command actually was.
    assert "python" not in MANIFEST["compatibility"]["runtimes"]
    assert MANIFEST["compatibility"]["runtimes"]["node"]


def test_manifest_advertises_the_local_sign_in_tool() -> None:
    # Sign-in is the one capability that is not proxied, so the install screen must list it too —
    # it is what a user without a terminal uses to get authenticated at all.
    assert "sellerclaw_login" in {tool["name"] for tool in MANIFEST["tools"]}


def test_assembled_bundle_ships_the_bridge_and_no_python_launcher(tmp_path: Path) -> None:
    out = assemble("claude-desktop", PLUGIN_SRC, tmp_path / "out", version="9.9.9")

    assert (out / "server" / "index.js").is_file()
    assert json.loads((out / "manifest.json").read_text())["version"] == "9.9.9"
    assert not list(out.rglob("*.py")), "the bundle must not ship Python — that is what blocked installs"


# --------------------------------------------------------------------------------------------- #
# Fake hosted SellerClaw: the MCP server and the Agent API the bridge talks to


class FakeSellerClaw:
    """Both hosted halves on one port, with the knobs the tests need to steer the device flow."""

    def __init__(self) -> None:
        self.mcp_requests: list[dict[str, Any]] = []
        self.mcp_authorizations: list[str] = []
        self.device_codes: list[str] = []
        self.polls: dict[str, int] = {}
        # How many polls answer "authorization_pending" before the owner approves.
        self.pending_polls = 1
        # Seconds a tool call takes upstream — long enough to cancel it mid-flight.
        self.tool_call_delay = 0.0
        self.url = ""

    def issue_device_code(self) -> str:
        code = f"device-{len(self.device_codes)}"
        self.device_codes.append(code)
        return code

    def poll(self, device_code: str) -> dict[str, Any]:
        self.polls[device_code] = self.polls.get(device_code, 0) + 1
        if self.polls[device_code] > self.pending_polls:
            return {"agent_token": VALID_TOKEN}
        return {"error": "authorization_pending"}


def _handler(state: FakeSellerClaw) -> type[BaseHTTPRequestHandler]:
    class Handler(BaseHTTPRequestHandler):
        protocol_version = "HTTP/1.1"

        def log_message(self, format: str, *args: Any) -> None:  # noqa: A002 — parent's signature
            return  # the stderr access log would drown the test output

        def _send(self, status: int, payload: dict[str, Any], content_type: str = "application/json") -> None:
            if content_type == "text/event-stream":
                body = f"event: message\ndata: {json.dumps(payload)}\n\n".encode()
            else:
                body = json.dumps(payload).encode()
            self.send_response(status)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def _read_json(self) -> dict[str, Any]:
            length = int(self.headers.get("Content-Length") or 0)
            raw = self.rfile.read(length) if length else b"{}"
            try:
                parsed = json.loads(raw or b"{}")
            except json.JSONDecodeError:
                return {}
            return parsed if isinstance(parsed, dict) else {}

        def do_GET(self) -> None:  # noqa: N802 — BaseHTTPRequestHandler's naming
            if self.path == "/agent/me":
                if self.headers.get("Authorization") == f"Bearer {VALID_TOKEN}":
                    self._send(200, {"id": "u-1", "name": USER_NAME, "preferred_language": "en"})
                else:
                    self._send(401, {"detail": "Not authenticated"})
                return
            self._send(404, {"detail": "not found"})

        def do_POST(self) -> None:  # noqa: N802 — BaseHTTPRequestHandler's naming
            body = self._read_json()
            if self.path.startswith("/mcp"):
                self._handle_mcp(body)
                return
            if self.path == "/agent/auth/device/code":
                self._send(
                    200,
                    {
                        "device_code": state.issue_device_code(),
                        "user_code": USER_CODE,
                        "verification_uri": VERIFICATION_URI,
                        "expires_in": 600,
                        "interval": 1,
                    },
                )
                return
            if self.path == "/agent/auth/device/token":
                self._send(200, state.poll(str(body.get("device_code"))))
                return
            self._send(404, {"detail": "not found"})

        def _handle_mcp(self, body: dict[str, Any]) -> None:
            authorization = self.headers.get("Authorization") or ""
            state.mcp_authorizations.append(authorization)
            if authorization != f"Bearer {VALID_TOKEN}":
                self._send(401, {"error": "invalid_token"})
                return
            state.mcp_requests.append(body)
            method = body.get("method")
            request_id = body.get("id")
            if method == "initialize":
                result: dict[str, Any] = {
                    "protocolVersion": "2025-06-18",
                    "capabilities": {"tools": {"listChanged": False}, "prompts": {"listChanged": False}},
                    "serverInfo": {"name": "sellerclaw", "version": "1.2.3"},
                    "instructions": HOSTED_INSTRUCTIONS,
                }
            elif method == "tools/list":
                result = {"tools": HOSTED_TOOLS}
            elif method == "tools/call":
                if state.tool_call_delay:
                    time.sleep(state.tool_call_delay)
                result = {
                    "content": [{"type": "text", "text": json.dumps({"echo": body.get("params")})}],
                    "isError": False,
                }
            else:
                self._send(
                    200,
                    {"jsonrpc": "2.0", "id": request_id, "error": {"code": -32601, "message": "unknown"}},
                    content_type="text/event-stream",
                )
                return
            self._send(
                200,
                {"jsonrpc": "2.0", "id": request_id, "result": result},
                content_type="text/event-stream",
            )

    return Handler


@pytest.fixture
def hosted() -> Iterator[FakeSellerClaw]:
    state = FakeSellerClaw()
    server = ThreadingHTTPServer(("127.0.0.1", 0), _handler(state))
    state.url = f"http://127.0.0.1:{server.server_address[1]}"
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield state
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)


# --------------------------------------------------------------------------------------------- #
# The bridge process


class Bridge:
    """Drives the Node bridge over stdio the way an MCP client does."""

    def __init__(self, process: subprocess.Popen[str]) -> None:
        self._process = process
        self._inbox: queue.Queue[dict[str, Any]] = queue.Queue()
        self.notifications: list[dict[str, Any]] = []
        self._reader = threading.Thread(target=self._pump, daemon=True)
        self._reader.start()

    def _pump(self) -> None:
        assert self._process.stdout is not None
        for line in self._process.stdout:
            stripped = line.strip()
            if not stripped:
                continue
            try:
                self._inbox.put(json.loads(stripped))
            except json.JSONDecodeError:
                self._inbox.put({"_unparsed": stripped})

    def send_raw(self, line: str) -> None:
        assert self._process.stdin is not None
        self._process.stdin.write(f"{line}\n")
        self._process.stdin.flush()

    def next_message(self, timeout: float = 15.0) -> dict[str, Any]:
        return self._inbox.get(timeout=timeout)

    def call(self, method: str, params: dict[str, Any] | None = None, *, timeout: float = 15.0) -> dict[str, Any]:
        """Send one request and return its response, stashing any notification that arrives first."""
        request_id = id(params) % 100_000 or 1
        self.send_raw(json.dumps({"jsonrpc": "2.0", "id": request_id, "method": method, "params": params or {}}))
        while True:
            message = self.next_message(timeout=timeout)
            if message.get("id") == request_id:
                return message
            self.notifications.append(message)

    def close(self) -> None:
        if self._process.stdin is not None:
            self._process.stdin.close()
        try:
            self._process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            self._process.kill()


@pytest.fixture
def start_bridge(
    hosted: FakeSellerClaw, tmp_path: Path
) -> Iterator[Callable[..., Bridge]]:
    started: list[Bridge] = []

    def factory(token: str | None = None, **extra_env: str) -> Bridge:
        env = {
            **os.environ,
            "SELLERCLAW_MCP_URL": f"{hosted.url}/mcp",
            "SELLERCLAW_API_URL": hosted.url,
            # Keep sign-in state and the browser out of the developer's real session.
            "XDG_CONFIG_HOME": str(tmp_path / "config"),
            "SELLERCLAW_NO_BROWSER": "1",
            "SELLERCLAW_TOKEN": token or "",
            **extra_env,
        }
        process = subprocess.Popen(
            [str(NODE), str(BRIDGE_JS)],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            text=True,
            bufsize=1,
            env=env,
        )
        bridge = Bridge(process)
        started.append(bridge)
        return bridge

    try:
        yield factory
    finally:
        for bridge in started:
            bridge.close()


def _config_token(tmp_path: Path) -> str | None:
    config = tmp_path / "config" / "sellerclaw" / "config.toml"
    if not config.is_file():
        return None
    for line in config.read_text().splitlines():
        if line.strip().startswith("token"):
            return line.split("=", 1)[1].strip().strip('"')
    return None


# --------------------------------------------------------------------------------------------- #
# Behaviour


@requires_node
def test_handshake_succeeds_without_credentials(start_bridge: Callable[..., Bridge], hosted: FakeSellerClaw) -> None:
    # The hosted server rejects an unauthenticated initialize, so a fresh install would look broken
    # if the bridge simply forwarded it. It answers locally instead and explains how to sign in.
    bridge = start_bridge()

    response = bridge.call("initialize", {"protocolVersion": "2025-06-18", "capabilities": {}})

    result = response["result"]
    assert result["protocolVersion"] == "2025-06-18"
    assert result["serverInfo"]["name"] == "sellerclaw"
    assert "sellerclaw_login" in result["instructions"]
    # listChanged must be on: the tool list grows the moment the user signs in.
    assert result["capabilities"]["tools"]["listChanged"] is True
    assert hosted.mcp_requests == []


@requires_node
def test_unauthenticated_client_is_offered_sign_in_only(start_bridge: Callable[..., Bridge]) -> None:
    bridge = start_bridge()
    bridge.call("initialize", {"protocolVersion": "2025-06-18"})

    listed = bridge.call("tools/list")

    assert [tool["name"] for tool in listed["result"]["tools"]] == ["sellerclaw_login"]

    called = bridge.call("tools/call", {"name": "sellerclaw_run", "arguments": {}})

    assert called["result"]["isError"] is True
    assert "sellerclaw_login" in called["result"]["content"][0]["text"]


@requires_node
def test_signed_in_client_gets_the_hosted_surface(
    start_bridge: Callable[..., Bridge], hosted: FakeSellerClaw
) -> None:
    bridge = start_bridge(token=VALID_TOKEN)

    handshake = bridge.call("initialize", {"protocolVersion": "2025-06-18"})
    listed = bridge.call("tools/list")

    # Instructions and tools come from the hosted server — the bundle never carries its own copy.
    assert handshake["result"]["instructions"] == HOSTED_INSTRUCTIONS
    assert handshake["result"]["capabilities"]["tools"]["listChanged"] is True
    assert [tool["name"] for tool in listed["result"]["tools"]] == [
        "sellerclaw_groups",
        "sellerclaw_describe",
        "sellerclaw_run",
        "sellerclaw_login",
    ]
    assert hosted.mcp_authorizations == [f"Bearer {VALID_TOKEN}"] * 2


@requires_node
def test_tool_call_is_forwarded_verbatim_and_its_result_returned(
    start_bridge: Callable[..., Bridge], hosted: FakeSellerClaw
) -> None:
    bridge = start_bridge(token=VALID_TOKEN)
    arguments = {"group": "orders", "command": "list", "flags": {"limit": 5}}

    response = bridge.call("tools/call", {"name": "sellerclaw_run", "arguments": arguments})

    forwarded = [r for r in hosted.mcp_requests if r.get("method") == "tools/call"]
    assert len(forwarded) == 1
    assert forwarded[0]["params"] == {"name": "sellerclaw_run", "arguments": arguments}
    echoed = json.loads(response["result"]["content"][0]["text"])
    assert echoed["echo"]["arguments"] == arguments
    assert response["result"]["isError"] is False


@requires_node
def test_rejected_token_reports_how_to_fix_it(start_bridge: Callable[..., Bridge]) -> None:
    # A token that the hosted server no longer accepts must read as "sign in again", not as a
    # transport failure the model cannot act on.
    bridge = start_bridge(token="sca_expired")

    listed = bridge.call("tools/list")
    called = bridge.call("tools/call", {"name": "sellerclaw_run", "arguments": {}})

    assert [tool["name"] for tool in listed["result"]["tools"]] == ["sellerclaw_login"]
    assert called["result"]["isError"] is True
    assert "sellerclaw_login" in called["result"]["content"][0]["text"]


@requires_node
def test_sign_in_completes_in_chat_and_unlocks_the_hosted_tools(
    start_bridge: Callable[..., Bridge], tmp_path: Path
) -> None:
    bridge = start_bridge()

    response = bridge.call("tools/call", {"name": "sellerclaw_login", "arguments": {}}, timeout=30)

    assert response["result"]["isError"] is False
    assert "Signed in" in response["result"]["content"][0]["text"]
    # Persisted where the CLI keeps it, so a later `sellerclaw auth whoami` sees the same session.
    assert _config_token(tmp_path) == VALID_TOKEN
    # The client is told to re-read the tool list, so the real tools appear without a restart.
    assert any(n.get("method") == "notifications/tools/list_changed" for n in bridge.notifications)

    listed = bridge.call("tools/list")
    assert "sellerclaw_run" in {tool["name"] for tool in listed["result"]["tools"]}


@requires_node
def test_sign_in_that_is_not_approved_yet_hands_back_the_code_and_resumes(
    start_bridge: Callable[..., Bridge], hosted: FakeSellerClaw
) -> None:
    hosted.pending_polls = 99  # nobody approves during the first call
    bridge = start_bridge(SELLERCLAW_LOGIN_POLL_MS="1200")

    first = bridge.call("tools/call", {"name": "sellerclaw_login", "arguments": {}}, timeout=30)

    text = first["result"]["content"][0]["text"]
    assert VERIFICATION_URI in text
    assert USER_CODE in text
    assert first["result"]["isError"] is False

    hosted.pending_polls = 0  # the owner approves, then the model calls the tool again
    second = bridge.call("tools/call", {"name": "sellerclaw_login", "arguments": {}}, timeout=30)

    assert "Signed in" in second["result"]["content"][0]["text"]
    # One code for the whole flow: re-issuing would invalidate the one the user is looking at.
    assert len(hosted.device_codes) == 1


@requires_node
def test_sign_in_says_so_when_already_authenticated(start_bridge: Callable[..., Bridge]) -> None:
    bridge = start_bridge(token=VALID_TOKEN)

    response = bridge.call("tools/call", {"name": "sellerclaw_login", "arguments": {}})

    assert USER_NAME in response["result"]["content"][0]["text"]
    assert response["result"]["isError"] is False


@requires_node
def test_unreachable_hosted_server_is_reported_not_crashed(start_bridge: Callable[..., Bridge]) -> None:
    # Port 9 (discard) refuses connections — the bridge must survive and say what went wrong.
    bridge = start_bridge(token=VALID_TOKEN, SELLERCLAW_MCP_URL="http://127.0.0.1:9/mcp")

    handshake = bridge.call("initialize", {"protocolVersion": "2025-06-18"}, timeout=30)
    called = bridge.call("tools/call", {"name": "sellerclaw_run", "arguments": {}}, timeout=30)

    assert handshake["result"]["serverInfo"]["name"] == "sellerclaw"  # local fallback answer
    assert called["result"]["isError"] is True
    assert "Could not reach" in called["result"]["content"][0]["text"]


@requires_node
def test_saved_sign_in_survives_an_unsubstituted_token_field(
    start_bridge: Callable[..., Bridge], tmp_path: Path
) -> None:
    # Claude Desktop fills SELLERCLAW_TOKEN from the extension's optional field. A host that leaves
    # the placeholder unsubstituted must not shadow the session the user already has on disk.
    config = tmp_path / "config" / "sellerclaw" / "config.toml"
    config.parent.mkdir(parents=True, exist_ok=True)
    config.write_text(f'token = "{VALID_TOKEN}"\n')
    bridge = start_bridge(token="${user_config.token}")

    listed = bridge.call("tools/list")

    assert "sellerclaw_run" in {tool["name"] for tool in listed["result"]["tools"]}


@requires_node
def test_cancelled_call_gets_no_late_response(
    start_bridge: Callable[..., Bridge], hosted: FakeSellerClaw
) -> None:
    hosted.tool_call_delay = 1.0
    bridge = start_bridge(token=VALID_TOKEN)

    bridge.send_raw(json.dumps({
        "jsonrpc": "2.0",
        "id": 4242,
        "method": "tools/call",
        "params": {"name": "sellerclaw_run", "arguments": {}},
    }))
    bridge.send_raw(json.dumps({
        "jsonrpc": "2.0",
        "method": "notifications/cancelled",
        "params": {"requestId": 4242},
    }))
    time.sleep(2.0)  # past the point where the upstream call would have answered

    # The next thing the client hears must be the answer to its *next* request: a response to a
    # request the client took back would confuse it, and an error for it even more so.
    pong = bridge.call("ping")
    assert pong.get("result") == {}
    assert all(message.get("id") != 4242 for message in bridge.notifications)


@requires_node
def test_malformed_input_line_gets_a_parse_error(start_bridge: Callable[..., Bridge]) -> None:
    bridge = start_bridge()

    bridge.send_raw("{not json")

    message = bridge.next_message()
    assert message["error"]["code"] == -32700
