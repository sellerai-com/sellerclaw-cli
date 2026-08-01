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


_INVENTORY_JSON = {
    "store_id": STORE_ID,
    "period": "last_30d",
    "period_start": "2026-05-13T00:00:00Z",
    "period_end": "2026-06-12T00:00:00Z",
    "currency": "USD",
    "lead_time_days": 14,
    "lead_time_is_default": True,
    "velocity_days": 30,
    "stockouts": [],
    "out_of_stock_count": 0,
    "total_lost_revenue_per_day": "0",
    "reorders": [],
    "reorder_count": 0,
}


@respx.mock
def test_analytics_inventory_gets_and_forwards_period_and_top(
    env_pointing_at_fake_api: None,  # noqa: ARG001
    fake_api_url: str,
) -> None:
    route = respx.get(f"{fake_api_url}/agent/analytics/stores/{STORE_ID}/inventory").mock(
        return_value=httpx.Response(200, json=_INVENTORY_JSON)
    )
    result = runner.invoke(
        app, ["analytics", "inventory", STORE_ID, "--period", "last_7d", "--top", "5"]
    )
    assert result.exit_code == 0, result.stderr
    assert route.call_count == 1
    params = route.calls.last.request.url.params
    assert params["period"] == "last_7d"
    assert params["top"] == "5"


@respx.mock
def test_analytics_inventory_rejects_bad_period_locally(
    env_pointing_at_fake_api: None,  # noqa: ARG001
    fake_api_url: str,
) -> None:
    route = respx.get(f"{fake_api_url}/agent/analytics/stores/{STORE_ID}/inventory").mock(
        return_value=httpx.Response(200, json=_INVENTORY_JSON)
    )
    result = runner.invoke(app, ["analytics", "inventory", STORE_ID, "--period", "bogus"])
    assert result.exit_code != 0
    assert route.call_count == 0


@respx.mock
def test_analytics_inventory_rejects_out_of_range_top_locally(
    env_pointing_at_fake_api: None,  # noqa: ARG001
    fake_api_url: str,
) -> None:
    route = respx.get(f"{fake_api_url}/agent/analytics/stores/{STORE_ID}/inventory").mock(
        return_value=httpx.Response(200, json=_INVENTORY_JSON)
    )
    result = runner.invoke(app, ["analytics", "inventory", STORE_ID, "--top", "500"])
    assert result.exit_code != 0
    assert route.call_count == 0


_DIGEST_JSON = {
    "store_id": STORE_ID,
    "platform": "ebay",
    "generated_at": "2026-06-30T12:00:00Z",
    "headline": {
        "orders_to_ship": 2,
        "shipments_overdue": 1,
        "disputes_open": 0,
        "disputes_overdue": 0,
        "amount_at_risk": "0",
        "amount_at_risk_currency": None,
        "out_of_stock": 3,
        "reorders_due": 1,
        "account_level": "TOP_RATED",
        "account_at_risk": False,
        "attention_count": 3,
        "has_errors": False,
    },
    "orders": {"awaiting_count": 2, "top_oldest": [], "truncated": False, "error": None},
    "inventory": {
        "available": True,
        "out_of_stock_count": 3,
        "total_lost_revenue_per_day": "40",
        "currency": "USD",
        "reorder_count": 1,
        "lead_time_days": 14,
        "lead_time_is_default": True,
        "top_stockouts": [],
        "top_reorders": [],
        "error": None,
    },
    "shipping": {
        "available": True,
        "in_transit_count": 3,
        "overdue_count": 1,
        "top_overdue": [],
        "truncated": False,
        "error": None,
    },
    "disputes": {
        "available": True,
        "total_open": 0,
        "overdue_count": 0,
        "amount_at_risk": "0",
        "currency": None,
        "soonest_respond_by": None,
        "top_urgent": [],
        "error": None,
    },
    "account_health": {
        "available": True,
        "level": "TOP_RATED",
        "at_risk": False,
        "closest_metric": None,
        "metrics": [],
        "error": None,
    },
}


@respx.mock
def test_analytics_operations_digest_gets_and_substitutes_store_id(
    env_pointing_at_fake_api: None,  # noqa: ARG001
    fake_api_url: str,
) -> None:
    route = respx.get(f"{fake_api_url}/agent/stores/{STORE_ID}/operations-digest").mock(
        return_value=httpx.Response(200, json=_DIGEST_JSON)
    )
    result = runner.invoke(app, ["analytics", "operations-digest", STORE_ID])
    assert result.exit_code == 0, result.stderr
    assert route.call_count == 1
    # No window flag → the server default applies (velocity_period not sent).
    assert "velocity_period" not in route.calls.last.request.url.params
    payload = json.loads(result.stdout)
    assert payload["data"]["headline"]["attention_count"] == 3


