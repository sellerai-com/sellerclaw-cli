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
LISTING_ID = "22222222-2222-4222-8222-222222222222"
OTHER_LISTING_ID = "44444444-4444-4444-8444-444444444444"

_SET_POLICIES_JSON = {
    "results": [{"id": LISTING_ID, "sku": "SKU-1", "readiness": {"ready": True, "issues": []}}],
    "errors": [],
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
def test_set_policies_posts_one_policy_set_for_every_listing(
    env_pointing_at_fake_api: None,  # noqa: ARG001
    fake_api_url: str,
) -> None:
    """The whole point of the command: one shipping profile, many drafts, one call."""
    route = respx.post(f"{fake_api_url}/agent/etsy/stores/{STORE_ID}/listings/set-policies").mock(
        return_value=httpx.Response(200, json=_SET_POLICIES_JSON)
    )

    result = runner.invoke(
        app,
        [
            "etsy-listings",
            "set-policies",
            STORE_ID,
            "-b",
            json.dumps(
                {
                    "listing_ids": [LISTING_ID, OTHER_LISTING_ID],
                    "shipping_profile_id": "123456789",
                }
            ),
        ],
    )

    assert result.exit_code == 0, result.stderr
    assert route.call_count == 1
    sent = json.loads(route.calls.last.request.content)
    assert sent == {
        "listing_ids": [LISTING_ID, OTHER_LISTING_ID],
        "shipping_profile_id": "123456789",
    }
    # The response carries fresh readiness, so the caller learns whether the drafts can publish now.
    assert json.loads(result.stdout)["data"]["results"][0]["readiness"]["ready"] is True


@respx.mock
def test_set_policies_leaves_an_unnamed_policy_out_of_the_body(
    env_pointing_at_fake_api: None,  # noqa: ARG001
    fake_api_url: str,
) -> None:
    """An omitted policy must stay omitted — sending it empty would blank it on the server."""
    route = respx.post(f"{fake_api_url}/agent/etsy/stores/{STORE_ID}/listings/set-policies").mock(
        return_value=httpx.Response(200, json=_SET_POLICIES_JSON)
    )

    result = runner.invoke(
        app,
        [
            "etsy-listings",
            "set-policies",
            STORE_ID,
            "-b",
            json.dumps({"listing_ids": [LISTING_ID], "return_policy_id": "999"}),
        ],
    )

    assert result.exit_code == 0, result.stderr
    sent = json.loads(route.calls.last.request.content)
    assert "shipping_profile_id" not in sent


@respx.mock
def test_set_policies_requires_listing_ids_locally(
    env_pointing_at_fake_api: None,  # noqa: ARG001
    fake_api_url: str,
) -> None:
    route = respx.post(f"{fake_api_url}/agent/etsy/stores/{STORE_ID}/listings/set-policies").mock(
        return_value=httpx.Response(200, json=_SET_POLICIES_JSON)
    )

    result = runner.invoke(
        app,
        ["etsy-listings", "set-policies", STORE_ID, "-b", json.dumps({"shipping_profile_id": "1"})],
    )

    assert result.exit_code != 0
    assert route.call_count == 0  # caught before the network call
    assert "listing_ids" in result.stderr


@respx.mock
def test_set_policies_rejects_an_ebay_policy_name_locally(
    env_pointing_at_fake_api: None,  # noqa: ARG001
    fake_api_url: str,
) -> None:
    """Etsy has no fulfillment policy — the neighbouring group's name must not silently no-op."""
    route = respx.post(f"{fake_api_url}/agent/etsy/stores/{STORE_ID}/listings/set-policies").mock(
        return_value=httpx.Response(200, json=_SET_POLICIES_JSON)
    )

    result = runner.invoke(
        app,
        [
            "etsy-listings",
            "set-policies",
            STORE_ID,
            "-b",
            json.dumps({"listing_ids": [LISTING_ID], "fulfillment_policy_id": "1"}),
        ],
    )

    assert result.exit_code != 0
    assert route.call_count == 0
    assert "fulfillment_policy_id" in result.stderr


@respx.mock
def test_update_sends_the_shipping_profile_to_a_draft(
    env_pointing_at_fake_api: None,  # noqa: ARG001
    fake_api_url: str,
) -> None:
    """A draft missing its profile has to be fixable one listing at a time, not only in bulk."""
    route = respx.patch(
        f"{fake_api_url}/agent/etsy/stores/{STORE_ID}/listings/{LISTING_ID}"
    ).mock(return_value=httpx.Response(200, json={"id": LISTING_ID}))

    result = runner.invoke(
        app,
        [
            "etsy-listings",
            "update",
            STORE_ID,
            LISTING_ID,
            "-b",
            json.dumps({"shipping_profile_id": "123456789"}),
        ],
    )

    assert result.exit_code == 0, result.stderr
    assert json.loads(route.calls.last.request.content) == {"shipping_profile_id": "123456789"}
