"""The account, its connections and stores: settings, locations, policies, FBA, reviews, finances."""

from __future__ import annotations

from typing import Any

from sellerclaw_cli._errors import UserInputError
from sellerclaw_cli.chatgpt._action import (
    Param,
    action,
    by_platform,
    execute,
    per_platform,
    platform_of,
    runs,
    store_param,
    unsupported,
)

_STORE = store_param()
_CHANNEL = store_param(key="sales_channel_id")


def _list_connections(values: dict[str, Any]) -> Any:
    # The stores first: they are what this tool is called for, and the first command a call runs is
    # the one its usage report names.
    stores = execute("channels", "list")
    ad_accounts = execute("ad-accounts", "list")
    supplier_accounts = execute("suppliers", "list-accounts")
    integrations = execute("integrations", "list")
    if isinstance(integrations, list):
        # Which of our own agent's modules use a connection says nothing to someone running their
        # business from a chat, and it is most of the payload.
        integrations = [
            {k: v for k, v in group.items() if k != "used_by"} if isinstance(group, dict) else group
            for group in integrations
        ]
    return {
        "stores": stores,
        "ad_accounts": ad_accounts,
        "supplier_accounts": supplier_accounts,
        "integrations": integrations,
    }


def _account_overview(values: dict[str, Any]) -> Any:
    overview = execute("account", "overview")
    overview = overview if isinstance(overview, dict) else {}
    return {
        "profile": overview.get("profile"),
        "business_profile": overview.get("onboarding_profile"),
        "billing": execute("account", "billing"),
    }


#: Store setting -> the command that sets it alone. They all write the same store record.
_SETTERS = {
    "reorder_lead_time_days": "set-lead-time",
    "listing_quantity_cap": "set-listing-quantity",
    "default_policies": "set-default-policies",
    "default_warehouse_id": "set-default-warehouse",
    "target_market": "set-target-market",
    "shipping_included_in_price": "set-shipping-in-price",
    "cj_auto_purchase": "set-auto-purchase",
    "amazon_fulfils_orders": "set-amazon-fulfilment",
}


def _update_store_settings(values: dict[str, Any]) -> Any:
    body = {key: values[key] for key in _SETTERS if key in values}
    if values.get("remove_listing_quantity_cap"):
        body["listing_quantity_cap"] = None
    if not body:
        raise UserInputError("pass at least one setting to change.")
    first = next(iter(body))
    return execute("channels", _SETTERS[first], {"sales_channel_id": values["store_id"]}, None, body)


_LOCATION_PLATFORMS = ("ebay", "shopify", "bigcommerce", "wix", "tiktok_shop")
_POLICY_PLATFORMS = ("ebay", "etsy")


def _reviews(values: dict[str, Any], params: tuple[Param, ...]) -> Any:
    platform = platform_of(str(values["store_id"]))
    if platform == "bigcommerce" and not values.get("product_id"):
        raise UserInputError("BigCommerce keeps reviews per product: pass product_id.")
    commands = {
        "ebay": ("ebay-feedback", "negative"),
        "bigcommerce": ("reviews", "bigcommerce"),
        "woocommerce": ("reviews", "list"),
        "wix": ("reviews", "list"),
        "etsy": ("reviews", "list"),
    }
    return by_platform(values, params, what="Reviews", commands=commands)


def _reply_to_review(values: dict[str, Any]) -> Any:
    store_id = str(values["store_id"])
    platform = platform_of(store_id)
    if platform != "ebay":
        raise unsupported("Replying to a review", platform, ["ebay"])
    reply_id = values.get("reply_id")
    if reply_id:
        return execute(
            "ebay-feedback", "send-reply", {"store_id": store_id, "reply_id": reply_id}
        )
    missing = [name for name in ("review_id", "buyer", "text") if not values.get(name)]
    if missing:
        raise UserInputError(f"to draft a reply pass {', '.join(missing)}.")
    body = {
        "feedback_id": values["review_id"],
        "target_user": values["buyer"],
        "response_text": values["text"],
        **{k: values[k] for k in ("item_id", "transaction_id") if values.get(k)},
    }
    return execute("ebay-feedback", "reply", {"store_id": store_id}, None, body)


