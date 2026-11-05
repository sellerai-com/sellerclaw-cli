"""The goal journal: the agent reads it, writes entries in it and rewrites its working state."""

from __future__ import annotations

import json
from pathlib import Path

import httpx
import pytest
import respx
from typer.testing import CliRunner

from sellerclaw_cli.cli import app

pytestmark = pytest.mark.unit

runner = CliRunner()

GOAL_ID = "3f0c6a0e-9a57-4f43-9a61-0c2d8f3b51aa"
ENTRY_ID = "b1e6f1c2-1f0e-4d43-8a51-2a6a9d0f7c11"


@pytest.fixture
def env(
    isolated_config_home: Path,  # noqa: ARG001 — redirects XDG so state.toml lands in tmp
    monkeypatch: pytest.MonkeyPatch,
    fake_api_url: str,
    fake_token: str,
) -> str:
    monkeypatch.setenv("SELLERCLAW_API_URL", fake_api_url)
    monkeypatch.setenv("SELLERCLAW_TOKEN", fake_token)
    return fake_api_url


@respx.mock
def test_journal_pages_back_with_before_and_limit(env: str) -> None:
    route = respx.get(f"{env}/agent/goals/{GOAL_ID}/journal").mock(
        return_value=httpx.Response(200, json={"goal_id": GOAL_ID, "items": []})
    )

    result = runner.invoke(
        app,
        ["goals", "journal", GOAL_ID, "--limit", "20", "--before", "2026-11-05T09:00:00Z"],
    )

    assert result.exit_code == 0, result.stderr
    assert dict(route.calls.last.request.url.params) == {
        "limit": "20",
        "before": "2026-11-05T09:00:00Z",
    }


@respx.mock
@pytest.mark.parametrize(
    ("args", "body"),
    [
        pytest.param(
            ["--entry", "decision", "--text", "Relisting headlights first."],
            {"entry": "decision", "text": "Relisting headlights first."},
            id="decision",
        ),
        pytest.param(
            [
                "--entry", "result", "--text", "Switched to mirrors.",
                "--details", "CJ: 40 hits",
            ],
            {
                "entry": "result",
                "text": "Switched to mirrors.",
                "details": "CJ: 40 hits",
            },
            id="with-details",
        ),
    ],
)
def test_add_entry_sends_both_layers(env: str, args: list[str], body: dict[str, str]) -> None:
    route = respx.post(f"{env}/agent/goals/{GOAL_ID}/journal").mock(
        return_value=httpx.Response(200, json={"id": ENTRY_ID})
    )

    result = runner.invoke(app, ["goals", "add-entry", GOAL_ID, *args])

    assert result.exit_code == 0, result.stderr
    assert json.loads(route.calls.last.request.content) == body


@respx.mock
@pytest.mark.parametrize(
    "entry",
    [
        pytest.param("note", id="the-owners-kind"),
        pytest.param("state", id="the-systems-kind"),
    ],
)
def test_add_entry_refuses_a_kind_the_agent_does_not_write(env: str, entry: str) -> None:
    route = respx.post(f"{env}/agent/goals/{GOAL_ID}/journal").mock(
        return_value=httpx.Response(200, json={})
    )

    result = runner.invoke(
        app, ["goals", "add-entry", GOAL_ID, "--entry", entry, "--text", "x"]
    )

    assert result.exit_code != 0
    assert not route.called


@respx.mock
def test_set_state_puts_the_whole_page(env: str) -> None:
    route = respx.put(f"{env}/agent/goals/{GOAL_ID}/state").mock(
        return_value=httpx.Response(200, json={"id": GOAL_ID})
    )

    result = runner.invoke(
        app,
        [
            "goals", "set-state", GOAL_ID,
            "--text", "Strategy: relist first. Next: mirrors.",
            "--details", "baseline $5,400",
        ],
    )

    assert result.exit_code == 0, result.stderr
    assert json.loads(route.calls.last.request.content) == {
        "text": "Strategy: relist first. Next: mirrors.",
        "details": "baseline $5,400",
    }
