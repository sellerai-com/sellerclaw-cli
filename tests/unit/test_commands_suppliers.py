from __future__ import annotations

import json

import httpx
import pytest
import respx
from typer.testing import CliRunner

from sellerclaw_cli.cli import app

pytestmark = pytest.mark.unit

runner = CliRunner()


@pytest.fixture
def env_pointing_at_fake_api(
    monkeypatch: pytest.MonkeyPatch,
    fake_api_url: str,
    fake_token: str,
) -> None:
    monkeypatch.setenv("SELLERCLAW_API_URL", fake_api_url)
    monkeypatch.setenv("SELLERCLAW_TOKEN", fake_token)


@respx.mock
def test_search_products_sends_all_filters_as_query_params(
    env_pointing_at_fake_api: None,  # noqa: ARG001
    fake_api_url: str,
) -> None:
    route = respx.get(f"{fake_api_url}/agent/suppliers/cj/products").mock(
        return_value=httpx.Response(200, json={"items": [], "total": 0})
    )
    result = runner.invoke(
        app,
        [
            "suppliers",
            "search-products",
            "cj",
            "--query",
            "wireless earbuds",
            "--stocked-in",
            "US",
            "--verified-only",
            "--min-price",
            "5",
            "--max-price",
            "40",
            "--sort",
            "price",
            "--order-by",
            "asc",
        ],
    )
    assert result.exit_code == 0, result.stderr
    params = route.calls.last.request.url.params
    assert params["query"] == "wireless earbuds"
    # Named for what it does — where the goods sit — so it cannot be read as a destination.
    assert params["stocked_in"] == "US"
    assert params["verified_only"] == "true"
    # min/max price are floats on the wire.
    assert params["min_price"] == "5.0"
    assert params["max_price"] == "40.0"
    assert params["sort"] == "price"
    assert params["order_by"] == "asc"


@respx.mock
def test_search_products_omits_unset_filters(
    env_pointing_at_fake_api: None,  # noqa: ARG001
    fake_api_url: str,
) -> None:
    """Unset flags are dropped so the server default applies (no ``?verified_only=&country_code=``)."""
    route = respx.get(f"{fake_api_url}/agent/suppliers/cj/products").mock(
        return_value=httpx.Response(200, json={"items": [], "total": 0})
    )
    result = runner.invoke(app, ["suppliers", "search-products", "cj", "--query", "mug"])
    assert result.exit_code == 0, result.stderr
    params = route.calls.last.request.url.params
    assert params["query"] == "mug"
    for dropped in ("country_code", "verified_only", "min_price", "max_price", "sort", "order_by"):
        assert dropped not in params


@respx.mock
def test_search_products_sends_the_category_filter_without_a_query(
    env_pointing_at_fake_api: None,  # noqa: ARG001
    fake_api_url: str,
) -> None:
    """Browsing a category whole is the point of the filter: keyword search returns whatever says
    "belt", so asking by category has to work without inventing a word to go with it."""
    route = respx.get(f"{fake_api_url}/agent/suppliers/cj/products").mock(
        return_value=httpx.Response(200, json={"items": [], "total": 0})
    )
    result = runner.invoke(
        app, ["suppliers", "search-products", "cj", "--category", "cat-belts"]
    )
    assert result.exit_code == 0, result.stderr
    params = route.calls.last.request.url.params
    # --category is presented to the user but maps to the API's category_id key.
    assert params["category_id"] == "cat-belts"
    assert "query" not in params


@respx.mock
def test_categories_browses_the_top_level_by_default(
    env_pointing_at_fake_api: None,  # noqa: ARG001
    fake_api_url: str,
) -> None:
    route = respx.get(f"{fake_api_url}/agent/suppliers/cj/categories").mock(
        return_value=httpx.Response(200, json={"categories": [], "total": 0})
    )
    result = runner.invoke(app, ["suppliers", "categories", "cj"])
    assert result.exit_code == 0, result.stderr
    params = route.calls.last.request.url.params
    for dropped in ("search", "parent", "limit"):
        assert dropped not in params