@respx.mock
def test_analytics_operations_digest_forwards_velocity_period(
    env_pointing_at_fake_api: None,  # noqa: ARG001
    fake_api_url: str,
) -> None:
    route = respx.get(f"{fake_api_url}/agent/stores/{STORE_ID}/operations-digest").mock(
        return_value=httpx.Response(200, json=_DIGEST_JSON)
    )
    result = runner.invoke(
        app, ["analytics", "operations-digest", STORE_ID, "--velocity-period", "last_7d"]
    )
    assert result.exit_code == 0, result.stderr
    assert route.calls.last.request.url.params["velocity_period"] == "last_7d"


@respx.mock
def test_analytics_operations_digest_rejects_bad_period_locally(
    env_pointing_at_fake_api: None,  # noqa: ARG001
    fake_api_url: str,
) -> None:
    route = respx.get(f"{fake_api_url}/agent/stores/{STORE_ID}/operations-digest").mock(
        return_value=httpx.Response(200, json=_DIGEST_JSON)
    )
    result = runner.invoke(
        app, ["analytics", "operations-digest", STORE_ID, "--velocity-period", "bogus"]
    )
    assert result.exit_code != 0
    assert route.call_count == 0


# --- The shared window + store-selection contract ---------------------------------------------


@pytest.mark.parametrize(
    ("cli_args", "expected_params"),
    [
        pytest.param(["--week", "0"], {"week": "0"}, id="completed_week"),
        pytest.param(["--month", "3"], {"month": "3"}, id="completed_month"),
        pytest.param(
            ["--from", "2026-03-01", "--to", "2026-03-31"],
            {"from": "2026-03-01", "to": "2026-03-31"},
            id="explicit_range_uses_bare_from_and_to_keys",
        ),
        pytest.param(["--period", "last_month"], {"period": "last_month"}, id="last_month_keyword"),
    ],
)
@respx.mock
def test_analytics_metrics_forwards_every_window_form(
    env_pointing_at_fake_api: None,  # noqa: ARG001
    fake_api_url: str,
    cli_args: list[str],
    expected_params: dict[str, str],
) -> None:
    route = respx.get(f"{fake_api_url}/agent/analytics/stores/{STORE_ID}/metrics").mock(
        return_value=httpx.Response(200, json=_METRICS_JSON)
    )
    result = runner.invoke(app, ["analytics", "metrics", STORE_ID, *cli_args])
    assert result.exit_code == 0, result.stderr
    params = route.calls.last.request.url.params
    for key, value in expected_params.items():
        assert params[key] == value


@respx.mock
def test_analytics_metrics_rejects_an_out_of_range_week_locally(
    env_pointing_at_fake_api: None,  # noqa: ARG001
    fake_api_url: str,
) -> None:
    """Bad offsets fail before the round-trip, so the caller sees the limit rather than a 422."""
    route = respx.get(f"{fake_api_url}/agent/analytics/stores/{STORE_ID}/metrics").mock(
        return_value=httpx.Response(200, json=_METRICS_JSON)
    )
    result = runner.invoke(app, ["analytics", "metrics", STORE_ID, "--week", "99"])
    assert result.exit_code != 0
    assert route.call_count == 0


@respx.mock
def test_analytics_metrics_repeats_the_store_flag_for_an_aggregate(
    env_pointing_at_fake_api: None,  # noqa: ARG001
    fake_api_url: str,
) -> None:
    other = "22222222-2222-4222-8222-222222222222"
    route = respx.get(f"{fake_api_url}/agent/analytics/stores/{STORE_ID}/metrics").mock(
        return_value=httpx.Response(200, json=_METRICS_JSON)
    )
    result = runner.invoke(app, ["analytics", "metrics", STORE_ID, "--store", other])
    assert result.exit_code == 0, result.stderr
    assert route.calls.last.request.url.params.get_list("store") == [other]


@respx.mock
def test_analytics_metrics_accepts_all_in_place_of_a_store_id(
    env_pointing_at_fake_api: None,  # noqa: ARG001
    fake_api_url: str,
) -> None:
    """`all` is the whole-business selection — it must reach the API untouched, not be resolved."""
    route = respx.get(f"{fake_api_url}/agent/analytics/stores/all/metrics").mock(
        return_value=httpx.Response(200, json=_METRICS_JSON)
    )
    result = runner.invoke(app, ["analytics", "metrics", "all"])
    assert result.exit_code == 0, result.stderr
    assert route.call_count == 1


