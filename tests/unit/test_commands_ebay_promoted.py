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
REPORT_TASK_ID = "rt-42"

_EFFECTIVENESS_JSON = {
    "report_task_id": REPORT_TASK_ID,
    "status": "COMPLETED",
    "report_href": "https://api.ebay.com/sell/marketing/v1/ad_report/9",
    "date_from": "2026-06-23T00:00:00.000Z",
    "date_to": "2026-06-30T00:00:00.000Z",
    "effectiveness": {
        "currency": "USD",
        "spend": "240.00",
        "ad_sales": "560.00",
        "clicks": 1230,
        "impressions": 69000,
        "sales": 13,
        "roas": "2.33",
        "acos_pct": 42.86,
        "ctr_pct": 1.78,
        "by_tool": [
            {
                "tool": "PROMOTED_LISTINGS",
                "pay_model": "per_sale",
                "spend": "90.00",
                "ad_sales": "410.00",
                "clicks": 880,
                "impressions": 42000,
                "sales": 10,
                "roas": "4.56",
                "acos_pct": 21.95,
                "ctr_pct": 2.10,
                "verdict": "SCALE",
            }
        ],
        "by_sku": [
            {
                "listing_id": "L1",
                "sku": "MUG-X",
                "title": "Mug X",
                "tool": "PROMOTED_LISTINGS",
                "spend": "90.00",
                "ad_sales": "410.00",
                "clicks": 880,
                "impressions": 42000,
                "sales": 10,
                "roas": "4.56",
                "acos_pct": 21.95,
                "ctr_pct": 2.10,
                "cpc": "0.10",
                "verdict": "SCALE",
            }
        ],
    },
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
def test_promoted_effectiveness_gets_breakdown(
    env_pointing_at_fake_api: None,  # noqa: ARG001
    fake_api_url: str,
) -> None:
    route = respx.get(
        f"{fake_api_url}/agent/ebay/stores/{STORE_ID}/promoted/reports/{REPORT_TASK_ID}/effectiveness"
    ).mock(return_value=httpx.Response(200, json=_EFFECTIVENESS_JSON))

    result = runner.invoke(app, ["ebay-promoted", "effectiveness", STORE_ID, REPORT_TASK_ID])

    assert result.exit_code == 0, result.stderr
    assert route.call_count == 1
    payload = json.loads(result.stdout)
    data = payload["data"]["effectiveness"]
    assert data["by_tool"][0]["verdict"] == "SCALE"
    assert data["by_sku"][0]["sku"] == "MUG-X"


@respx.mock
def test_promoted_create_report_forwards_days(
    env_pointing_at_fake_api: None,  # noqa: ARG001
    fake_api_url: str,
) -> None:
    route = respx.post(f"{fake_api_url}/agent/ebay/stores/{STORE_ID}/promoted/reports").mock(
        return_value=httpx.Response(202, json={"report_task_id": REPORT_TASK_ID, "status": "PENDING"})
    )

    result = runner.invoke(app, ["ebay-promoted", "create-report", STORE_ID, "--days", "30"])

    assert result.exit_code == 0, result.stderr
    assert route.calls.last.request.url.params["days"] == "30"


@respx.mock
def test_promoted_create_report_rejects_out_of_range_days_locally(
    env_pointing_at_fake_api: None,  # noqa: ARG001
    fake_api_url: str,
) -> None:
    route = respx.post(f"{fake_api_url}/agent/ebay/stores/{STORE_ID}/promoted/reports").mock(
        return_value=httpx.Response(202, json={"report_task_id": REPORT_TASK_ID})
    )

    result = runner.invoke(app, ["ebay-promoted", "create-report", STORE_ID, "--days", "365"])

    assert result.exit_code != 0
    assert route.call_count == 0
