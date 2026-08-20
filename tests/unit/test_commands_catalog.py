"""Paging a store's listings, and editing a set of catalog products in one call.

Both pin gaps that cost a live agent a whole turn (staging chat b76fd17a): it tried to page past
the first 100 of 626 Shopify rows and got "No such option: --offset", then tried to fix 53 product
names in one call and got "Missing argument 'product_id'". The endpoints could serve both — only
the CLI surface could not say so.
"""

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
PRODUCT_A = "22222222-2222-4222-8222-222222222222"
PRODUCT_B = "33333333-3333-4333-8333-333333333333"

#: Every channel group whose `list` reads the shared mirror endpoint, which has always paged.
CHANNEL_GROUPS = [
    pytest.param(name, id=name)
    for name in (
        "shopify-listings",
        "ebay-listings",
        "amazon-listings",
        "etsy-listings",
        "walmart-listings",
        "wix-listings",
        "woocommerce-listings",
        "bigcommerce-listings",
        "tiktok-shop-listings",
    )
]


@pytest.fixture
def env_pointing_at_fake_api(
    monkeypatch: pytest.MonkeyPatch,
    fake_api_url: str,
    fake_token: str,
) -> None:
    monkeypatch.setenv("SELLERCLAW_API_URL", fake_api_url)
    monkeypatch.setenv("SELLERCLAW_TOKEN", fake_token)


@respx.mock
@pytest.mark.parametrize("group", CHANNEL_GROUPS)
def test_a_channel_listing_page_can_be_asked_for_by_offset(
    env_pointing_at_fake_api: None,  # noqa: ARG001
    fake_api_url: str,
    group: str,
) -> None:
    """`--offset` reaches the shared mirror endpoint, so a catalog past one page is readable."""
    route = respx.get(f"{fake_api_url}/agent/stores/{STORE_ID}/listings").mock(
        return_value=httpx.Response(200, json={"items": [], "total": 626})
    )

    result = runner.invoke(app, [group, "list", STORE_ID, "--limit", "100", "--offset", "500"])

    assert result.exit_code == 0, result.stderr
    assert dict(route.calls[0].request.url.params) == {"limit": "100", "offset": "500"}


@respx.mock
@pytest.mark.parametrize("group", CHANNEL_GROUPS)
def test_a_channel_listing_page_without_an_offset_sends_none(
    env_pointing_at_fake_api: None,  # noqa: ARG001
    fake_api_url: str,
    group: str,
) -> None:
    """An unset flag is still dropped, so the endpoint's own default keeps applying."""
    route = respx.get(f"{fake_api_url}/agent/stores/{STORE_ID}/listings").mock(
        return_value=httpx.Response(200, json={"items": [], "total": 0})
    )

    result = runner.invoke(app, [group, "list", STORE_ID])

    assert result.exit_code == 0, result.stderr
    assert "offset" not in dict(route.calls[0].request.url.params)


@respx.mock
def test_catalog_search_pages_like_catalog_list_does(
    env_pointing_at_fake_api: None,  # noqa: ARG001
    fake_api_url: str,
) -> None:
    """`search` and `list` are the same endpoint; only `list` could page, which was the whole bug."""
    route = respx.get(f"{fake_api_url}/agent/products").mock(
        return_value=httpx.Response(200, json={"items": [], "total": 0})
    )

    result = runner.invoke(app, ["catalog", "search", "--q", "mat", "--offset", "50"])

    assert result.exit_code == 0, result.stderr
    assert dict(route.calls[0].request.url.params) == {"q": "mat", "offset": "50"}


@pytest.mark.parametrize(
    "offset",
    [pytest.param("-1", id="negative"), pytest.param("abc", id="not-a-number")],
)
def test_a_bad_offset_is_refused_before_the_request(
    env_pointing_at_fake_api: None,  # noqa: ARG001
    offset: str,
) -> None:
    """Local validation still answers instantly instead of spending a round-trip on a 422."""
    result = runner.invoke(app, ["shopify-listings", "list", STORE_ID, "--offset", offset])

    assert result.exit_code != 0


@respx.mock
def test_bulk_update_posts_every_patch_in_one_call(
    env_pointing_at_fake_api: None,  # noqa: ARG001
    fake_api_url: str,
) -> None:
    """The batch rename that used to need one call per product, or a CSV round-trip."""
    body = {
        "items": [
            {"product_id": PRODUCT_A, "patch": {"name": "Cat Litter Mat"}},
            {"product_id": PRODUCT_B, "patch": {"brand": "ACME", "weight_grams": None}},
        ]
    }
    route = respx.post(f"{fake_api_url}/agent/products/bulk-update").mock(
        return_value=httpx.Response(
            200,
            json={
                "items": [
                    {"product_id": PRODUCT_A, "ok": True, "error": None, "product": {}},
                    {"product_id": PRODUCT_B, "ok": True, "error": None, "product": {}},
                ]
            },
        )
    )

    result = runner.invoke(app, ["catalog", "bulk-update", "-b", json.dumps(body)])

    assert result.exit_code == 0, result.stderr
    sent = json.loads(route.calls[0].request.content)
    assert sent == body
    # An explicit null must survive the trip: it is how a wrong weight is cleared.
    assert sent["items"][1]["patch"]["weight_grams"] is None


def test_bulk_update_without_items_is_refused_before_the_request(
    env_pointing_at_fake_api: None,  # noqa: ARG001
) -> None:
    """`items` is required, and the local schema check says so without a round-trip."""
    result = runner.invoke(app, ["catalog", "bulk-update", "-b", json.dumps({})])

    assert result.exit_code != 0
    assert "items" in result.stderr


def test_bulk_update_refuses_an_undeclared_top_level_key(
    env_pointing_at_fake_api: None,  # noqa: ARG001
) -> None:
    """A typo at the top level costs an instant, readable refusal, not a server error."""
    result = runner.invoke(
        app,
        [
            "catalog",
            "bulk-update",
            "-b",
            json.dumps({"products": [{"product_id": PRODUCT_A, "patch": {"name": "x"}}]}),
        ],
    )

    assert result.exit_code != 0
    assert "products" in result.stderr
