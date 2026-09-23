"""Answering an ask from the chat, and changing a task the owner already gave you.

`confirm` carries the owner's answer in whichever of two shapes the caller can honestly produce.
*Pointers* — which chat, which message — when they answered inside SellerClaw: the cloud reads the
reply from storage and the caller never authors the evidence. A *quote* when the conversation
happens somewhere SellerClaw cannot read, which is every connected app and every terminal; without
it an assistant that hits a gate has nothing to offer but "go to the website", which is the friction
the connector exists to remove.

Which shape is acceptable from which caller, and whether the words really answer the action, is the
cloud's decision — it refuses both halves at once, neither, and anything short of a plain yes or no.
What these tests pin is that the CLI passes each shape through intact and invents nothing.
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
def test_confirm_carries_the_owners_words_when_the_conversation_is_elsewhere(env: str) -> None:
    """The shape a connected app or a terminal uses: their sentence, passed through untouched.

    Untouched matters — the cloud weighs these exact words against the action that would run, so a
    CLI that trimmed, rephrased or re-cased them would be editing the evidence.
    """
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
            json.dumps({"quote": "yes, publish it"}),
        ],
    )

    assert result.exit_code == 0, result.stderr
    assert json.loads(route.calls.last.request.content) == {"quote": "yes, publish it"}
    assert "approved" in result.stdout


@respx.mock
def test_confirm_leaves_the_choice_between_the_two_shapes_to_the_cloud(env: str) -> None:
    """A body carrying both is not refused locally — the CLI must not hold its own opinion here.

    The rule ("exactly one piece of evidence") lives with the judge that acts on it; duplicating it
    in the client is how the two drift apart and a legal call starts being refused on the way out.
    """
    route = respx.post(
        f"{env}/agent/goals/action-requests/{REQUEST_ID}/confirm-from-chat"
    ).mock(return_value=httpx.Response(422, json={"detail": "one call, one piece of evidence"}))
    body = {"chat_id": CHAT_ID, "message_id": MESSAGE_ID, "quote": "they said yes"}

    result = runner.invoke(
        app, ["action-requests", "confirm", REQUEST_ID, "-b", json.dumps(body)]
    )

    assert json.loads(route.calls.last.request.content) == body
    assert result.exit_code != 0
    assert "one piece of evidence" in result.stderr


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
