"""Handing back a background job, and waiting one out when the caller asks.

Publishing became a job on the server because a model call per product does not belong inside an
HTTP request. The caller must not be left holding an id it cannot use, so the queued job always
comes back carrying the exact command that reads it.

Waiting is opt-in (``--wait``) rather than the default, because the caller is usually an agent, not
a person at a terminal: its sandbox detaches anything still running after a few seconds and then
answers every poll on a fixed ~30-second cadence, so a two-minute wait costs five or six turns of
"no new output" — turns spent loading the very service the job is waiting on.

The property that makes all of this safe is that only the first call writes. Everything after it is
a read, and a read can be repeated — so checking on a job is always one more read, never a re-send
that would publish the same product twice.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import httpx
import pytest
import respx
from typer.testing import CliRunner

from sellerclaw_cli._job_wait import (
    is_finished,
    looks_like_job,
    poll_intervals,
    wait_for_job,
)
from sellerclaw_cli.cli import app

pytestmark = pytest.mark.unit

runner = CliRunner()

STORE_ID = "46438868-3117-408f-a7d6-7e8a4b55e4c9"
PRODUCT_ID = "a847c4af-86ec-4f26-8861-357637e57c14"
JOB_ID = "3f6a5b3c-1b4a-4a2f-9d1e-2c8c2a5f9a11"


@pytest.fixture
def env(
    isolated_config_home: Path,  # noqa: ARG001 — keeps config reads off the real ~/.config
    monkeypatch: pytest.MonkeyPatch,
    fake_api_url: str,
    fake_token: str,
) -> str:
    monkeypatch.setenv("SELLERCLAW_API_URL", fake_api_url)
    monkeypatch.setenv("SELLERCLAW_TOKEN", fake_token)
    return fake_api_url


@pytest.fixture(autouse=True)
def _no_real_sleeping(monkeypatch: pytest.MonkeyPatch) -> None:
    """The schedule is asserted separately; no test should spend real seconds on it."""
    monkeypatch.setattr("time.sleep", lambda _seconds: None)


def _job(status: str, **extra: Any) -> dict[str, Any]:
    return {"id": JOB_ID, "status": status, "kind": "draft", **extra}


def _create_drafts(*args: str) -> Any:
    return runner.invoke(
        app,
        [
            *args,
            "ebay-listings",
            "create-drafts",
            STORE_ID,
            "-b",
            json.dumps({"product_ids": [PRODUCT_ID]}),
        ],
    )


class TestRecognisingAJob:
    @pytest.mark.parametrize(
        ("payload", "expected"),
        [
            pytest.param({"id": JOB_ID, "status": "queued"}, True, id="queued-job"),
            pytest.param({"id": JOB_ID}, False, id="row-without-a-status"),
            pytest.param({"status": "queued"}, False, id="status-without-an-id"),
            pytest.param([{"id": JOB_ID, "status": "queued"}], False, id="a-list"),
            pytest.param(None, False, id="empty-body"),
        ],
    )
    def test_only_a_job_is_waited_on(self, payload: Any, expected: bool) -> None:
        assert looks_like_job(payload) is expected

    @pytest.mark.parametrize(
        ("status", "expected"),
        [
            pytest.param("queued", False, id="queued"),
            pytest.param("running", False, id="running"),
            pytest.param("succeeded", True, id="succeeded"),
            # Partial means every item was processed and some failed — the run is over.
            pytest.param("partial", True, id="partial"),
            pytest.param("failed", True, id="failed"),
        ],
    )
    def test_terminal_states_end_the_wait(self, status: str, expected: bool) -> None:
        assert is_finished(_job(status)) is expected


class TestTheSchedule:
    def test_polling_starts_quickly_then_eases_off(self) -> None:
        """A one-product job is often done in seconds; a fifty-product one must not be hammered."""
        intervals = poll_intervals(60.0)

        assert intervals[0] == 2.0
        assert max(intervals) <= 5.0
        # Non-decreasing, except that the final gap is clipped to whatever budget is left.
        assert intervals[:-1] == sorted(intervals[:-1])

    def test_the_schedule_never_exceeds_the_budget(self) -> None:
        assert sum(poll_intervals(7.0)) == pytest.approx(7.0)

    def test_no_budget_means_no_polling(self) -> None:
        assert poll_intervals(0.0) == []


class TestWaiting:
    def test_it_returns_as_soon_as_the_job_is_done(self) -> None:
        states = [_job("running"), _job("succeeded", succeeded_count=1)]
        seen: list[str] = []

        def fetch(job_id: str) -> dict[str, Any]:
            seen.append(job_id)
            return states.pop(0)

        final = wait_for_job(_job("queued"), fetch=fetch, budget_seconds=60.0, sleep=lambda _s: None)

        assert final["status"] == "succeeded"
        assert final["succeeded_count"] == 1
        # Stopped at the finished state instead of polling out the budget.
        assert seen == [JOB_ID, JOB_ID]

    def test_a_blip_mid_wait_does_not_lose_the_job(self) -> None:
        """A failed poll is not a failed job — the id is still known and the next read tries again."""
        answers: list[Any] = [RuntimeError("connection reset"), _job("succeeded")]

        def fetch(_job_id: str) -> dict[str, Any]:
            answer = answers.pop(0)
            if isinstance(answer, Exception):
                raise answer
            return answer

        final = wait_for_job(_job("queued"), fetch=fetch, budget_seconds=60.0, sleep=lambda _s: None)

        assert final["status"] == "succeeded"

    def test_running_out_of_budget_returns_the_last_state_seen(self) -> None:
        def fetch(_job_id: str) -> dict[str, Any]:
            return _job("running", pending_count=3)

        final = wait_for_job(_job("queued"), fetch=fetch, budget_seconds=4.0, sleep=lambda _s: None)

        assert final["status"] == "running"
        assert final["pending_count"] == 3


class TestThroughTheCommand:
    @pytest.mark.parametrize(
        "args",
        [
            pytest.param((), id="by-default"),
            pytest.param(("--no-wait",), id="asked-for-explicitly"),
        ],
    )
    @respx.mock
    def test_create_drafts_hands_back_the_queued_job_without_polling(
        self, env: str, args: tuple[str, ...]
    ) -> None:
        """Waiting costs an agent five or six turns of "no new output"; the job id costs it none."""
        respx.post(f"{env}/agent/stores/{STORE_ID}/ebay-draft-listings").mock(
            return_value=httpx.Response(202, json=_job("queued"))
        )
        poll = respx.get(f"{env}/agent/stores/{STORE_ID}/bulk-listing-jobs/{JOB_ID}").mock(
            return_value=httpx.Response(200, json=_job("succeeded"))
        )

        result = _create_drafts(*args)

        assert result.exit_code == 0, result.output
        assert json.loads(result.stdout)["data"]["status"] == "queued"
        assert poll.call_count == 0

    @respx.mock
    def test_the_queued_job_names_the_command_that_reads_it(self, env: str) -> None:
        """A job id alone is a dead end: it does not say which command reads it, and an agent that
        cannot find out either re-sends the write or reports "started it" as the outcome."""
        respx.post(f"{env}/agent/stores/{STORE_ID}/ebay-draft-listings").mock(
            return_value=httpx.Response(202, json=_job("queued"))
        )

        result = _create_drafts()

        assert result.exit_code == 0, result.output
        note = json.loads(result.stdout)["data"]["note"]
        assert f"listings bulk-job {STORE_ID} {JOB_ID}" in note
        assert "nothing needs re-sending" in note
        assert "--wait" in note

    @respx.mock
    def test_wait_answers_with_the_finished_job(self, env: str) -> None:
        respx.post(f"{env}/agent/stores/{STORE_ID}/ebay-draft-listings").mock(
            return_value=httpx.Response(202, json=_job("queued"))
        )
        respx.get(f"{env}/agent/stores/{STORE_ID}/bulk-listing-jobs/{JOB_ID}").mock(
            return_value=httpx.Response(200, json=_job("succeeded", succeeded_count=1))
        )

        result = _create_drafts("--wait")

        assert result.exit_code == 0, result.output
        payload = json.loads(result.stdout)["data"]
        assert payload["status"] == "succeeded"
        assert payload["succeeded_count"] == 1

    @respx.mock
    def test_a_wait_that_runs_out_names_the_command_that_reads_the_job(self, env: str) -> None:
        """Nothing failed and nothing may be re-sent — so the answer must point at the one safe call."""
        respx.post(f"{env}/agent/stores/{STORE_ID}/ebay-draft-listings").mock(
            return_value=httpx.Response(202, json=_job("queued"))
        )
        respx.get(f"{env}/agent/stores/{STORE_ID}/bulk-listing-jobs/{JOB_ID}").mock(
            return_value=httpx.Response(200, json=_job("running"))
        )

        result = _create_drafts("--wait", "--timeout", "4")

        assert result.exit_code == 0, result.output
        payload = json.loads(result.stdout)["data"]
        assert payload["status"] == "running"
        assert f"listings bulk-job {STORE_ID}" in payload["note"]
        assert JOB_ID in payload["note"]
        assert "nothing needs re-sending" in payload["note"]

    @respx.mock
    def test_a_command_that_starts_no_job_is_untouched(self, env: str) -> None:
        respx.get(f"{env}/agent/stores/{STORE_ID}/listings").mock(
            return_value=httpx.Response(200, json={"items": []})
        )

        result = runner.invoke(app, ["ebay-listings", "list", STORE_ID])

        assert result.exit_code == 0, result.output
        assert json.loads(result.stdout)["data"] == {"items": []}


class TestDescribeTellsTheCaller:
    def test_a_job_starting_command_says_so(self, env: str) -> None:  # noqa: ARG002
        result = runner.invoke(app, ["describe", "ebay-listings", "create-drafts"])

        assert result.exit_code == 0, result.output
        assert json.loads(result.stdout)["data"]["starts_background_job"] is True

    def test_an_ordinary_command_says_so_too(self, env: str) -> None:  # noqa: ARG002
        result = runner.invoke(app, ["describe", "ebay-listings", "list"])

        assert result.exit_code == 0, result.output
        assert json.loads(result.stdout)["data"]["starts_background_job"] is False
