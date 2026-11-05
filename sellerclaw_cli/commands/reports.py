"""Report tasks: the reports the owner set up in Reports, made by a scheduled task's run.

A report task is a scheduled task made from a report template ("Weekly finance every Monday"). Each
run makes the report's copy (the numbers are the server's), reads it and publishes a short take on
top; the owner gets it by email or messenger and finds every copy in Reports. In a chat the agent
reads a copy the owner attached (an ``[report]`` reference).

Hidden from connectors (not in ``MCP_VISIBLE_GROUPS``): only our own agent's scheduled runs make
and publish report copies.
"""

from __future__ import annotations

import typer

from sellerclaw_cli._command_group import LONG_TIMEOUT_SECONDS, Cmd, body_field, build_group

NAME = "reports"

SPECS = (
    Cmd(
        "list",
        "GET",
        "/agent/reports",
        summary=(
            "The reports the owner set up in Reports, each with its schedule state and its latest "
            "copy (id, period, headline). Read one copy in full with `sellerclaw reports get COPY_ID`."
        ),
        read_only=True,
    ),
    Cmd(
        "get",
        "GET",
        "/agent/reports/copies/{copy_id}",
        summary=(
            "One copy of a report: its lead numbers (`metrics`), the facts to write a take from "
            "(`brief`), the copy before it (`previous`), whether anything needs the owner "
            "(`needs_attention`) and the take already published (`note`). `status` is `running` "
            "while the numbers are still being computed — use `sellerclaw --wait reports get "
            "COPY_ID` to hold until they are in."
        ),
        read_only=True,
        # A copy still computing answers like a job, so `--wait` holds on it the way `make` does.
        timeout=LONG_TIMEOUT_SECONDS,
        job_poll_path="/agent/reports/copies/{job_id}",
    ),
    Cmd(
        "make",
        "POST",
        "/agent/reports/make",
        summary=(
            "Make this run's report copy — only inside a scheduled report task's run (its "
            "instruction says which report). Run it as `sellerclaw --wait reports make`: some "
            "reports take a minute to compute. Asking again in the same run returns the same copy. "
            "The answer is the copy as `reports get` shows it, with `next` naming the publish "
            "command."
        ),
        timeout=LONG_TIMEOUT_SECONDS,
        job_poll_path="/agent/reports/copies/{job_id}",
    ),
    Cmd(
        "publish",
        "POST",
        "/agent/reports/copies/{copy_id}/publish",
        summary=(
            "Publish your take on this run's report copy: one headline (what changed since the last "
            "copy and why) and 1–3 points, each with at most one errand the owner can hand you "
            "with a click. Only facts from the copy's `metrics` and `brief`. The copy is then sent "
            "to the owner the way the task delivers (email / messenger); add --quiet when the task "
            "is a quiet one (`quiet_template`) and nothing needs the owner — the copy is kept in "
            "Reports and nothing is sent. To attach errands, pass the points as JSON with -b: "
            '{"headline": "...", "points": [{"text": "...", "action": {"label": "Draft replies", '
            '"prompt": "Draft replies to the two unanswered reviews"}}]}.'
        ),
        body=(
            body_field(
                "headline",
                required=True,
                option="--headline",
                help="One sentence, under 200 characters: what changed since the last copy and why.",
                example="Sales fell 42% to $355.96 on four orders — two big buyers from last week did not return.",
            ),
            body_field(
                "points",
                type=list,
                option="--point",
                item_key="text",
                help=(
                    "1–3 points, each under 400 characters; repeat --point for each. In -b JSON a "
                    "point may carry `action` = {label (under 40 characters), prompt (the errand you "
                    "will be asked to do, under 500)}."
                ),
                example=[{"text": "Two orders have waited three days to ship."}],
            ),
            body_field(
                "quiet",
                type=bool,
                option="--quiet",
                help=(
                    "Keep the copy in Reports without sending it — only for a quiet report task, "
                    "when nothing needs the owner."
                ),
            ),
        ),
    ),
)

app = build_group(
    NAME,
    "Report tasks: make, read and publish the copies of the reports the owner set up in Reports.",
    SPECS,
)


def register(parent: typer.Typer) -> None:
    parent.add_typer(app, name=NAME)
