from __future__ import annotations

import typer

from sellerclaw_cli._command_group import Cmd, body_field, build_group, flag

NAME = "woocommerce-orders"

# WooCommerce orders go through the unified store endpoints (live via the channel adapter).
SPECS = (
    Cmd(
        "list",
        "GET",
        "/agent/stores/{store_id}/orders",
        summary="List the store's WooCommerce orders.",
        flags=(
            flag("status", help="Order status filter: unfulfilled (default) or fulfilled."),
            flag("limit", type=int, minimum=1, maximum=500, default=100, help="Max results."),
        ),
    ),
    Cmd(
        "cancel",
        "POST",
        "/agent/stores/{store_id}/orders/{order_id}/cancel",
        summary=(
            "Cancel the order at WooCommerce. Cancelling in WooCommerce is a status change: the order moves to `cancelled`. The reply says what the platform actually did: "
            "`cancelled`, its own `status`, and `restocked`/`refunded` — where those are null the "
            "platform did not say, which is not the same as 'no'."
        ),
        body=(
            body_field(
                "reason",
                help="Why it is being cancelled. Kept as an order note, where the shop's staff read it.",
            ),
            body_field(
                "restock",
                type=bool,
                help="Ignored: WooCommerce restores stock itself on this status change when stock management is on, and reports nothing about having done it.",
            ),
            body_field(
                "refund",
                type=bool,
                help=(
                    "Refund the buyer as part of cancelling. WooCommerce cannot do both in one step "
                    "and refuses rather than cancelling without the refund — refund separately."
                ),
            ),
            body_field(
                "notify_customer",
                type=bool,
                help="Let WooCommerce email the buyer about the cancellation.",
            ),
            body_field(
                "customer_message",
                help="A note for the buyer, sent with that email. Ignored without notify_customer.",
            ),
        ),
    ),
    Cmd(
        "create-fulfillment",
        "POST",
        "/agent/stores/{store_id}/orders/{order_id}/fulfillments",
        summary=(
            "Mark a WooCommerce order completed and record tracking as an order note "
            "(WooCommerce core has no native tracking field, so it goes into a note)."
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
                help="Items to fulfill, each {remote_line_item_id, quantity}; omit to complete the whole order.",
            ),
        ),
    ),
)

app = build_group(NAME, "WooCommerce orders: read orders and confirm shipments with tracking.", SPECS)


def register(parent: typer.Typer) -> None:
    parent.add_typer(app, name=NAME)
