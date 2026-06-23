from __future__ import annotations

import typer

from sellerclaw_cli._command_group import Cmd, body_field, build_group, flag

NAME = "subagent-tasks"

SPECS = (
    Cmd("overview", "GET", "/agent/goals/overview", summary="Goals overview (active goal, team tasks, your tasks)."),
    Cmd(
        "list",
        "GET",
        "/agent/goals/my-tasks",
        summary="List the tasks assigned to you.",
        flags=(flag("agent_id", help="Filter by agent id (defaults to the caller)."),),
    ),
    Cmd("get", "GET", "/agent/goals/agent-tasks/{task_id}", summary="Get one of your tasks by id."),
    Cmd(
        "get-timeline",
        "GET",
        "/agent/goals/events/agent_task/{task_id}",
        summary="Audit timeline (events) for a task.",
    ),
    Cmd(
        "create",
        "POST",
        "/agent/goals/agent-tasks",
        summary="Create a subagent task.",
        body=(
            body_field("title", required=True, help="Short task title."),
            body_field("description", required=True, help="What the assignee must do."),
            body_field("assigned_to", required=True, help="Agent id of the assignee (e.g. 'scout')."),
            body_field("team_task_id", help="Parent team task id (UUID), if any."),
            body_field("deadline", help="ISO-8601 deadline, e.g. 2026-06-20T00:00:00Z."),
        ),
    ),
    Cmd("start", "POST", "/agent/goals/agent-tasks/{task_id}/start", summary="Start working on a task."),
    Cmd(
        "add-note",
        "POST",
        "/agent/goals/agent-tasks/{task_id}/progress",
        summary="Add a progress note to a task.",
        body=(
            body_field(
                "message",
                required=True,
                help="Progress note with concrete data points, not just a status label.",
            ),
        ),
    ),
    Cmd(
        "request-review",
        "POST",
        "/agent/goals/agent-tasks/{task_id}/request-review",
        summary="Submit a task for review with an outcome.",
        body=(
            body_field(
                "outcome",
                required=True,
                help="One string: the full result as a Markdown report (TL;DR, findings, numbers). "
                "The reviewer reads only this field — put structured data inside it, not as extra keys.",
            ),
        ),
    ),
    Cmd("complete", "POST", "/agent/goals/agent-tasks/{task_id}/complete", summary="Mark a task complete."),
    Cmd(
        "fail",
        "POST",
        "/agent/goals/agent-tasks/{task_id}/fail",
        summary="Mark a task failed with a reason.",
        body=(body_field("failure_reason", required=True, help="Concrete blocker that stopped the work."),),
    ),
    Cmd("cancel", "POST", "/agent/goals/agent-tasks/{task_id}/cancel", summary="Cancel a task."),
    Cmd(
        "reopen",
        "POST",
        "/agent/goals/agent-tasks/{task_id}/reopen",
        summary="Reopen a closed task.",
        body=(body_field("feedback", required=True, help="Why the task is being reopened."),),
    ),
    Cmd(
        "reject-review",
        "POST",
        "/agent/goals/agent-tasks/{task_id}/reject-review",
        summary="Reject a task that was submitted for review.",
        body=(body_field("feedback", required=True, help="What must change before it can pass review."),),
    ),
    Cmd(
        "return",
        "POST",
        "/agent/goals/agent-tasks/{task_id}/return-to-work",
        summary="Return a task to in-progress.",
        body=(body_field("feedback", required=True, help="What the assignee should do next."),),
    ),
)

app = build_group(NAME, "Tasks assigned to you by the supervisor (executor lifecycle).", SPECS)


def register(parent: typer.Typer) -> None:
    parent.add_typer(app, name=NAME)
