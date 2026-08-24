"""Plan bookkeeping on agent/team tasks — the `plan-check` body must mirror the server schema.

Regression guard: the CLI validates bodies locally, so a field the API accepts but the CLI never
declared (`note`) was rejected before the request left the machine, and the owner-facing progress
line silently never reached their plan view.
"""

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

TASK_ID = "7715c2ce-af22-44ed-bc8d-67aa8fd69a80"

_GROUPS = (
    pytest.param("subagent-tasks", "agent-tasks", id="subagent-tasks"),
    pytest.param("team-tasks", "team-tasks", id="team-tasks"),
)


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
@pytest.mark.parametrize(("group", "path"), _GROUPS)
def test_plan_check_sends_note_alongside_status_and_metadata(
    env: str, group: str, path: str
) -> None:
    route = respx.post(f"{env}/agent/goals/{path}/{TASK_ID}/plan/check").mock(
        return_value=httpx.Response(200, json={"id": TASK_ID})
    )
    body = {
        "item_id": "3",
        "status": "done",
        "note": "Saved the folding organizer to the catalog",
        "metadata": {"catalog_product_id": "prod-9"},
    }

    result = runner.invoke(app, [group, "plan-check", TASK_ID, "-b", json.dumps(body)])

    assert result.exit_code == 0, result.stderr
    assert route.call_count == 1
    assert json.loads(route.calls.last.request.content) == body


@respx.mock
@pytest.mark.parametrize(("group", "path"), _GROUPS)
def test_plan_check_accepts_a_note_on_its_own(env: str, group: str, path: str) -> None:
    """The server allows any one of status / metadata / note — the CLI must not force a status."""
    route = respx.post(f"{env}/agent/goals/{path}/{TASK_ID}/plan/check").mock(
        return_value=httpx.Response(200, json={"id": TASK_ID})
    )

    result = runner.invoke(
        app,
        [group, "plan-check", TASK_ID, "-b", json.dumps({"item_id": "1", "note": "Halfway there"})],
    )

    assert result.exit_code == 0, result.stderr
    assert json.loads(route.calls.last.request.content) == {"item_id": "1", "note": "Halfway there"}


@respx.mock
@pytest.mark.parametrize(("group", "path"), _GROUPS)
def test_plan_check_still_rejects_unknown_fields_locally(env: str, group: str, path: str) -> None:
    route = respx.post(f"{env}/agent/goals/{path}/{TASK_ID}/plan/check").mock(
        return_value=httpx.Response(200, json={"id": TASK_ID})
    )

    result = runner.invoke(
        app,
        [group, "plan-check", TASK_ID, "-b", json.dumps({"item_id": "1", "message": "oops"})],
    )

    assert result.exit_code != 0
    assert "unknown field" in result.stderr
    assert route.call_count == 0  # caught before the network call


@respx.mock
@pytest.mark.parametrize(
    ("group", "path", "review_path"),
    [
        pytest.param("subagent-tasks", "agent-tasks", "request-review", id="subagent-request-review"),
        pytest.param("team-tasks", "team-tasks", "request-review", id="team-request-review"),
        pytest.param("team-tasks", "team-tasks", "complete", id="team-complete"),
    ],
)
def test_report_can_close_the_plan_in_the_same_call(
    env: str, group: str, path: str, review_path: str
) -> None:
    route = respx.post(f"{env}/agent/goals/{path}/{TASK_ID}/{review_path}").mock(
        return_value=httpx.Response(200, json={"id": TASK_ID})
    )
    plan = [{"item_id": "1", "status": "done"}, {"item_id": "2", "status": "skipped"}]

    result = runner.invoke(
        app,
        [group, review_path, TASK_ID, "-b", json.dumps({"outcome": "All live.", "plan": plan})],
    )

    assert result.exit_code == 0, result.stderr
    assert json.loads(route.calls.last.request.content) == {"outcome": "All live.", "plan": plan}


@respx.mock
@pytest.mark.parametrize(("group", "path"), _GROUPS)
def test_plan_check_sends_a_batch(env: str, group: str, path: str) -> None:
    # Several items in one call — the shape that collapses a burst of ticks into one model turn.
    route = respx.post(f"{env}/agent/goals/{path}/{TASK_ID}/plan/check").mock(
        return_value=httpx.Response(200, json={"id": TASK_ID})
    )
    items = [
        {"item_id": "1", "status": "done", "note": "Saved the folding organizer"},
        {"item_id": "2", "status": "in_progress"},
    ]

    result = runner.invoke(
        app, [group, "plan-check", TASK_ID, "-b", json.dumps({"items": items})]
    )

    assert result.exit_code == 0, result.stderr
    assert json.loads(route.calls.last.request.content) == {"items": items}


