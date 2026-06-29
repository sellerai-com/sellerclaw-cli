from __future__ import annotations

import typer

from sellerclaw_cli._command_group import Cmd, build_group

NAME = "etsy-store"

SPECS = (
    Cmd(
        "get-info",
        "GET",
        "/agent/stores/{store_id}/info",
        summary="Get the Etsy shop info (name, currency, shop id).",
    ),
)

app = build_group(NAME, "Etsy shop admin: shop name, currency and id.", SPECS)


def register(parent: typer.Typer) -> None:
    parent.add_typer(app, name=NAME)
