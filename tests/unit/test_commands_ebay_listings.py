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

_PERFORMANCE_JSON = {
    "window_start": "2026-06-20",
    "window_end": "2026-06-27",
    "currency": "USD",
    "last_updated": "2026-06-27T00:00:00.000Z",
    "median_conversion_rate": 1.75,
    "listings_to_improve": 1,
    "avg_completeness_pct": 0.26,
    "lost_traffic_views": 160,
    "opportunity_total": 40.0,
    "rows": [],
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
def test_performance_gets_report_and_substitutes_store_id(
    env_pointing_at_fake_api: None,  # noqa: ARG001
    fake_api_url: str,
) -> None:
    route = respx.get(
        f"{fake_api_url}/agent/ebay/stores/{STORE_ID}/listing-performance"
    ).mock(return_value=httpx.Response(200, json=_PERFORMANCE_JSON))

    result = runner.invoke(app, ["ebay-listings", "performance", STORE_ID])

    assert result.exit_code == 0, result.stderr
    assert route.call_count == 1
    # Unset flags are dropped, so the server defaults apply.
    assert "days" not in route.calls.last.request.url.params
    assert "top_n" not in route.calls.last.request.url.params
    payload = json.loads(result.stdout)
    assert payload["data"]["listings_to_improve"] == 1


@respx.mock
def test_performance_forwards_days_and_top_n_flags(
    env_pointing_at_fake_api: None,  # noqa: ARG001
    fake_api_url: str,
) -> None:
    route = respx.get(
        f"{fake_api_url}/agent/ebay/stores/{STORE_ID}/listing-performance"
    ).mock(return_value=httpx.Response(200, json=_PERFORMANCE_JSON))

    result = runner.invoke(
        app,
        ["ebay-listings", "performance", STORE_ID, "--days", "14", "--top-n", "5"],
    )

    assert result.exit_code == 0, result.stderr
    params = route.calls.last.request.url.params
    assert params["days"] == "14"
    assert params["top_n"] == "5"


@respx.mock
def test_set_policies_posts_one_policy_set_for_every_draft(
    env_pointing_at_fake_api: None,  # noqa: ARG001
    fake_api_url: str,
) -> None:
    """The whole point of the command: three policy ids, many drafts, one call."""
    route = respx.post(
        f"{fake_api_url}/agent/stores/{STORE_ID}/ebay-draft-listings/set-policies"
    ).mock(return_value=httpx.Response(200, json=_SET_POLICIES_JSON))

    result = runner.invoke(
        app,
        [
            "ebay-listings",
            "set-policies",
            STORE_ID,
            "-b",
            json.dumps(
                {
                    "listing_ids": [LISTING_ID, OTHER_LISTING_ID],
                    "fulfillment_policy_id": "6001",
                    "payment_policy_id": "6002",
                    "return_policy_id": "6003",
                }
            ),
        ],
    )

    assert result.exit_code == 0, result.stderr
    assert route.call_count == 1
    sent = json.loads(route.calls.last.request.content)
    assert sent == {
        "listing_ids": [LISTING_ID, OTHER_LISTING_ID],
        "fulfillment_policy_id": "6001",
        "payment_policy_id": "6002",
        "return_policy_id": "6003",
    }
    # The response carries fresh readiness, so the caller learns whether the drafts can publish now.
    assert json.loads(result.stdout)["data"]["results"][0]["readiness"]["ready"] is True


@respx.mock
def test_set_policies_leaves_an_unnamed_policy_out_of_the_body(
    env_pointing_at_fake_api: None,  # noqa: ARG001
    fake_api_url: str,
) -> None:
    """An omitted policy must stay omitted — sending it empty would blank it on the server."""
    route = respx.post(
        f"{fake_api_url}/agent/stores/{STORE_ID}/ebay-draft-listings/set-policies"
    ).mock(return_value=httpx.Response(200, json=_SET_POLICIES_JSON))

    result = runner.invoke(
        app,
        [
            "ebay-listings",
            "set-policies",
            STORE_ID,
            "-b",
            json.dumps({"listing_ids": [LISTING_ID], "payment_policy_id": "6002"}),
        ],
    )

    assert result.exit_code == 0, result.stderr
    sent = json.loads(route.calls.last.request.content)
    assert sent == {"listing_ids": [LISTING_ID], "payment_policy_id": "6002"}


@respx.mock
def test_set_policies_requires_listing_ids_locally(
    env_pointing_at_fake_api: None,  # noqa: ARG001
    fake_api_url: str,
) -> None:
    route = respx.post(
        f"{fake_api_url}/agent/stores/{STORE_ID}/ebay-draft-listings/set-policies"
    ).mock(return_value=httpx.Response(200, json=_SET_POLICIES_JSON))

    result = runner.invoke(
        app,
        ["ebay-listings", "set-policies", STORE_ID, "-b", json.dumps({"payment_policy_id": "6002"})],
    )

    assert result.exit_code != 0
    assert route.call_count == 0  # caught before the network call
    assert "listing_ids" in result.stderr


@respx.mock
def test_set_policies_rejects_an_etsy_policy_name_locally(
    env_pointing_at_fake_api: None,  # noqa: ARG001
    fake_api_url: str,
) -> None:
    """eBay has no shipping profile — the neighbouring group's name must not silently no-op."""
    route = respx.post(
        f"{fake_api_url}/agent/stores/{STORE_ID}/ebay-draft-listings/set-policies"
    ).mock(return_value=httpx.Response(200, json=_SET_POLICIES_JSON))

    result = runner.invoke(
        app,
        [
            "ebay-listings",
            "set-policies",
            STORE_ID,
            "-b",
            json.dumps({"listing_ids": [LISTING_ID], "shipping_profile_id": "1"}),
        ],
    )

    assert result.exit_code != 0
    assert route.call_count == 0
    assert "shipping_profile_id" in result.stderr
