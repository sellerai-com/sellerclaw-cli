from __future__ import annotations

import json

import httpx
import pytest
import respx
from typer.testing import CliRunner

from sellerclaw_cli.cli import app

pytestmark = pytest.mark.unit

runner = CliRunner()

STORE_ID = "11111111-1111-4111-8111-111111111111"

_NEGATIVE_JSON = {
    "period_start": "2026-06-29T12:00:00Z",
    "period_end": "2026-06-30T12:00:00Z",
    "score": {"score": 1234, "positive_percent": None},
    "new_negative": 1,
    "new_neutral": 0,
    "total_new": 1,
    "entries": [],
    "truncated": False,
}

_INSIGHTS_JSON = {
    "current_period_start": "2026-06-23T12:00:00Z",
    "previous_period_start": "2026-06-16T12:00:00Z",
    "period_end": "2026-06-30T12:00:00Z",
    "current": {"negative": 2, "neutral": 1, "positive": 1, "adverse": 3},
    "previous": {"negative": 1, "neutral": 0, "positive": 1, "adverse": 1},
    "negative_delta": 1,
    "neutral_delta": 1,
    "adverse_delta": 2,
    "score": {"score": 1234, "positive_percent": None},
    "dsr": [],
    "dragging_dimension": "ShippingTime",
    "entries": [],
    "truncated": False,
}


@pytest.fixture
def env_pointing_at_fake_api(
    monkeypatch: pytest.MonkeyPatch,
    fake_api_url: str,
    fake_token: str,
) -> None:
    monkeypatch.setenv("SELLERCLAW_API_URL", fake_api_url)
    monkeypatch.setenv("SELLERCLAW_TOKEN", fake_token)


@respx.mock
def test_ebay_feedback_negative_forwards_days(
    env_pointing_at_fake_api: None,  # noqa: ARG001
    fake_api_url: str,
) -> None:
    route = respx.get(f"{fake_api_url}/agent/ebay/stores/{STORE_ID}/feedback/negative").mock(
        return_value=httpx.Response(200, json=_NEGATIVE_JSON)
    )
    result = runner.invoke(app, ["ebay-feedback", "negative", STORE_ID, "--days", "7"])
    assert result.exit_code == 0, result.stderr
    assert route.calls.last.request.url.params["days"] == "7"
    payload = json.loads(result.stdout)
    assert payload["data"]["total_new"] == 1


@respx.mock
def test_ebay_feedback_negative_rejects_out_of_range_days_locally(
    env_pointing_at_fake_api: None,  # noqa: ARG001
    fake_api_url: str,
) -> None:
    route = respx.get(f"{fake_api_url}/agent/ebay/stores/{STORE_ID}/feedback/negative").mock(
        return_value=httpx.Response(200, json=_NEGATIVE_JSON)
    )
    result = runner.invoke(app, ["ebay-feedback", "negative", STORE_ID, "--days", "200"])
    assert result.exit_code != 0
    assert route.call_count == 0


@respx.mock
def test_ebay_feedback_insights_forwards_weeks(
    env_pointing_at_fake_api: None,  # noqa: ARG001
    fake_api_url: str,
) -> None:
    route = respx.get(f"{fake_api_url}/agent/ebay/stores/{STORE_ID}/feedback/insights").mock(
        return_value=httpx.Response(200, json=_INSIGHTS_JSON)
    )
    result = runner.invoke(app, ["ebay-feedback", "insights", STORE_ID, "--weeks", "2"])
    assert result.exit_code == 0, result.stderr
    assert route.calls.last.request.url.params["weeks"] == "2"


@respx.mock
def test_ebay_feedback_reply_posts_body(
    env_pointing_at_fake_api: None,  # noqa: ARG001
    fake_api_url: str,
) -> None:
    route = respx.post(f"{fake_api_url}/agent/ebay/stores/{STORE_ID}/feedback/reply").mock(
        return_value=httpx.Response(200, json={"ok": True, "feedback_id": "fb-1"})
    )
    result = runner.invoke(
        app,
        [
            "ebay-feedback",
            "reply",
            STORE_ID,
            "-b",
            json.dumps(
                {"feedback_id": "fb-1", "target_user": "buyer_a", "response_text": "Thanks!"}
            ),
        ],
    )
    assert result.exit_code == 0, result.stderr
    assert route.call_count == 1
    sent = json.loads(route.calls.last.request.content)
    assert sent["feedback_id"] == "fb-1"
    assert sent["target_user"] == "buyer_a"
    assert sent["response_text"] == "Thanks!"


@respx.mock
def test_ebay_feedback_send_reply_posts_to_send_path(
    env_pointing_at_fake_api: None,  # noqa: ARG001
    fake_api_url: str,
) -> None:
    reply_id = "22222222-2222-4222-8222-222222222222"
    route = respx.post(
        f"{fake_api_url}/agent/ebay/stores/{STORE_ID}/feedback/reply/{reply_id}/send"
    ).mock(return_value=httpx.Response(200, json={"ok": True, "reply_id": reply_id, "status": "sent"}))
    result = runner.invoke(app, ["ebay-feedback", "send-reply", STORE_ID, reply_id])
    assert result.exit_code == 0, result.stderr
    assert route.call_count == 1
    payload = json.loads(result.stdout)
    assert payload["data"]["status"] == "sent"


@respx.mock
def test_ebay_feedback_reply_rejects_missing_required_field_locally(
    env_pointing_at_fake_api: None,  # noqa: ARG001
    fake_api_url: str,
) -> None:
    route = respx.post(f"{fake_api_url}/agent/ebay/stores/{STORE_ID}/feedback/reply").mock(
        return_value=httpx.Response(200, json={"ok": True, "feedback_id": "fb-1"})
    )
    result = runner.invoke(
        app,
        [
            "ebay-feedback",
            "reply",
            STORE_ID,
            "-b",
            json.dumps({"feedback_id": "fb-1", "target_user": "buyer_a"}),  # missing response_text
        ],
    )
    assert result.exit_code != 0
    assert route.call_count == 0
