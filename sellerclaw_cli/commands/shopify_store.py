from __future__ import annotations

import typer

from sellerclaw_cli._command_group import Cmd, body_field, build_group

NAME = "shopify-store"

SPECS = (
    Cmd("get-info", "GET", "/agent/stores/{store_id}/info", summary="Get store info."),
    Cmd("get-settings", "GET", "/agent/stores/{store_id}/shop/settings", summary="Get shop settings."),
    Cmd("list-locations", "GET", "/agent/stores/{store_id}/locations", summary="List store locations."),
    Cmd(
        "create-location",
        "POST",
        "/agent/stores/{store_id}/locations",
        summary="Create a store location.",
        body=(
            body_field("merchant_location_key", required=True, help="Unique key for the location."),
            body_field("name", required=True, help="Display name of the location."),
            body_field(
                "address",
                type=dict,
                help="Address: {addressLine1 (required), city (required), country (required), "
                "stateOrProvince, postalCode}.",
            ),
        ),
    ),
    Cmd(
        "ensure-warehouse-location",
        "POST",
        "/agent/stores/{store_id}/locations/warehouse",
        summary="Get or create the SellerClaw Warehouse location.",
    ),
    Cmd(
        "delete-location",
        "DELETE",
        "/agent/stores/{store_id}/locations/{merchant_location_key}",
        summary="Delete a store location.",
    ),
)

app = build_group(NAME, "Shopify store admin: info, settings, locations.", SPECS)


def register(parent: typer.Typer) -> None:
    parent.add_typer(app, name=NAME)
