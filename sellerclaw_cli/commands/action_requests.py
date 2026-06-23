from __future__ import annotations

import typer

from sellerclaw_cli._command_group import Cmd, body_field, build_group

NAME = "action-requests"

SPECS = (
    Cmd(
        "list",
        "GET",
        "/agent/goals/action-requests",
        summary="List action requests you raised to the owner (still open).",
    ),
    Cmd(
        "get",
        "GET",
        "/agent/goals/action-requests/{request_id}",
        summary="Get one action request by id (check its status).",
    ),
    Cmd(
        "create",
        "POST",
        "/agent/goals/action-requests",
        summary="Ask the owner to decide on or carry out something (approve, pay, connect, provide info).",
        body=(
            body_field(
                "kind",
                help="Request kind.",
                choices=("approval", "payment", "input", "connect", "review", "generic"),
                example="generic",
            ),
            body_field(
                "mode",
                help=(
                    "Who acts after the owner responds. 'decision': you can do it yourself but "
                    "need a go-ahead (owner approves/rejects, then you act). 'delegation': only "
                    "the owner can do it (they do it and report back). Omit to default from kind "
                    "(approval/review -> decision, else delegation)."
                ),
                choices=("decision", "delegation"),
                example="decision",
            ),
            body_field("title", required=True, help="Short, action-oriented title."),
            body_field("description", required=True, help="What you need the owner to do and why."),
            body_field(
                "summary",
                help=(
                    "Optional one-line statement of exactly what you're asking, shown to the owner "
                    "above the details (e.g. 'Approve sending this email before it goes out')."
                ),
            ),
            body_field("goal_id", help="Related goal id (UUID), if any."),
            body_field("team_task_id", help="Related team task id (UUID), if any."),
            body_field("cta_label", help="Optional button label for the owner."),
            body_field("cta_url", help="Optional link the owner should open."),
            body_field("blocking", type=bool, help="Whether work is blocked until the owner acts (default true)."),
            body_field("deadline", help="ISO-8601 deadline, e.g. 2026-06-20T00:00:00Z."),
        ),
    ),
    Cmd(
        "cancel",
        "POST",
        "/agent/goals/action-requests/{request_id}/cancel",
        summary="Withdraw an action request that is no longer needed.",
    ),
)

app = build_group(NAME, "Action requests (ask the owner to act).", SPECS)


def register(parent: typer.Typer) -> None:
    parent.add_typer(app, name=NAME)
