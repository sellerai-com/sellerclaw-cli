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

_CHANNEL_JSON = {
    "id": STORE_ID,
    "user_id": "33333333-3333-4333-8333-333333333333",
    "platform": "shopify",
    "status": "active",
    "name": "My Shop",
    "domain": "my-shop.myshopify.com",
    "specifics": {"reorder_lead_time_days": 21},
    "categories": [],
    "description": "",
    "margin": 1.15,
    "created_at": "2026-01-01T00:00:00Z",
    "updated_at": "2026-06-12T00:00:00Z",
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
def test_set_lead_time_patches_body_and_substitutes_store_id(
    env_pointing_at_fake_api: None,  # noqa: ARG001
    fake_api_url: str,
) -> None:
    route = respx.patch(f"{fake_api_url}/agent/sales-channels/{STORE_ID}").mock(
        return_value=httpx.Response(200, json=_CHANNEL_JSON)
    )
    result = runner.invoke(
        app,
        ["channels", "set-lead-time", STORE_ID, "-b", json.dumps({"reorder_lead_time_days": 21})],
    )
    assert result.exit_code == 0, result.stderr
    assert route.call_count == 1
    sent = json.loads(route.calls.last.request.content)
    assert sent == {"reorder_lead_time_days": 21}


@respx.mock
def test_set_lead_time_requires_the_field_locally(
    env_pointing_at_fake_api: None,  # noqa: ARG001
    fake_api_url: str,
) -> None:
    route = respx.patch(f"{fake_api_url}/agent/sales-channels/{STORE_ID}").mock(
        return_value=httpx.Response(200, json=_CHANNEL_JSON)
    )
    result = runner.invoke(app, ["channels", "set-lead-time", STORE_ID, "-b", "{}"])
    assert result.exit_code != 0
    assert route.call_count == 0  # missing required field caught before the network call


@respx.mock
def test_set_lead_time_rejects_unknown_field_locally(
    env_pointing_at_fake_api: None,  # noqa: ARG001
    fake_api_url: str,
) -> None:
    route = respx.patch(f"{fake_api_url}/agent/sales-channels/{STORE_ID}").mock(
        return_value=httpx.Response(200, json=_CHANNEL_JSON)
    )
    result = runner.invoke(
        app,
        ["channels", "set-lead-time", STORE_ID, "-b", json.dumps({"lead_time": 21})],
    )
    assert result.exit_code != 0
    assert route.call_count == 0  # unknown field caught locally (strict body schema)


@respx.mock
def test_set_margin_patches_body(
    env_pointing_at_fake_api: None,  # noqa: ARG001
    fake_api_url: str,
) -> None:
    route = respx.patch(f"{fake_api_url}/agent/sales-channels/{STORE_ID}").mock(
        return_value=httpx.Response(200, json=_CHANNEL_JSON)
    )
    result = runner.invoke(
        app, ["channels", "set-margin", STORE_ID, "-b", json.dumps({"margin": 1.3})]
    )
    assert result.exit_code == 0, result.stderr
    sent = json.loads(route.calls.last.request.content)
    assert sent == {"margin": 1.3}
