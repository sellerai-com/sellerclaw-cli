"""Report tasks: a scheduled run makes its report copy, reads it and publishes its take."""

from __future__ import annotations

import json

import httpx
import pytest
import respx
from typer.testing import CliRunner

from sellerclaw_cli._runtime import _poll_command
from sellerclaw_cli.cli import app

pytestmark = pytest.mark.unit

runner = CliRunner()

RUN_SESSION_KEY = "agent:supervisor:cron:oc-1:run:s-1"
COPY_ID = "6a1f0c64-6a40-4d5e-9f8f-0f7c3c1b2d3e"


def _copy(status: str, **extra: object) -> dict[str, object]:
    return {
        "id": COPY_ID,
        "status": status,
        "kind": "pending",
        "report": {"title": "Weekly finance", "quiet_template": False},
        "metrics": [],
        **extra,
    }


@pytest.fixture
def env_pointing_at_fake_api(monkeypatch: pytest.MonkeyPatch, fake_api_url: str, fake_token: str) -> None:
    monkeypatch.setenv("SELLERCLAW_API_URL", fake_api_url)
    monkeypatch.setenv("SELLERCLAW_TOKEN", fake_token)
    monkeypatch.setenv("SELLERCLAW_SESSION_KEY", RUN_SESSION_KEY)


@respx.mock
def test_make_names_the_run_and_waits_for_the_numbers(
    env_pointing_at_fake_api: None,  # noqa: ARG001
    fake_api_url: str,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr("sellerclaw_cli._job_wait.time.sleep", lambda _s: None)
    make = respx.post(f"{fake_api_url}/agent/reports/make").mock(
        return_value=httpx.Response(200, json=_copy("running"))
    )
    poll = respx.get(f"{fake_api_url}/agent/reports/copies/{COPY_ID}").mock(
        side_effect=[
            httpx.Response(200, json=_copy("running")),
            httpx.Response(200, json=_copy("succeeded", needs_attention=True)),
        ]
    )

    result = runner.invoke(app, ["--wait", "reports", "make"])

    assert result.exit_code == 0, result.stderr
    assert make.calls.last.request.headers["X-Session-Key"] == RUN_SESSION_KEY
    assert poll.call_count == 2
    assert json.loads(result.stdout)["data"]["status"] == "succeeded"


@respx.mock
def test_make_without_wait_names_the_read_command(
    env_pointing_at_fake_api: None,  # noqa: ARG001
    fake_api_url: str,
) -> None:
    respx.post(f"{fake_api_url}/agent/reports/make").mock(return_value=httpx.Response(200, json=_copy("running")))

    result = runner.invoke(app, ["reports", "make"])

    assert result.exit_code == 0, result.stderr
    note = json.loads(result.stdout)["data"]["note"]
    assert f"`sellerclaw reports get {COPY_ID}`" in note


@respx.mock
@pytest.mark.parametrize(
    ("argv", "body"),
    [
        pytest.param(
            ["--headline", "Sales fell 42%.", "--point", "Two orders wait.", "--point", "Stock is low."],
            {"headline": "Sales fell 42%.", "points": [{"text": "Two orders wait."}, {"text": "Stock is low."}]},
            id="headline-and-points",
        ),
        pytest.param(
            ["--headline", "Nothing new.", "--quiet"],
            {"headline": "Nothing new.", "quiet": True},
            id="quiet",
        ),
        pytest.param(
            [
                "-b",
                json.dumps(
                    {
                        "headline": "Two new 1★ reviews.",
                        "points": [
                            {
                                "text": "Both about late parcels.",
                                "action": {"label": "Draft replies", "prompt": "Draft"},
                            }
                        ],
                    }
                ),
            ],
            {
                "headline": "Two new 1★ reviews.",
                "points": [
                    {"text": "Both about late parcels.", "action": {"label": "Draft replies", "prompt": "Draft"}}
                ],
            },
            id="points-with-errands-as-json",
        ),
    ],
)
def test_publish_sends_the_take(
    env_pointing_at_fake_api: None,  # noqa: ARG001
    fake_api_url: str,
    argv: list[str],
    body: dict[str, object],
) -> None:
    route = respx.post(f"{fake_api_url}/agent/reports/copies/{COPY_ID}/publish").mock(
        return_value=httpx.Response(200, json=_copy("succeeded", kind="sent"))
    )

    result = runner.invoke(app, ["reports", "publish", COPY_ID, *argv])

    assert result.exit_code == 0, result.stderr
    assert json.loads(route.calls.last.request.content) == body
    assert route.calls.last.request.headers["X-Session-Key"] == RUN_SESSION_KEY


def test_publish_needs_a_headline(env_pointing_at_fake_api: None) -> None:  # noqa: ARG001
    result = runner.invoke(app, ["reports", "publish", COPY_ID, "--point", "Two orders wait."])

    assert result.exit_code != 0
    assert "headline" in result.stderr


@respx.mock
def test_list_and_get_read_without_changing_anything(
    env_pointing_at_fake_api: None,  # noqa: ARG001
    fake_api_url: str,
) -> None:
    listed = respx.get(f"{fake_api_url}/agent/reports").mock(return_value=httpx.Response(200, json={"reports": []}))
    got = respx.get(f"{fake_api_url}/agent/reports/copies/{COPY_ID}").mock(
        return_value=httpx.Response(200, json=_copy("succeeded"))
    )

    assert runner.invoke(app, ["reports", "list"]).exit_code == 0
    assert runner.invoke(app, ["reports", "get", COPY_ID]).exit_code == 0
    assert (listed.call_count, got.call_count) == (1, 1)


@respx.mock
def test_get_with_wait_holds_until_the_numbers_are_in(
    env_pointing_at_fake_api: None,  # noqa: ARG001
    fake_api_url: str,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr("sellerclaw_cli._job_wait.time.sleep", lambda _s: None)
    got = respx.get(f"{fake_api_url}/agent/reports/copies/{COPY_ID}").mock(
        side_effect=[
            httpx.Response(200, json=_copy("running")),
            httpx.Response(200, json=_copy("running")),
            httpx.Response(200, json=_copy("succeeded", needs_attention=False)),
        ]
    )

    result = runner.invoke(app, ["--wait", "reports", "get", COPY_ID])

    assert result.exit_code == 0, result.stderr
    assert got.call_count == 3
    assert json.loads(result.stdout)["data"]["status"] == "succeeded"


@pytest.mark.parametrize(
    ("job_poll_path", "expected"),
    [
        pytest.param("/agent/reports/copies/{job_id}", "sellerclaw reports get", id="report-copy"),
        pytest.param(
            "/agent/stores/abc/bulk-listing-jobs/{job_id}", "sellerclaw listings bulk-job abc", id="bulk-job"
        ),
    ],
)
def test_the_read_command_comes_from_the_registry(job_poll_path: str, expected: str) -> None:
    assert _poll_command(job_poll_path) == expected
