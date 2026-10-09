"""Orders: finding them, shipping them on any platform, closing and cancelling them."""

from __future__ import annotations

import re
from typing import Any

from sellerclaw_cli._errors import UserInputError
from sellerclaw_cli.chatgpt._action import (
    Param,
    action,
    by_platform,
    execute,
    group_for,
    platform_of,
    runs,
    store_param,
    unsupported,
)

_STORE = store_param()
_ORDER = Param(
    "order_id",
    "string",
    "The order's id from list_orders, or the marketplace's order number.",
    required=True,
    to="path",
)
_STORE_FILTER = store_param(to="flag", key="sales_channel_id", required=False)
_STATUSES = (
    "open", "closed", "new", "pending_approval", "approved", "purchasing", "purchased",
    "awaiting_payment", "shipped", "fulfilled", "cancelled", "failed",
)
_UUID = re.compile(r"^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$")
#: Platforms that ship and list orders through their own addresses, which take only the
#: marketplace's order id; every other platform's address also finds an order by our id.
_OWN_ORDER_IDS = ("amazon", "ebay")
#: What each platform calls a line of the order when shipping part of it.
_LINE_KEY = {"amazon": "orderItemId", "ebay": "lineItemId"}


def _marketplace_order_id(order_id: str) -> str:
    if not _UUID.match(order_id):
        return order_id
    order = execute("orders", "get", {"order_id": order_id})
    remote = order.get("remote_order_id") if isinstance(order, dict) else None
    return str(remote) if remote else order_id


#: Platforms whose store orders can be read and shipped from here.
_ORDER_PLATFORMS = (
    "shopify", "ebay", "amazon", "walmart", "woocommerce", "wix", "bigcommerce", "etsy", "tiktok_shop",
)


def _order_platform(store_id: str, what: str) -> str:
    platform = platform_of(store_id)
    if platform not in _ORDER_PLATFORMS:
        raise unsupported(what, platform, _ORDER_PLATFORMS)
    return platform


def _list_store_orders(values: dict[str, Any]) -> Any:
    store_id = str(values["store_id"])
    platform = _order_platform(store_id, "Reading a store's orders")
    status = values.get("status")
    flags: dict[str, Any] = {"limit": values.get("limit")}
    if platform == "amazon":
        flags |= {"order_statuses": status, "created_after": values.get("created_after"),
                  "created_before": values.get("created_before")}
    elif platform == "ebay":
        flags |= {"fulfillment_statuses": status, "created_after": values.get("created_after"),
                  "created_before": values.get("created_before"), "offset": values.get("offset")}
    else:
        flags |= {"status": status}
    flags = {k: v for k, v in flags.items() if v is not None}
    return execute(group_for(platform, "orders"), "list", {"store_id": store_id}, flags)


def _ship_order(values: dict[str, Any]) -> Any:
    store_id = str(values["store_id"])
    platform = _order_platform(store_id, "Shipping an order")
    lines = values.get("line_items") or []
    order_id = str(values["order_id"])
    if platform in _OWN_ORDER_IDS:
        if not values.get("carrier"):
            raise UserInputError("Amazon and eBay need the carrier's name: pass carrier.")
        line_key = _LINE_KEY[platform]
        body: dict[str, Any] = {"carrier": values["carrier"], "tracking_number": values["tracking_number"]}
        if values.get("ship_date") and platform == "amazon":
            body["ship_date"] = values["ship_date"]
        order_id = _marketplace_order_id(order_id)
    else:
        line_key = "remote_line_item_id"
        tracking = {"number": values["tracking_number"]}
        tracking |= {k: v for k, v in (("company", values.get("carrier")), ("url", values.get("tracking_url"))) if v}
        body = {"tracking": tracking}
    if lines and platform != "etsy":
        body["line_items"] = [
            {line_key: line.get("line_item_id"), "quantity": line.get("quantity")}
            for line in lines
            if isinstance(line, dict)
        ]
    return execute(
        group_for(platform, "orders"), "create-fulfillment", {"store_id": store_id, "order_id": order_id}, None, body
    )


