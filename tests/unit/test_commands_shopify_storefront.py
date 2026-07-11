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


@pytest.fixture
def env_pointing_at_fake_api(
    monkeypatch: pytest.MonkeyPatch,
    fake_api_url: str,
    fake_token: str,
) -> None:
    monkeypatch.setenv("SELLERCLAW_API_URL", fake_api_url)
    monkeypatch.setenv("SELLERCLAW_TOKEN", fake_token)


@respx.mock
def test_graphql_query_flag_builds_body_without_json_wrapping(
    env_pointing_at_fake_api: None,  # noqa: ARG001
    fake_api_url: str,
) -> None:
    """`-q '<doc>'` sends {"query": "<doc>"} — no hand-wrapped JSON, no double escaping."""
    route = respx.post(f"{fake_api_url}/agent/stores/{STORE_ID}/graphql").mock(
        return_value=httpx.Response(200, json={"data": {}})
    )
    doc = "mutation { publishablePublish(id: \"x\") { userErrors { message } } }"
    result = runner.invoke(app, ["shopify", "graphql", STORE_ID, "-q", doc])
    assert result.exit_code == 0, result.stderr
    assert json.loads(route.calls.last.request.content) == {"query": doc}


@respx.mock
def test_graphql_query_with_variables(
    env_pointing_at_fake_api: None,  # noqa: ARG001
    fake_api_url: str,
) -> None:
    route = respx.post(f"{fake_api_url}/agent/stores/{STORE_ID}/graphql").mock(
        return_value=httpx.Response(200, json={"data": {}})
    )
    result = runner.invoke(
        app,
        ["shopify", "graphql", STORE_ID, "-q", "query($id: ID!){ node(id:$id){ id } }",
         "--variables", '{"id": "gid://shopify/Product/1"}'],
    )
    assert result.exit_code == 0, result.stderr
    sent = json.loads(route.calls.last.request.content)
    assert sent["variables"] == {"id": "gid://shopify/Product/1"}


def test_graphql_without_query_or_body_errors(
    env_pointing_at_fake_api: None,  # noqa: ARG001
) -> None:
    result = runner.invoke(app, ["shopify", "graphql", STORE_ID])
    assert result.exit_code == 1
    assert "-q/--query" in result.stderr


@respx.mock
def test_collection_publish_posts_publication_names(
    env_pointing_at_fake_api: None,  # noqa: ARG001
    fake_api_url: str,
) -> None:
    route = respx.post(f"{fake_api_url}/agent/stores/{STORE_ID}/collections/55/publish").mock(
        return_value=httpx.Response(200, json={"collection_id": "55"})
    )
    result = runner.invoke(
        app,
        ["shopify-collections", "publish", STORE_ID, "55", "-b",
         json.dumps({"publication_names": ["Online Store"]})],
    )
    assert result.exit_code == 0, result.stderr
    assert json.loads(route.calls.last.request.content) == {"publication_names": ["Online Store"]}


@respx.mock
def test_inventory_repeats_sku_query_params(
    env_pointing_at_fake_api: None,  # noqa: ARG001
    fake_api_url: str,
) -> None:
    route = respx.get(f"{fake_api_url}/agent/stores/{STORE_ID}/listings/inventory").mock(
        return_value=httpx.Response(200, json={"items": []})
    )
    result = runner.invoke(
        app,
        ["shopify-listings", "inventory", STORE_ID, "--skus", "A", "--skus", "B"],
    )
    assert result.exit_code == 0, result.stderr
    assert route.calls.last.request.url.params.get_list("skus") == ["A", "B"]


def test_set_inventory_policy_command_is_removed() -> None:
    """The oversell toggle is gone — the store must never sell below zero."""
    result = runner.invoke(app, ["shopify-listings", "set-inventory-policy", STORE_ID, "-b", "{}"])
    assert result.exit_code != 0
    assert "No such command" in result.stderr or "set-inventory-policy" in result.stderr


@respx.mock
def test_publish_product_posts_full_body(
    env_pointing_at_fake_api: None,  # noqa: ARG001
    fake_api_url: str,
) -> None:
    """One-shot publish forwards product_ids + optional content to the new endpoint."""
    route = respx.post(
        f"{fake_api_url}/agent/stores/{STORE_ID}/draft-listings/publish-product"
    ).mock(return_value=httpx.Response(200, json={"results": [], "errors": []}))
    body = {
        "product_ids": ["p1", "p2"],
        "title": "Nice widget",
        "tags": ["a", "b"],
        "vendor": "Acme",
        "sell_prices": {"SKU-1": "19.99"},
        "compare_at_prices": {"SKU-1": "29.99"},
        "barcodes": {"SKU-1": "0123456789012"},
    }
    result = runner.invoke(
        app, ["shopify-listings", "publish-product", STORE_ID, "-b", json.dumps(body)]
    )
    assert result.exit_code == 0, result.stderr
    assert json.loads(route.calls.last.request.content) == body


@respx.mock
def test_create_drafts_forwards_optional_content_fields(
    env_pointing_at_fake_api: None,  # noqa: ARG001
    fake_api_url: str,
) -> None:
    """create-drafts now accepts the same optional content/price fields, not just product_ids."""
    route = respx.post(f"{fake_api_url}/agent/stores/{STORE_ID}/draft-listings").mock(
        return_value=httpx.Response(200, json={"results": [], "errors": []})
    )
    body = {
        "product_ids": ["p1"],
        "description": "Body HTML",
        "product_type": "Gadget",
        "sell_prices": {"SKU-1": "9.99"},
    }
    result = runner.invoke(
        app, ["shopify-listings", "create-drafts", STORE_ID, "-b", json.dumps(body)]
    )
    assert result.exit_code == 0, result.stderr
    assert json.loads(route.calls.last.request.content) == body


@respx.mock
def test_publish_works_without_publication_names(
    env_pointing_at_fake_api: None,  # noqa: ARG001
    fake_api_url: str,
) -> None:
    """Visibility toggle needs no channel — the backend defaults to the Online Store."""
    route = respx.post(f"{fake_api_url}/agent/stores/{STORE_ID}/listings/publish").mock(
        return_value=httpx.Response(200, json={"results": [], "errors": []})
    )
    result = runner.invoke(
        app,
        ["shopify-listings", "publish", STORE_ID, "-b", json.dumps({"product_ids": ["p1"]})],
    )
    assert result.exit_code == 0, result.stderr
    assert json.loads(route.calls.last.request.content) == {"product_ids": ["p1"]}


@respx.mock
def test_menu_get_substitutes_menu_id(
    env_pointing_at_fake_api: None,  # noqa: ARG001
    fake_api_url: str,
) -> None:
    route = respx.get(f"{fake_api_url}/agent/stores/{STORE_ID}/navigation/menus/9").mock(
        return_value=httpx.Response(200, json={"menu": {"id": "gid://shopify/Menu/9"}})
    )
    result = runner.invoke(app, ["shopify-menus", "get", STORE_ID, "9"])
    assert result.exit_code == 0, result.stderr
    assert route.call_count == 1
