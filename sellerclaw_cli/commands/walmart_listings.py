from __future__ import annotations

import typer

from sellerclaw_cli._command_group import Cmd, body_field, build_group, flag

NAME = "walmart-listings"

# Listing READS come from the unified SellerClaw mirror (/agent/stores/{store_id}/listings),
# warmed on connect + refreshed periodically; pass --live on search to hit Walmart directly.
# The publish lifecycle is feed-based and asynchronous: publish submits a Walmart item feed and the
# row stays draft until the feed processes — poll publish-status for the result.
SPECS = (
    Cmd(
        "list",
        "GET",
        "/agent/stores/{store_id}/listings",
        summary="List the store's Walmart listings from the SellerClaw mirror.",
        flags=(
            flag(
                "status",
                choices=("active", "published", "draft", "withdrawn"),
                help="Mirror status to filter by; omit for all.",
            ),
            flag("search", help="Match title or SKU."),
            flag("limit", type=int, minimum=1, maximum=500, default=100, help="Max results."),
        ),
    ),
    Cmd(
        "summary",
        "GET",
        "/agent/stores/{store_id}/listings/summary",
        summary=(
            "Aggregate stats over the store's Walmart listings (row count, total & zero stock, "
            "price min/max/avg, currencies). Use this instead of listing every row for an overview."
        ),
        flags=(
            flag(
                "status",
                choices=("active", "published", "draft", "withdrawn"),
                help="Mirror status to filter by; omit for all.",
            ),
        ),
    ),
    Cmd(
        "search",
        "GET",
        "/agent/stores/{store_id}/listings/search",
        summary=(
            "Search one store's Walmart listings by title or SKU. Default: the local mirror "
            "(carries a SellerClaw id for chat cards). Pass --live to query Walmart directly for "
            "current price/stock (no SellerClaw id). To search all stores, use 'listings'."
        ),
        flags=(
            flag("q", required=True, help="Search text (matched as a substring of title/SKU)."),
            flag("type", help="Live-search field: sku (default); mirror ignores it."),
            flag(
                "live",
                type=bool,
                help="Query Walmart live instead of the mirror — current price/stock, but no SellerClaw id.",
            ),
            flag("limit", type=int, minimum=1, maximum=500, default=100, help="Max results."),
        ),
    ),
    Cmd(
        "sync-stock",
        "POST",
        "/agent/stores/{store_id}/listings/sync-stock",
        summary=(
            "Update price and/or stock on existing Walmart items "
            '(body: {"items": [{"sku": "...", "quantity": 5, "price": 19.99}]}). '
            "Identify each item by sku."
        ),
        body=(
            body_field(
                "items",
                type=dict,
                repeatable=True,
                help="Items to update, each {sku, quantity?, price?}.",
            ),
        ),
    ),
    Cmd(
        "draft",
        "POST",
        "/agent/walmart/stores/{store_id}/listings/draft",
        summary=(
            "Create local DRAFT listings from catalog products before publishing "
            '(body: {"product_ids": ["<uuid>", ...], "product_type": "Office Supplies"}). '
            "A Walmart productType is required (each category has its own attribute spec)."
        ),
        body=(
            body_field(
                "product_ids",
                repeatable=True,
                required=True,
                help="Catalog product UUIDs to stage as Walmart drafts.",
            ),
            body_field(
                "product_type",
                help="Walmart productType applied to every draft, e.g. 'Office Supplies'.",
            ),
        ),
    ),
    Cmd(
        "publish",
        "POST",
        "/agent/walmart/stores/{store_id}/listings/publish",
        summary=(
            "Submit a Walmart item feed for DRAFT listings "
            '(body: {"listing_ids": ["<uuid>", ...]}). Async: rows stay draft (publish_state '
            "'submitted') until the feed processes — poll publish-status for the result."
        ),
        body=(
            body_field(
                "listing_ids",
                repeatable=True,
                required=True,
                help="Listing UUIDs (from 'draft') to publish to the store.",
            ),
        ),
    ),
    Cmd(
        "publish-status",
        "GET",
        "/agent/walmart/stores/{store_id}/listings/{listing_id}/publish-status",
        summary=(
            "Check the feed-based publish progress of a listing: publish_state is submitted, done "
            "(row is now published with its wpid), or error (with feed_errors)."
        ),
    ),
    Cmd(
        "withdraw",
        "POST",
        "/agent/walmart/stores/{store_id}/listings/withdraw",
        summary=(
            "Retire published Walmart listings from the catalog "
            '(body: {"listing_ids": ["<uuid>", ...]}). The rows are kept for history.'
        ),
        body=(
            body_field(
                "listing_ids",
                repeatable=True,
                required=True,
                help="Listing UUIDs to withdraw from the store.",
            ),
        ),
    ),
    Cmd(
        "update",
        "PATCH",
        "/agent/walmart/stores/{store_id}/listings/{listing_id}",
        summary=(
            "Edit a Walmart listing group; price/stock are pushed to Walmart when PUBLISHED "
            '(body: {"title"?, "description"?, "sell_prices"?: {sku: price}, "quantities"?: {sku: qty}}).'
        ),
        body=(
            body_field("title", help="New product title."),
            body_field("description", help="New product description."),
            body_field(
                "sell_prices",
                type=dict,
                help="New prices keyed by listing SKU, e.g. {\"SKU-1\": 19.99}.",
            ),
            body_field(
                "quantities",
                type=dict,
                help="New stock quantities keyed by listing SKU, e.g. {\"SKU-1\": 5}.",
            ),
        ),
    ),
)

app = build_group(
    NAME,
    "Walmart listings: read (mirror, --live on search), sync price/stock, and feed-based publish/withdraw.",
    SPECS,
)


def register(parent: typer.Typer) -> None:
    parent.add_typer(app, name=NAME)