@respx.mock
@pytest.mark.parametrize(("group", "path"), _GROUPS)
def test_set_plan_carries_per_item_notes(env: str, group: str, path: str) -> None:
    route = respx.post(f"{env}/agent/goals/{path}/{TASK_ID}/plan").mock(
        return_value=httpx.Response(200, json={"id": TASK_ID})
    )
    plan = [
        {"text": "Source a pet product", "status": "done", "note": "Picked the CJ traction rope"},
        {"text": "Publish to Shopify"},
    ]

    result = runner.invoke(
        app, [group, "set-plan", TASK_ID, "-b", json.dumps({"plan": plan})]
    )

    assert result.exit_code == 0, result.stderr
    assert json.loads(route.calls.last.request.content) == {"plan": plan}


@respx.mock
@pytest.mark.parametrize(("group", "path"), _GROUPS)
@pytest.mark.parametrize(
    "status",
    [
        pytest.param("pending", id="pending"),
        pytest.param("in_progress", id="in_progress"),
        pytest.param("done", id="done"),
        pytest.param("skipped", id="skipped"),
        pytest.param("failed", id="failed"),
    ],
)
def test_plan_check_sends_every_server_status(
    env: str, group: str, path: str, status: str
) -> None:
    """The single-item form must carry the same statuses the batch form and the server accept.

    Regression guard: `failed` was missing from the local `choices`, so a phase that was worked and
    did not land was refused before the request left the machine — while the very same value went
    through untouched inside `items`. The supervisor filed it as `skipped` ("nobody tried") instead.
    """
    route = respx.post(f"{env}/agent/goals/{path}/{TASK_ID}/plan/check").mock(
        return_value=httpx.Response(200, json={"id": TASK_ID})
    )
    body = {"item_id": "4", "status": status, "note": "1 of 3 live; two blocked on the owner"}

    result = runner.invoke(app, [group, "plan-check", TASK_ID, "-b", json.dumps(body)])

    assert result.exit_code == 0, result.stderr
    assert route.call_count == 1
    assert json.loads(route.calls.last.request.content) == body


@respx.mock
@pytest.mark.parametrize(("group", "path"), _GROUPS)
def test_plan_check_rejects_a_status_the_server_does_not_have(
    env: str, group: str, path: str
) -> None:
    """The choice list still guards — it is the stale list that was the bug, not the checking."""
    route = respx.post(f"{env}/agent/goals/{path}/{TASK_ID}/plan/check").mock(
        return_value=httpx.Response(200, json={"id": TASK_ID})
    )

    result = runner.invoke(
        app,
        [group, "plan-check", TASK_ID, "-b", json.dumps({"item_id": "1", "status": "blocked"})],
    )

    assert result.exit_code != 0
    assert "must be one of" in result.stderr
    assert "failed" in result.stderr
    assert route.call_count == 0


@respx.mock
@pytest.mark.parametrize(
    ("group", "path", "review_path"),
    [
        pytest.param("subagent-tasks", "agent-tasks", "request-review", id="subagent-request-review"),
        pytest.param("team-tasks", "team-tasks", "request-review", id="team-request-review"),
        pytest.param("team-tasks", "team-tasks", "complete", id="team-complete"),
    ],
)
def test_report_can_close_a_phase_as_failed(
    env: str, group: str, path: str, review_path: str
) -> None:
    route = respx.post(f"{env}/agent/goals/{path}/{TASK_ID}/{review_path}").mock(
        return_value=httpx.Response(200, json={"id": TASK_ID})
    )
    plan = [
        {"item_id": "1", "status": "done"},
        {"item_id": "2", "status": "failed", "note": "Drafts ready; publish blocked on the policy choice"},
    ]

    result = runner.invoke(
        app,
        [group, review_path, TASK_ID, "-b", json.dumps({"outcome": "3 of 5 live.", "plan": plan})],
    )

    assert result.exit_code == 0, result.stderr
    assert json.loads(route.calls.last.request.content) == {"outcome": "3 of 5 live.", "plan": plan}
