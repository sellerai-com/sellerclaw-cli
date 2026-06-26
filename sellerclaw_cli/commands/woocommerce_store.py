from __future__ import annotations

import typer

from sellerclaw_cli._command_group import Cmd, build_group

NAME = "woocommerce-store"

SPECS = (
    Cmd(
        "get-info",
        "GET",
        "/agent/stores/{store_id}/info",
        summary="Get the WooCommerce store info (name, currency, WooCommerce version, store URL).",
    ),
)

app = build_group(NAME, "WooCommerce store admin: store name, currency and version.", SPECS)


def register(parent: typer.Typer) -> None:
    parent.add_typer(app, name=NAME)
