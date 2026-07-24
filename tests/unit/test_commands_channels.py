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
    "markup_percent": 15,
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
def test_set_markup_patches_body(
    env_pointing_at_fake_api: None,  # noqa: ARG001
    fake_api_url: str,
) -> None:
    route = respx.patch(f"{fake_api_url}/agent/sales-channels/{STORE_ID}").mock(
        return_value=httpx.Response(200, json=_CHANNEL_JSON)
    )
    result = runner.invoke(
        app, ["channels", "set-markup", STORE_ID, "-b", json.dumps({"markup_percent": 30})]
    )
    assert result.exit_code == 0, result.stderr
    sent = json.loads(route.calls.last.request.content)
    assert sent == {"markup_percent": 30}


@respx.mock
def test_set_default_policies_patches_the_owners_standing_answer(
    env_pointing_at_fake_api: None,  # noqa: ARG001
    fake_api_url: str,
) -> None:
    """Pinning a default is what stops the store being asked on every draft."""
    route = respx.patch(f"{fake_api_url}/agent/sales-channels/{STORE_ID}").mock(
        return_value=httpx.Response(200, json=_CHANNEL_JSON)
    )
    result = runner.invoke(
        app,
        [
            "channels",
            "set-default-policies",
            STORE_ID,
            "-b",
            json.dumps({"default_policies": {"default_shipping_profile_id": "123456789"}}),
        ],
    )
    assert result.exit_code == 0, result.stderr
    assert route.call_count == 1
    sent = json.loads(route.calls.last.request.content)
    assert sent == {"default_policies": {"default_shipping_profile_id": "123456789"}}


@respx.mock
def test_set_default_policies_requires_the_field_locally(
    env_pointing_at_fake_api: None,  # noqa: ARG001
    fake_api_url: str,
) -> None:
    route = respx.patch(f"{fake_api_url}/agent/sales-channels/{STORE_ID}").mock(
        return_value=httpx.Response(200, json=_CHANNEL_JSON)
    )
    result = runner.invoke(app, ["channels", "set-default-policies", STORE_ID, "-b", "{}"])
    assert result.exit_code != 0
    assert route.call_count == 0  # missing required field caught before the network call


@respx.mock
def test_set_default_policies_rejects_a_flattened_policy_key_locally(
    env_pointing_at_fake_api: None,  # noqa: ARG001
    fake_api_url: str,
) -> None:
    """The ids go inside `default_policies`; flattened, they would be silently ignored server-side."""
    route = respx.patch(f"{fake_api_url}/agent/sales-channels/{STORE_ID}").mock(
        return_value=httpx.Response(200, json=_CHANNEL_JSON)
    )
    result = runner.invoke(
        app,
        [
            "channels",
            "set-default-policies",
            STORE_ID,
            "-b",
            json.dumps({"default_shipping_profile_id": "123456789"}),
        ],
    )
    assert result.exit_code != 0
    assert route.call_count == 0
    assert "default_policies" in result.stderr


@respx.mock
def test_set_target_market_patches_the_override(
    env_pointing_at_fake_api: None,  # noqa: ARG001
    fake_api_url: str,
) -> None:
    route = respx.patch(f"{fake_api_url}/agent/sales-channels/{STORE_ID}").mock(
        return_value=httpx.Response(200, json=_CHANNEL_JSON)
    )
    result = runner.invoke(
        app,
        ["channels", "set-target-market", STORE_ID, "-b", json.dumps({"target_market": "GB"})],
    )
    assert result.exit_code == 0, result.stderr
    assert route.call_count == 1
    assert json.loads(route.calls.last.request.content) == {"target_market": "GB"}


@respx.mock
def test_set_target_market_accepts_empty_string_to_clear_the_override(
    env_pointing_at_fake_api: None,  # noqa: ARG001
    fake_api_url: str,
) -> None:
    """An empty string clears the override (falls back to the auto/derived market), not a no-op."""
    route = respx.patch(f"{fake_api_url}/agent/sales-channels/{STORE_ID}").mock(
        return_value=httpx.Response(200, json=_CHANNEL_JSON)
    )
    result = runner.invoke(
        app,
        ["channels", "set-target-market", STORE_ID, "-b", json.dumps({"target_market": ""})],
    )
    assert result.exit_code == 0, result.stderr
    assert json.loads(route.calls.last.request.content) == {"target_market": ""}


@respx.mock
def test_set_shipping_in_price_patches_the_boolean(
    env_pointing_at_fake_api: None,  # noqa: ARG001
    fake_api_url: str,
) -> None:
    route = respx.patch(f"{fake_api_url}/agent/sales-channels/{STORE_ID}").mock(
        return_value=httpx.Response(200, json=_CHANNEL_JSON)
    )
    result = runner.invoke(
        app,
        [
            "channels",
            "set-shipping-in-price",
            STORE_ID,
            "-b",
            json.dumps({"shipping_included_in_price": False}),
        ],
    )
    assert result.exit_code == 0, result.stderr
    assert json.loads(route.calls.last.request.content) == {"shipping_included_in_price": False}


@respx.mock
def test_set_shipping_in_price_rejects_a_non_boolean_locally(
    env_pointing_at_fake_api: None,  # noqa: ARG001
    fake_api_url: str,
) -> None:
    route = respx.patch(f"{fake_api_url}/agent/sales-channels/{STORE_ID}").mock(
        return_value=httpx.Response(200, json=_CHANNEL_JSON)
    )
    result = runner.invoke(
        app,
        [
            "channels",
            "set-shipping-in-price",
            STORE_ID,
            "-b",
            json.dumps({"shipping_included_in_price": "yes"}),
        ],
    )
    assert result.exit_code != 0
    assert route.call_count == 0  # wrong type caught before the network call
