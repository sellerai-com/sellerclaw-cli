from __future__ import annotations

import typer

from sellerclaw_cli._command_group import Cmd, body_field, build_group, flag

NAME = "subagent-tasks"

# Active-task ergonomics: `start <id>` remembers the task per agent, so the follow-up commands
# below can omit the id (they act on your active task) and accept a short id prefix, expanded
# against your task list. Avoids retyping — and mistyping — a 36-char UUID across separate calls.
_SLOT = "subagent_task"
_LIST = "/agent/goals/my-tasks"

SPECS = (
    Cmd("overview", "GET", "/agent/goals/overview", summary="Goals overview (active goal, team tasks, your tasks)."),
    Cmd(
        "list",
        "GET",
        "/agent/goals/my-tasks",
        summary="List the tasks assigned to you.",
        flags=(
            flag("agent_id", help="Filter by agent id (defaults to the caller)."),
            flag("team_task_id", help="Filter to the subtasks of this team task (UUID)."),
        ),
    ),
    Cmd(
        "get",
        "GET",
        "/agent/goals/agent-tasks/{task_id}",
        summary="Get one of your tasks by id.",
        active_slot=_SLOT,
        resolve_list_path=_LIST,
    ),
    Cmd(
        "get-timeline",
        "GET",
        "/agent/goals/events/agent_task/{task_id}",
        summary="Audit timeline (events) for a task.",
        active_slot=_SLOT,
        resolve_list_path=_LIST,
    ),
    Cmd(
        "reports",
        "GET",
        "/agent/goals/reports/agent_task/{task_id}",
        summary="Report history: every result submitted across the task's re-runs, with review verdicts. "
        "Read this before re-running a returned task to see what earlier attempts already covered.",
        active_slot=_SLOT,
        resolve_list_path=_LIST,
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
    Cmd(
        "start",
        "POST",
        "/agent/goals/agent-tasks/{task_id}/start",
        summary="Start working on a task (remembers it as your active task for later commands).",
        active_slot=_SLOT,
        active_write=True,
        resolve_list_path=_LIST,
    ),
    Cmd(
        "add-note",
        "POST",
        "/agent/goals/agent-tasks/{task_id}/progress",
        summary="Add a progress note to a task.",
        body=(
            body_field(
                "message",
                required=True,
                option="--message",
                help="Progress note with concrete data points, not just a status label.",
            ),
        ),
        active_slot=_SLOT,
        resolve_list_path=_LIST,
    ),
    Cmd(
        "set-plan",
        "POST",
        "/agent/goals/agent-tasks/{task_id}/plan",
        summary="Replace your task's plan — an ordered checklist you tick off and resume from.",
        body=(
            body_field(
                "plan",
                type=list,
                required=True,
                help=(
                    "Ordered list of steps. Each item is an object with `text` (required) and "
                    "optional `status` (pending|in_progress|done|skipped|failed), `id`, `note` (the "
                    "owner-facing progress line) and `metadata` (private). Omit `id` for a new "
                    "step (the server assigns one); re-send an existing `id` to keep that item's "
                    "history when restructuring."
                ),
                example=[
                    {"text": "Search CJ for pet products"},
                    {"text": "Pick the best candidate"},
                    {"text": "Save chosen product to catalog"},
                    {"text": "Publish to Shopify"},
                ],
                option="--step",
                item_key="text",
            ),
        ),
        active_slot=_SLOT,
        resolve_list_path=_LIST,
    ),
    Cmd(
        "plan-check",
        "POST",
        "/agent/goals/agent-tasks/{task_id}/plan/check",
        summary="Update plan items: set status, owner-facing note, and/or merge metadata.",
        body=(
            body_field(
                "items",
                type=dict,
                repeatable=True,
                help=(
                    "Several items at once — an array of "
                    '{"item_id": "...", "status"?: ..., "note"?: ..., "metadata"?: {...}}. '
                    "Use it when more than one step changed in the same breath (one finished, the "
                    "next started). Either send this or the single-item fields below, not both."
                ),
                example=[
                    {"item_id": "1", "status": "done", "note": "Saved the folding organizer"},
                    {"item_id": "2", "status": "in_progress"},
                ],
            ),
            body_field(
                "item_id",
                option="--item-id",
                help="Id of the plan item to update (read it from `get`). Single-item shorthand.",
            ),
            body_field(
                "status",
                choices=("pending", "in_progress", "done", "skipped", "failed"),
                option="--status",
                help=(
                    "New status for the item. A step you worked that did not land is `failed`, "
                    "never `done` — partial counts as failed. `skipped` and `failed` need a `note`."
                ),
            ),
            body_field(
                "note",
                option="--note",
                help=(
                    "Short plain-language line the owner reads under this step in their plan view "
                    '(e.g. "Saved the folding organizer to the catalog"). No raw ids.'
                ),
            ),
            body_field(
                "metadata",
                type=dict,
                help=(
                    "Keys to merge into the item — ids of things you created or saved so you don't "
                    'redo them on resume (e.g. {"catalog_product_id": "prod-9"}). Never shown to '
                    "the owner."
                ),
            ),
        ),
        active_slot=_SLOT,
        resolve_list_path=_LIST,
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
            body_field(
                "plan",
                type=dict,
                repeatable=True,
                help=(
                    "Close the plan in this same call — an array of "
                    '{"item_id": "...", "status": "done"|"skipped"|"failed", "note"?: ...}. '
                    "Every step must end `done`, `skipped` or `failed`, or the report is rejected "
                    "and names what is still open. A step you worked that did not land is `failed`, "
                    "never `done` — partial counts as failed. `skipped` and `failed` need a `note`."
                ),
                example=[
                    {"item_id": "1", "status": "done"},
                    {"item_id": "2", "status": "failed", "note": "1 of 3 published; two refused by the marketplace"},
                ],
            ),
        ),
        active_slot=_SLOT,
        resolve_list_path=_LIST,
    ),
    Cmd(
        "complete",
        "POST",
        "/agent/goals/agent-tasks/{task_id}/complete",
        summary="Mark a task complete.",
        active_slot=_SLOT,
        resolve_list_path=_LIST,
    ),
    Cmd(
        "fail",
        "POST",
        "/agent/goals/agent-tasks/{task_id}/fail",
        summary="Mark a task failed with a reason.",
        body=(body_field("failure_reason", required=True, help="Concrete blocker that stopped the work."),),
        active_slot=_SLOT,
        resolve_list_path=_LIST,
    ),
    Cmd(
        "cancel",
        "POST",
        "/agent/goals/agent-tasks/{task_id}/cancel",
        summary="Cancel a task.",
        active_slot=_SLOT,
        resolve_list_path=_LIST,
    ),
    Cmd(
        "reopen",
        "POST",
        "/agent/goals/agent-tasks/{task_id}/reopen",
        summary="Reopen a closed task.",
        body=(body_field("feedback", required=True, help="Why the task is being reopened."),),
        active_slot=_SLOT,
        resolve_list_path=_LIST,
    ),
    Cmd(
        "reject-review",
        "POST",
        "/agent/goals/agent-tasks/{task_id}/reject-review",
        summary="Reject a task that was submitted for review.",
        body=(body_field("feedback", required=True, help="What must change before it can pass review."),),
        active_slot=_SLOT,
        resolve_list_path=_LIST,
    ),
    Cmd(
        "return",
        "POST",
        "/agent/goals/agent-tasks/{task_id}/return-to-work",
        summary="Return a task to in-progress.",
        body=(body_field("feedback", required=True, help="What the assignee should do next."),),
        active_slot=_SLOT,
        resolve_list_path=_LIST,
    ),
)

app = build_group(NAME, "Tasks assigned to you by the supervisor (executor lifecycle).", SPECS)


def register(parent: typer.Typer) -> None:
    parent.add_typer(app, name=NAME)
