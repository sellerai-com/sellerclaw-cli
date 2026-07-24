from __future__ import annotations

import json

import httpx
import pytest
import respx
from typer.testing import CliRunner

from sellerclaw_cli.cli import app

pytestmark = pytest.mark.unit

runner = CliRunner()

CHANNEL_ID = "11111111-1111-4111-8111-111111111111"
PROBLEM_A = "22222222-2222-4222-8222-222222222222"
PROBLEM_B = "33333333-3333-4333-8333-333333333333"


@pytest.fixture
def env_pointing_at_fake_api(
    monkeypatch: pytest.MonkeyPatch,
    fake_api_url: str,
    fake_token: str,
) -> None:
    monkeypatch.setenv("SELLERCLAW_API_URL", fake_api_url)
    monkeypatch.setenv("SELLERCLAW_TOKEN", fake_token)


@respx.mock
def test_list_forwards_filters(
    env_pointing_at_fake_api: None,  # noqa: ARG001
    fake_api_url: str,
) -> None:
    route = respx.get(f"{fake_api_url}/agent/listing-problems").mock(
        return_value=httpx.Response(200, json={"items": [], "summary": {"total": 0, "errors": 0, "warnings": 0}})
    )
    result = runner.invoke(
        app,
        ["listing-problems", "list", "--sales-channel-id", CHANNEL_ID, "--severity", "error"],
    )
    assert result.exit_code == 0, result.stderr
    params = route.calls.last.request.url.params
    assert params["sales_channel_id"] == CHANNEL_ID
    assert params["severity"] == "error"


@respx.mock
def test_list_hidden_gets_the_hidden_endpoint(
    env_pointing_at_fake_api: None,  # noqa: ARG001
    fake_api_url: str,
) -> None:
    route = respx.get(f"{fake_api_url}/agent/listing-problems/hidden").mock(
        return_value=httpx.Response(200, json={"items": [], "summary": {"total": 0, "errors": 0, "warnings": 0}})
    )
    result = runner.invoke(app, ["listing-problems", "list-hidden"])
    assert result.exit_code == 0, result.stderr
    assert route.call_count == 1


@respx.mock
def test_hide_posts_the_problem_ids(
    env_pointing_at_fake_api: None,  # noqa: ARG001
    fake_api_url: str,
) -> None:
    route = respx.post(f"{fake_api_url}/agent/listing-problems/hide").mock(
        return_value=httpx.Response(204)
    )
    result = runner.invoke(
        app,
        ["listing-problems", "hide", "-b", json.dumps({"problem_ids": [PROBLEM_A, PROBLEM_B]})],
    )
    assert result.exit_code == 0, result.stderr
    sent = json.loads(route.calls.last.request.content)
    assert sent == {"problem_ids": [PROBLEM_A, PROBLEM_B]}


@respx.mock
def test_unhide_posts_the_problem_ids(
    env_pointing_at_fake_api: None,  # noqa: ARG001
    fake_api_url: str,
) -> None:
    route = respx.post(f"{fake_api_url}/agent/listing-problems/unhide").mock(
        return_value=httpx.Response(204)
    )
    result = runner.invoke(
        app,
        ["listing-problems", "unhide", "-b", json.dumps({"problem_ids": [PROBLEM_A]})],
    )
    assert result.exit_code == 0, result.stderr
    sent = json.loads(route.calls.last.request.content)
    assert sent == {"problem_ids": [PROBLEM_A]}
