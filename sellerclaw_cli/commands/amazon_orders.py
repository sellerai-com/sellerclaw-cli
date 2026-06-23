from __future__ import annotations

import typer

from sellerclaw_cli._command_group import Cmd, body_field, build_group, flag

NAME = "amazon-orders"

SPECS = (
    Cmd(
        "list",
        "GET",
        "/agent/amazon/stores/{store_id}/orders",
        summary="List Amazon orders (both FBA and merchant-fulfilled), order-level detail.",
        flags=(
            flag("limit", type=int, minimum=1, maximum=100, default=100, help="Max results."),
            flag("created_after", help="ISO timestamp (defaults to a wide window)."),
            flag("created_before", help="ISO timestamp."),
            flag("order_statuses", help="Comma-separated order statuses (e.g. Unshipped,Shipped)."),
            flag("fulfillment_channels", help="Comma-separated channels: AFN (FBA) or MFN (merchant)."),
        ),
    ),
    Cmd(
        "items",
        "GET",
        "/agent/amazon/stores/{store_id}/orders/{order_id}/items",
        summary="List the line items of one Amazon order (needed to confirm a shipment).",
    ),
    Cmd(
        "create-fulfillment",
        "POST",
        "/agent/amazon/stores/{store_id}/orders/{order_id}/fulfillments",
        summary=(
            "Confirm a merchant-fulfilled shipment with carrier + tracking "
            '(body: {"carrier": "UPS", "tracking_number": "...", "line_items": [...]}). '
            "No-op for FBA orders, which Amazon ships."
        ),
        body=(
            body_field("carrier", required=True, help="Shipping carrier name, e.g. UPS."),
            body_field("tracking_number", required=True, help="Carrier tracking number."),
            body_field("ship_date", help="ISO-8601 ship date; defaults to now if omitted."),
            body_field(
                "line_items",
                type=dict,
                repeatable=True,
                help="Lines shipped, each {orderItemId, quantity}; omit to ship the whole order.",
            ),
        ),
    ),
)

app = build_group(NAME, "Amazon orders: read orders and confirm merchant-fulfilled shipments.", SPECS)


def register(parent: typer.Typer) -> None:
    parent.add_typer(app, name=NAME)
