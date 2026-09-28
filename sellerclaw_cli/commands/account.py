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
    Cmd(
        "billing",
        "GET",
        "/agent/billing/overview",
        summary="Your plan, credits left, this period's spend and what happens when credits run out.",
    ),
)

app = build_group(NAME, "Your SellerClaw account: profile, settings, integrations, plan and credits.", SPECS)


def register(parent: typer.Typer) -> None:
    parent.add_typer(app, name=NAME)
