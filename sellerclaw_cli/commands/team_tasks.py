from __future__ import annotations

import typer

from sellerclaw_cli._command_group import Cmd, body_field, build_group

NAME = "team-tasks"

# Active-task ergonomics (see subagent-tasks): `start <id>` remembers the team task per agent, so
# the follow-up commands can omit the id and accept a short id prefix (expanded against the team
# task list). Slot is separate from subagent-tasks so the two pointers never collide.
_SLOT = "team_task"
_LIST = "/agent/goals/team-tasks"

# Reporting and closing the plan are one decision; sending them together is what removes the
# "tick, tick, tick, report" sequence at the end of every job.
_PLAN_CLOSE_FIELD = body_field(
    "plan",
    type=dict,
    repeatable=True,
    help=(
        "Close the plan in this same call — an array of "
        '{"item_id": "...", "status": "done"|"skipped", "note"?: ...}. '
        "Every phase must end `done` or `skipped`, or the report is rejected and names what is "
        "still open."
    ),
    example=[{"item_id": "1", "status": "done"}, {"item_id": "2", "status": "skipped"}],
)

SPECS = (
    Cmd("overview", "GET", "/agent/goals/overview", summary="Goals overview (active goal, team tasks, agent tasks)."),
    Cmd(
        "get",
        "GET",
        "/agent/goals/team-tasks/{task_id}",
        summary="Get one team task by id.",
        active_slot=_SLOT,
        resolve_list_path=_LIST,
    ),
    Cmd(
        "get-timeline",
        "GET",
        "/agent/goals/events/team_task/{task_id}",
        summary="Audit timeline (events) for a team task.",
        active_slot=_SLOT,
        resolve_list_path=_LIST,
    ),
    Cmd(
        "reports",
        "GET",
        "/agent/goals/reports/team_task/{task_id}",
        summary="Report history: every result submitted across the team task's re-runs, with review verdicts. "
        "Read this before re-running a returned task to see what earlier attempts already covered.",
        active_slot=_SLOT,
        resolve_list_path=_LIST,
    ),
    Cmd(
        "create",
        "POST",
        "/agent/goals/team-tasks",
        summary="Create a team task.",
        body=(
            body_field("title", required=True, help="Short task title."),
            body_field("description", required=True, help="What the team task delivers."),
            body_field("goal_id", help="Parent goal id (UUID), if this serves the active goal."),
            body_field("deadline", help="ISO-8601 deadline, e.g. 2026-06-20T00:00:00Z."),
            body_field("task_type", help="Optional classifier for the task."),
            body_field("effort", help="Effort tier.", example="standard"),
            body_field("auto_approve", type=bool, help="Auto-approve on completion instead of owner review."),
        ),
    ),
    Cmd(
        "update",
        "PATCH",
        "/agent/goals/team-tasks/{task_id}",
        summary="Update a team task.",
        body=(
            body_field("title", help="New title."),
            body_field("description", help="New description."),
            body_field("deadline", help="New ISO-8601 deadline."),
        ),
        active_slot=_SLOT,
        resolve_list_path=_LIST,
    ),
    Cmd(
        "start",
        "POST",
        "/agent/goals/team-tasks/{task_id}/start",
        summary="Start a team task (remembers it as your active team task for later commands).",
        active_slot=_SLOT,
        active_write=True,
        resolve_list_path=_LIST,
    ),
    Cmd(
        "approve",
        "POST",
        "/agent/goals/team-tasks/{task_id}/approve",
        summary="Approve a team task.",
        active_slot=_SLOT,
        resolve_list_path=_LIST,
    ),
    Cmd(
        "set-plan",
        "POST",
        "/agent/goals/team-tasks/{task_id}/plan",
        summary="Replace the team task's plan — your ordered list of the phases the job takes.",
        body=(
            body_field(
                "plan",
                type=list,
                required=True,
                help=(
                    "Ordered list of phases. Each item is an object with `text` (required) and "
                    "optional `status` (pending|in_progress|done|skipped), `id`, `note` (the "
                    "owner-facing progress line) and `metadata` (private). "
                    "Omit `id` for a new phase (the server assigns one); re-send an existing `id` "
                    "to keep its history. Lay out every phase up front, including ones whose agent "
                    "task you can't create yet (they depend on an earlier phase's output)."
                ),
                example=[
                    {"text": "Source a pet product from the supplier"},
                    {"text": "Publish the chosen product to Shopify"},
                ],
            ),
        ),
        active_slot=_SLOT,
        resolve_list_path=_LIST,
    ),
    Cmd(
        "plan-check",
        "POST",
        "/agent/goals/team-tasks/{task_id}/plan/check",
        summary="Update plan phases: set status, owner-facing note, and/or merge metadata.",
        body=(
            body_field(
                "items",
                type=dict,
                repeatable=True,
                help=(
                    "Several phases at once — an array of "
                    '{"item_id": "...", "status"?: ..., "note"?: ..., "metadata"?: {...}}. '
                    "Use it when more than one phase changed in the same breath (one finished, the "
                    "next started). Either send this or the single-phase fields below, not both."
                ),
                example=[
                    {"item_id": "1", "status": "done", "note": "Sourced the folding organizer"},
                    {"item_id": "2", "status": "in_progress"},
                ],
            ),
            body_field(
                "item_id",
                help="Id of the plan item to update (read it from `get`). Single-phase shorthand.",
            ),
            body_field(
                "status",
                choices=("pending", "in_progress", "done", "skipped"),
                help="New status for the phase.",
            ),
            body_field(
                "note",
                help=(
                    "Short plain-language line the owner reads under this phase in their plan view "
                    '(e.g. "Sourced the folding organizer ($4.20) from CJ"). No raw ids.'
                ),
            ),
            body_field(
                "metadata",
                type=dict,
                help=(
                    "Keys to merge into the item — e.g. the fulfilling agent task id: "
                    '{"agent_task_id": "<id>"}. Never shown to the owner.'
                ),
            ),
        ),
        active_slot=_SLOT,
        resolve_list_path=_LIST,
    ),
    Cmd(
        "request-review",
        "POST",
        "/agent/goals/team-tasks/{task_id}/request-review",
        summary="Submit a team task for review.",
        body=(
            body_field("outcome", required=True, help="The result as a Markdown report; the owner reads only this."),
            body_field(
                "attachments",
                type=dict,
                repeatable=True,
                help="Optional media for the report — an array of objects, each "
                '{"kind": "image"|"file"|"link", "url": "...", "title"?: "...", '
                '"file_id"?: "<id from `sellerclaw files upload`>"}. '
                "Use for screenshots, generated files, or reference links; do not paste these into `outcome`.",
                example=[{"kind": "link", "url": "https://example.com/dashboard", "title": "Live dashboard"}],
            ),
            _PLAN_CLOSE_FIELD,
        ),
        active_slot=_SLOT,
        resolve_list_path=_LIST,
    ),
    Cmd(
        "complete",
        "POST",
        "/agent/goals/team-tasks/{task_id}/complete",
        summary="Mark a team task complete.",
        body=(
            body_field("outcome", required=True, help="Final result summary as a Markdown report."),
            _PLAN_CLOSE_FIELD,
        ),
        active_slot=_SLOT,
        resolve_list_path=_LIST,
    ),
    Cmd(
        "fail",
        "POST",
        "/agent/goals/team-tasks/{task_id}/fail",
        summary="Mark a team task failed.",
        body=(body_field("failure_reason", required=True, help="Concrete blocker that stopped the work."),),
        active_slot=_SLOT,
        resolve_list_path=_LIST,
    ),
    Cmd(
        "cancel",
        "POST",
        "/agent/goals/team-tasks/{task_id}/cancel",
        summary="Cancel a team task.",
        active_slot=_SLOT,
        resolve_list_path=_LIST,
    ),
)

app = build_group(NAME, "Team tasks (supervisor-level work items).", SPECS)


def register(parent: typer.Typer) -> None:
    parent.add_typer(app, name=NAME)
