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

# The report is computed asynchronously; the command only gets a queued acknowledgement back.
_QUEUED_JSON = {"status": "queued", "store_id": STORE_ID, "period": "last_30d"}


@pytest.fixture
def env_pointing_at_fake_api(
    monkeypatch: pytest.MonkeyPatch,
    fake_api_url: str,
    fake_token: str,
) -> None:
    monkeypatch.setenv("SELLERCLAW_API_URL", fake_api_url)
    monkeypatch.setenv("SELLERCLAW_TOKEN", fake_token)


@respx.mock
def test_analytics_report_posts_and_substitutes_store_id(
    env_pointing_at_fake_api: None,  # noqa: ARG001
    fake_api_url: str,
) -> None:
    route = respx.post(f"{fake_api_url}/agent/analytics/stores/{STORE_ID}/report").mock(
        return_value=httpx.Response(202, json=_QUEUED_JSON)
    )
    result = runner.invoke(app, ["analytics", "report", STORE_ID])
    assert result.exit_code == 0, result.stderr
    assert route.call_count == 1
    assert "period" not in route.calls.last.request.url.params
    payload = json.loads(result.stdout)
    assert payload["data"]["status"] == "queued"


@respx.mock
def test_analytics_report_forwards_period_flag(
    env_pointing_at_fake_api: None,  # noqa: ARG001
    fake_api_url: str,
) -> None:
    route = respx.post(f"{fake_api_url}/agent/analytics/stores/{STORE_ID}/report").mock(
        return_value=httpx.Response(202, json=_QUEUED_JSON)
    )
    result = runner.invoke(app, ["analytics", "report", STORE_ID, "--period", "last_7d"])
    assert result.exit_code == 0, result.stderr
    assert route.calls.last.request.url.params["period"] == "last_7d"


@respx.mock
def test_analytics_report_rejects_bad_period_locally(
    env_pointing_at_fake_api: None,  # noqa: ARG001
    fake_api_url: str,
) -> None:
    route = respx.post(f"{fake_api_url}/agent/analytics/stores/{STORE_ID}/report").mock(
        return_value=httpx.Response(202, json=_QUEUED_JSON)
    )
    result = runner.invoke(app, ["analytics", "report", STORE_ID, "--period", "bogus"])
    assert result.exit_code != 0
    assert route.call_count == 0


_METRICS_JSON = {
    "store_id": STORE_ID,
    "period": "this_month",
    "period_start": "2026-06-01T00:00:00Z",
    "period_end": "2026-06-12T00:00:00Z",
    "currency": "USD",
    "revenue": "500",
    "order_count": 4,
    "aov": "125",
    "revenue_previous": "0",
    "aov_previous": None,
    "revenue_trend_pct": None,
    "aov_trend_pct": None,
    "product_count": 3,
    "sold_sku_count": 3,
    "sleeping_sku_count": 0,
    "abc_tiers": [],
    "top_skus": [],
}


@respx.mock
def test_analytics_metrics_gets_and_forwards_period_and_top(
    env_pointing_at_fake_api: None,  # noqa: ARG001
    fake_api_url: str,
) -> None:
    route = respx.get(f"{fake_api_url}/agent/analytics/stores/{STORE_ID}/metrics").mock(
        return_value=httpx.Response(200, json=_METRICS_JSON)
    )
    result = runner.invoke(
        app, ["analytics", "metrics", STORE_ID, "--period", "this_month", "--top", "5"]
    )
    assert result.exit_code == 0, result.stderr
    assert route.call_count == 1
    params = route.calls.last.request.url.params
    assert params["period"] == "this_month"
    assert params["top"] == "5"
    # Default reads the mirror — no live bypass is requested.
    assert "fresh" not in params


@respx.mock
def test_analytics_metrics_forwards_fresh_flag(
    env_pointing_at_fake_api: None,  # noqa: ARG001
    fake_api_url: str,
) -> None:
    route = respx.get(f"{fake_api_url}/agent/analytics/stores/{STORE_ID}/metrics").mock(
        return_value=httpx.Response(200, json=_METRICS_JSON)
    )
    result = runner.invoke(app, ["analytics", "metrics", STORE_ID, "--fresh"])
    assert result.exit_code == 0, result.stderr
    assert route.calls.last.request.url.params["fresh"] == "true"
