from __future__ import annotations

import typer

from sellerclaw_cli._command_group import Cmd, body_field, build_group, flag

NAME = "woocommerce-listings"

# Listing READS come from the unified SellerClaw mirror (/agent/stores/{store_id}/listings),
# warmed on connect + refreshed periodically; pass --live on search to hit WooCommerce directly.
# The publish lifecycle (draft -> publish -> withdraw -> update) is WooCommerce-specific.
SPECS = (
    Cmd(
        "list",
        "GET",
        "/agent/stores/{store_id}/listings",
        summary="List the store's WooCommerce listings from the SellerClaw mirror.",
        flags=(
            flag(
                "status",
                choices=("active", "published", "draft", "withdrawn"),
                help="Mirror status to filter by; omit for all.",
            ),
            flag("search", help="Match title, SKU, or remote id."),
            flag("limit", type=int, minimum=1, maximum=500, default=100, help="Max results."),
        ),
    ),
    Cmd(
        "summary",
        "GET",
        "/agent/stores/{store_id}/listings/summary",
        summary=(
            "Aggregate stats over the store's WooCommerce listings (row count, total & zero stock, "
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
            "Search one store's WooCommerce listings by title, SKU, or remote id. Default: the "
            "local mirror (carries a SellerClaw id for chat cards). Pass --live to query WooCommerce "
            "directly for current price/stock (no SellerClaw id). To search all stores, use 'listings'."
        ),
        flags=(
            flag("q", required=True, help="Search text (matched as a substring of title/SKU/remote id)."),
            flag(
                "type",
                help="Live-search field: sku (default) or remote_id (product / product:variation); ignored by the mirror.",
            ),
            flag(
                "live",
                type=bool,
                help="Query WooCommerce live instead of the mirror — current price/stock, but no SellerClaw id.",
            ),
            flag("limit", type=int, minimum=1, maximum=500, default=100, help="Max results."),
        ),
    ),
    Cmd(
        "sync-stock",
        "POST",
        "/agent/stores/{store_id}/listings/sync-stock",
        summary=(
            "Update price and/or stock on existing WooCommerce products/variations "
            '(body: {"items": [{"sku": "...", "quantity": 5, "price": 19.99}]}). '
            "Identify each item by sku or remote_id."
        ),
        body=(
            body_field(
                "items",
                type=dict,
                repeatable=True,
                help="Products to update, each {sku?, remote_id?, quantity?, price?} (sku or remote_id).",
            ),
        ),
    ),
    Cmd(
        "draft",
        "POST",
        "/agent/woocommerce/stores/{store_id}/listings/draft",
        summary=(
            "Create local DRAFT listings from catalog products before publishing "
            '(body: {"product_ids": ["<uuid>", ...]}). One draft row per product variation.'
        ),
        body=(
            body_field(
                "product_ids",
                repeatable=True,
                required=True,
                help="Catalog product UUIDs to stage as WooCommerce drafts.",
            ),
        ),
    ),
    Cmd(
        "publish",
        "POST",
        "/agent/woocommerce/stores/{store_id}/listings/publish",
        summary=(
            "Publish local DRAFT listings to WooCommerce as live products "
            '(body: {"listing_ids": ["<uuid>", ...]}). Returns published rows + per-id errors.'
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
        "withdraw",
        "POST",
        "/agent/woocommerce/stores/{store_id}/listings/withdraw",
        summary=(
            "Take published WooCommerce listings off the storefront (status -> draft) "
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
        "/agent/woocommerce/stores/{store_id}/listings/{listing_id}",
        summary=(
            "Edit a WooCommerce listing group; pushed to WooCommerce when the listing is PUBLISHED "
            '(body: {"title"?, "description"?, "sell_prices"?: {sku: price}, "quantities"?: {sku: qty}}).'
        ),
        body=(
            body_field("title", help="New product title."),
            body_field("description", help="New product description (HTML allowed)."),
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
    "WooCommerce listings: read (mirror, --live on search), sync price/stock, and publish/withdraw.",
    SPECS,
)


def register(parent: typer.Typer) -> None:
    parent.add_typer(app, name=NAME)
