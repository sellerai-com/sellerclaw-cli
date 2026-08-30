from __future__ import annotations

import typer

from sellerclaw_cli._command_group import Cmd, build_group

NAME = "team"

SPECS = (
    Cmd(
        "list",
        "GET",
        "/agent/team",
        summary=(
            "Every specialist that exists, with `on_team` (delegate to it now), `can_add` "
            "(its integration is connected) and `agent_id` (what to spawn). "
            "`activation_pending` is true while a just-added specialist is still reaching the "
            "running agent."
        ),
    ),
    Cmd(
        "add",
        "POST",
        "/agent/team/{module_id}/enable",
        summary=(
            "Put a specialist on the owner's team — no approval needed, and safe to repeat "
            "(adding one already there answers `added_now: false`). Answers `ready_to_delegate`: "
            "true means spawn now, false means the roster is still on its way — re-read "
            "`team list` in half a minute. A specialist whose integration the owner has not "
            "connected is refused with the reason."
        ),
    ),
)

app = build_group(
    NAME,
    "The owner's specialist team: who is on it, and adding the one a job needs.",
    SPECS,
)


def register(parent: typer.Typer) -> None:
    parent.add_typer(app, name=NAME)
