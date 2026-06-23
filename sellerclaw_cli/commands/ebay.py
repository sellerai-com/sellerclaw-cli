from __future__ import annotations

import typer

from sellerclaw_cli._command_group import Cmd, body_field, build_group

NAME = "ebay"

# Raw eBay API passthrough — the fallback when no curated ebay-* command fits (rare operations,
# fields not surfaced by ebay-listings/ebay-store, or working around a gap). eBay has two distinct
# API surfaces, so there are two commands: `request` for the modern REST API (Sell/Buy/Commerce)
# and `trading` for the legacy Trading API (XML, called by verb).
SPECS = (
    Cmd(
        "request",
        "POST",
        "/agent/ebay/stores/{store_id}/request",
        summary=(
            "Raw eBay REST passthrough (Sell/Buy/Commerce). Pins to api.ebay.com; "
            "path like /sell/inventory/v1/inventory_item/SKU123."
        ),
        body=(
            body_field(
                "path",
                required=True,
                help="API path on api.ebay.com, e.g. /sell/fulfillment/v1/order.",
            ),
            body_field(
                "method",
                choices=("GET", "POST", "PUT", "PATCH", "DELETE"),
                help="HTTP method [default GET].",
            ),
            body_field("params", type=dict, help="Query-string params as a flat string->string object."),
            body_field("body", type=dict, help="JSON request body (for POST/PUT/PATCH)."),
        ),
    ),
    Cmd(
        "trading",
        "POST",
        "/agent/ebay/stores/{store_id}/trading",
        summary="Raw eBay Trading API call (legacy XML verb, e.g. GetItem, AddFixedPriceItem).",
        body=(
            body_field("verb", required=True, help="Trading API call name, e.g. GetItem."),
            body_field("data", type=dict, help="Trading API request payload as a JSON object."),
        ),
    ),
)

app = build_group(NAME, "Raw eBay API passthrough (fallback for uncovered operations).", SPECS)


def register(parent: typer.Typer) -> None:
    parent.add_typer(app, name=NAME)
