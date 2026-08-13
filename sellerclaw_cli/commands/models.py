from __future__ import annotations

import typer

from sellerclaw_cli._command_group import Cmd, body_field, build_group, flag

NAME = "models"

#: Every value below is a word the owner reads back in `overview` — one vocabulary for reads and
#: writes, so a change is written the way it was seen instead of guessed from a boolean flag.
_REASON = body_field(
    "reason",
    required=True,
    help="Why the owner is being asked, in their words. It is shown on the approval.",
)

SPECS = (
    Cmd(
        "overview",
        "GET",
        "/agent/models",
        summary="What this account runs on: chat and media models, and whose keys they use.",
        flags=(
            flag(
                "effort",
                choices=("medium", "high", "max"),
                help="One level in full. Default: the level in use.",
            ),
            flag("all", type=bool, help="Every level in full instead of one."),
        ),
    ),
    Cmd(
        "set-effort",
        "POST",
        "/agent/models/effort",
        summary="Ask the owner to change the effort level (stronger models cost more per run).",
        body=(
            body_field(
                "effort",
                required=True,
                choices=("medium", "high", "max"),
                help="Chat and image/video generation both move to this level.",
            ),
            _REASON,
        ),
    ),
    Cmd(
        "set-region",
        "POST",
        "/agent/models/region",
        summary="Ask the owner to restrict routing to US providers, or to lift that.",
        body=(
            body_field(
                "region",
                required=True,
                choices=("us-only", "worldwide"),
                help="us-only keeps every model with a US provider; worldwide lifts the limit.",
            ),
            _REASON,
        ),
    ),
    Cmd(
        "set-source",
        "POST",
        "/agent/models/source",
        summary="Ask the owner to run only on their own keys, or to use SellerClaw's models too.",
        body=(
            body_field(
                "source",
                required=True,
                choices=("all", "own-only"),
                help=(
                    "own-only drops every model SellerClaw pays for; it needs the owner's own key "
                    "or endpoint, added by them in Settings — never handed over in chat."
                ),
            ),
            _REASON,
        ),
    ),
    Cmd(
        "disable",
        "POST",
        "/agent/models/disable",
        summary="Ask the owner to stop routing to one model, or to a whole provider.",
        body=(
            body_field(
                "target",
                required=True,
                example="moonshot",
                help="A model id or a provider id, exactly as printed by `overview`.",
            ),
            body_field(
                "effort",
                choices=("medium", "high", "max"),
                help="Narrow to one level. Default: every level it appears on.",
            ),
            body_field(
                "role",
                choices=("complex", "simple"),
                help="Narrow to one group. Default: both. Media models have no on/off switch.",
            ),
            _REASON,
        ),
    ),
    Cmd(
        "enable",
        "POST",
        "/agent/models/enable",
        summary="Ask the owner to put a switched-off model or provider back into the lineup.",
        body=(
            body_field(
                "target",
                required=True,
                example="moonshot",
                help="A model id or a provider id, exactly as printed by `overview`.",
            ),
            body_field(
                "effort",
                choices=("medium", "high", "max"),
                help="Narrow to one level. Default: every level it is switched off on.",
            ),
            body_field(
                "role",
                choices=("complex", "simple"),
                help="Narrow to one group. Default: both.",
            ),
            _REASON,
        ),
    ),
)

app = build_group(
    NAME,
    "Which AI models this account runs on. Reads are free; every change asks the owner first.",
    SPECS,
)


def register(parent: typer.Typer) -> None:
    parent.add_typer(app, name=NAME)
