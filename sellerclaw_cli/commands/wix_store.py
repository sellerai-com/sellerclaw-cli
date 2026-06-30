from __future__ import annotations

import typer

from sellerclaw_cli._command_group import Cmd, build_group

NAME = "wix-store"

SPECS = (
    Cmd(
        "get-info",
        "GET",
        "/agent/stores/{store_id}/info",
        summary="Get the Wix site info (name, currency, storefront URL).",
    ),
)

app = build_group(NAME, "Wix store admin: site name, currency and storefront URL.", SPECS)


def register(parent: typer.Typer) -> None:
    parent.add_typer(app, name=NAME)
