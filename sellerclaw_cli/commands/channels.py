from __future__ import annotations

import typer

from sellerclaw_cli._command_group import Cmd, body_field, build_group, flag

NAME = "channels"

SPECS = (
    Cmd(
        "list",
        "GET",
        "/agent/sales-channels",
        summary="List connected sales channels (stores).",
        flags=(
            flag("platform", help="Filter by platform (shopify, ebay, ...)."),
            flag(
                "status",
                repeatable=True,
                help="Filter by status (active, credentials_invalid, ...); repeat for multiple.",
            ),
        ),
    ),
    Cmd(
        "get",
        "GET",
        "/agent/sales-channels/{sales_channel_id}",
        summary="Get one sales channel by id.",
    ),
    Cmd(
        "set-margin",
        "PATCH",
        "/agent/sales-channels/{sales_channel_id}",
        summary="Set this store's dropshipping markup (margin multiplier, e.g. 1.3 = +30%).",
        body=(
            body_field(
                "margin",
                type=float,
                required=True,
                help="Cost multiplier applied when pricing listings (>= 1.0; 1.15 = +15%).",
                example=1.3,
            ),
        ),
    ),
    Cmd(
        "set-lead-time",
        "PATCH",
        "/agent/sales-channels/{sales_channel_id}",
        summary=(
            "Set this store's supplier restock lead time (days) — how long a reorder takes to "
            "arrive. Drives the reorder math in `analytics inventory`; unset stores fall back to a "
            "built-in default."
        ),
        body=(
            body_field(
                "reorder_lead_time_days",
                type=int,
                required=True,
                help="Days from placing a reorder to stock arriving (1-365).",
                example=14,
            ),
        ),
    ),
)

app = build_group(NAME, "Connected sales channels (stores).", SPECS)


def register(parent: typer.Typer) -> None:
    parent.add_typer(app, name=NAME)
