from __future__ import annotations

import typer

from sellerclaw_cli._command_group import Cmd, body_field, build_group, flag

NAME = "etsy-listings"

# Listing READS come from the unified SellerClaw mirror (/agent/stores/{store_id}/listings),
# warmed on connect + refreshed periodically; pass --live on search to hit Etsy directly. The
# publish lifecycle (draft -> publish -> withdraw -> update) is Etsy-specific.
SPECS = (
    Cmd(
        "list",
        "GET",
        "/agent/stores/{store_id}/listings",
        summary="List the shop's Etsy listings from the SellerClaw mirror.",
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
            "Aggregate stats over the shop's Etsy listings (row count, total & zero stock, "
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
            "Search one shop's Etsy listings by title, SKU, or remote id. Default: the local mirror "
            "(carries a SellerClaw id for chat cards). Pass --live to query Etsy directly for "
            "current price/stock (no SellerClaw id). To search all stores, use 'listings'."
        ),
        flags=(
            flag("q", required=True, help="Search text (matched as a substring of title/SKU/remote id)."),
            flag(
                "type",
                help="Live-search field: sku (default) or remote_id (the Etsy listing id); mirror ignores it.",
            ),
            flag(
                "live",
                type=bool,
                help="Query Etsy live instead of the mirror — current price/stock, but no SellerClaw id.",
            ),
            flag("limit", type=int, minimum=1, maximum=500, default=100, help="Max results."),
        ),
    ),
    Cmd(
        "sync-stock",
        "POST",
        "/agent/stores/{store_id}/listings/sync-stock",
        summary=(
            "Update price and/or stock on existing Etsy listings "
            '(body: {"items": [{"sku": "...", "quantity": 5, "price": 19.99}]}). '
            "Identify each item by sku or remote_id (the Etsy listing id, or listing_id::sku)."
        ),
        body=(
            body_field(
                "items",
                type=dict,
                repeatable=True,
                help="Listings to update, each {sku?, remote_id?, quantity?, price?} (sku or remote_id).",
            ),
        ),
    ),
    Cmd(
        "draft",
        "POST",
        "/agent/etsy/stores/{store_id}/listings/draft",
        summary=(
            "Create local DRAFT listings from catalog products before publishing "
            '(body: {"product_ids": ["<uuid>", ...], plus Etsy attributes}). One draft row per '
            "variant; a whole product publishes as one Etsy listing."
        ),
        body=(
            body_field(
                "product_ids",
                repeatable=True,
                required=True,
                help="Catalog product UUIDs to stage as Etsy drafts.",
            ),
            body_field(
                "taxonomy_id",
                type=int,
                help="Etsy taxonomy (category) id — required to publish; falls back to the shop default.",
            ),
            body_field(
                "shipping_profile_id",
                help="Etsy shipping profile id — required to publish; falls back to the shop default.",
            ),
            body_field(
                "return_policy_id",
                help="Etsy return policy id (recommended for physical goods).",
            ),
            body_field(
                "who_made",
                choices=("i_did", "someone_else", "collective"),
                help="Who made the item — required to publish; falls back to the shop default.",
            ),
            body_field(
                "when_made",
                help='When it was made, e.g. "made_to_order", "2020_2024" — required to publish.',
            ),
            body_field(
                "is_supply",
                type=bool,
                help="Whether the item is a craft supply (true/false) — required to publish.",
            ),
        ),
    ),
    Cmd(
        "publish",
        "POST",
        "/agent/etsy/stores/{store_id}/listings/publish",
        summary=(
            "Publish local DRAFT listings to Etsy as active listings "
            '(body: {"listing_ids": ["<uuid>", ...]}). Returns published rows + per-id errors; a '
            "missing Etsy attribute (taxonomy/shipping/who_made/...) is reported as not-publishable."
        ),
        body=(
            body_field(
                "listing_ids",
                repeatable=True,
                required=True,
                help="Listing UUIDs (from 'draft') to publish to the shop.",
            ),
        ),
    ),
    Cmd(
        "withdraw",
        "POST",
        "/agent/etsy/stores/{store_id}/listings/withdraw",
        summary=(
            "Take published Etsy listings off the storefront (sets the listing inactive) "
            '(body: {"listing_ids": ["<uuid>", ...]}). The rows are kept for history.'
        ),
        body=(
            body_field(
                "listing_ids",
                repeatable=True,
                required=True,
                help="Listing UUIDs to withdraw from the shop.",
            ),
        ),
    ),
    Cmd(
        "update",
        "PATCH",
        "/agent/etsy/stores/{store_id}/listings/{listing_id}",
        summary=(
            "Edit an Etsy listing group; pushed to Etsy when the listing is PUBLISHED "
            '(body: {"title"?, "description"?, "sell_prices"?: {sku: price}, "quantities"?: {sku: qty}}).'
        ),
        body=(
            body_field("title", help="New listing title."),
            body_field("description", help="New listing description."),
            body_field(
                "sell_prices",
                type=dict,
                help='New prices keyed by listing SKU, e.g. {"SKU-1": 19.99}.',
            ),
            body_field(
                "quantities",
                type=dict,
                help='New stock quantities keyed by listing SKU, e.g. {"SKU-1": 5}.',
            ),
        ),
    ),
)

app = build_group(
    NAME,
    "Etsy listings: read (mirror, --live on search), sync price/stock, and publish/withdraw.",
    SPECS,
)


def register(parent: typer.Typer) -> None:
    parent.add_typer(app, name=NAME)
