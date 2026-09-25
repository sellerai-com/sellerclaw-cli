from __future__ import annotations

import json

import httpx
import pytest
import respx
from typer.testing import CliRunner

from sellerclaw_cli.cli import app

pytestmark = pytest.mark.unit

runner = CliRunner()

ORDER_ID = "44444444-4444-4444-8444-444444444444"


@pytest.fixture
def env_pointing_at_fake_api(
    monkeypatch: pytest.MonkeyPatch,
    fake_api_url: str,
    fake_token: str,
) -> None:
    monkeypatch.setenv("SELLERCLAW_API_URL", fake_api_url)
    monkeypatch.setenv("SELLERCLAW_TOKEN", fake_token)


@respx.mock
def test_set_shipped_posts_the_tracking_to_the_order(
    env_pointing_at_fake_api: None,  # noqa: ARG001
    fake_api_url: str,
) -> None:
    route = respx.post(f"{fake_api_url}/agent/orders/{ORDER_ID}/shipped").mock(
        return_value=httpx.Response(200, json={"id": ORDER_ID, "status": "fulfilled"})
    )
    result = runner.invoke(
        app,
        [
            "orders",
            "set-shipped",
            ORDER_ID,
            "-b",
            json.dumps({"tracking_number": "1Z999AA10123456784", "tracking_carrier": "UPS"}),
        ],
    )
    assert result.exit_code == 0, result.stderr
    body = json.loads(route.calls.last.request.content)
    assert body == {"tracking_number": "1Z999AA10123456784", "tracking_carrier": "UPS"}


@respx.mock
def test_set_shipped_accepts_a_shipment_with_no_tracking_at_all(
    env_pointing_at_fake_api: None,  # noqa: ARG001
    fake_api_url: str,
) -> None:
    """A channel lets an order be marked sent without a number — the CLI must not demand one."""
    route = respx.post(f"{fake_api_url}/agent/orders/{ORDER_ID}/shipped").mock(
        return_value=httpx.Response(200, json={"id": ORDER_ID, "status": "fulfilled"})
    )
    result = runner.invoke(app, ["orders", "set-shipped", ORDER_ID, "-b", "{}"])
    assert result.exit_code == 0, result.stderr
    assert route.call_count == 1


def test_set_shipped_rejects_an_unknown_body_field(
    env_pointing_at_fake_api: None,  # noqa: ARG001
) -> None:
    """Local schema validation: a misspelled field fails here instead of at the API."""
    result = runner.invoke(
        app,
        ["orders", "set-shipped", ORDER_ID, "-b", json.dumps({"tracking": "1Z999"})],
    )
    assert result.exit_code != 0
    assert "tracking" in (result.stderr or result.stdout)


@respx.mock
def test_set_shipped_works_with_no_body_flag_at_all(
    env_pointing_at_fake_api: None,  # noqa: ARG001
    fake_api_url: str,
) -> None:
    """Closing an order the channel shipped without a number takes no `-b` — and must stay that way."""
    route = respx.post(f"{fake_api_url}/agent/orders/{ORDER_ID}/shipped").mock(
        return_value=httpx.Response(200, json={"id": ORDER_ID, "status": "fulfilled"})
    )
    result = runner.invoke(app, ["orders", "set-shipped", ORDER_ID])
    assert result.exit_code == 0, result.stderr
    assert route.calls.last.request.content == b""


@pytest.mark.parametrize(
    ("reference", "path"),
    [
        pytest.param("#1001", "/agent/orders/%231001", id="hash-would-start-the-fragment"),
        pytest.param("14-15000-75039", "/agent/orders/14-15000-75039", id="marketplace-id"),
        pytest.param(ORDER_ID, f"/agent/orders/{ORDER_ID}", id="our-id-unchanged"),
    ],
)
@respx.mock
def test_get_sends_the_order_number_as_one_path_segment(
    env_pointing_at_fake_api: None,  # noqa: ARG001
    fake_api_url: str,
    reference: str,
    path: str,
) -> None:
    """``#1001`` put in the URL as it is starts the fragment: the request reached the order list."""
    route = respx.get(url__startswith=f"{fake_api_url}/agent/orders/").mock(
        return_value=httpx.Response(200, json={"id": ORDER_ID})
    )
    result = runner.invoke(app, ["orders", "get", reference])
    assert result.exit_code == 0, result.stderr
    assert route.call_count == 1
    assert route.calls.last.request.url.raw_path.decode() == path
