from __future__ import annotations

import httpx
import pytest
import respx
from typer.testing import CliRunner

from sellerclaw_cli.cli import app

pytestmark = pytest.mark.unit

runner = CliRunner()

_ROSTER_JSON = {
    "specialists": [
        {
            "module_id": "product_scout",
            "agent_id": "scout",
            "name": "Product Scout",
            "description": "Researches niches, demand and competitors.",
            "on_team": False,
            "can_add": True,
            "blocked_by": [],
        }
    ],
    "activation_pending": False,
}

_ADDED_JSON = {
    "specialist": {
        "module_id": "product_scout",
        "agent_id": "scout",
        "name": "Product Scout",
        "description": "Researches niches, demand and competitors.",
        "on_team": True,
        "can_add": True,
        "blocked_by": [],
    },
    "added_now": True,
    "ready_to_delegate": True,
    "note": "Added and live — you can spawn this specialist now.",
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
def test_list_reads_the_roster(
    env_pointing_at_fake_api: None,  # noqa: ARG001
    fake_api_url: str,
) -> None:
    route = respx.get(f"{fake_api_url}/agent/team").mock(
        return_value=httpx.Response(200, json=_ROSTER_JSON)
    )
    result = runner.invoke(app, ["team", "list"])
    assert result.exit_code == 0, result.stderr
    assert route.call_count == 1
    assert "product_scout" in result.stdout


@respx.mock
def test_add_substitutes_the_specialist_id_into_the_path(
    env_pointing_at_fake_api: None,  # noqa: ARG001
    fake_api_url: str,
) -> None:
    route = respx.post(f"{fake_api_url}/agent/team/product_scout/enable").mock(
        return_value=httpx.Response(200, json=_ADDED_JSON)
    )
    result = runner.invoke(app, ["team", "add", "product_scout"])
    assert result.exit_code == 0, result.stderr
    assert route.call_count == 1
    assert "ready_to_delegate" in result.stdout
