from __future__ import annotations

import typer

from sellerclaw_cli._command_group import Cmd, build_group, flag

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
)

app = build_group(NAME, "Connected sales channels (stores).", SPECS)


def register(parent: typer.Typer) -> None:
    parent.add_typer(app, name=NAME)
