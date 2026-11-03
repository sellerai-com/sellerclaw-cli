"""The scheduled-task wizard: the draft card the agent fills while it talks a task through with the owner.

The wizard is a chat of its own with a draft card next to it. The agent fills the card here, the owner
corrects it and presses Create — only that button makes the task. Running and changing tasks that
already exist is not this group's business, so it has a single command.

Hidden from connectors (not in ``MCP_VISIBLE_GROUPS``): the wizard chat is our own agent's.
"""

from __future__ import annotations

import typer

from sellerclaw_cli._command_group import Cmd, body_field, build_group

NAME = "scheduled-tasks"

SPECS = (
    Cmd(
        "draft",
        "PUT",
        "/agent/cron/draft",
        summary=(
            "Fill the draft card of a scheduled task in the scheduled-task wizard chat. The owner "
            "sees the card next to the chat, can correct it, and creates the task with its Create "
            "button — this command never creates, runs or changes a task itself. Works only in the "
            "wizard chat; anywhere else it is refused with what to do instead. Each call changes "
            "only the fields you pass, so fill the card as you learn things; the answer is the whole "
            "draft with `missing` (what it still needs) and `ready` (true once Create can be "
            "pressed). One schedule form per call — daily: --daily-at 09:00; weekly: --weekly-on "
            "mon,thu --at 09:00; monthly: --monthly-on 1,15 --at 09:00; once: --once-at "
            "2026-11-20T09:00; repeating: --every 2h."
        ),
        body=(
            body_field(
                "name",
                option="--name",
                help="Task name the owner recognises in the task list, e.g. 'Morning sales digest'.",
                example="Morning sales digest",
            ),
            body_field(
                "description",
                option="--description",
                help="One or two sentences telling the owner what the task does.",
            ),
            body_field(
                "message",
                option="--message",
                help=(
                    "What you will be told to do on every run — a complete brief: what to check or "
                    "do, for which stores, what to report. A run starts without this chat, so leave "
                    "nothing implied."
                ),
                example="Check yesterday's orders in every store and report revenue and refunds.",
            ),
            body_field(
                "daily_at",
                option="--daily-at",
                help="Every day at this time, HH:MM (24-hour), e.g. 09:00.",
                example="09:00",
            ),
            body_field(
                "weekly_on",
                option="--weekly-on",
                help=(
                    "Every week on these days, comma-separated from mon,tue,wed,thu,fri,sat,sun, "
                    "e.g. mon,thu. Give the time with --at."
                ),
            ),
            body_field(
                "monthly_on",
                option="--monthly-on",
                help="Every month on these days of the month (1-31), comma-separated, e.g. 1,15. Give the time with --at.",
            ),
            body_field(
                "at",
                option="--at",
                help="Time of day for --weekly-on and --monthly-on, HH:MM (24-hour), e.g. 09:00.",
            ),
            body_field(
                "once_at",
                option="--once-at",
                help="Run once, at this local date and time, YYYY-MM-DDTHH:MM, e.g. 2026-11-20T09:00.",
            ),
            body_field(
                "every",
                option="--every",
                help="Run over and over at this interval, in minutes or hours, e.g. 30m or 2h.",
            ),
            body_field(
                "timezone",
                option="--timezone",
                help="IANA time zone the times are in, e.g. Europe/Berlin or America/New_York.",
                example="Europe/Berlin",
            ),
            body_field(
                "email_report",
                type=bool,
                option="--email-report",
                help="Email the owner the result of every run; --no-email-report turns it off.",
            ),
            body_field(
                "messenger_push",
                type=bool,
                option="--messenger-push",
                help=(
                    "Notify the owner in their messenger after every run; --no-messenger-push turns "
                    "it off."
                ),
            ),
        ),
    ),
)

app = build_group(
    NAME,
    "The scheduled-task wizard: fill the draft card the owner turns into a task with Create.",
    SPECS,
)


def register(parent: typer.Typer) -> None:
    parent.add_typer(app, name=NAME)
