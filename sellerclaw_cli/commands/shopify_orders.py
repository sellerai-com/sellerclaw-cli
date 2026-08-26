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
        summary=(
            "Cancel the order at Shopify. Shopify cancels asynchronously: the reply carries the "
            "`job` doing the work, and `status` is null because nothing has changed on the order "
            "yet. Unlike Wix and WooCommerce, Shopify can refund in the same step."
        ),
        body=(
            body_field(
                "reason",
                help=(
                    "Why it is being cancelled. Shopify accepts only its own words — CUSTOMER, "
                    "DECLINED, FRAUD, INVENTORY, STAFF, OTHER — and anything else becomes OTHER."
                ),
            ),
            body_field("refund", type=bool, help="Refund the buyer as part of cancelling."),
            body_field("restock", type=bool, help="Put the goods back on sale."),
            body_field(
                "notify_customer",
                type=bool,
                help="Ignored by Shopify: its own notification settings decide.",
            ),
            body_field("customer_message", help="Ignored by Shopify; see notify_customer."),
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
