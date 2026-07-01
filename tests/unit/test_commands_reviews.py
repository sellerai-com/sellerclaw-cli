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

_REVIEWS_JSON = {
    "reviews": [
        {
            "review_id": "rev-1",
            "rating": 2,
            "title": None,
            "text": "Arrived cracked.",
            "author": "Alex",
            "created_at": "2026-06-20T10:00:00Z",
            "product_id": "14",
            "product_title": "Blue Mug",
            "status": "approved",
            "reply": None,
            "verified": True,
        }
    ],
    "total": 1,
    "average_rating": 2.0,
    "low_rating_count": 1,
    "truncated": False,
}


@pytest.fixture
def env_pointing_at_fake_api(
    monkeypatch: pytest.MonkeyPatch,
    fake_api_url: str,
    fake_token: str,
) -> None:
    monkeypatch.setenv("SELLERCLAW_API_URL", fake_api_url)
    monkeypatch.setenv("SELLERCLAW_TOKEN", fake_token)


@respx.mock
def test_reviews_list_gets_and_substitutes_store_id(
    env_pointing_at_fake_api: None,  # noqa: ARG001
    fake_api_url: str,
) -> None:
    route = respx.get(f"{fake_api_url}/agent/stores/{STORE_ID}/reviews").mock(
        return_value=httpx.Response(200, json=_REVIEWS_JSON)
    )
    result = runner.invoke(app, ["reviews", "list", STORE_ID])
    assert result.exit_code == 0, result.stderr
    assert route.call_count == 1
    assert "limit" not in route.calls.last.request.url.params
    assert "fresh" not in route.calls.last.request.url.params
    payload = json.loads(result.stdout)
    assert payload["data"]["total"] == 1


@respx.mock
def test_reviews_list_forwards_limit_and_fresh(
    env_pointing_at_fake_api: None,  # noqa: ARG001
    fake_api_url: str,
) -> None:
    route = respx.get(f"{fake_api_url}/agent/stores/{STORE_ID}/reviews").mock(
        return_value=httpx.Response(200, json=_REVIEWS_JSON)
    )
    result = runner.invoke(app, ["reviews", "list", STORE_ID, "--limit", "50", "--fresh"])
    assert result.exit_code == 0, result.stderr
    params = route.calls.last.request.url.params
    assert params["limit"] == "50"
    assert params["fresh"] == "true"


@respx.mock
def test_reviews_list_rejects_out_of_range_limit_locally(
    env_pointing_at_fake_api: None,  # noqa: ARG001
    fake_api_url: str,
) -> None:
    route = respx.get(f"{fake_api_url}/agent/stores/{STORE_ID}/reviews").mock(
        return_value=httpx.Response(200, json=_REVIEWS_JSON)
    )
    result = runner.invoke(app, ["reviews", "list", STORE_ID, "--limit", "9000"])
    assert result.exit_code != 0
    assert route.call_count == 0


@respx.mock
def test_reviews_bigcommerce_requires_and_forwards_product_id(
    env_pointing_at_fake_api: None,  # noqa: ARG001
    fake_api_url: str,
) -> None:
    route = respx.get(f"{fake_api_url}/agent/bigcommerce/stores/{STORE_ID}/reviews").mock(
        return_value=httpx.Response(200, json=_REVIEWS_JSON)
    )
    result = runner.invoke(
        app, ["reviews", "bigcommerce", STORE_ID, "--product-id", "77", "--limit", "25"]
    )
    assert result.exit_code == 0, result.stderr
    params = route.calls.last.request.url.params
    assert params["product_id"] == "77"
    assert params["limit"] == "25"


@respx.mock
def test_reviews_bigcommerce_rejects_missing_product_id_locally(
    env_pointing_at_fake_api: None,  # noqa: ARG001
    fake_api_url: str,
) -> None:
    route = respx.get(f"{fake_api_url}/agent/bigcommerce/stores/{STORE_ID}/reviews").mock(
        return_value=httpx.Response(200, json=_REVIEWS_JSON)
    )
    result = runner.invoke(app, ["reviews", "bigcommerce", STORE_ID])
    assert result.exit_code != 0
    assert route.call_count == 0
