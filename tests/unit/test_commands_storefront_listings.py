"""Editing a storefront listing's category — Wix, WooCommerce and BigCommerce alike.

The CLI validates a ``-b`` body against the command's declared schema **before** the request goes
out, so a field the command does not declare never reaches the API at all. That is the failure these
pin: the API grew ``category_id`` on all three storefront ``update`` endpoints, and until it was
declared here the agent got "unknown field" locally and had no way to file a published product into
a category at all.

The two spellings that mean different things are pinned too: no key at all leaves the listing where
it is, and an empty string files it under nothing — a choice the seller can legitimately make.
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
LISTING_ID = "22222222-2222-4222-8222-222222222222"
CATEGORY_ID = "bbd52b32-21d2-4dbe-bfc5-d320f93f8911"

#: ``(cli group, API path segment)`` for the three storefronts that file products into shop
#: categories. Shopify is absent on purpose: its "category" is the free-text ``product_type``.
STOREFRONTS = [
    pytest.param("wix-listings", "wix", id="wix"),
    pytest.param("woocommerce-listings", "woocommerce", id="woocommerce"),
    pytest.param("bigcommerce-listings", "bigcommerce", id="bigcommerce"),
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
@pytest.mark.parametrize(("group", "segment"), STOREFRONTS)
@pytest.mark.parametrize(
    "category_id",
    [
        pytest.param(CATEGORY_ID, id="filed-under-a-category"),
        pytest.param("", id="filed-under-nothing"),
    ],
)
def test_update_sends_the_category_to_the_api(
    env_pointing_at_fake_api: None,  # noqa: ARG001
    fake_api_url: str,
    group: str,
    segment: str,
    category_id: str,
) -> None:
    route = respx.patch(
        f"{fake_api_url}/agent/{segment}/stores/{STORE_ID}/listings/{LISTING_ID}"
    ).mock(return_value=httpx.Response(200, json=[{"id": LISTING_ID}]))

    result = runner.invoke(
        app,
        [group, "update", STORE_ID, LISTING_ID, "-b", json.dumps({"category_id": category_id})],
    )

    assert result.exit_code == 0, result.stderr
    assert json.loads(route.calls[0].request.content) == {"category_id": category_id}


@respx.mock
@pytest.mark.parametrize(("group", "segment"), STOREFRONTS)
def test_a_patch_without_a_category_sends_no_category_key(
    env_pointing_at_fake_api: None,  # noqa: ARG001
    fake_api_url: str,
    group: str,
    segment: str,
) -> None:
    """"Not mentioned" and "cleared" are different answers, and the API reads them apart — so the
    CLI must not turn an omitted category into a null."""
    route = respx.patch(
        f"{fake_api_url}/agent/{segment}/stores/{STORE_ID}/listings/{LISTING_ID}"
    ).mock(return_value=httpx.Response(200, json=[{"id": LISTING_ID}]))

    result = runner.invoke(
        app,
        [group, "update", STORE_ID, LISTING_ID, "-b", json.dumps({"title": "Renamed"})],
    )

    assert result.exit_code == 0, result.stderr
    assert json.loads(route.calls[0].request.content) == {"title": "Renamed"}


@pytest.mark.parametrize(("group", "segment"), STOREFRONTS)
def test_an_undeclared_field_is_still_refused_before_the_request(
    env_pointing_at_fake_api: None,  # noqa: ARG001
    group: str,
    segment: str,  # noqa: ARG001
) -> None:
    """The local check that made this change necessary is still doing its job: a typo costs the
    agent an instant, readable refusal rather than a round-trip and a server error."""
    result = runner.invoke(
        app,
        [group, "update", STORE_ID, LISTING_ID, "-b", json.dumps({"categoryId": CATEGORY_ID})],
    )

    assert result.exit_code != 0
    assert "categoryId" in result.stderr