@respx.mock
def test_categories_passes_search_parent_and_limit(
    env_pointing_at_fake_api: None,  # noqa: ARG001
    fake_api_url: str,
) -> None:
    route = respx.get(f"{fake_api_url}/agent/suppliers/cj/categories").mock(
        return_value=httpx.Response(200, json={"categories": [], "total": 0})
    )
    result = runner.invoke(
        app,
        [
            "suppliers",
            "categories",
            "cj",
            "--search",
            "belt",
            "--parent",
            "Men's Accessories",
            "--limit",
            "5",
        ],
    )
    assert result.exit_code == 0, result.stderr
    params = route.calls.last.request.url.params
    assert params["search"] == "belt"
    assert params["parent"] == "Men's Accessories"
    assert params["limit"] == "5"


@respx.mock
def test_categories_rejects_an_out_of_range_limit_before_the_network_call(
    env_pointing_at_fake_api: None,  # noqa: ARG001
    fake_api_url: str,
) -> None:
    """A bad bound fails fast with the allowed range instead of costing a round trip and a 422."""
    route = respx.get(f"{fake_api_url}/agent/suppliers/cj/categories").mock(
        return_value=httpx.Response(200, json={"categories": [], "total": 0})
    )
    result = runner.invoke(app, ["suppliers", "categories", "cj", "--limit", "5000"])
    assert result.exit_code != 0
    assert route.call_count == 0


@respx.mock
def test_quote_shipping_posts_items_and_destination(
    env_pointing_at_fake_api: None,  # noqa: ARG001
    fake_api_url: str,
) -> None:
    route = respx.post(f"{fake_api_url}/agent/suppliers/cj/shipping/quote").mock(
        return_value=httpx.Response(200, json=[])
    )
    body = {
        "items": [{"variant_id": "v1", "quantity": 1}],
        "destination": {"country_code": "US", "zip_code": "10001"},
    }
    result = runner.invoke(
        app, ["suppliers", "quote-shipping", "cj", "-b", json.dumps(body)]
    )
    assert result.exit_code == 0, result.stderr
    assert route.call_count == 1
    assert json.loads(route.calls.last.request.content) == body


@respx.mock
def test_quote_shipping_requires_destination_locally(
    env_pointing_at_fake_api: None,  # noqa: ARG001
    fake_api_url: str,
) -> None:
    route = respx.post(f"{fake_api_url}/agent/suppliers/cj/shipping/quote").mock(
        return_value=httpx.Response(200, json=[])
    )
    result = runner.invoke(
        app,
        [
            "suppliers",
            "quote-shipping",
            "cj",
            "-b",
            json.dumps({"items": [{"variant_id": "v1", "quantity": 1}]}),
        ],
    )
    assert result.exit_code != 0
    assert route.call_count == 0  # missing required field caught before the network call


@respx.mock
def test_calculate_shipping_accepts_from_country_code(
    env_pointing_at_fake_api: None,  # noqa: ARG001
    fake_api_url: str,
) -> None:
    """The ship-from origin override is a known body field, not rejected as unknown."""
    route = respx.post(f"{fake_api_url}/agent/suppliers/cj/shipping/calculate").mock(
        return_value=httpx.Response(200, json=[])
    )
    body = {
        "items": [{"variant_id": "v1", "quantity": 1}],
        "shipping_address": {
            "country_code": "US",
            "province": "NY",
            "city": "New York",
            "zip_code": "10001",
            "address_line": "1 Main St",
            "full_name": "Jane Doe",
            "phone": "555-0100",
        },
        "from_country_code": "US",
    }
    result = runner.invoke(
        app, ["suppliers", "calculate-shipping", "cj", "-b", json.dumps(body)]
    )
    assert result.exit_code == 0, result.stderr
    assert json.loads(route.calls.last.request.content)["from_country_code"] == "US"


