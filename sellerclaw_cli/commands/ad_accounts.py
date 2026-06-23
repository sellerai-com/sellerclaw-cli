from __future__ import annotations

import typer

from sellerclaw_cli._command_group import Cmd, build_group

NAME = "ad-accounts"

SPECS = (
    Cmd("list", "GET", "/agent/ad-accounts", summary="List connected ad accounts (Meta, Google)."),
    Cmd(
        "get-strategy",
        "GET",
        "/agent/ad-accounts/{account_id}/strategy",
        summary="Read strategy thresholds (target CPA/ROAS, spend caps) for one ad account.",
    ),
)

app = build_group(NAME, "Connected ad accounts and their strategy settings.", SPECS)


def register(parent: typer.Typer) -> None:
    parent.add_typer(app, name=NAME)
