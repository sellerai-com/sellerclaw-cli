from __future__ import annotations

import typer

from sellerclaw_cli._command_group import Cmd, body_field, build_group, flag

NAME = "ebay-orders"

SPECS = (
    Cmd(
        "list",
        "GET",
        "/agent/ebay/stores/{store_id}/orders",
        summary="List live eBay orders.",
        flags=(
            flag("limit", type=int, help="Max results."),
            flag("offset", type=int, help="Pagination offset."),
            flag("created_after", help="ISO timestamp."),
            flag("created_before", help="ISO timestamp."),
            flag("updated_after", help="ISO timestamp."),
            flag("updated_before", help="ISO timestamp."),
            flag("fulfillment_statuses", help="Comma-separated fulfillment statuses."),
        ),
    ),
    Cmd(
        "create-fulfillment",
        "POST",
        "/agent/ebay/stores/{store_id}/orders/{order_id}/fulfillments",
        summary="Create a fulfillment (shipment) for an eBay order.",
        body=(
            body_field("carrier", required=True, help="Shipping carrier name, e.g. UPS."),
            body_field("tracking_number", required=True, help="Carrier tracking number."),
            body_field(
                "line_items",
                type=dict,
                repeatable=True,
                help="Lines shipped, each {lineItemId, quantity}; omit to ship the whole order.",
            ),
        ),
    ),
)

app = build_group(NAME, "eBay orders and fulfillment (store_id is the first argument).", SPECS)


def register(parent: typer.Typer) -> None:
    parent.add_typer(app, name=NAME)
