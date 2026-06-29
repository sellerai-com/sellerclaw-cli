from __future__ import annotations

import typer

from sellerclaw_cli._command_group import Cmd, body_field, build_group, flag

NAME = "etsy-orders"

# Etsy orders go through the unified store endpoints (live via the channel adapter). order_id is the
# Etsy receipt id; Etsy attaches tracking at the receipt level (the whole receipt ships at once).
SPECS = (
    Cmd(
        "list",
        "GET",
        "/agent/stores/{store_id}/orders",
        summary="List the shop's Etsy orders (receipts).",
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
            "Attach tracking to an Etsy receipt, marking it shipped and notifying the buyer. Etsy "
            "tracks shipment at the receipt level, so the whole receipt ships at once."
        ),
        body=(
            body_field(
                "tracking",
                type=dict,
                required=True,
                help="Tracking details: {number (required), company, url}.",
            ),
        ),
    ),
)

app = build_group(NAME, "Etsy orders: read receipts and confirm shipments with tracking.", SPECS)


def register(parent: typer.Typer) -> None:
    parent.add_typer(app, name=NAME)
