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
    Cmd("list-locations", "GET", "/agent/ebay/stores/{store_id}/locations", summary="List inventory locations."),
    Cmd(
        "create-location",
        "POST",
        "/agent/ebay/stores/{store_id}/locations",
        summary="Create an inventory location.",
        body=(
            body_field("merchant_location_key", required=True, help="Unique location key (max 36 chars)."),
            body_field("name", required=True, help="Human-readable location name."),
            body_field(
                "address",
                type=dict,
                help="Postal address {addressLine1, city, country, stateOrProvince?, postalCode?}.",
            ),
        ),
    ),
    Cmd(
        "ensure-warehouse-location",
        "POST",
        "/agent/ebay/stores/{store_id}/locations/warehouse",
        summary="Get or create the SellerClaw Warehouse location.",
    ),
    Cmd(
        "delete-location",
        "DELETE",
        "/agent/ebay/stores/{store_id}/locations/{merchant_location_key}",
        summary="Delete an inventory location.",
    ),
)

app = build_group(NAME, "eBay store admin: account, business policies, inventory locations.", SPECS)


def register(parent: typer.Typer) -> None:
    parent.add_typer(app, name=NAME)
