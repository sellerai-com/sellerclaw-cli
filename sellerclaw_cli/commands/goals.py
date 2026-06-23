from __future__ import annotations

import typer

from sellerclaw_cli._command_group import Cmd, body_field, build_group

NAME = "goals"

SPECS = (
    Cmd(
        "overview",
        "GET",
        "/agent/goals/overview",
        summary="Working snapshot: the owner's single active goal plus team tasks and agent tasks.",
    ),
    Cmd("get", "GET", "/agent/goals/{goal_id}", summary="Get one goal by id."),
    Cmd(
        "get-timeline",
        "GET",
        "/agent/goals/events/goal/{goal_id}",
        summary="Audit timeline (events) for a goal.",
    ),
    Cmd(
        "create",
        "POST",
        "/agent/goals",
        summary="Propose a goal — created as a draft for the owner to activate.",
        body=(
            body_field("title", required=True, help="Short goal title."),
            body_field("description", required=True, help="What success looks like for the owner."),
            body_field("context", type=dict, help="Optional structured context object."),
            body_field("success_criteria", type=str, repeatable=True, help="List of measurable criteria."),
            body_field("deadline", help="ISO-8601 deadline, e.g. 2026-06-20T00:00:00Z."),
        ),
    ),
    Cmd(
        "request-review",
        "POST",
        "/agent/goals/{goal_id}/request-review",
        summary="Submit a goal for the owner's review when it looks achieved.",
        body=(body_field("outcome", required=True, help="Why the goal looks achieved, as a Markdown summary."),),
    ),
)

app = build_group(NAME, "Goals (the owner's single active objective).", SPECS)


def register(parent: typer.Typer) -> None:
    parent.add_typer(app, name=NAME)
