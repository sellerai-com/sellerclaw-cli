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


@pytest.fixture
def env_pointing_at_fake_api(
    monkeypatch: pytest.MonkeyPatch,
    fake_api_url: str,
    fake_token: str,
) -> None:
    monkeypatch.setenv("SELLERCLAW_API_URL", fake_api_url)
    monkeypatch.setenv("SELLERCLAW_TOKEN", fake_token)


@respx.mock
def test_categories_substitutes_store_id(
    env_pointing_at_fake_api: None,  # noqa: ARG001
    fake_api_url: str,
) -> None:
    route = respx.get(
        f"{fake_api_url}/agent/tiktok-shop/stores/{STORE_ID}/categories"
    ).mock(return_value=httpx.Response(200, json=[{"id": "600123", "is_leaf": True}]))

    result = runner.invoke(app, ["tiktok-shop-store", "categories", STORE_ID])

    assert result.exit_code == 0, result.stderr
    assert route.call_count == 1
    payload = json.loads(result.stdout)
    assert payload["data"][0]["id"] == "600123"


@respx.mock
def test_category_attributes_forwards_category_id_flag(
    env_pointing_at_fake_api: None,  # noqa: ARG001
    fake_api_url: str,
) -> None:
    route = respx.get(
        f"{fake_api_url}/agent/tiktok-shop/stores/{STORE_ID}/category-attributes"
    ).mock(return_value=httpx.Response(200, json=[{"id": "100392", "is_required": True}]))

    result = runner.invoke(
        app,
        ["tiktok-shop-store", "category-attributes", STORE_ID, "--category-id", "600123"],
    )

    assert result.exit_code == 0, result.stderr
    assert route.calls.last.request.url.params["category_id"] == "600123"


def test_category_attributes_requires_category_id(
    env_pointing_at_fake_api: None,  # noqa: ARG001
) -> None:
    # The flag is required; omitting it fails locally before any HTTP call.
    result = runner.invoke(app, ["tiktok-shop-store", "category-attributes", STORE_ID])
    assert result.exit_code != 0


@respx.mock
def test_draft_posts_product_ids_and_category(
    env_pointing_at_fake_api: None,  # noqa: ARG001
    fake_api_url: str,
) -> None:
    route = respx.post(
        f"{fake_api_url}/agent/tiktok-shop/stores/{STORE_ID}/listings/draft"
    ).mock(return_value=httpx.Response(200, json=[]))

    result = runner.invoke(
        app,
        [
            "tiktok-shop-listings",
            "draft",
            STORE_ID,
            "-b",
            json.dumps({"product_ids": ["p-1", "p-2"], "category_id": "600123"}),
        ],
    )

    assert result.exit_code == 0, result.stderr
    sent = json.loads(route.calls.last.request.content)
    assert sent == {"product_ids": ["p-1", "p-2"], "category_id": "600123"}


@respx.mock
def test_publish_posts_listing_ids(
    env_pointing_at_fake_api: None,  # noqa: ARG001
    fake_api_url: str,
) -> None:
    route = respx.post(
        f"{fake_api_url}/agent/tiktok-shop/stores/{STORE_ID}/listings/publish"
    ).mock(return_value=httpx.Response(200, json={"results": [], "errors": []}))

    result = runner.invoke(
        app,
        [
            "tiktok-shop-listings",
            "publish",
            STORE_ID,
            "-b",
            json.dumps({"listing_ids": [LISTING_ID]}),
        ],
    )

    assert result.exit_code == 0, result.stderr
    assert route.call_count == 1
    sent = json.loads(route.calls.last.request.content)
    assert sent == {"listing_ids": [LISTING_ID]}


@respx.mock
def test_orders_create_fulfillment_posts_tracking(
    env_pointing_at_fake_api: None,  # noqa: ARG001
    fake_api_url: str,
) -> None:
    order_id = "33333333-3333-4333-8333-333333333333"
    route = respx.post(
        f"{fake_api_url}/agent/stores/{STORE_ID}/orders/{order_id}/fulfillments"
    ).mock(return_value=httpx.Response(200, json={"remote_id": order_id, "status": "shipped"}))

    result = runner.invoke(
        app,
        [
            "tiktok-shop-orders",
            "create-fulfillment",
            STORE_ID,
            order_id,
            "-b",
            json.dumps({"tracking": {"number": "1Z999", "company": "USPS"}}),
        ],
    )

    assert result.exit_code == 0, result.stderr
    sent = json.loads(route.calls.last.request.content)
    assert sent == {"tracking": {"number": "1Z999", "company": "USPS"}}


@respx.mock
def test_update_substitutes_listing_id_and_patches(
    env_pointing_at_fake_api: None,  # noqa: ARG001
    fake_api_url: str,
) -> None:
    route = respx.patch(
        f"{fake_api_url}/agent/tiktok-shop/stores/{STORE_ID}/listings/{LISTING_ID}"
    ).mock(return_value=httpx.Response(200, json=[]))

    result = runner.invoke(
        app,
        [
            "tiktok-shop-listings",
            "update",
            STORE_ID,
            LISTING_ID,
            "-b",
            json.dumps({"sell_prices": {"SKU-1": 19.99}}),
        ],
    )

    assert result.exit_code == 0, result.stderr
    sent = json.loads(route.calls.last.request.content)
    assert sent == {"sell_prices": {"SKU-1": 19.99}}
