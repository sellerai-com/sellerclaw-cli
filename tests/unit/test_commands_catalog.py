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
def test_the_product_catalogue_is_read_page_by_page(
    env_pointing_at_fake_api: None,  # noqa: ARG001
    fake_api_url: str,
) -> None:
    """`products` answered with the whole store at once — on a store of a hundred thousand listings,
    more than the server could hold. It pages now, and the next page has to be reachable."""
    route = respx.get(f"{fake_api_url}/agent/stores/{STORE_ID}/listings/products").mock(
        return_value=httpx.Response(
            200, json={"items": [], "total": 1200, "variant_rows": 3000, "next_offset": 1000}
        )
    )

    result = runner.invoke(
        app, ["shopify-listings", "products", STORE_ID, "--limit", "500", "--offset", "500"]
    )

    assert result.exit_code == 0, result.stderr
    assert dict(route.calls[0].request.url.params) == {"limit": "500", "offset": "500"}


@pytest.mark.parametrize(
    "limit", [pytest.param("0", id="empty-page"), pytest.param("501", id="over-the-cap")]
)
def test_a_product_page_the_server_would_refuse_is_refused_before_the_request(
    env_pointing_at_fake_api: None,  # noqa: ARG001
    limit: str,
) -> None:
    result = runner.invoke(app, ["shopify-listings", "products", STORE_ID, "--limit", limit])

    assert result.exit_code != 0


#: Channel groups whose marketplace can count its own products by status — drafts, hidden, archived.
MARKETPLACE_STATUS_GROUPS = (
    "shopify-listings",
    "walmart-listings",
    "wix-listings",
    "woocommerce-listings",
    "bigcommerce-listings",
    "tiktok-shop-listings",
)


@respx.mock
@pytest.mark.parametrize(
    ("group", "extra", "params"),
    [
        *(
            pytest.param(name, ["--marketplace-statuses"], {"marketplace_statuses": "true"}, id=f"{name}-asked")
            for name in MARKETPLACE_STATUS_GROUPS
        ),
        pytest.param("shopify-listings", [], {}, id="not-asked"),
    ],
)
def test_the_store_summary_counts_the_marketplace_statuses_only_when_asked(
    env_pointing_at_fake_api: None,  # noqa: ARG001
    fake_api_url: str,
    group: str,
    extra: list[str],
    params: dict[str, str],
) -> None:
    route = respx.get(f"{fake_api_url}/agent/stores/{STORE_ID}/listings/summary").mock(
        return_value=httpx.Response(200, json={"total_rows": 0, "marketplace_statuses": None})
    )

    result = runner.invoke(app, [group, "summary", STORE_ID, *extra])

    assert result.exit_code == 0, result.stderr
    assert dict(route.calls[0].request.url.params) == params


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


@respx.mock
def test_a_product_is_moved_to_another_warehouse_of_its_supplier(
    env_pointing_at_fake_api: None,  # noqa: ARG001
    fake_api_url: str,
) -> None:
    warehouse_id = "22222222-2222-2222-2222-222222222222"
    route = respx.patch(f"{fake_api_url}/agent/products/{PRODUCT_A}/supplier-warehouse").mock(
        return_value=httpx.Response(200, json={"id": PRODUCT_A})
    )

    result = runner.invoke(
        app,
        [
            "catalog",
            "set-supplier-warehouse",
            PRODUCT_A,
            "-b",
            json.dumps({"supplier_warehouse_id": warehouse_id}),
        ],
    )

    assert result.exit_code == 0, result.stderr
    assert json.loads(route.calls.last.request.content) == {"supplier_warehouse_id": warehouse_id}


@respx.mock
def test_binding_a_supplier_can_name_the_warehouse(
    env_pointing_at_fake_api: None,  # noqa: ARG001
    fake_api_url: str,
) -> None:
    route = respx.patch(f"{fake_api_url}/agent/products/{PRODUCT_A}/supplier").mock(
        return_value=httpx.Response(200, json={"id": PRODUCT_A})
    )
    body = {
        "supplier_id": "11111111-1111-1111-1111-111111111111",
        "supplier_product_id": "NSC-1",
        "supplier_warehouse_id": "22222222-2222-2222-2222-222222222222",
    }

    result = runner.invoke(app, ["catalog", "set-supplier", PRODUCT_A, "-b", json.dumps(body)])

    assert result.exit_code == 0, result.stderr
    assert json.loads(route.calls.last.request.content) == body


