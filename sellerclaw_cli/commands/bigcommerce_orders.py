from __future__ import annotations

import typer

from sellerclaw_cli._command_group import Cmd, body_field, build_group, flag

NAME = "bigcommerce-orders"

# BigCommerce orders go through the unified store endpoints (live via the channel adapter).
SPECS = (
    Cmd(
        "list",
        "GET",
        "/agent/stores/{store_id}/orders",
        summary="List the store's BigCommerce orders.",
        flags=(
            flag("status", help="Order status filter: unfulfilled (default) or fulfilled."),
            flag("limit", type=int, minimum=1, maximum=500, default=100, help="Max results."),
        ),
    ),
    Cmd(
        "create-fulfillment",
        "POST",
        "/agent/stores/{store_id}/orders/{order_id}/fulfillments",
        summary=(
            "Create a BigCommerce shipment with tracking, which advances the order to Shipped "
            "(BigCommerce has a native shipments/tracking model)."
        ),
        body=(
            body_field(
                "tracking",
                type=dict,
                required=True,
                help="Tracking details: {number (required), company, url}.",
            ),
            body_field(
                "line_items",
                type=dict,
                repeatable=True,
                help="Items to ship, each {remote_line_item_id, quantity}; omit to ship the whole order.",
            ),
        ),
    ),
)

app = build_group(NAME, "BigCommerce orders: read orders and confirm shipments with tracking.", SPECS)


def register(parent: typer.Typer) -> None:
    parent.add_typer(app, name=NAME)
