"""The scheduled-task wizard's draft card: what the agent's flags put into it, and what it hears back."""

from __future__ import annotations

import json

import httpx
import pytest
import respx
from typer.testing import CliRunner

from sellerclaw_cli._errors import UserInputError
from sellerclaw_cli.cli import app
from sellerclaw_cli.mcp_server import run_command

pytestmark = pytest.mark.unit

runner = CliRunner()

WIZARD_SESSION_KEY = "agent:supervisor:sellerclaw-ui:direct:48729abf-b759-46bf-8802-6768891edc7e"

_DRAFT_JSON = {
    "id": "7d1c3a52-5a8e-4f4e-9d0b-3f4a3c2b1e10",
    "name": "Morning sales digest",
    "description": None,
    "message": "Check yesterday's orders in every store and report revenue and refunds.",
    "schedule": {"kind": "daily", "time": "09:00", "timezone": "Europe/Berlin"},
    "email_report": True,
    "messenger_push": False,
    "missing": ["description"],
    "ready": False,
}


@pytest.fixture
def env_pointing_at_fake_api(
    monkeypatch: pytest.MonkeyPatch,
    fake_api_url: str,
    fake_token: str,
) -> None:
    monkeypatch.setenv("SELLERCLAW_API_URL", fake_api_url)
    monkeypatch.setenv("SELLERCLAW_TOKEN", fake_token)
    monkeypatch.setenv("SELLERCLAW_SESSION_KEY", WIZARD_SESSION_KEY)


@respx.mock
@pytest.mark.parametrize(
    ("argv", "body"),
    [
        pytest.param(
            [
                "--name", "Morning sales digest",
                "--message", "Check yesterday's orders in every store and report revenue and refunds.",
                "--daily-at", "09:00",
                "--timezone", "Europe/Berlin",
            ],
            {
                "name": "Morning sales digest",
                "message": "Check yesterday's orders in every store and report revenue and refunds.",
                "daily_at": "09:00",
                "timezone": "Europe/Berlin",
            },
            id="daily-with-name-and-brief",
        ),
        pytest.param(
            ["--weekly-on", "mon,thu", "--at", "09:00"],
            {"weekly_on": "mon,thu", "at": "09:00"},
            id="weekly",
        ),
        pytest.param(
            ["--monthly-on", "1,15", "--at", "18:30"],
            {"monthly_on": "1,15", "at": "18:30"},
            id="monthly",
        ),
        pytest.param(["--once-at", "2026-11-20T09:00"], {"once_at": "2026-11-20T09:00"}, id="once"),
        pytest.param(["--every", "2h"], {"every": "2h"}, id="every"),
        pytest.param(
            ["--description", "Tells you every morning how yesterday went."],
            {"description": "Tells you every morning how yesterday went."},
            id="one-field-only",
        ),
        pytest.param(["--email-report"], {"email_report": True}, id="email-report-on"),
        pytest.param(["--no-email-report"], {"email_report": False}, id="email-report-off"),
        pytest.param(["--messenger-push"], {"messenger_push": True}, id="messenger-push-on"),
        pytest.param(["--no-messenger-push"], {"messenger_push": False}, id="messenger-push-off"),
        pytest.param(
            ["--no-email-report", "--messenger-push"],
            {"email_report": False, "messenger_push": True},
            id="both-switches",
        ),
        pytest.param(
            ["--report-template", "weekly-finance", "--report-store", "all"],
            {"report_template": "weekly-finance", "report_store": "all"},
            id="ready-made-report",
        ),
        pytest.param(["--report-template", ""], {"report_template": ""}, id="report-template-dropped"),
    ],
)
def test_only_the_flags_given_reach_the_draft(
    env_pointing_at_fake_api: None,  # noqa: ARG001
    fake_api_url: str,
    argv: list[str],
    body: dict[str, object],
) -> None:
    """A partial update: a flag left off is absent from the body, so the field on the card stays as
    it was — including a switch, which is only ever turned on or off when its flag is given."""
    route = respx.put(f"{fake_api_url}/agent/cron/draft").mock(
        return_value=httpx.Response(200, json=_DRAFT_JSON)
    )

    result = runner.invoke(app, ["scheduled-tasks", "draft", *argv])

    assert result.exit_code == 0, result.stderr
    assert route.call_count == 1
    assert json.loads(route.calls.last.request.content) == body
    assert dict(route.calls.last.request.url.params) == {}


@respx.mock
def test_the_wizard_chat_is_named_and_the_whole_draft_comes_back(
    env_pointing_at_fake_api: None,  # noqa: ARG001
    fake_api_url: str,
) -> None:
    """The session key is how the server finds the wizard chat the card belongs to, and the answer —
    the draft with what it still misses — is what the agent reads to know what to ask next."""
    route = respx.put(f"{fake_api_url}/agent/cron/draft").mock(
        return_value=httpx.Response(200, json=_DRAFT_JSON)
    )

    result = runner.invoke(app, ["scheduled-tasks", "draft", "--email-report"])

    assert result.exit_code == 0, result.stderr
    assert route.calls.last.request.headers["X-Session-Key"] == WIZARD_SESSION_KEY
    assert json.loads(result.stdout) == {"data": _DRAFT_JSON}


@respx.mock
def test_a_refusal_outside_the_wizard_chat_reaches_the_agent_word_for_word(
    env_pointing_at_fake_api: None,  # noqa: ARG001
    fake_api_url: str,
) -> None:
    """The server's message says what to do instead; the agent has to read exactly that."""
    message = (
        "This is not the scheduled-task wizard chat. Here, create the task yourself once the owner "
        "agrees: openclaw cron create."
    )
    route = respx.put(f"{fake_api_url}/agent/cron/draft").mock(
        return_value=httpx.Response(
            409, json={"detail": {"code": "not_in_scheduled_task_wizard", "message": message}}
        )
    )

    result = runner.invoke(app, ["scheduled-tasks", "draft", "--daily-at", "09:00"])

    assert result.exit_code == 1
    assert result.stdout == ""
    error = json.loads(result.stderr)["error"]
    assert error["message"] == message
    assert error["status"] == 409
    assert error["details"]["detail"]["code"] == "not_in_scheduled_task_wizard"
    assert route.call_count == 1


def test_the_example_fills_one_schedule_form_and_spells_both_switches() -> None:
    """`describe` is what an agent copies from: an example passing every schedule form at once would
    be refused, and a switch shown as `--email-report '<value>'` would not even parse."""
    result = runner.invoke(app, ["describe", "scheduled-tasks", "draft"])

    assert result.exit_code == 0, result.output
    detail = json.loads(result.stdout)["data"]
    assert detail["example"] == (
        "sellerclaw scheduled-tasks draft --name '<name>' --message '<message>' "
        "--daily-at '<daily_at>' --timezone '<timezone>'"
    )
    options = {f["field"]: f["option"] for f in detail["body_fields"]}
    assert options["email_report"] == "--email-report/--no-email-report"
    assert options["messenger_push"] == "--messenger-push/--no-messenger-push"
    assert options["daily_at"] == "--daily-at"


def test_connectors_cannot_reach_the_wizard_draft() -> None:
    """Owner's decision: scheduled tasks are not managed from Claude or ChatGPT for now."""
    with pytest.raises(UserInputError, match="unknown group 'scheduled-tasks'"):
        run_command("scheduled-tasks", "draft", body={"daily_at": "09:00"})
