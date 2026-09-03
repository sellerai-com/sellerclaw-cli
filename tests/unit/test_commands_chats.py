"""Opening a chat with the owner, and reading the ones that already exist.

`chats open` is the only write in this group. The thing that makes it useful is the address it
returns: without that the agent has a chat it cannot reach, so the tests below pin that the
address survives to stdout, and that the cloud's refusal (too many threads left unanswered)
arrives as a failure rather than a chat the agent believes it opened.

`chats list` is paged because an agent asking it is nearly always after the thread it was just
in, not the archive. A real run typed `chats list --limit 5`, got "No such option", and spent two
more turns guessing its way to the history it needed.
"""

from __future__ import annotations

import json
from pathlib import Path

import httpx
import pytest
import respx
from typer.testing import CliRunner

from sellerclaw_cli.cli import app

pytestmark = pytest.mark.unit

runner = CliRunner()

CHAT_ID = "6f1b6a2c-08a2-4a2f-9a6f-2c9d5b3e1f04"


@pytest.fixture
def env(
    isolated_config_home: Path,  # noqa: ARG001 — redirects XDG so state.toml lands in tmp
    monkeypatch: pytest.MonkeyPatch,
    fake_api_url: str,
    fake_token: str,
) -> str:
    monkeypatch.setenv("SELLERCLAW_API_URL", fake_api_url)
    monkeypatch.setenv("SELLERCLAW_TOKEN", fake_token)
    return fake_api_url


def _opened_chat_response() -> httpx.Response:
    return httpx.Response(
        200,
        json={
            "chat": {
                "id": CHAT_ID,
                "user_id": "0b0a3e8a-2a26-4a4e-9f0a-1d7f2c3b4a55",
                "agent_id": "supervisor",
                "title": "Order #1234 shipping address looks wrong",
                "status": "active",
                "origin": "agent",
                "openclaw_session_key": f"agent:supervisor:sellerclaw-ui:direct:{CHAT_ID}",
                "created_at": "2026-08-28T10:00:00Z",
                "updated_at": "2026-08-28T10:00:00Z",
                "last_message_created_at": None,
                "last_user_message_created_at": None,
            },
            "outbound_address": f"sellerclaw-ui:direct:{CHAT_ID}",
        },
    )


@respx.mock
def test_open_sends_the_title_and_returns_the_address_to_write_to(env: str) -> None:
    route = respx.post(f"{env}/agent/chat/chats").mock(return_value=_opened_chat_response())

    result = runner.invoke(
        app,
        [
            "chats",
            "open",
            "-b",
            json.dumps({"title": "Order #1234 shipping address looks wrong"}),
        ],
    )

    assert result.exit_code == 0, result.stderr
    assert json.loads(route.calls.last.request.content) == {
        "title": "Order #1234 shipping address looks wrong"
    }
    # The address is what the agent passes to `message`; losing it strands the new chat.
    assert f"sellerclaw-ui:direct:{CHAT_ID}" in result.stdout


@respx.mock
def test_open_works_without_a_title(env: str) -> None:
    """A title is a nicety; refusing to open a chat without one would be worse than one
    row reading 'Untitled chat'."""
    route = respx.post(f"{env}/agent/chat/chats").mock(return_value=_opened_chat_response())

    result = runner.invoke(app, ["chats", "open"])

    assert result.exit_code == 0, result.stderr
    assert json.loads(route.calls.last.request.content or b"{}") == {}


@respx.mock
def test_open_reports_the_unanswered_chat_limit_as_a_failure(env: str) -> None:
    """At the limit the cloud refuses. The agent must see that and fold the topic into an
    existing thread, not carry on as though a chat exists."""
    respx.post(f"{env}/agent/chat/chats").mock(
        return_value=httpx.Response(
            409,
            json={
                "detail": {
                    "code": "unanswered_agent_chats_limit",
                    "message": "3 agent-opened chats are still unanswered.",
                }
            },
        )
    )

    result = runner.invoke(app, ["chats", "open", "-b", json.dumps({"title": "One more"})])

    assert result.exit_code != 0
    assert "unanswered" in (result.stdout + result.stderr).lower()


def _chats_page_response() -> httpx.Response:
    return httpx.Response(200, json={"chats": [], "total": 7})


@respx.mock
@pytest.mark.parametrize(
    ("argv", "expected_query"),
    [
        pytest.param([], {}, id="unpaged-sends-no-query"),
        pytest.param(["--limit", "5"], {"limit": "5"}, id="limit"),
        pytest.param(["--offset", "10"], {"offset": "10"}, id="offset"),
        pytest.param(
            ["--agent-id", "supervisor", "--limit", "5"],
            {"agent_id": "supervisor", "limit": "5"},
            id="limit-alongside-the-agent-filter",
        ),
    ],
)
def test_list_passes_paging_through_to_the_query(
    env: str, argv: list[str], expected_query: dict[str, str]
) -> None:
    """Each flag reaches the URL under its own name — a flag the CLI accepts and then drops is
    worse than one it rejects, because the caller believes it was applied."""
    route = respx.get(f"{env}/agent/chat/chats").mock(return_value=_chats_page_response())

    result = runner.invoke(app, ["chats", "list", *argv])

    assert result.exit_code == 0, result.stderr
    assert dict(route.calls.last.request.url.params) == expected_query


@respx.mock
@pytest.mark.parametrize(
    "argv",
    [
        pytest.param(["--limit", "0"], id="limit-below-one"),
        pytest.param(["--limit", "201"], id="limit-above-the-cap"),
        pytest.param(["--offset", "-1"], id="negative-offset"),
    ],
)
def test_list_refuses_out_of_range_paging_before_the_request(env: str, argv: list[str]) -> None:
    """Caught locally, so an out-of-range page costs no round trip and no 422 to interpret."""
    route = respx.get(f"{env}/agent/chat/chats").mock(return_value=_chats_page_response())

    result = runner.invoke(app, ["chats", "list", *argv])

    assert result.exit_code != 0
    assert not route.called
