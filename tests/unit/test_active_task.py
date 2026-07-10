"""Active-task pointer + short-id prefix expansion (see _task_context / _command_group)."""

from __future__ import annotations

from pathlib import Path

import httpx
import pytest
import respx
from typer.testing import CliRunner

from sellerclaw_cli import _task_context
from sellerclaw_cli.cli import app

pytestmark = pytest.mark.unit

runner = CliRunner()

TASK_A = "7715c2ce-af22-44ed-bc8d-67aa8fd69a80"
TASK_B = "7715c2ce-af22-44ed-bcff-000000000000"  # shares the 8-char prefix with TASK_A


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


def test_state_roundtrip_is_agent_scoped(
    isolated_config_home: Path,  # noqa: ARG001 — redirects XDG so state.toml lands in tmp
) -> None:
    _task_context.set_active("subagent_task", "shopify", "task-1")
    _task_context.set_active("subagent_task", "supplier", "task-2")
    assert _task_context.get_active("subagent_task", "shopify") == "task-1"
    assert _task_context.get_active("subagent_task", "supplier") == "task-2"
    assert _task_context.get_active("subagent_task", "unknown") is None


def test_collect_ids_handles_common_shapes() -> None:
    assert _task_context.collect_ids([{"id": "a"}, {"id": "b"}]) == ["a", "b"]
    assert _task_context.collect_ids({"tasks": [{"id": "x"}]}) == ["x"]
    assert _task_context.collect_ids({"nope": 1}) == []


@respx.mock
def test_start_remembers_task_then_follow_up_omits_id(env: str) -> None:
    """`start <id>` records the task; a later `complete` with no id acts on it."""
    respx.post(f"{env}/agent/goals/agent-tasks/{TASK_A}/start").mock(
        return_value=httpx.Response(200, json={"id": TASK_A})
    )
    complete = respx.post(f"{env}/agent/goals/agent-tasks/{TASK_A}/complete").mock(
        return_value=httpx.Response(200, json={"id": TASK_A})
    )

    started = runner.invoke(app, ["subagent-tasks", "start", TASK_A])
    assert started.exit_code == 0, started.stderr
    assert _task_context.get_active("subagent_task", None) == TASK_A

    done = runner.invoke(app, ["subagent-tasks", "complete"])
    assert done.exit_code == 0, done.stderr
    assert complete.call_count == 1


def test_follow_up_without_active_task_errors(env: str) -> None:
    result = runner.invoke(app, ["subagent-tasks", "complete"])
    assert result.exit_code == 1
    assert "no active task" in result.stderr


@respx.mock
def test_short_prefix_is_expanded_against_task_list(env: str) -> None:
    """A unique short id prefix is expanded to the full id via the task list."""
    respx.get(f"{env}/agent/goals/my-tasks").mock(
        return_value=httpx.Response(200, json={"tasks": [{"id": TASK_A}]})
    )
    complete = respx.post(f"{env}/agent/goals/agent-tasks/{TASK_A}/complete").mock(
        return_value=httpx.Response(200, json={"id": TASK_A})
    )
    result = runner.invoke(app, ["subagent-tasks", "complete", "7715c2ce"])
    assert result.exit_code == 0, result.stderr
    assert complete.call_count == 1


@respx.mock
def test_ambiguous_prefix_is_rejected(env: str) -> None:
    respx.get(f"{env}/agent/goals/my-tasks").mock(
        return_value=httpx.Response(200, json={"tasks": [{"id": TASK_A}, {"id": TASK_B}]})
    )
    result = runner.invoke(app, ["subagent-tasks", "complete", "7715c2ce"])
    assert result.exit_code == 1
    assert "prefix" in result.stderr
