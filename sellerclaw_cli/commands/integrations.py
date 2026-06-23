from __future__ import annotations

import typer

from sellerclaw_cli._command_group import Cmd, build_group

NAME = "integrations"

SPECS = (
    Cmd(
        "list",
        "GET",
        "/agent/integrations",
        summary=(
            "List all integration kinds with the user's current connections and basic info "
            "(domain, platform, marketplace_id, account name, status, dates, margin, "
            "shopify_theme_api). Replaces per-kind listings (channels, ad-accounts, suppliers, "
            "research-*) when a single overview is enough."
        ),
    ),
)

app = build_group(
    NAME,
    "Unified overview of all integrations (stores, ad accounts, suppliers, research).",
    SPECS,
)


def register(parent: typer.Typer) -> None:
    parent.add_typer(app, name=NAME)
