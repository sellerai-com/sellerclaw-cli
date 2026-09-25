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
            flag("sales_channel_id", help="Filter by sales channel id.", aliases=("--store-id",)),
            flag(
                "product_id",
                help=(
                    "Keep only orders containing this catalog product — the 'who bought this?' "
                    "lookup."
                ),
            ),
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
    Cmd(
        "get",
        "GET",
        "/agent/orders/{order_id}",
        summary=(
            "Get one order by its id, its whole order number (#1001, the # optional) or the "
            "marketplace's order id. A number two stores share answers 409 naming both."
        ),
    ),
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
            flag(
                "status",
                help="Also filter by internal order status.",
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
            flag("sales_channel_id", help="Also filter by sales channel id.", aliases=("--store-id",)),
            flag("limit", type=int, minimum=1, maximum=200, default=50, help="Max results in this page."),
            flag("offset", type=int, minimum=0, default=0, help="Number of results to skip (for paging)."),
        ),
    ),
    Cmd(
        "update",
        "PATCH",
        "/agent/orders/{order_id}",
        summary=(
            "Update order status, supplier info or tracking, or fill in buyer details the store did "
            "not send (some marketplaces share only the town and postcode). Only what you send changes."
        ),
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
            body_field(
                "shipping_address",
                type=dict,
                help=(
                    "Delivery details to write in: any of full_name, address1, address2, city, province, "
                    "zip_code, country_code (two letters), phone. Refused once the order was bought at "
                    "the supplier or is closed."
                ),
                example={"full_name": "Jane Doe", "address1": "1 Main St", "phone": "+15125550100"},
            ),
            body_field("customer_name", help="The buyer's name."),
            body_field("customer_email", help="The buyer's email address."),
        ),
    ),
    Cmd(
        "set-shipped",
        "POST",
        "/agent/orders/{order_id}/shipped",
        summary=(
            "Record that the sales channel has already shipped this order, and close it "
            "(internal status becomes 'fulfilled'). Use it right after the channel's own "
            "'<platform>-orders create-fulfillment', or when the seller shipped on the channel "
            "by hand. It does NOT ship anything itself and does not notify the buyer. Tracking "
            "fields are optional: a channel lets an order be marked sent without a number, and "
            "nothing is invented for one that has none. Repeating the call is safe."
        ),
        body=(
            body_field(
                "tracking_number",
                help="Tracking number the channel holds for this shipment, if there is one.",
                example="1Z999AA10123456784",
            ),
            body_field("tracking_carrier", help="Carrier name, e.g. 'UPS'.", example="UPS"),
            body_field("tracking_url", help="Public tracking URL, if the channel gives one."),
        ),
    ),
)

app = build_group(NAME, "Internal SellerClaw orders.", SPECS)


def register(parent: typer.Typer) -> None:
    parent.add_typer(app, name=NAME)
