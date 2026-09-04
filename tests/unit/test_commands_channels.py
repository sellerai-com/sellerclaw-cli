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
WAREHOUSE_ID = "22222222-2222-4222-8222-222222222222"

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
def test_set_markup_sends_an_explicit_null_through_to_remove_the_markup(
    env_pointing_at_fake_api: None,  # noqa: ARG001
    fake_api_url: str,
) -> None:
    """`null` is a value here, not an omission — it is how a markup set by mistake is undone.

    The local "missing required field" check used to read it as nothing sent and refuse the call,
    which left the API's own clear unreachable and `0` (a real markup, pricing at cost) as the only
    way out.
    """
    route = respx.patch(f"{fake_api_url}/agent/sales-channels/{STORE_ID}").mock(
        return_value=httpx.Response(200, json={**_CHANNEL_JSON, "markup_percent": None})
    )
    result = runner.invoke(
        app, ["channels", "set-markup", STORE_ID, "-b", json.dumps({"markup_percent": None})]
    )
    assert result.exit_code == 0, result.stderr
    sent = json.loads(route.calls.last.request.content)
    assert sent == {"markup_percent": None}


@respx.mock
def test_set_markup_still_refuses_a_body_that_names_no_markup_at_all(
    env_pointing_at_fake_api: None,  # noqa: ARG001
    fake_api_url: str,
) -> None:
    """Nullable widens what counts as an answer; it does not stop the field being required."""
    route = respx.patch(f"{fake_api_url}/agent/sales-channels/{STORE_ID}").mock(
        return_value=httpx.Response(200, json=_CHANNEL_JSON)
    )
    result = runner.invoke(app, ["channels", "set-markup", STORE_ID, "-b", json.dumps({})])
    assert result.exit_code != 0
    assert "markup_percent" in (result.stderr or "")
    assert route.call_count == 0


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
def test_set_default_warehouse_pins_the_ship_from_location(
    env_pointing_at_fake_api: None,  # noqa: ARG001
    fake_api_url: str,
) -> None:
    """Pinning the location is what stops every draft coming back with `needs_warehouses`."""
    route = respx.patch(f"{fake_api_url}/agent/sales-channels/{STORE_ID}").mock(
        return_value=httpx.Response(200, json=_CHANNEL_JSON)
    )
    result = runner.invoke(
        app,
        [
            "channels",
            "set-default-warehouse",
            STORE_ID,
            "-b",
            json.dumps({"default_warehouse_id": WAREHOUSE_ID}),
        ],
    )
    assert result.exit_code == 0, result.stderr
    assert route.call_count == 1
    # The id travels as it was given: it is SellerClaw's own, and the server — not the CLI —
    # translates it into the marketplace's location key.
    assert json.loads(route.calls.last.request.content) == {"default_warehouse_id": WAREHOUSE_ID}


@respx.mock
def test_set_default_warehouse_requires_the_field_locally(
    env_pointing_at_fake_api: None,  # noqa: ARG001
    fake_api_url: str,
) -> None:
    route = respx.patch(f"{fake_api_url}/agent/sales-channels/{STORE_ID}").mock(
        return_value=httpx.Response(200, json=_CHANNEL_JSON)
    )
    result = runner.invoke(app, ["channels", "set-default-warehouse", STORE_ID, "-b", "{}"])
    assert result.exit_code != 0
    assert route.call_count == 0  # missing required field caught before the network call


@respx.mock
def test_set_default_warehouse_rejects_the_platforms_own_field_name_locally(
    env_pointing_at_fake_api: None,  # noqa: ARG001
    fake_api_url: str,
) -> None:
    """`merchant_location_key` is the publish-path field; the pin takes SellerClaw's warehouse id."""
    route = respx.patch(f"{fake_api_url}/agent/sales-channels/{STORE_ID}").mock(
        return_value=httpx.Response(200, json=_CHANNEL_JSON)
    )
    result = runner.invoke(
        app,
        [
            "channels",
            "set-default-warehouse",
            STORE_ID,
            "-b",
            json.dumps({"merchant_location_key": "WAREHOUSE_1"}),
        ],
    )
    assert result.exit_code != 0
    assert route.call_count == 0
    assert "default_warehouse_id" in result.stderr


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


