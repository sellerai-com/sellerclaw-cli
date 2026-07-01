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
ORDER_ID = "12-34567-89012"

_REPORT_JSON = {
    "store_id": STORE_ID,
    "generated_at": "2026-06-30T12:00:00Z",
    "window_days": 30,
    "awaiting_shipment_count": 1,
    "in_transit_count": 2,
    "overdue_count": 1,
    "shipments": [],
    "awaiting_shipment": [],
    "carriers": [],
    "truncated": False,
}

_TRACKING_JSON = {
    "order_id": ORDER_ID,
    "trackings": [
        {
            "carrier_code": "USPS",
            "carrier_name": "USPS",
            "tracking_number": "T1",
            "tracking_url": "https://tools.usps.com/go/TrackConfirmAction?tLabels=T1",
        }
    ],
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
def test_shipping_report_forwards_flags(
    env_pointing_at_fake_api: None,
    fake_api_url: str,
) -> None:
    route = respx.get(f"{fake_api_url}/agent/ebay/stores/{STORE_ID}/shipping/report").mock(
        return_value=httpx.Response(200, json=_REPORT_JSON)
    )
    result = runner.invoke(
        app,
        ["ebay-shipping", "report", STORE_ID, "--window-days", "7", "--stuck-after-days", "5"],
    )
    assert result.exit_code == 0, result.stderr
    assert route.calls.last.request.url.params["window_days"] == "7"
    assert route.calls.last.request.url.params["stuck_after_days"] == "5"
    payload = json.loads(result.stdout)
    assert payload["data"]["overdue_count"] == 1


@respx.mock
def test_shipping_report_defaults_omit_flags(
    env_pointing_at_fake_api: None,
    fake_api_url: str,
) -> None:
    route = respx.get(f"{fake_api_url}/agent/ebay/stores/{STORE_ID}/shipping/report").mock(
        return_value=httpx.Response(200, json=_REPORT_JSON)
    )
    result = runner.invoke(app, ["ebay-shipping", "report", STORE_ID])
    assert result.exit_code == 0, result.stderr
    # Defaults are documentation-only; the CLI does not send them unless the user passes a flag.
    assert "window_days" not in route.calls.last.request.url.params
    assert "stuck_after_days" not in route.calls.last.request.url.params


@respx.mock
def test_shipping_report_rejects_out_of_range_window_locally(
    env_pointing_at_fake_api: None,
    fake_api_url: str,
) -> None:
    route = respx.get(f"{fake_api_url}/agent/ebay/stores/{STORE_ID}/shipping/report").mock(
        return_value=httpx.Response(200, json=_REPORT_JSON)
    )
    result = runner.invoke(app, ["ebay-shipping", "report", STORE_ID, "--window-days", "200"])
    assert result.exit_code != 0
    assert route.call_count == 0  # validation failed locally; the API was never called


@respx.mock
def test_order_tracking_hits_path(
    env_pointing_at_fake_api: None,
    fake_api_url: str,
) -> None:
    route = respx.get(
        f"{fake_api_url}/agent/ebay/stores/{STORE_ID}/orders/{ORDER_ID}/tracking"
    ).mock(return_value=httpx.Response(200, json=_TRACKING_JSON))
    result = runner.invoke(app, ["ebay-shipping", "tracking", STORE_ID, ORDER_ID])
    assert result.exit_code == 0, result.stderr
    assert route.call_count == 1
    payload = json.loads(result.stdout)
    assert payload["data"]["trackings"][0]["tracking_url"].endswith("tLabels=T1")
