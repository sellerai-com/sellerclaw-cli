from __future__ import annotations

import typer

from sellerclaw_cli._command_group import Cmd, body_field, build_group, flag

NAME = "support-requests"

SPECS = (
    Cmd(
        "create",
        "POST",
        "/agent/support-requests",
        summary=(
            "Pass a problem, complaint or feature request to the SellerClaw team (the people behind "
            "SellerClaw) on the owner's behalf. One topic per request."
        ),
        body=(
            body_field(
                "kind",
                required=True,
                help=(
                    "bug: something in SellerClaw fails; billing: money, plan or credits; "
                    "feature_request: something SellerClaw cannot do yet; agent_quality: the owner "
                    "is unhappy with how you worked; other."
                ),
                choices=("bug", "billing", "feature_request", "agent_quality", "other"),
                example="bug",
            ),
            body_field(
                "raised_by",
                required=True,
                help=(
                    "owner: they asked to pass it on, or agreed when you offered; agent: a "
                    "SellerClaw-side failure you hit yourself."
                ),
                choices=("owner", "agent"),
                example="owner",
            ),
            body_field("title", required=True, help="One line the team reads first."),
            body_field(
                "details",
                required=True,
                help=(
                    "What happened or what is wanted, in plain words: what was tried, what went "
                    "wrong, which store, order or product."
                ),
            ),
            body_field(
                "owner_quote",
                help="The owner's own words, verbatim. Required when raised_by is owner.",
            ),
            body_field(
                "technical_details",
                help="For the team only: the command that failed and the error text.",
            ),
        ),
    ),
    Cmd(
        "list",
        "GET",
        "/agent/support-requests",
        summary=(
            "Requests this account has sent to the SellerClaw team, newest first, with their "
            "status and the team's comment."
        ),
        flags=(
            flag(
                "status",
                choices=("open", "in_progress", "resolved", "dismissed"),
                help="Keep only requests in this state. Omit for every state.",
            ),
            flag("limit", type=int, minimum=1, maximum=50, help="Max requests to return."),
        ),
    ),
    Cmd(
        "get",
        "GET",
        "/agent/support-requests/{request_id}",
        summary="One request sent to the SellerClaw team: its status and the team's comment.",
    ),
)

app = build_group(
    NAME,
    "Requests to the SellerClaw team: problems, complaints and wishes passed on for the owner.",
    SPECS,
)


def register(parent: typer.Typer) -> None:
    parent.add_typer(app, name=NAME)
