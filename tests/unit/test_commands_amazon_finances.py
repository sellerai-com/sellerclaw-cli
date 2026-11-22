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


@pytest.mark.parametrize(
    ("argv", "path", "params"),
    [
        pytest.param(["summary", STORE_ID, "--days", "14"], "summary", {"days": "14"}, id="summary"),
        pytest.param(
            ["payouts", STORE_ID, "--days", "60", "--limit", "5"], "payouts", {"days": "60", "limit": "5"}, id="payouts"
        ),
        pytest.param(["order", STORE_ID, "113-1234567-1234567"], "orders/113-1234567-1234567", {}, id="order"),
    ],
)
@respx.mock
def test_amazon_finances_reads_the_endpoint_asked(
    env_pointing_at_fake_api: None,  # noqa: ARG001
    fake_api_url: str,
    argv: list[str],
    path: str,
    params: dict[str, str],
) -> None:
    route = respx.get(f"{fake_api_url}/agent/amazon/stores/{STORE_ID}/finances/{path}").mock(
        return_value=httpx.Response(200, json={"ok": True})
    )

    result = runner.invoke(app, ["amazon-finances", *argv])

    assert result.exit_code == 0, result.stderr
    assert dict(route.calls.last.request.url.params) == params
    assert json.loads(result.stdout)["data"] == {"ok": True}


def test_amazon_finances_summary_refuses_a_window_amazon_would(env_pointing_at_fake_api: None) -> None:  # noqa: ARG001
    result = runner.invoke(app, ["amazon-finances", "summary", STORE_ID, "--days", "400"])

    assert result.exit_code != 0