@respx.mock
def test_analytics_metrics_forwards_with_fees(
    env_pointing_at_fake_api: None,  # noqa: ARG001
    fake_api_url: str,
) -> None:
    route = respx.get(f"{fake_api_url}/agent/analytics/stores/{STORE_ID}/metrics").mock(
        return_value=httpx.Response(200, json=_METRICS_JSON)
    )
    result = runner.invoke(app, ["analytics", "metrics", STORE_ID, "--with-fees"])
    assert result.exit_code == 0, result.stderr
    assert route.calls.last.request.url.params["with_fees"] == "true"


# --- geography / capital ----------------------------------------------------------------------


_GEOGRAPHY_JSON = {
    "store_id": STORE_ID,
    "period": "iso_week",
    "period_start": "2026-06-01T00:00:00Z",
    "period_end": "2026-06-07T23:59:59Z",
    "total_orders": 100,
    "countries": [
        {"country_code": "US", "order_count": 90, "order_share": 0.9, "share_delta_pp": 2.0}
    ],
    "primary_country": "US",
    "primary_country_regions": [{"region": "CA", "order_count": 22, "order_share": 0.244}],
}


@respx.mock
def test_analytics_geography_gets_and_forwards_the_window(
    env_pointing_at_fake_api: None,  # noqa: ARG001
    fake_api_url: str,
) -> None:
    route = respx.get(f"{fake_api_url}/agent/analytics/stores/{STORE_ID}/geography").mock(
        return_value=httpx.Response(200, json=_GEOGRAPHY_JSON)
    )
    result = runner.invoke(app, ["analytics", "geography", STORE_ID, "--week", "0"])
    assert result.exit_code == 0, result.stderr
    assert route.calls.last.request.url.params["week"] == "0"
    payload = json.loads(result.stdout)
    assert payload["data"]["primary_country"] == "US"


_CAPITAL_JSON = {
    "currency": "USD",
    "tied_up_value": "4200",
    "dead_stock_value": "900",
    "dead_stock_lookback_days": 180,
    "valued_units": 60,
    "total_units": 100,
    "coverage_pct": 0.6,
}


@respx.mock
def test_analytics_capital_gets_and_forwards_dead_after(
    env_pointing_at_fake_api: None,  # noqa: ARG001
    fake_api_url: str,
) -> None:
    route = respx.get(f"{fake_api_url}/agent/analytics/stores/{STORE_ID}/capital").mock(
        return_value=httpx.Response(200, json=_CAPITAL_JSON)
    )
    result = runner.invoke(app, ["analytics", "capital", STORE_ID, "--dead-after", "180"])
    assert result.exit_code == 0, result.stderr
    assert route.calls.last.request.url.params["dead_after"] == "180"
    payload = json.loads(result.stdout)
    assert payload["data"]["coverage_pct"] == 0.6


@respx.mock
def test_analytics_capital_rejects_a_period_flag(
    env_pointing_at_fake_api: None,  # noqa: ARG001
    fake_api_url: str,
) -> None:
    """Stock has no history, so offering a period would promise something we cannot answer."""
    route = respx.get(f"{fake_api_url}/agent/analytics/stores/{STORE_ID}/capital").mock(
        return_value=httpx.Response(200, json=_CAPITAL_JSON)
    )
    result = runner.invoke(app, ["analytics", "capital", STORE_ID, "--period", "last_30d"])
    assert result.exit_code != 0
    assert route.call_count == 0


@respx.mock
def test_analytics_timeseries_buckets_the_window_without_a_count(
    env_pointing_at_fake_api: None,  # noqa: ARG001
    fake_api_url: str,
) -> None:
    """Omitting --buckets means "chart this whole window", so no count is sent."""
    route = respx.get(f"{fake_api_url}/agent/analytics/stores/{STORE_ID}/timeseries").mock(
        return_value=httpx.Response(
            200, json={"store_id": STORE_ID, "granularity": "day", "points": []}
        )
    )
    result = runner.invoke(
        app, ["analytics", "timeseries", STORE_ID, "--month", "0", "--granularity", "day"]
    )
    assert result.exit_code == 0, result.stderr
    params = route.calls.last.request.url.params
    assert params["month"] == "0"
    assert params["granularity"] == "day"
    assert "buckets" not in params
