"""The amazon-fba group: Amazon's warehouse as a supplier that ships for other channels.

Two things are worth pinning. Linking the warehouse is a *pointer* to a connected store, not a set
of credentials — so the one field that travels has to reach the server intact, and nothing is ever
echoed back that looks like a key. And binding products is two commands on purpose: the reading one
writes nothing, and the writing one only ever touches the ids it was handed.
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

SUPPLIER = "/agent/supplier-accounts/amazon-fba"
BINDING = "/agent/amazon/fba/binding"
STORE = "11111111-1111-1111-1111-111111111111"


@pytest.fixture
def env_pointing_at_fake_api(
    monkeypatch: pytest.MonkeyPatch,
    fake_api_url: str,
    fake_token: str,
) -> None:
    monkeypatch.setenv("SELLERCLAW_API_URL", fake_api_url)
    monkeypatch.setenv("SELLERCLAW_TOKEN", fake_token)


@respx.mock
def test_connect_names_the_store_that_ships(
    env_pointing_at_fake_api: None,  # noqa: ARG001
    fake_api_url: str,
) -> None:
    """The store id is the whole content of this supplier — mangling it links the wrong warehouse."""
    route = respx.post(f"{fake_api_url}{SUPPLIER}").mock(
        return_value=httpx.Response(201, json={"id": "acc-1", "sales_channel_id": STORE})
    )

    result = runner.invoke(
        app, ["amazon-fba", "connect", "-b", json.dumps({"sales_channel_id": STORE})]
    )

    assert result.exit_code == 0, result.output
    assert json.loads(route.calls.last.request.content) == {"sales_channel_id": STORE}


def test_connecting_without_a_store_is_caught_before_the_request(
    env_pointing_at_fake_api: None,  # noqa: ARG001
) -> None:
    """There is nothing else to send, so an empty body is a mistake worth naming locally."""
    result = runner.invoke(app, ["amazon-fba", "connect", "-b", json.dumps({})])

    assert result.exit_code != 0
    assert "sales_channel_id" in result.output


@respx.mock
def test_status_reports_the_linked_store(
    env_pointing_at_fake_api: None,  # noqa: ARG001
    fake_api_url: str,
) -> None:
    respx.get(f"{fake_api_url}{SUPPLIER}").mock(
        return_value=httpx.Response(200, json={"id": "acc-1", "sales_channel_id": STORE})
    )

    result = runner.invoke(app, ["amazon-fba", "status"])

    assert result.exit_code == 0, result.output
    assert STORE in result.output


@respx.mock
def test_disconnect_deletes_the_link_and_not_the_store(
    env_pointing_at_fake_api: None,  # noqa: ARG001
    fake_api_url: str,
) -> None:
    route = respx.delete(f"{fake_api_url}{SUPPLIER}").mock(return_value=httpx.Response(204))

    result = runner.invoke(app, ["amazon-fba", "disconnect"])

    assert result.exit_code == 0, result.output
    assert route.called


@respx.mock
def test_list_stock_asks_the_store_it_was_given(
    env_pointing_at_fake_api: None,  # noqa: ARG001
    fake_api_url: str,
) -> None:
    route = respx.get(f"{fake_api_url}/agent/amazon/stores/{STORE}/fba/inventory").mock(
        return_value=httpx.Response(
            200,
            json={
                "items": [
                    {
                        "seller_sku": "SKU-1",
                        "marketplace_id": "ATVPDKIKX0DER",
                        "available_quantity": 7,
                        "synced_at": "2026-08-05T06:00:00Z",
                    }
                ],
                "fulfillment_options": [],
            },
        )
    )

    result = runner.invoke(app, ["amazon-fba", "list-stock", STORE])

    assert result.exit_code == 0, result.output
    assert route.called
    assert "SKU-1" in result.output


@respx.mock
def test_refresh_stock_posts_for_one_store(
    env_pointing_at_fake_api: None,  # noqa: ARG001
    fake_api_url: str,
) -> None:
    route = respx.post(f"{fake_api_url}/agent/amazon/stores/{STORE}/fba/refresh").mock(
        return_value=httpx.Response(200, json={"marketplace_id": "ATVPDKIKX0DER", "skus_in_stock": 3})
    )

    result = runner.invoke(app, ["amazon-fba", "refresh-stock", STORE])

    assert result.exit_code == 0, result.output
    assert route.called


@respx.mock
def test_preview_binding_reads_and_writes_nothing(
    env_pointing_at_fake_api: None,  # noqa: ARG001
    fake_api_url: str,
) -> None:
    """A GET by design: the value of this call is the products it refuses to bind."""
    route = respx.get(f"{fake_api_url}{BINDING}").mock(
        return_value=httpx.Response(
            200,
            json={
                "sales_channel_id": STORE,
                "items": [
                    {
                        "product_id": "p-1",
                        "outcome": "ambiguous",
                        "message": "More than one connected Amazon store holds this product.",
                    }
                ],
                "bound_product_ids": [],
                "not_in_warehouse": 240,
            },
        )
    )

    result = runner.invoke(app, ["amazon-fba", "preview-binding", "--limit", "10"])

    assert result.exit_code == 0, result.output
    assert route.calls.last.request.url.params["limit"] == "10"
    assert "ambiguous" in result.output


def test_preview_binding_refuses_an_impossible_limit_locally(
    env_pointing_at_fake_api: None,  # noqa: ARG001
) -> None:
    result = runner.invoke(app, ["amazon-fba", "preview-binding", "--limit", "500"])

    assert result.exit_code != 0
    assert "200" in result.output


@respx.mock
def test_bind_sends_exactly_the_products_it_was_handed(
    env_pointing_at_fake_api: None,  # noqa: ARG001
    fake_api_url: str,
) -> None:
    """Nothing is swept in: the owner decided this list, and the call must not widen it."""
    route = respx.post(f"{fake_api_url}{BINDING}/apply").mock(
        return_value=httpx.Response(
            200,
            json={
                "sales_channel_id": STORE,
                "items": [{"product_id": "p-1", "outcome": "matched", "message": "…"}],
                "bound_product_ids": ["p-1"],
            },
        )
    )

    result = runner.invoke(
        app, ["amazon-fba", "bind", "-b", json.dumps({"product_ids": ["p-1", "p-2"]})]
    )

    assert result.exit_code == 0, result.output
    assert json.loads(route.calls.last.request.content) == {"product_ids": ["p-1", "p-2"]}


def test_binding_nothing_is_caught_before_the_request(
    env_pointing_at_fake_api: None,  # noqa: ARG001
) -> None:
    result = runner.invoke(app, ["amazon-fba", "bind", "-b", json.dumps({})])

    assert result.exit_code != 0
    assert "product_ids" in result.output


def test_the_group_reads_the_warehouse_before_it_writes_anything() -> None:
    """Ordering is documentation: link, look, then bind — and the destructive one is last of its pair."""
    from sellerclaw_cli.commands.amazon_fba import SPECS

    assert [spec.name for spec in SPECS] == [
        "connect",
        "status",
        "disconnect",
        "list-stock",
        "refresh-stock",
        "preview-binding",
        "bind",
    ]