ACTIONS = (
    action(
        "list_orders",
        "List orders",
        "Open orders across all stores, newest first, filtered by store, status, product or still "
        "awaiting shipment. Orders leave this list once they ship; list_store_orders reads older "
        "ones from the marketplace.",
        (
            Param(
                "status",
                "string",
                "open = still owed something, closed = fulfilled or cancelled, or one status.",
                to="flag",
                choices=_STATUSES,
            ),
            _STORE_FILTER,
            Param("awaiting_shipment", "boolean", "Only orders with no tracking number yet.", to="flag"),
            Param("product_id", "string", "Only orders containing this catalog product.", to="flag"),
            Param("limit", "integer", "Orders per page.", to="flag"),
            Param("offset", "integer", "Orders to skip.", to="flag"),
        ),
        runs("orders", "list"),
        read_only=True,
    ),
    action(
        "search_orders",
        "Search orders",
        "Find open orders by order number, marketplace order id, buyer name or email, or an item's "
        "SKU or title.",
        (
            Param("q", "string", "What to search for.", required=True, to="flag"),
            Param("status", "string", "Also filter by status.", to="flag", choices=_STATUSES),
            _STORE_FILTER,
            Param("limit", "integer", "Orders per page.", to="flag"),
            Param("offset", "integer", "Orders to skip.", to="flag"),
        ),
        runs("orders", "search"),
        read_only=True,
    ),
    action(
        "get_order",
        "Get an order",
        "One order by its number (#1001), the marketplace's order id or its id: items, buyer, "
        "shipping address, the supplier's order and tracking.",
        (_ORDER,),
        runs("orders", "get"),
        read_only=True,
    ),
    action(
        "get_orders_overview",
        "Get the orders overview",
        "How many orders are in each status, and how many have lines not matched to a product.",
        (),
        runs("orders", "overview"),
        read_only=True,
    ),
    action(
        "list_store_orders",
        "List a store's orders",
        "Orders read live from a store's marketplace, including shipped and older ones, newest first.",
        (
            _STORE,
            Param(
                "status",
                "string",
                "The marketplace's own status word; Amazon and eBay take several, comma-separated.",
            ),
            Param("created_after", "string", "Amazon, eBay: ISO date-time."),
            Param("created_before", "string", "Amazon, eBay: ISO date-time."),
            Param("limit", "integer", "Most orders."),
            Param("offset", "integer", "eBay: orders to skip."),
        ),
        _list_store_orders,
        read_only=True,
    ),
    action(
        "ship_order",
        "Ship an order",
        "Send the tracking number to the order's marketplace and mark it shipped there; the "
        "marketplace notifies the buyer. Pass line_items to ship part of the order. Afterwards "
        "close it with mark_order_shipped.",
        (
            _STORE,
            _ORDER,
            Param("tracking_number", "string", "The carrier's tracking number.", required=True),
            Param("carrier", "string", "Carrier name, e.g. UPS; required on Amazon and eBay."),
            Param("tracking_url", "string", "Public tracking link."),
            Param(
                "line_items",
                "array",
                "Lines shipped, each {line_item_id: the line's remote_line_item_id from get_order, "
                "quantity}; omit to ship it all.",
                items="object",
            ),
            Param("ship_date", "string", "Amazon: ISO ship date, default now."),
        ),
        _ship_order,
        read_only=False,
        destructive=True,
        open_world=True,
    ),
    action(
        "mark_order_shipped",
        "Mark an order shipped",
        "Close an order in SellerClaw once it has shipped, with its tracking if known. Does not "
        "contact the marketplace or the buyer; repeating it is safe.",
        (
            _ORDER,
            Param("tracking_number", "string", "Tracking number, if any."),
            Param("tracking_carrier", "string", "Carrier name."),
            Param("tracking_url", "string", "Public tracking link."),
        ),
        runs("orders", "set-shipped"),
        read_only=False,
        destructive=True,
    ),
    action(
        "update_order",
        "Update an order",
        "Update an order in SellerClaw: status, the supplier's order, tracking, or buyer details "
        "the marketplace did not send. Only the fields passed change; the marketplace is not contacted.",
        (
            _ORDER,
            Param("status", "string", "New status.", choices=_STATUSES[2:]),
            Param("supplier_order_id", "string", "The supplier's order id."),
            Param("supplier_provider", "string", "Supplier, e.g. cj."),
            Param("supplier_cost", "number", "What the supplier charged for the order."),
            Param("tracking_number", "string", "Tracking number."),
            Param("tracking_carrier", "string", "Carrier name."),
            Param("tracking_url", "string", "Public tracking link."),
            Param(
                "shipping_address", "object",
                "Any of full_name, address1, address2, city, province, zip_code, country_code, phone.",
            ),
            Param("customer_name", "string", "The buyer's name."),
            Param("customer_email", "string", "The buyer's email."),
        ),
        runs("orders", "update"),
        read_only=False,
        destructive=True,
    ),
    action(
        "cancel_order",
        "Cancel an order",
        "Cancel an order on its marketplace, optionally refunding the buyer and restocking. "
        "Shopify, Wix, WooCommerce.",
        (
            _STORE,
            _ORDER,
            Param("reason", "string", "Why; Shopify takes CUSTOMER, DECLINED, FRAUD, INVENTORY, STAFF or OTHER."),
            Param("refund", "boolean", "Refund the buyer (Shopify)."),
            Param("restock", "boolean", "Put the goods back on sale."),
            Param("notify_customer", "boolean", "Tell the buyer (Wix, WooCommerce)."),
            Param("customer_message", "string", "Message to the buyer (Wix, WooCommerce)."),
        ),
        lambda values, params: by_platform(
            values, params, what="Cancelling an order",
            commands={p: (group_for(p, "orders"), "cancel") for p in ("shopify", "wix", "woocommerce")},
        ),
        read_only=False,
        destructive=True,
    ),
)
