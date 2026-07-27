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
    Cmd(
        "list-locations",
        "GET",
        "/agent/stores/{store_id}/locations",
        summary=(
            "List the site's locations. Each row's 'id' is SellerClaw's — pass it to "
            "`channels set-default-warehouse` to pin the one stock is written to ('is_default' "
            "marks the current pin)."
        ),
    ),
    Cmd(
        "refresh-locations",
        "POST",
        "/agent/stores/{store_id}/locations/refresh",
        summary=(
            "Re-read locations from Wix now — for one the seller just created there. Otherwise the "
            "mirror only refreshes daily."
        ),
    ),
)

app = build_group(NAME, "Wix store admin: site name, currency and storefront URL.", SPECS)


def register(parent: typer.Typer) -> None:
    parent.add_typer(app, name=NAME)
