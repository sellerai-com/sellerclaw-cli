"""List filters that answer a question in one call instead of a dump the caller diffs itself."""

from __future__ import annotations

import httpx
import pytest
import respx
from typer.testing import CliRunner

from sellerclaw_cli.cli import app

pytestmark = pytest.mark.unit

runner = CliRunner()

STORE_ID = "11111111-1111-4111-8111-111111111111"
OTHER_STORE_ID = "22222222-2222-4222-8222-222222222222"


@pytest.fixture
def env_pointing_at_fake_api(
    monkeypatch: pytest.MonkeyPatch,
    fake_api_url: str,
    fake_token: str,
) -> None:
    monkeypatch.setenv("SELLERCLAW_API_URL", fake_api_url)
    monkeypatch.setenv("SELLERCLAW_TOKEN", fake_token)


@respx.mock
@pytest.mark.parametrize(
    ("argv", "path", "expected"),
    [
        pytest.param(
            ["catalog", "list", "--supplier-provider", "cj", "--supplier-product-id", "A1",
             "--supplier-product-id", "B2"],
            "/agent/products",
            [("supplier_product_id", "A1"), ("supplier_product_id", "B2"), ("supplier_provider", "cj")],
            id="catalog-batch-of-supplier-items",
        ),
        pytest.param(
            ["catalog", "list", "--sku", "MUG-1", "--sku", "MUG-2"],
            "/agent/products",
            [("sku", "MUG-1"), ("sku", "MUG-2")],
            id="catalog-batch-of-skus",
        ),
        pytest.param(
            ["catalog", "list", "--published-in", "pets.example.com", "--not-published-in", STORE_ID],
            "/agent/products",
            [("not_published_in", STORE_ID), ("published_in", "pets.example.com")],
            id="catalog-on-one-store-not-on-another",
        ),
        pytest.param(
            ["catalog", "list", "--supplier-id", OTHER_STORE_ID],
            "/agent/products",
            [("supplier_id", OTHER_STORE_ID)],
            id="catalog-one-supplier",
        ),
        pytest.param(
            ["listings", "search", "--sku", "A", "--sku", "B", "--remote-id", "R1", "--not-in-catalog"],
            "/agent/listings/search",
            [("not_in_catalog", "true"), ("remote_id", "R1"), ("sku", "A"), ("sku", "B")],
            id="listings-batch-and-not-in-catalog",
        ),
        pytest.param(
            ["orders", "list", "--status", "open", "--awaiting-shipment"],
            "/agent/orders",
            [("awaiting_shipment", "true"), ("status", "open")],
            id="orders-shipping-queue",
        ),
        pytest.param(
            ["listing-problems", "list", "--store-id", STORE_ID],
            "/agent/listing-problems",
            [("sales_channel_id", STORE_ID)],
            id="listing-problems-store-id-spelling",
        ),
    ],
)
def test_list_filters_reach_the_api(
    env_pointing_at_fake_api: None,  # noqa: ARG001
    fake_api_url: str,
    argv: list[str],
    path: str,
    expected: list[tuple[str, str]],
) -> None:
    """Each filter lands as its query key; a repeated flag lands as a repeated key."""
    route = respx.get(f"{fake_api_url}{path}").mock(
        return_value=httpx.Response(200, json={"items": [], "total": 0})
    )

    result = runner.invoke(app, argv)

    assert result.exit_code == 0, result.stderr
    assert sorted(route.calls.last.request.url.params.multi_items()) == expected


@respx.mock
def test_an_order_status_that_is_neither_a_status_nor_a_group_is_refused_locally(
    env_pointing_at_fake_api: None,  # noqa: ARG001
    fake_api_url: str,
) -> None:
    route = respx.get(f"{fake_api_url}/agent/orders").mock(
        return_value=httpx.Response(200, json={"items": [], "total": 0})
    )

    result = runner.invoke(app, ["orders", "list", "--status", "pending"])

    assert result.exit_code != 0
    assert "open" in result.stderr
    assert route.call_count == 0
