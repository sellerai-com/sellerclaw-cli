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
PRODUCT_ID = "22222222-2222-4222-8222-222222222222"
CATEGORY = "66784"


@pytest.fixture
def env_pointing_at_fake_api(
    monkeypatch: pytest.MonkeyPatch,
    fake_api_url: str,
    fake_token: str,
) -> None:
    monkeypatch.setenv("SELLERCLAW_API_URL", fake_api_url)
    monkeypatch.setenv("SELLERCLAW_TOKEN", fake_token)


@respx.mock
def test_schema_posts_body(
    env_pointing_at_fake_api: None,  # noqa: ARG001
    fake_api_url: str,
) -> None:
    route = respx.post(f"{fake_api_url}/agent/attributes/schema").mock(
        return_value=httpx.Response(
            200, json={"platform": "ebay", "category_external_id": CATEGORY, "attributes": []}
        )
    )
    result = runner.invoke(
        app,
        [
            "attributes",
            "schema",
            "-b",
            json.dumps({"store_id": STORE_ID, "category_external_id": CATEGORY}),
        ],
    )
    assert result.exit_code == 0, result.stderr
    assert route.call_count == 1
    sent = json.loads(route.calls.last.request.content)
    assert sent == {"store_id": STORE_ID, "category_external_id": CATEGORY}


@respx.mock
def test_map_posts_body(
    env_pointing_at_fake_api: None,  # noqa: ARG001
    fake_api_url: str,
) -> None:
    route = respx.post(f"{fake_api_url}/agent/attributes/map").mock(
        return_value=httpx.Response(
            200,
            json={
                "variation_attributes": [],
                "common_attributes": [],
                "custom_attributes": [],
                "variations": [],
                "dropped": [],
                "missing_required": [],
                "warnings": [],
            },
        )
    )
    result = runner.invoke(
        app,
        [
            "attributes",
            "map",
            "-b",
            json.dumps(
                {
                    "store_id": STORE_ID,
                    "category_external_id": CATEGORY,
                    "product_id": PRODUCT_ID,
                }
            ),
        ],
    )
    assert result.exit_code == 0, result.stderr
    assert route.call_count == 1
    sent = json.loads(route.calls.last.request.content)
    assert sent == {
        "store_id": STORE_ID,
        "category_external_id": CATEGORY,
        "product_id": PRODUCT_ID,
    }


@respx.mock
def test_map_missing_required_field_is_rejected_client_side(
    env_pointing_at_fake_api: None,  # noqa: ARG001
    fake_api_url: str,
) -> None:
    route = respx.post(f"{fake_api_url}/agent/attributes/map").mock(
        return_value=httpx.Response(200, json={})
    )
    result = runner.invoke(
        app,
        ["attributes", "map", "-b", json.dumps({"store_id": STORE_ID})],
    )
    assert result.exit_code != 0
    assert route.call_count == 0  # never reaches the server with a known-bad body
