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
            "A raw read of the eBay account's fulfillment/payment/return business policies, for "
            "detail the mirror normalizes away. The ids here are eBay's own — SellerClaw commands "
            "take the ids from `list-policies` instead. Empty sets mean the seller has not opted in "
            "to eBay Business Policies."
        ),
    ),
    Cmd(
        "list-locations",
        "GET",
        "/agent/stores/{store_id}/locations",
        summary=(
            "List the store's ship-from warehouses. Each row's 'id' is SellerClaw's, and it is what "
            "every command naming a warehouse takes — delete-location, and "
            "`channels set-default-warehouse` to pin the one publishing and stock sync use "
            "('is_default' marks the current pin)."
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
            "owner's explicit request. Takes the warehouse 'id' (SellerClaw's) from list-locations."
        ),
    ),
    Cmd(
        "refresh-locations",
        "POST",
        "/agent/stores/{store_id}/locations/refresh",
        summary=(
            "Re-read locations from eBay now — for one the seller just created there. Otherwise the "
            "mirror only refreshes daily."
        ),
    ),
    Cmd(
        "list-policies",
        "GET",
        "/agent/stores/{store_id}/policies",
        summary=(
            "List the store's business policies (fulfillment / payment / return). Each row's 'id' "
            "is SellerClaw's, and it is the one every command naming a policy takes — drafts, "
            "set-policies, `channels set-default-policies`. 'is_default' marks the one a listing "
            "uses when it names none."
        ),
    ),
    Cmd(
        "refresh-policies",
        "POST",
        "/agent/stores/{store_id}/policies/refresh",
        summary=(
            "Re-read business policies from eBay now — for one the seller just created there. "
            "Otherwise the mirror only refreshes daily. Pin one as the store's default with "
            "`channels set-default-policies` (the owner's call — ask first)."
        ),
    ),
)

app = build_group(NAME, "eBay store admin: account, business policies, inventory locations.", SPECS)


def register(parent: typer.Typer) -> None:
    parent.add_typer(app, name=NAME)
