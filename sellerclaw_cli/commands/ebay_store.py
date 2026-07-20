from __future__ import annotations

import typer

from sellerclaw_cli._command_group import Cmd, body_field, build_group

NAME = "ebay-store"

SPECS = (
    Cmd("get-account", "GET", "/agent/ebay/stores/{store_id}/account", summary="Get the eBay account info."),
    Cmd(
        "seller-standards",
        "GET",
        "/agent/ebay/stores/{store_id}/seller-standards",
        summary=(
            "Account health: seller level (Top Rated/Above/Below Standard) and the metrics that "
            "hold it (e.g. transaction defect rate, late shipment rate) with their thresholds. "
            "Use for the report's 'Account' section — which metric is closest to its limit."
        ),
    ),
    Cmd(
        "list-business-policies",
        "GET",
        "/agent/ebay/stores/{store_id}/business-policies",
        summary=(
            "List fulfillment/payment/return business policies with their ids "
            "(required by create-drafts/publish). Empty sets mean the seller has not "
            "opted in to eBay Business Policies."
        ),
    ),
    Cmd(
        "list-locations",
        "GET",
        "/agent/stores/{store_id}/locations",
        summary=(
            "List the store's ship-from warehouses. 'is_default' marks the one publishing and stock "
            "sync use; use each row's 'id' with delete-location."
        ),
    ),
    Cmd(
        "list-raw-locations",
        "GET",
        "/agent/ebay/stores/{store_id}/locations",
        summary=(
            "eBay's raw location payload (merchantLocationKey, status, full address), for details "
            "the mirrored list-locations view normalizes away."
        ),
    ),
    Cmd(
        "create-location",
        "POST",
        "/agent/stores/{store_id}/locations",
        summary=(
            "Create a ship-from location on eBay AND mirror it here in one call — no separate "
            "refresh needed. Prefer letting the owner do this in Seller Hub; only run it when they "
            "ask you to. No location key is taken: it is derived from the name."
        ),
        body=(
            body_field("name", required=True, help="Human-readable location name."),
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
            "Remove a ship-from location from eBay and tombstone it here. Destructive — only on the "
            "owner's explicit request. Takes the warehouse 'id' from list-locations."
        ),
    ),
)

app = build_group(NAME, "eBay store admin: account, business policies, inventory locations.", SPECS)


def register(parent: typer.Typer) -> None:
    parent.add_typer(app, name=NAME)
