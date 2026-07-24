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
            "--country",
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
    # --country is presented to the user but maps to the API's country_code key.
    assert params["country_code"] == "US"
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
