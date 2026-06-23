from __future__ import annotations

import typer

from sellerclaw_cli._command_group import Cmd, body_field, build_group, flag

NAME = "orders"

SPECS = (
    Cmd(
        "overview",
        "GET",
        "/agent/orders/overview",
        summary="Orders summary: total, counts by status, unresolved-line-item count.",
    ),
    Cmd(
        "list",
        "GET",
        "/agent/orders",
        summary=(
            "List one page of orders stored in SellerClaw (newest first). Only unshipped/"
            "unresolved orders are stored locally — this is not full sales history; use the "
            "'analytics' group for revenue and historical metrics. Response includes 'total'."
        ),
        flags=(
            flag(
                "status",
                help="Filter by internal order status (not the marketplace fulfillment status).",
                choices=(
                    "new",
                    "pending_approval",
                    "approved",
                    "purchasing",
                    "purchased",
                    "awaiting_payment",
                    "shipped",
                    "fulfilled",
                    "cancelled",
                    "failed",
                ),
            ),
            flag("sales_channel_id", help="Filter by sales channel id."),
            flag(
                "limit",
                type=int,
                param="limit",
                minimum=1,
                maximum=200,
                default=50,
                help="Max orders to return in this page.",
            ),
            flag(
                "offset",
                type=int,
                param="offset",
                minimum=0,
                default=0,
                help="Number of orders to skip (for paging through results).",
            ),
        ),
    ),
    Cmd("get", "GET", "/agent/orders/{order_id}", summary="Get one order by id."),
    Cmd(
        "search",
        "GET",
        "/agent/orders",
        summary=(
            "Find locally-stored orders by order number, marketplace id, customer name/email, or "
            "the SKU/title of any item in the order (case-insensitive substring). Only unshipped/"
            "unresolved orders are stored locally. Each result carries its id for a 'get' follow-up."
        ),
        flags=(
            flag("q", required=True, help="Search text (order number, customer, or a line-item SKU/title)."),
            flag("limit", type=int, minimum=1, maximum=200, default=50, help="Max results in this page."),
            flag("offset", type=int, minimum=0, default=0, help="Number of results to skip (for paging)."),
        ),
    ),
    Cmd(
        "update",
        "PATCH",
        "/agent/orders/{order_id}",
        summary="Update order status, supplier info, or tracking.",
        body=(
            body_field(
                "status",
                choices=(
                    "new",
                    "pending_approval",
                    "approved",
                    "purchasing",
                    "purchased",
                    "awaiting_payment",
                    "shipped",
                    "fulfilled",
                    "cancelled",
                    "failed",
                ),
                help="New internal order status.",
            ),
            body_field("supplier_order_id", help="Supplier-side order id for this purchase."),
            body_field("supplier_provider", help="Supplier provider slug, e.g. 'cj'."),
            body_field("supplier_cost", type=float, help="Total supplier cost for the order."),
            body_field("tracking_number", help="Shipment tracking number."),
            body_field("tracking_carrier", help="Shipment carrier name."),
            body_field("tracking_url", help="Public tracking URL."),
            body_field("supplier_pay_url", help="Supplier payment URL, if any."),
        ),
    ),
)

app = build_group(NAME, "Internal SellerClaw orders.", SPECS)


def register(parent: typer.Typer) -> None:
    parent.add_typer(app, name=NAME)
