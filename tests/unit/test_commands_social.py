from __future__ import annotations

import json

import httpx
import pytest
import respx
from typer.testing import CliRunner

from sellerclaw_cli.cli import app

pytestmark = pytest.mark.unit

runner = CliRunner()

ACCOUNT_ID = "11111111-1111-4111-8111-111111111111"
CHAT_ID = "chat-42"
MESSAGE_ID = "22222222-2222-4222-8222-222222222222"


@pytest.fixture
def env_pointing_at_fake_api(
    monkeypatch: pytest.MonkeyPatch,
    fake_api_url: str,
    fake_token: str,
) -> None:
    monkeypatch.setenv("SELLERCLAW_API_URL", fake_api_url)
    monkeypatch.setenv("SELLERCLAW_TOKEN", fake_token)


@respx.mock
def test_social_accounts_lists_connected_accounts(
    env_pointing_at_fake_api: None,  # noqa: ARG001
    fake_api_url: str,
) -> None:
    route = respx.get(f"{fake_api_url}/agent/social/accounts").mock(
        return_value=httpx.Response(
            200,
            json={
                "items": [
                    {"id": ACCOUNT_ID, "channel": "instagram", "display_name": "@shop", "status": "active"}
                ],
                "monthly_price_credits": "675",
            },
        )
    )
    result = runner.invoke(app, ["social", "accounts"])
    assert result.exit_code == 0, result.stderr
    assert route.call_count == 1
    payload = json.loads(result.stdout)
    assert payload["data"]["items"][0]["channel"] == "instagram"


@respx.mock
def test_social_conversations_forwards_paging_flags(
    env_pointing_at_fake_api: None,  # noqa: ARG001
    fake_api_url: str,
) -> None:
    route = respx.get(f"{fake_api_url}/agent/social/conversations").mock(
        return_value=httpx.Response(200, json={"items": []})
    )
    result = runner.invoke(app, ["social", "conversations", "--limit", "5", "--offset", "10"])
    assert result.exit_code == 0, result.stderr
    params = route.calls.last.request.url.params
    assert params["limit"] == "5"
    assert params["offset"] == "10"


@respx.mock
def test_social_conversations_rejects_out_of_range_limit_locally(
    env_pointing_at_fake_api: None,  # noqa: ARG001
    fake_api_url: str,
) -> None:
    route = respx.get(f"{fake_api_url}/agent/social/conversations").mock(
        return_value=httpx.Response(200, json={"items": []})
    )
    result = runner.invoke(app, ["social", "conversations", "--limit", "500"])
    assert result.exit_code != 0
    assert route.call_count == 0


@respx.mock
def test_social_thread_substitutes_chat_id(
    env_pointing_at_fake_api: None,  # noqa: ARG001
    fake_api_url: str,
) -> None:
    route = respx.get(f"{fake_api_url}/agent/social/conversations/{CHAT_ID}/messages").mock(
        return_value=httpx.Response(200, json={"items": []})
    )
    result = runner.invoke(app, ["social", "thread", CHAT_ID])
    assert result.exit_code == 0, result.stderr
    assert route.call_count == 1


@respx.mock
def test_social_draft_posts_body(
    env_pointing_at_fake_api: None,  # noqa: ARG001
    fake_api_url: str,
) -> None:
    route = respx.post(f"{fake_api_url}/agent/social/drafts").mock(
        return_value=httpx.Response(200, json={"id": MESSAGE_ID, "status": "pending_approval"})
    )
    result = runner.invoke(
        app,
        [
            "social",
            "draft",
            "-b",
            json.dumps(
                {"social_account_id": ACCOUNT_ID, "chat_id": CHAT_ID, "body_text": "Yes, in stock!"}
            ),
        ],
    )
    assert result.exit_code == 0, result.stderr
    assert route.call_count == 1
    sent = json.loads(route.calls.last.request.content)
    assert sent == {"social_account_id": ACCOUNT_ID, "chat_id": CHAT_ID, "body_text": "Yes, in stock!"}


@respx.mock
def test_social_draft_rejects_missing_required_field_locally(
    env_pointing_at_fake_api: None,  # noqa: ARG001
    fake_api_url: str,
) -> None:
    route = respx.post(f"{fake_api_url}/agent/social/drafts").mock(
        return_value=httpx.Response(200, json={})
    )
    # No body_text — the CLI must reject locally before any network call.
    result = runner.invoke(
        app,
        ["social", "draft", "-b", json.dumps({"social_account_id": ACCOUNT_ID, "chat_id": CHAT_ID})],
    )
    assert result.exit_code != 0
    assert "body_text" in result.stderr
    assert route.call_count == 0


@respx.mock
def test_social_send_substitutes_message_id(
    env_pointing_at_fake_api: None,  # noqa: ARG001
    fake_api_url: str,
) -> None:
    route = respx.post(f"{fake_api_url}/agent/social/drafts/{MESSAGE_ID}/send").mock(
        return_value=httpx.Response(200, json={"id": MESSAGE_ID, "status": "sent"})
    )
    result = runner.invoke(app, ["social", "send", MESSAGE_ID])
    assert result.exit_code == 0, result.stderr
    assert route.call_count == 1
    payload = json.loads(result.stdout)
    assert payload["data"]["status"] == "sent"