@respx.mock
def test_set_auto_purchase_sends_the_off_switch(
    env_pointing_at_fake_api: None,  # noqa: ARG001
    fake_api_url: str,
) -> None:
    """Stopping automatic CJ buying for a store is one PATCH with one field."""
    route = respx.patch(f"{fake_api_url}/agent/sales-channels/{STORE_ID}").mock(
        return_value=httpx.Response(200, json=_CHANNEL_JSON)
    )
    result = runner.invoke(
        app,
        ["channels", "set-auto-purchase", STORE_ID, "-b", json.dumps({"cj_auto_purchase": False})],
    )
    assert result.exit_code == 0, result.stderr
    assert json.loads(route.calls.last.request.content) == {"cj_auto_purchase": False}


# --------------------------------------------------------------------------
# The quantity ceiling: a whole number, and an option that can also remove it.
#
# Every body option before this one carried a string, so the option path never had to turn what the
# shell handed it into the type the field declares. A ceiling is an integer, and "40" is not one —
# the local body check refused the CLI's own option with "expected integer, got string", which no
# caller could act on because they had passed exactly what --help asked for.
# --------------------------------------------------------------------------


@respx.mock
def test_set_listing_quantity_sends_the_option_as_a_number(
    env_pointing_at_fake_api: None,  # noqa: ARG001
    fake_api_url: str,
) -> None:
    route = respx.patch(f"{fake_api_url}/agent/sales-channels/{STORE_ID}").mock(
        return_value=httpx.Response(200, json=_CHANNEL_JSON)
    )
    result = runner.invoke(app, ["channels", "set-listing-quantity", STORE_ID, "--units", "40"])
    assert result.exit_code == 0, result.stderr
    sent = json.loads(route.calls.last.request.content)
    assert sent == {"listing_quantity_cap": 40}


@respx.mock
def test_set_listing_quantity_removes_the_cap_from_the_option(
    env_pointing_at_fake_api: None,  # noqa: ARG001
    fake_api_url: str,
) -> None:
    """Removing has to be reachable the same way setting is — the help says "null removes the cap"."""
    route = respx.patch(f"{fake_api_url}/agent/sales-channels/{STORE_ID}").mock(
        return_value=httpx.Response(200, json=_CHANNEL_JSON)
    )
    result = runner.invoke(app, ["channels", "set-listing-quantity", STORE_ID, "--units", "null"])
    assert result.exit_code == 0, result.stderr
    sent = json.loads(route.calls.last.request.content)
    assert sent == {"listing_quantity_cap": None}


@respx.mock
def test_set_listing_quantity_still_takes_a_json_body(
    env_pointing_at_fake_api: None,  # noqa: ARG001
    fake_api_url: str,
) -> None:
    route = respx.patch(f"{fake_api_url}/agent/sales-channels/{STORE_ID}").mock(
        return_value=httpx.Response(200, json=_CHANNEL_JSON)
    )
    result = runner.invoke(
        app,
        ["channels", "set-listing-quantity", STORE_ID, "-b", json.dumps({"listing_quantity_cap": None})],
    )
    assert result.exit_code == 0, result.stderr
    assert json.loads(route.calls.last.request.content) == {"listing_quantity_cap": None}


@respx.mock
def test_set_listing_quantity_refuses_a_value_that_is_not_a_number(
    env_pointing_at_fake_api: None,  # noqa: ARG001
    fake_api_url: str,
) -> None:
    """And says so in terms of the option the caller typed, not the field behind it."""
    route = respx.patch(f"{fake_api_url}/agent/sales-channels/{STORE_ID}").mock(
        return_value=httpx.Response(200, json=_CHANNEL_JSON)
    )
    result = runner.invoke(app, ["channels", "set-listing-quantity", STORE_ID, "--units", "fifty"])
    assert result.exit_code != 0
    assert route.call_count == 0
    assert "--units" in result.stdout + result.stderr