@respx.mock
def test_cancel_order_posts_to_the_suppliers_own_order_id(
    env_pointing_at_fake_api: None,  # noqa: ARG001
    fake_api_url: str,
) -> None:
    """The path carries the supplier's order id, the same one `confirm` and `pay` take."""
    route = respx.post(f"{fake_api_url}/agent/suppliers/cj/orders/SD-2608/cancel").mock(
        return_value=httpx.Response(
            200,
            json={
                "supplier_order_id": "SD-2608",
                "cancelled": True,
                "message": "Cancelled at the supplier.",
                "linked_order_id": None,
            },
        )
    )
    result = runner.invoke(app, ["suppliers", "cancel-order", "cj", "SD-2608"])
    assert result.exit_code == 0, result.stderr
    assert route.call_count == 1


@respx.mock
def test_cancel_order_passes_the_sellerclaw_order_to_unhook(
    env_pointing_at_fake_api: None,  # noqa: ARG001
    fake_api_url: str,
) -> None:
    """`internal_order_id` is a known body field — without it the order keeps a dead purchase."""
    order_id = "8b0b8192-0b2f-41fd-87b6-817b5754b82b"
    route = respx.post(f"{fake_api_url}/agent/suppliers/cj/orders/SD-2608/cancel").mock(
        return_value=httpx.Response(
            200,
            json={
                "supplier_order_id": "SD-2608",
                "cancelled": True,
                "message": "Cancelled at the supplier.",
                "linked_order_id": order_id,
            },
        )
    )
    result = runner.invoke(
        app,
        [
            "suppliers",
            "cancel-order",
            "cj",
            "SD-2608",
            "-b",
            json.dumps({"internal_order_id": order_id}),
        ],
    )
    assert result.exit_code == 0, result.stderr
    assert json.loads(route.calls.last.request.content) == {"internal_order_id": order_id}


@respx.mock
def test_cancel_order_rejects_an_unknown_body_field_before_the_network_call(
    env_pointing_at_fake_api: None,  # noqa: ARG001
    fake_api_url: str,
) -> None:
    """A mistyped field must not reach the supplier as a silently ignored extra."""
    route = respx.post(f"{fake_api_url}/agent/suppliers/cj/orders/SD-2608/cancel").mock(
        return_value=httpx.Response(200, json={})
    )
    result = runner.invoke(
        app,
        ["suppliers", "cancel-order", "cj", "SD-2608", "-b", json.dumps({"order_id": "x"})],
    )
    assert result.exit_code != 0
    assert route.call_count == 0


@respx.mock
def test_a_warehouse_is_added_to_one_supplier_with_its_address(
    env_pointing_at_fake_api: None,  # noqa: ARG001
    fake_api_url: str,
) -> None:
    supplier_id = "8f6b3c1e-0000-4000-8000-000000000001"
    route = respx.post(
        f"{fake_api_url}/agent/supplier-accounts/offline/{supplier_id}/warehouses"
    ).mock(return_value=httpx.Response(201, json={"id": "w-1", "products": 3}))

    result = runner.invoke(
        app,
        [
            "suppliers",
            "create-warehouse",
            supplier_id,
            "-b",
            json.dumps({"name": "Main", "country_code": "US", "postal_code": "10001", "city": "NYC"}),
        ],
    )

    assert result.exit_code == 0, result.stderr
    assert json.loads(route.calls.last.request.content) == {
        "name": "Main",
        "country_code": "US",
        "postal_code": "10001",
        "city": "NYC",
    }


def test_a_warehouse_without_a_postal_code_is_refused_before_the_request(
    env_pointing_at_fake_api: None,  # noqa: ARG001
) -> None:
    result = runner.invoke(
        app,
        [
            "suppliers",
            "create-warehouse",
            "8f6b3c1e-0000-4000-8000-000000000001",
            "-b",
            json.dumps({"name": "Main", "country_code": "US"}),
        ],
    )

    assert result.exit_code != 0
    assert "postal_code" in result.output + result.stderr


