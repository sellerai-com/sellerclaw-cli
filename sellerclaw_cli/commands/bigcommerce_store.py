from __future__ import annotations

import typer

from sellerclaw_cli._command_group import Cmd, build_group

NAME = "bigcommerce-store"

SPECS = (
    Cmd(
        "get-info",
        "GET",
        "/agent/stores/{store_id}/info",
        summary="Get the BigCommerce store info (name, currency, storefront domain).",
    ),
)

app = build_group(NAME, "BigCommerce store admin: store name, currency and domain.", SPECS)


def register(parent: typer.Typer) -> None:
    parent.add_typer(app, name=NAME)
