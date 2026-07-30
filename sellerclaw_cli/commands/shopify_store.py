from __future__ import annotations

import typer

from sellerclaw_cli._command_group import Cmd, body_field, build_group

NAME = "shopify-store"

SPECS = (
    Cmd("get-info", "GET", "/agent/stores/{store_id}/info", summary="Get store info."),
    Cmd("get-settings", "GET", "/agent/stores/{store_id}/shop/settings", summary="Get shop settings."),
    Cmd(
        "list-locations",
        "GET",
        "/agent/stores/{store_id}/locations",
        summary=(
            "List the store's ship-from warehouses. Each row's 'id' is SellerClaw's, and it is what "
            "every command naming a warehouse takes — delete-location, and "
            "`channels set-default-warehouse` to pin the one stock is written to ('is_default' "
            "marks the current pin)."
        ),
    ),
    Cmd(
        "create-location",
        "POST",
        "/agent/stores/{store_id}/locations",
        summary=(
            "Create a ship-from location on the platform AND mirror it here in one call — no "
            "separate refresh needed. Prefer letting the owner do this in their store admin; only "
            "run it when they ask you to. No location id is taken: the platform assigns one."
        ),
        body=(
            body_field("name", required=True, help="Display name of the location."),
            body_field(
                "address",
                type=dict,
                required=True,
                help="Address: {address_line1 (required), city (required), country_code (required, "
                "ISO-3166 alpha-2 e.g. US), address_line2, state_or_province, postal_code, phone}.",
            ),
        ),
    ),
    Cmd(
        "delete-location",
        "DELETE",
        "/agent/stores/{store_id}/locations/{warehouse_id}",
        summary=(
            "Remove a ship-from location from the platform and tombstone it here. Destructive — "
            "only on the owner's explicit request. Takes the warehouse 'id' from list-locations."
        ),
    ),
    Cmd(
        "refresh-locations",
        "POST",
        "/agent/stores/{store_id}/locations/refresh",
        summary=(
            "Re-read locations from Shopify now — for one the seller just created there. Otherwise "
            "the mirror only refreshes daily."
        ),
    ),
)

app = build_group(NAME, "Shopify store admin: info, settings, locations.", SPECS)


def register(parent: typer.Typer) -> None:
    parent.add_typer(app, name=NAME)
