"""Answering an ask from the chat, and changing a task the owner already gave you.

Both commands take *pointers* — which chat, which message — and never the words themselves. The
tests below pin that: the body that leaves the machine names ids, so the cloud reads the owner's
reply from storage rather than taking the agent's account of it.
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

REQUEST_ID = "1d0a4b3e-9d0a-4f18-9f5e-1a4f6c2d1b77"
TASK_ID = "7715c2ce-af22-44ed-bc8d-67aa8fd69a80"
CHAT_ID = "0c4a4dd0-6f68-4a3a-9f9d-2b41c3b3f0a1"
MESSAGE_ID = "3a9d0b21-4e6c-4c7f-8a1e-9b2d5f4c6e30"


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


@respx.mock
def test_confirm_sends_only_the_pointers_to_the_owners_reply(env: str) -> None:
    route = respx.post(
        f"{env}/agent/goals/action-requests/{REQUEST_ID}/confirm-from-chat"
    ).mock(
        return_value=httpx.Response(
            200,
            json={
                "decision": "approved",
                "reason": "Owner said go ahead",
                "quoted": "yes, publish it",
                "request": {"id": REQUEST_ID, "status": "resolved"},
            },
        )
    )

    result = runner.invoke(
        app,
        [
            "action-requests",
            "confirm",
            REQUEST_ID,
            "-b",
            json.dumps({"chat_id": CHAT_ID, "message_id": MESSAGE_ID}),
        ],
    )

    assert result.exit_code == 0, result.stderr
    assert json.loads(route.calls.last.request.content) == {
        "chat_id": CHAT_ID,
        "message_id": MESSAGE_ID,
    }
    assert "approved" in result.stdout


@respx.mock
@pytest.mark.parametrize(
    "body",
    [
        pytest.param({"chat_id": CHAT_ID}, id="message_id_missing"),
        pytest.param({"message_id": MESSAGE_ID}, id="chat_id_missing"),
    ],
)
def test_confirm_needs_both_halves_of_the_pointer(env: str, body: dict[str, str]) -> None:
    route = respx.post(f"{env}/agent/goals/action-requests/{REQUEST_ID}/confirm-from-chat")

    result = runner.invoke(
        app, ["action-requests", "confirm", REQUEST_ID, "-b", json.dumps(body)]
    )

    assert result.exit_code != 0
    assert route.call_count == 0  # caught before the network call


@respx.mock
def test_confirm_refuses_to_carry_the_owners_words_itself(env: str) -> None:
    """Passing the quote instead of the message is exactly the shortcut this route exists to block."""
    route = respx.post(f"{env}/agent/goals/action-requests/{REQUEST_ID}/confirm-from-chat")

    result = runner.invoke(
        app,
        [
            "action-requests",
            "confirm",
            REQUEST_ID,
            "-b",
            json.dumps({"chat_id": CHAT_ID, "message_id": MESSAGE_ID, "quote": "they said yes"}),
        ],
    )

    assert result.exit_code != 0
    assert "unknown field" in result.stderr
    assert route.call_count == 0


@respx.mock
def test_amend_sends_the_change_with_the_message_behind_it(env: str) -> None:
    route = respx.post(f"{env}/agent/goals/team-tasks/{TASK_ID}/amend").mock(
        return_value=httpx.Response(
            200,
            json={
                "amendment": {"id": "1", "kind": "narrowing", "text": "eBay is out"},
                "task": {"id": TASK_ID},
                "quoted": "drop eBay",
                "reason": "Owner asked to drop it",
            },
        )
    )
    body = {
        "kind": "narrowing",
        "text": "eBay is out — publish to Shopify only",
        "chat_id": CHAT_ID,
        "message_id": MESSAGE_ID,
    }

    result = runner.invoke(app, ["team-tasks", "amend", TASK_ID, "-b", json.dumps(body)])

    assert result.exit_code == 0, result.stderr
    assert json.loads(route.calls.last.request.content) == body


@respx.mock
def test_amend_accepts_an_approval_instead_of_a_message(env: str) -> None:
    route = respx.post(f"{env}/agent/goals/team-tasks/{TASK_ID}/amend").mock(
        return_value=httpx.Response(200, json={"task": {"id": TASK_ID}})
    )
    body = {"kind": "widening", "text": "also list on Etsy", "action_request_id": REQUEST_ID}

    result = runner.invoke(app, ["team-tasks", "amend", TASK_ID, "-b", json.dumps(body)])

    assert result.exit_code == 0, result.stderr
    assert json.loads(route.calls.last.request.content) == body


@respx.mock
@pytest.mark.parametrize(
    "body",
    [
        pytest.param({"text": "eBay is out"}, id="kind_missing"),
        pytest.param({"kind": "narrowing"}, id="text_missing"),
        pytest.param(
            {"kind": "shrink", "text": "eBay is out"}, id="kind_outside_the_three_choices"
        ),
    ],
)
def test_amend_rejects_an_incomplete_change_locally(env: str, body: dict[str, str]) -> None:
    route = respx.post(f"{env}/agent/goals/team-tasks/{TASK_ID}/amend")

    result = runner.invoke(app, ["team-tasks", "amend", TASK_ID, "-b", json.dumps(body)])

    assert result.exit_code != 0
    assert route.call_count == 0