@respx.mock
def test_a_warehouse_field_is_cleared_with_null(
    env_pointing_at_fake_api: None,  # noqa: ARG001
    fake_api_url: str,
) -> None:
    supplier_id = "8f6b3c1e-0000-4000-8000-000000000001"
    warehouse_id = "8f6b3c1e-0000-4000-8000-000000000002"
    route = respx.patch(
        f"{fake_api_url}/agent/supplier-accounts/offline/{supplier_id}/warehouses/{warehouse_id}"
    ).mock(return_value=httpx.Response(200, json={"id": warehouse_id}))

    result = runner.invoke(
        app,
        ["suppliers", "update-warehouse", supplier_id, warehouse_id, "-b", '{"city": null}'],
    )

    assert result.exit_code == 0, result.stderr
    assert json.loads(route.calls.last.request.content) == {"city": None}


@respx.mock
def test_warehouses_are_listed_and_deleted_by_supplier(
    env_pointing_at_fake_api: None,  # noqa: ARG001
    fake_api_url: str,
) -> None:
    supplier_id = "8f6b3c1e-0000-4000-8000-000000000001"
    warehouse_id = "8f6b3c1e-0000-4000-8000-000000000002"
    base = f"{fake_api_url}/agent/supplier-accounts/offline/{supplier_id}/warehouses"
    listed = respx.get(base).mock(return_value=httpx.Response(200, json=[]))
    deleted = respx.delete(f"{base}/{warehouse_id}").mock(return_value=httpx.Response(204))

    listing = runner.invoke(app, ["suppliers", "list-warehouses", supplier_id])
    deletion = runner.invoke(app, ["suppliers", "delete-warehouse", supplier_id, warehouse_id])

    assert listing.exit_code == 0, listing.stderr
    assert deletion.exit_code == 0, deletion.stderr
    assert listed.called and deleted.called


@respx.mock
def test_a_countrys_warehouse_rates_are_sent_as_weight_bands(
    env_pointing_at_fake_api: None,  # noqa: ARG001
    fake_api_url: str,
) -> None:
    supplier_id = "8f6b3c1e-0000-4000-8000-000000000001"
    warehouse_id = "8f6b3c1e-0000-4000-8000-000000000002"
    route = respx.put(
        f"{fake_api_url}/agent/supplier-accounts/offline/{supplier_id}/warehouses/{warehouse_id}"
        "/shipping-rates/US"
    ).mock(return_value=httpx.Response(200, json={"id": warehouse_id, "shipping_rates": []}))
    bands = [
        {"max_weight_grams": 500, "price": "5.00"},
        {"max_weight_grams": 1000, "price": "8.00"},
    ]

    result = runner.invoke(
        app,
        [
            "suppliers",
            "set-warehouse-rates",
            supplier_id,
            warehouse_id,
            "US",
            "-b",
            json.dumps({"bands": bands}),
        ],
    )

    assert result.exit_code == 0, result.stderr
    assert json.loads(route.calls.last.request.content) == {"bands": bands}


def test_warehouse_rates_without_bands_are_refused_before_the_request(
    env_pointing_at_fake_api: None,  # noqa: ARG001
) -> None:
    result = runner.invoke(
        app,
        [
            "suppliers",
            "set-warehouse-rates",
            "8f6b3c1e-0000-4000-8000-000000000001",
            "8f6b3c1e-0000-4000-8000-000000000002",
            "US",
            "-b",
            "{}",
        ],
    )

    assert result.exit_code != 0
    assert "bands" in result.output + result.stderr


@respx.mock
def test_a_countrys_warehouse_rates_are_removed(
    env_pointing_at_fake_api: None,  # noqa: ARG001
    fake_api_url: str,
) -> None:
    supplier_id = "8f6b3c1e-0000-4000-8000-000000000001"
    warehouse_id = "8f6b3c1e-0000-4000-8000-000000000002"
    route = respx.delete(
        f"{fake_api_url}/agent/supplier-accounts/offline/{supplier_id}/warehouses/{warehouse_id}"
        "/shipping-rates/DE"
    ).mock(return_value=httpx.Response(204))

    result = runner.invoke(
        app, ["suppliers", "delete-warehouse-rates", supplier_id, warehouse_id, "DE"]
    )

    assert result.exit_code == 0, result.stderr
    assert route.called
