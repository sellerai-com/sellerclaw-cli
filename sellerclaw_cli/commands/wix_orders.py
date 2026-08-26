from __future__ import annotations

import typer

from sellerclaw_cli._command_group import Cmd, body_field, build_group, flag

NAME = "wix-orders"

# Wix orders go through the unified store endpoints (live via the channel adapter).
SPECS = (
    Cmd(
        "list",
        "GET",
        "/agent/stores/{store_id}/orders",
        summary="List the store's Wix orders.",
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
            "Cancel the order at Wix. Wix refuses an order that is still pending, was rejected, or holds an authorized payment — void or refund that first. The reply says what the platform actually did: "
            "`cancelled`, its own `status`, and `restocked`/`refunded` — where those are null the "
            "platform did not say, which is not the same as 'no'."
        ),
        body=(
            body_field(
                "reason",
                help="Why it is being cancelled. Wix has no reason field on an order; it reaches the buyer only in the email.",
            ),
            body_field(
                "restock",
                type=bool,
                help="Put the goods back on sale. Only reaches products Wix itself keeps stock for — a dropshipped line has no Wix inventory to return.",
            ),
            body_field(
                "refund",
                type=bool,
                help=(
                    "Refund the buyer as part of cancelling. Wix cannot do both in one step "
                    "and refuses rather than cancelling without the refund — refund separately."
                ),
            ),
            body_field(
                "notify_customer",
                type=bool,
                help="Let Wix email the buyer about the cancellation.",
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
            "Create a Wix fulfillment with tracking, which advances the order to Fulfilled "
            "(Wix has a native fulfillment/tracking model). The order must be approved (paid)."
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

app = build_group(NAME, "Wix orders: read orders and confirm shipments with tracking.", SPECS)


def register(parent: typer.Typer) -> None:
    parent.add_typer(app, name=NAME)
