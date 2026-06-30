from __future__ import annotations

import typer

from sellerclaw_cli._command_group import Cmd, build_group

NAME = "walmart-store"

SPECS = (
    Cmd(
        "get-info",
        "GET",
        "/agent/stores/{store_id}/info",
        summary="Get the Walmart store info (name, currency, marketplace).",
    ),
)

app = build_group(NAME, "Walmart store admin: store name, currency and marketplace.", SPECS)


def register(parent: typer.Typer) -> None:
    parent.add_typer(app, name=NAME)
