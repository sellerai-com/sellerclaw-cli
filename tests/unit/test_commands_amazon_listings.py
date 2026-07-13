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
PRODUCT_ID = "33333333-3333-4333-8333-333333333333"
ASIN = "B07N4M94X4"


@pytest.fixture
def env_pointing_at_fake_api(
    monkeypatch: pytest.MonkeyPatch,
    fake_api_url: str,
    fake_token: str,
) -> None:
    monkeypatch.setenv("SELLERCLAW_API_URL", fake_api_url)
    monkeypatch.setenv("SELLERCLAW_TOKEN", fake_token)


@respx.mock
def test_find_asin_searches_the_amazon_catalog_by_keywords(
    env_pointing_at_fake_api: None,  # noqa: ARG001
    fake_api_url: str,
) -> None:
    route = respx.post(f"{fake_api_url}/agent/amazon/stores/{STORE_ID}/catalog/search").mock(
        return_value=httpx.Response(
            200,
            json={
                "items": [{"asin": ASIN, "title": "Acme Earbuds", "brand": "Acme", "image": None}],
                "needs_confirmation": True,
            },
        )
    )
    body = {"keywords": "wireless earbuds"}

    result = runner.invoke(
        app, ["amazon-listings", "find-asin", STORE_ID, "-b", json.dumps(body)]
    )

    assert result.exit_code == 0, result.stderr
    assert route.call_count == 1
    assert json.loads(route.calls.last.request.content) == body
    payload = json.loads(result.stdout)
    # A keyword hit is a candidate, not a confirmed match.
    assert payload["data"]["needs_confirmation"] is True
    assert payload["data"]["items"][0]["asin"] == ASIN


@respx.mock
def test_draft_sends_the_chosen_asin_per_sku(
    env_pointing_at_fake_api: None,  # noqa: ARG001
    fake_api_url: str,
) -> None:
    route = respx.post(f"{fake_api_url}/agent/amazon/stores/{STORE_ID}/listings/draft").mock(
        return_value=httpx.Response(200, json=[{"id": LISTING_ID, "status": "draft"}])
    )
    body = {"product_ids": [PRODUCT_ID], "asins": {"SKU-1": ASIN}}

    result = runner.invoke(app, ["amazon-listings", "draft", STORE_ID, "-b", json.dumps(body)])

    assert result.exit_code == 0, result.stderr
    sent = json.loads(route.calls.last.request.content)
    assert sent == body
    # Omitted fields let the server default apply (condition_type = new_new).
    assert "condition_type" not in sent


@respx.mock
def test_publish_submits_the_listing_ids_and_reports_the_markup(
    env_pointing_at_fake_api: None,  # noqa: ARG001
    fake_api_url: str,
) -> None:
    route = respx.post(f"{fake_api_url}/agent/amazon/stores/{STORE_ID}/listings/publish").mock(
        return_value=httpx.Response(
            200,
            json={
                "results": [{"id": LISTING_ID, "status": "draft"}],
                "pricing": {"markup": 1.15, "markup_percent": 15.0, "overridden_skus": []},
                "errors": [],
            },
        )
    )

    result = runner.invoke(
        app,
        ["amazon-listings", "publish", STORE_ID, "-b", json.dumps({"listing_ids": [LISTING_ID]})],
    )

    assert result.exit_code == 0, result.stderr
    assert json.loads(route.calls.last.request.content) == {"listing_ids": [LISTING_ID]}
    payload = json.loads(result.stdout)
    # The applied store markup must travel back with every publish.
    assert payload["data"]["pricing"]["markup_percent"] == 15.0
    # Amazon only accepted the submission — the row is not live yet.
    assert payload["data"]["results"][0]["status"] == "draft"


@respx.mock
def test_publish_status_reports_a_suppressed_offer(
    env_pointing_at_fake_api: None,  # noqa: ARG001
    fake_api_url: str,
) -> None:
    route = respx.get(
        f"{fake_api_url}/agent/amazon/stores/{STORE_ID}/listings/{LISTING_ID}/publish-status"
    ).mock(
        return_value=httpx.Response(
            200,
            json={
                "listing_id": LISTING_ID,
                "status": "published",
                "publish_state": "done",
                "asin": ASIN,
                "suppressed": True,
                "issues": [],
                "restrictions": [],
            },
        )
    )

    result = runner.invoke(app, ["amazon-listings", "publish-status", STORE_ID, LISTING_ID])

    assert result.exit_code == 0, result.stderr
    assert route.call_count == 1
    payload = json.loads(result.stdout)
    # Live but not buyable — this must not read as a plain success.
    assert payload["data"]["suppressed"] is True


@respx.mock
def test_publish_status_carries_the_seller_central_approval_link(
    env_pointing_at_fake_api: None,  # noqa: ARG001
    fake_api_url: str,
) -> None:
    respx.get(
        f"{fake_api_url}/agent/amazon/stores/{STORE_ID}/listings/{LISTING_ID}/publish-status"
    ).mock(
        return_value=httpx.Response(
            200,
            json={
                "listing_id": LISTING_ID,
                "status": "draft",
                "publish_state": "error",
                "asin": ASIN,
                "suppressed": False,
                "issues": [],
                "restrictions": [
                    {
                        "reason_code": "APPROVAL_REQUIRED",
                        "message": "You need approval to list in this brand.",
                        "approval_url": "https://sellercentral.amazon.com/approve",
                    }
                ],
            },
        )
    )

    result = runner.invoke(app, ["amazon-listings", "publish-status", STORE_ID, LISTING_ID])

    assert result.exit_code == 0, result.stderr
    payload = json.loads(result.stdout)
    restriction = payload["data"]["restrictions"][0]
    assert restriction["reason_code"] == "APPROVAL_REQUIRED"
    # Without the link the owner has nothing actionable to do.
    assert restriction["approval_url"] == "https://sellercentral.amazon.com/approve"


@respx.mock
def test_update_patches_price_and_quantity(
    env_pointing_at_fake_api: None,  # noqa: ARG001
    fake_api_url: str,
) -> None:
    route = respx.patch(
        f"{fake_api_url}/agent/amazon/stores/{STORE_ID}/listings/{LISTING_ID}"
    ).mock(return_value=httpx.Response(200, json={"id": LISTING_ID, "price": 24.5, "quantity": 3}))
    body = {"sell_price": 24.5, "quantity": 3}

    result = runner.invoke(
        app, ["amazon-listings", "update", STORE_ID, LISTING_ID, "-b", json.dumps(body)]
    )

    assert result.exit_code == 0, result.stderr
    assert json.loads(route.calls.last.request.content) == body


@respx.mock
def test_withdraw_removes_the_offer(
    env_pointing_at_fake_api: None,  # noqa: ARG001
    fake_api_url: str,
) -> None:
    route = respx.post(f"{fake_api_url}/agent/amazon/stores/{STORE_ID}/listings/withdraw").mock(
        return_value=httpx.Response(
            200, json={"results": [{"id": LISTING_ID, "status": "withdrawn"}], "errors": []}
        )
    )

    result = runner.invoke(
        app,
        ["amazon-listings", "withdraw", STORE_ID, "-b", json.dumps({"listing_ids": [LISTING_ID]})],
    )

    assert result.exit_code == 0, result.stderr
    assert json.loads(route.calls.last.request.content) == {"listing_ids": [LISTING_ID]}