BOX_ID = "55555555-5555-4555-8555-555555555555"


@respx.mock
@pytest.mark.parametrize(
    ("command", "method", "path", "body"),
    [
        pytest.param(
            "update",
            "PATCH",
            f"/agent/products/{PRODUCT_A}",
            {"weight_grams": 450, "box_id": BOX_ID},
            id="update-sets-weight-and-box",
        ),
        pytest.param(
            "update",
            "PATCH",
            f"/agent/products/{PRODUCT_A}",
            {"box_id": None},
            id="update-takes-the-product-out-of-any-box",
        ),
        pytest.param(
            "set-variations",
            "PATCH",
            f"/agent/products/{PRODUCT_A}/variations",
            {"box_id": BOX_ID},
            id="set-variations-broadcasts-a-box",
        ),
        pytest.param(
            "set-variations",
            "PATCH",
            f"/agent/products/{PRODUCT_A}/variations",
            {"variations": [{"supplier_variant_id": "V-L", "weight_grams": 900, "box_id": None}]},
            id="set-variations-per-variation",
        ),
    ],
)
def test_a_product_weight_and_box_reach_the_api_as_sent(
    env_pointing_at_fake_api: None,  # noqa: ARG001
    fake_api_url: str,
    command: str,
    method: str,
    path: str,
    body: dict[str, object],
) -> None:
    """An explicit null is an instruction (no box), so it must survive the local check and the trip."""
    route = respx.route(method=method, url=f"{fake_api_url}{path}").mock(
        return_value=httpx.Response(200, json={"id": PRODUCT_A})
    )

    result = runner.invoke(app, ["catalog", command, PRODUCT_A, "-b", json.dumps(body)])

    assert result.exit_code == 0, result.stderr
    assert json.loads(route.calls.last.request.content) == body


@respx.mock
def test_a_product_is_created_with_its_weight_and_box(
    env_pointing_at_fake_api: None,  # noqa: ARG001
    fake_api_url: str,
) -> None:
    body = {
        "items": [
            {
                "name": "Wireless Mouse",
                "description": "2.4 GHz",
                "category": "Electronics",
                "weight_grams": 95,
                "box_id": BOX_ID,
                "variations": [
                    {
                        "supplier_variant_id": "WM-01",
                        "sku": "WM-01",
                        "name": "Black",
                        "available_quantity": 5,
                        "shipping_cost": 0,
                    }
                ],
            }
        ]
    }
    route = respx.post(f"{fake_api_url}/agent/products").mock(
        return_value=httpx.Response(200, json={"results": [], "errors": []})
    )

    result = runner.invoke(app, ["catalog", "create", "-b", json.dumps(body)])

    assert result.exit_code == 0, result.stderr
    assert json.loads(route.calls.last.request.content) == body


LISTING_S = "44444444-4444-4444-8444-444444444444"
LISTING_L = "55555555-5555-4555-8555-555555555555"


@respx.mock
def test_listings_are_copied_into_products_as_they_are_grouped(
    env_pointing_at_fake_api: None,  # noqa: ARG001
    fake_api_url: str,
) -> None:
    """The grouping is the caller's: the body reaches the API exactly as written."""
    route = respx.post(f"{fake_api_url}/agent/products/from-listings").mock(
        return_value=httpx.Response(
            200,
            json={
                "results": [{"outcome": "created", "product_id": PRODUCT_A, "variations": []}],
                "prices": {"CANDLE-S": "18.00", "CANDLE-L": "24.00"},
                "prices_currency": "USD",
            },
        )
    )
    body = {
        "products": [
            {
                "name": "Lavender soy candle",
                "variations": [
                    {"listing_id": LISTING_S, "options": {"Size": "8 oz"}},
                    {"listing_id": LISTING_L, "options": {"Size": "16 oz"}},
                ],
            }
        ]
    }

    result = runner.invoke(app, ["catalog", "create-from-listings", "-b", json.dumps(body)])

    assert result.exit_code == 0, result.stderr
    assert json.loads(route.calls.last.request.content) == body
    assert json.loads(result.stdout)["data"]["prices_currency"] == "USD"


def test_copying_listings_needs_the_products_to_make(
    env_pointing_at_fake_api: None,  # noqa: ARG001
) -> None:
    result = runner.invoke(app, ["catalog", "create-from-listings", "-b", json.dumps({})])

    assert result.exit_code != 0
    assert "products" in (result.stderr + result.stdout)
