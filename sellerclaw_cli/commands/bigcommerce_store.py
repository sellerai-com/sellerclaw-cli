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
    Cmd(
        "list-locations",
        "GET",
        "/agent/stores/{store_id}/locations",
        summary="List the store's warehouses; 'is_default' marks the one stock is written to.",
    ),
    Cmd(
        "refresh-locations",
        "POST",
        "/agent/stores/{store_id}/locations/refresh",
        summary=(
            "Re-read warehouses from BigCommerce now — for one the seller just created there. "
            "Otherwise the mirror only refreshes daily."
        ),
    ),
)

app = build_group(NAME, "BigCommerce store admin: store name, currency and domain.", SPECS)


def register(parent: typer.Typer) -> None:
    parent.add_typer(app, name=NAME)
