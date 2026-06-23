from __future__ import annotations

import typer

from sellerclaw_cli._command_group import Cmd, body_field, build_group, flag

NAME = "shopify-orders"

SPECS = (
    Cmd(
        "list",
        "GET",
        "/agent/stores/{store_id}/orders",
        summary="List live Shopify orders.",
        flags=(flag("status", help="Filter by status."), flag("limit", type=int, help="Max results.")),
    ),
    Cmd("sync", "POST", "/agent/stores/{store_id}/orders/sync", summary="Pull fresh orders from Shopify into SellerClaw."),
    Cmd(
        "cancel",
        "POST",
        "/agent/stores/{store_id}/orders/{order_id}/cancel",
        summary="Cancel a marketplace order.",
        body=(
            body_field("reason", required=True, help="Why the order is being cancelled."),
            body_field("refund", type=bool, help="Refund the customer when cancelling."),
            body_field("restock", type=bool, help="Restock the items when cancelling."),
        ),
    ),
    Cmd(
        "create-fulfillment",
        "POST",
        "/agent/stores/{store_id}/orders/{order_id}/fulfillments",
        summary="Create a fulfillment for an order.",
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
                help="Items to fulfill. Each: {remote_line_item_id (required), quantity}; "
                "omit to fulfill the whole order.",
            ),
        ),
    ),
    Cmd(
        "update-tracking",
        "PUT",
        "/agent/stores/{store_id}/fulfillments/{fulfillment_id}/tracking",
        summary="Update tracking on a fulfillment.",
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

app = build_group(NAME, "Shopify orders and fulfillment (store_id is the first argument).", SPECS)


def register(parent: typer.Typer) -> None:
    parent.add_typer(app, name=NAME)
