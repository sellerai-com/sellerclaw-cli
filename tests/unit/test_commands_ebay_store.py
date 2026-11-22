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
POLICY_ID = "55555555-5555-4555-8555-555555555555"
_POLICY_JSON = {"id": POLICY_ID, "policy_type": "fulfillment", "name": "Free 2-day", "used_by_products": 12}


@pytest.fixture
def env_pointing_at_fake_api(
    monkeypatch: pytest.MonkeyPatch,
    fake_api_url: str,
    fake_token: str,
) -> None:
    monkeypatch.setenv("SELLERCLAW_API_URL", fake_api_url)
    monkeypatch.setenv("SELLERCLAW_TOKEN", fake_token)


@respx.mock
def test_create_policy_posts_the_type_and_ebays_shape(
    env_pointing_at_fake_api: None,  # noqa: ARG001
    fake_api_url: str,
) -> None:
    route = respx.post(f"{fake_api_url}/agent/stores/{STORE_ID}/policies").mock(
        return_value=httpx.Response(201, json=_POLICY_JSON)
    )
    body = {"type": "fulfillment", "policy": {"name": "Free 2-day", "handlingTime": {"value": 1, "unit": "DAY"}}}

    result = runner.invoke(app, ["ebay-store", "create-policy", STORE_ID, "-b", json.dumps(body)])

    assert result.exit_code == 0, result.stderr
    assert json.loads(route.calls.last.request.content) == body
    assert json.loads(result.stdout)["data"]["id"] == POLICY_ID


@pytest.mark.parametrize(
    "body",
    [
        pytest.param({"type": "shipping", "policy": {"name": "x"}}, id="unknown_type"),
        pytest.param({"type": "return"}, id="no_policy"),
    ],
)
@respx.mock
def test_create_policy_refuses_a_malformed_body_locally(
    env_pointing_at_fake_api: None,  # noqa: ARG001
    fake_api_url: str,
    body: dict[str, object],
) -> None:
    route = respx.post(f"{fake_api_url}/agent/stores/{STORE_ID}/policies").mock(
        return_value=httpx.Response(201, json=_POLICY_JSON)
    )

    result = runner.invoke(app, ["ebay-store", "create-policy", STORE_ID, "-b", json.dumps(body)])

    assert result.exit_code != 0
    assert route.call_count == 0


@respx.mock
def test_update_policy_patches_only_the_changes(
    env_pointing_at_fake_api: None,  # noqa: ARG001
    fake_api_url: str,
) -> None:
    route = respx.patch(f"{fake_api_url}/agent/stores/{STORE_ID}/policies/{POLICY_ID}").mock(
        return_value=httpx.Response(200, json=_POLICY_JSON)
    )
    body = {"changes": {"handlingTime": {"value": 2, "unit": "DAY"}}}

    result = runner.invoke(app, ["ebay-store", "update-policy", STORE_ID, POLICY_ID, "-b", json.dumps(body)])

    assert result.exit_code == 0, result.stderr
    assert json.loads(route.calls.last.request.content) == body
