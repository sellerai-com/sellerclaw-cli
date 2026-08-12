from __future__ import annotations

import typer

from sellerclaw_cli._command_group import Cmd, LONG_TIMEOUT_SECONDS, SYNC_STOCK_PARTIAL_HELP, body_field, build_group, flag

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
            "Identify each item by sku (or by remote_id for an item we already mirror)."
        ),
        body=(
            body_field(
                "items",
                type=dict,
                repeatable=True,
                help="Items to update, each {sku, quantity?, price?}. " + SYNC_STOCK_PARTIAL_HELP,
            ),
        ),
    ),
    Cmd(
        "draft",
        "POST",
        "/agent/walmart/stores/{store_id}/listings/draft",
        timeout=LONG_TIMEOUT_SECONDS,
        summary=(
            "Create local DRAFT listings from catalog products before publishing. A Walmart "
            "productType is required (each category has its own attribute spec), and every "
            "variation needs its own product identifier (GTIN/UPC) — Walmart lists each variation "
            "as a separate item. Variations of one product are tied into one page by "
            "variant_attribute_names (up to 3, e.g. color+size); without it each variation becomes "
            "a separate Walmart page. Re-running for a product that gained a variation drafts just "
            "that one, into the same group."
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
            body_field("brand", help="Brand name applied to every variation."),
            body_field(
                "attributes",
                type=dict,
                help=(
                    "Category attributes shared by every variation, e.g. {\"material\": \"Cotton\"}. "
                    "Passed to Walmart as-is."
                ),
            ),
            body_field(
                "orderable",
                type=dict,
                help=(
                    "Extra Walmart Orderable attributes (country of origin, shipping weight, "
                    "package dimensions). Passed as-is."
                ),
            ),
            body_field(
                "variant_attribute_names",
                repeatable=True,
                help='Attributes the variations differ by, max 3, e.g. "color" "size".',
            ),
            body_field(
                "variant_group_id",
                help="Optional group id (max 20 chars); derived from the product and store if omitted.",
            ),
            body_field(
                "variants",
                type=dict,
                repeatable=True,
                help=(
                    "Per-variation fields: {sku, product_id, product_id_type?, attributes: "
                    '{color: "Red"}, is_primary?, swatch_image_url?}. One variation should be '
                    "is_primary (it opens by default); the first one is used otherwise."
                ),
            ),
        ),
    ),
    Cmd(
        "publish",
        "POST",
        "/agent/walmart/stores/{store_id}/listings/publish",
        timeout=LONG_TIMEOUT_SECONDS,
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
            '(body: {"listing_ids": ["<uuid>", ...]}). Pass "skus" to retire only those variations '
            "of the group; if the default variation leaves, another one takes its place. The rows "
            "are kept for history."
        ),
        body=(
            body_field(
                "listing_ids",
                repeatable=True,
                required=True,
                help="Listing UUIDs to withdraw from the store.",
            ),
            body_field(
                "skus",
                repeatable=True,
                help="Retire only these variations of the group; omit to retire the whole group.",
            ),
        ),
    ),
    Cmd(
        "update",
        "PATCH",
        "/agent/walmart/stores/{store_id}/listings/{listing_id}",
        summary=(
            "Edit a Walmart listing group — local only, nothing reaches Walmart here. The change "
            "is recorded as owed and the next publish delivers it "
            '(body: {"title"?, "description"?, "sell_prices"?: {sku: price}, "quantities"?: {sku: qty}}). '
            'A "spec" patch (product type, brand, attributes, identifiers, variant grouping, '
            "primary variation) changes the catalogue fields on the row; Walmart only accepts those "
            "as an item feed for the whole group, which the publish submits — poll publish-status "
            "after that publish, not after this call."
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
            body_field(
                "spec",
                type=dict,
                help=(
                    "Catalogue patch: {product_type?, brand?, attributes?, orderable?, "
                    "variant_attribute_names?, variants?: [{sku, product_id?, attributes?, "
                    "is_primary?}]}. Omitted fields are left as they are."
                ),
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
