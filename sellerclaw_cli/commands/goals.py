from __future__ import annotations

import typer

from sellerclaw_cli._command_group import Cmd, body_field, build_group, flag

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
    Cmd(
        "journal",
        "GET",
        "/agent/goals/{goal_id}/journal",
        summary=(
            "The goal's journal, newest first: your entries with their details, the owner's notes, "
            "your working state, the goal's own events and its tasks' milestones. Page back with "
            "--before set to the previous page's next_before."
        ),
        flags=(
            flag("limit", type=int, minimum=1, maximum=50, help="Max lines to return (default 20)."),
            flag("before", help="ISO-8601 time: only lines older than it (a page's next_before)."),
        ),
    ),
    Cmd(
        "add-entry",
        "POST",
        "/agent/goals/{goal_id}/journal",
        summary=(
            "Write in the goal's journal: a decision, a finding, an action you took outside any task, "
            "or a result. Tasks, approvals and status changes are recorded already; don't write them "
            "again."
        ),
        body=(
            body_field(
                "entry",
                required=True,
                option="--entry",
                choices=("decision", "finding", "action", "result"),
                help="What this entry is.",
            ),
            body_field(
                "text",
                required=True,
                option="--text",
                help="The owner's line, in their language: what you decided, found, did or got.",
            ),
            body_field(
                "details",
                option="--details",
                help="Your technical layer: ids, commands, raw figures. Never shown to the owner.",
            ),
        ),
    ),
    Cmd(
        "set-state",
        "PUT",
        "/agent/goals/{goal_id}/state",
        summary=(
            "Rewrite your working state for the goal: strategy, numbers (start → now), what you are "
            "doing, what comes next and when, what blocks you. It rides into your sessions in the "
            "<active_goal> block; the previous page stays in the journal."
        ),
        body=(
            body_field(
                "text",
                required=True,
                option="--text",
                help="The whole page, in the owner's language (up to 1,500 characters).",
            ),
            body_field(
                "details",
                option="--details",
                help="Your technical layer, up to 1,000 characters. Never shown to the owner.",
            ),
        ),
    ),
)

app = build_group(NAME, "Goals (the owner's single active objective).", SPECS)


def register(parent: typer.Typer) -> None:
    parent.add_typer(app, name=NAME)
