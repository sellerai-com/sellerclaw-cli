"""The account group: the owner's profile, settings and connections, and their plan and credits."""

from __future__ import annotations

import json

import httpx
import pytest
import respx
from typer.testing import CliRunner

from sellerclaw_cli.cli import app

pytestmark = pytest.mark.unit

runner = CliRunner()


@pytest.fixture
def env_pointing_at_fake_api(
    monkeypatch: pytest.MonkeyPatch,
    fake_api_url: str,
    fake_token: str,
) -> None:
    monkeypatch.setenv("SELLERCLAW_API_URL", fake_api_url)
    monkeypatch.setenv("SELLERCLAW_TOKEN", fake_token)


@respx.mock
def test_billing_reads_the_plan_credits_and_spend_in_one_call(
    env_pointing_at_fake_api: None,  # noqa: ARG001
    fake_api_url: str,
) -> None:
    answer = {
        "balance": {"subscription_state": "active", "active_period": {"balance": "12360"}},
        "usage": {"total_credits": "7640", "categories": []},
        "preferences": {"exhaustion_strategy": "soft_block"},
    }
    route = respx.get(f"{fake_api_url}/agent/billing/overview").mock(
        return_value=httpx.Response(200, json=answer)
    )

    result = runner.invoke(app, ["account", "billing"])

    assert result.exit_code == 0, result.stderr
    assert route.call_count == 1
    assert json.loads(result.stdout)["data"] == answer
