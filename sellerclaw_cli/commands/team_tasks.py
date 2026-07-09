from __future__ import annotations

import typer

from sellerclaw_cli._command_group import Cmd, body_field, build_group

NAME = "team-tasks"

# Active-task ergonomics (see subagent-tasks): `start <id>` remembers the team task per agent, so
# the follow-up commands can omit the id and accept a short id prefix (expanded against the team
# task list). Slot is separate from subagent-tasks so the two pointers never collide.
_SLOT = "team_task"
_LIST = "/agent/goals/team-tasks"

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
        "request-review",
        "POST",
        "/agent/goals/team-tasks/{task_id}/request-review",
        summary="Submit a team task for review.",
        body=(body_field("outcome", required=True, help="The result as a Markdown report; the owner reads only this."),),
        active_slot=_SLOT,
        resolve_list_path=_LIST,
    ),
    Cmd(
        "complete",
        "POST",
        "/agent/goals/team-tasks/{task_id}/complete",
        summary="Mark a team task complete.",
        body=(body_field("outcome", required=True, help="Final result summary as a Markdown report."),),
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