ACTIONS = (
    action(
        "list_connections",
        "List connections",
        "Everything connected to the owner's SellerClaw account: each store with its id, platform, "
        "status and settings (markup, restock lead time, default policies and location, target "
        "market), ad accounts, supplier accounts and other integrations, with what needs fixing. "
        "Store tools take the store_id from here.",
        (),
        _list_connections,
        read_only=True,
    ),
    action(
        "get_account_overview",
        "Get the account overview",
        "The owner's SellerClaw profile and business profile, and their billing: subscription "
        "status, credits left, this period's spend and when credits reset.",
        (),
        _account_overview,
        read_only=True,
    ),
    action(
        "update_store_settings",
        "Update store settings",
        "Change how SellerClaw runs a store: restock lead time, the most units one listing may "
        "offer, default policies and ship-from location for new drafts (eBay), target market, "
        "whether shipping is folded into the price, CJ auto-purchase (off only) and Amazon "
        "fulfilment. Only the fields passed change. Ask the owner before setting default "
        "policies, the default location or Amazon fulfilment.",
        (
            _STORE,
            Param("reorder_lead_time_days", "integer", "Days from placing a reorder to stock arriving (1-365)."),
            Param("listing_quantity_cap", "integer", "Most units one listing may offer on this store (1-1000000)."),
            Param("remove_listing_quantity_cap", "boolean", "true to remove the cap."),
            Param(
                "default_policies",
                "object",
                "Policy ids from list_store_policies keyed default_fulfillment_policy_id, "
                "default_payment_policy_id, default_return_policy_id; an empty value unpins one.",
            ),
            Param("default_warehouse_id", "string", "Location id from list_store_locations."),
            Param("target_market", "string", "Two-letter country whose shipping is priced in; empty clears it."),
            Param("shipping_included_in_price", "boolean", "true folds shipping into the price."),
            Param("cj_auto_purchase", "boolean", "false stops buying this store's CJ orders automatically."),
            Param("amazon_fulfils_orders", "boolean", "true lets Amazon's warehouse ship this store's orders."),
        ),
        _update_store_settings,
        read_only=False,
        destructive=True,
    ),
    action(
        "propose_store_markup",
        "Propose a store markup",
        "Propose a store's markup over product cost, in percent (0-500), or null to remove it. "
        "It applies after the owner approves; prices on the store follow.",
        (
            _CHANNEL,
            Param(
                "markup_percent",
                "number",
                "Percent over cost, e.g. 30; null removes it.",
                required=True,
                nullable=True,
            ),
        ),
        runs("channels", "set-markup"),
        read_only=False,
    ),
    action(
        "list_store_locations",
        "List store locations",
        "A store's ship-from locations and their ids. eBay, Shopify, BigCommerce, Wix.",
        (_STORE,),
        lambda values, params: by_platform(
            values, params, what="Locations",
            commands=per_platform("store", "list-locations", _LOCATION_PLATFORMS),
        ),
        read_only=True,
    ),
    action(
        "list_store_policies",
        "List store policies",
        "A store's shipping, return and payment policies and their ids. eBay.",
        (_STORE,),
        lambda values, params: by_platform(
            values, params, what="Business policies",
            commands=per_platform("store", "list-policies", _POLICY_PLATFORMS),
        ),
        read_only=True,
    ),
    action(
        "get_fba_status",
        "Get FBA status",
        "Which Amazon store, if any, ships other channels' orders through Amazon's warehouses. "
        "None is the usual state.",
        (),
        runs("amazon-fba", "status"),
        read_only=True,
    ),
    action(
        "list_fba_stock",
        "List FBA stock",
        "Stock an Amazon store holds in Amazon's warehouses, per SKU, with when each figure was read.",
        (_STORE,),
        runs("amazon-fba", "list-stock"),
        read_only=True,
    ),
    action(
        "list_fba_inbound",
        "List FBA inbound shipments",
        "Shipments on their way into Amazon's warehouses, read live from Amazon.",
        (_STORE, Param("limit", "integer", "Most shipments to return.", to="flag")),
        runs("amazon-fba", "list-inbound"),
        read_only=True,
    ),
    action(
        "list_reviews",
        "List reviews",
        "Buyer reviews and feedback for a store, newest first, with rating, text, product and any "
        "reply. eBay returns negative and neutral feedback with the feedback score; BigCommerce "
        "needs a product. eBay, WooCommerce, Wix, BigCommerce.",
        (
            _STORE,
            Param("days", "integer", "eBay: how many days back (default 1).", to="flag"),
            Param("product_id", "string", "BigCommerce: the product whose reviews to read.", to="flag"),
            Param("limit", "integer", "Most reviews to return.", to="flag"),
        ),
        _reviews,
        read_only=True,
    ),
    action(
        "reply_to_review",
        "Reply to a review",
        "Post a public reply to a buyer's review. The first call drafts it and waits for the "
        "owner's approval, returning a reply_id; once they approve, call again with that "
        "reply_id to post it. eBay.",
        (
            _STORE,
            Param("review_id", "string", "The feedback id to reply to."),
            Param("buyer", "string", "The buyer's username who left it."),
            Param("text", "string", "The public reply, up to 500 characters."),
            Param("item_id", "string", "The item the feedback is about."),
            Param("transaction_id", "string", "The transaction the feedback is about."),
            Param("reply_id", "string", "An approved draft reply to post."),
        ),
        _reply_to_review,
        read_only=False,
        destructive=True,
        open_world=True,
    ),
    action(
        "get_store_pnl",
        "Get store profit and loss",
        "Profit and loss for a period: gross sales minus marketplace and processing fees, refunds, "
        "disputes and adjustments, before the cost of goods. eBay, Shopify Payments.",
        (_STORE, Param("days", "integer", "How many days back.", to="flag")),
        lambda values, params: by_platform(
            values, params, what="Profit and loss",
            commands={"ebay": ("ebay-finances", "pnl"), "shopify": ("shopify-finances", "pnl")},
        ),
        read_only=True,
    ),
    action(
        "get_store_cashflow",
        "Get store cash flow",
        "Incoming cash: received last week, expected this week, on hold, a weekly series and the "
        "payouts. eBay, Shopify Payments.",
        (_STORE, Param("weeks", "integer", "How many weeks the series covers.", to="flag")),
        lambda values, params: by_platform(
            values, params, what="Cash flow",
            commands={"ebay": ("ebay-finances", "cashflow"), "shopify": ("shopify-finances", "cashflow")},
        ),
        read_only=True,
    ),
)
