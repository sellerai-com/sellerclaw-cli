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

_PERFORMANCE_JSON = {
    "window_start": "2026-06-20",
    "window_end": "2026-06-27",
    "currency": "USD",
    "last_updated": "2026-06-27T00:00:00.000Z",
    "median_conversion_rate": 1.75,
    "listings_to_improve": 1,
    "avg_completeness_pct": 0.26,
    "lost_traffic_views": 160,
    "opportunity_total": 40.0,
    "rows": [],
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
def test_performance_gets_report_and_substitutes_store_id(
    env_pointing_at_fake_api: None,  # noqa: ARG001
    fake_api_url: str,
) -> None:
    route = respx.get(
        f"{fake_api_url}/agent/ebay/stores/{STORE_ID}/listing-performance"
    ).mock(return_value=httpx.Response(200, json=_PERFORMANCE_JSON))

    result = runner.invoke(app, ["ebay-listings", "performance", STORE_ID])

    assert result.exit_code == 0, result.stderr
    assert route.call_count == 1
    # Unset flags are dropped, so the server defaults apply.
    assert "days" not in route.calls.last.request.url.params
    assert "top_n" not in route.calls.last.request.url.params
    payload = json.loads(result.stdout)
    assert payload["data"]["listings_to_improve"] == 1


@respx.mock
def test_performance_forwards_days_and_top_n_flags(
    env_pointing_at_fake_api: None,  # noqa: ARG001
    fake_api_url: str,
) -> None:
    route = respx.get(
        f"{fake_api_url}/agent/ebay/stores/{STORE_ID}/listing-performance"
    ).mock(return_value=httpx.Response(200, json=_PERFORMANCE_JSON))

    result = runner.invoke(
        app,
        ["ebay-listings", "performance", STORE_ID, "--days", "14", "--top-n", "5"],
    )

    assert result.exit_code == 0, result.stderr
    params = route.calls.last.request.url.params
    assert params["days"] == "14"
    assert params["top_n"] == "5"
