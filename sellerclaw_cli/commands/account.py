from __future__ import annotations

import typer

from sellerclaw_cli._command_group import Cmd, build_group

NAME = "account"

SPECS = (
    Cmd(
        "overview",
        "GET",
        "/agent/overview",
        summary="Profile, agent settings and connected integrations in one snapshot.",
    ),
)

app = build_group(NAME, "Your SellerClaw account: profile, settings, integrations.", SPECS)


def register(parent: typer.Typer) -> None:
    parent.add_typer(app, name=NAME)
