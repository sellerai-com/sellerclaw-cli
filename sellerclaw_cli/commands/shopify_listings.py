from __future__ import annotations

import typer

from sellerclaw_cli._command_group import Cmd, LONG_TIMEOUT_SECONDS, body_field, build_group, flag

NAME = "shopify-listings"

# Optional content overrides shared by `create-drafts` and `publish-product`. The agent never
# passes stock or a sales channel: stock is always taken from the catalog and the channel is always
# the Online Store. These fields only tweak the listing content / prices.
_LISTING_CONTENT_FIELDS = (
    body_field("title", help="Override the listing title (single-product only)."),
    body_field("description", help="Override the listing description (body HTML)."),
    body_field("product_type", help="Override the product type applied to the listing(s)."),
    body_field("tags", repeatable=True, help="Tags to set on the listing(s)."),
    body_field("vendor", help="Vendor / brand to set on the listing(s)."),
    body_field(
        "sell_prices",
        type=dict,
        help='Per-SKU sell price overrides, e.g. {"SKU-1": "19.99"}.',
    ),
    body_field(
        "compare_at_prices",
        type=dict,
        help='Per-SKU compare-at (was) price overrides, e.g. {"SKU-1": "29.99"}.',
    ),
    body_field(
        "barcodes",
        type=dict,
        help='Per-SKU barcode overrides, e.g. {"SKU-1": "0123456789012"}.',
    ),
)

SPECS = (
    Cmd(
        "list",
        "GET",
        "/agent/stores/{store_id}/listings",
        summary="List the store's Shopify listings from the SellerClaw mirror.",
        flags=(
            flag(
                "status",
                choices=("active", "published", "draft", "withdrawn"),
                help="Mirror status to filter by; omit for all live listings.",
            ),
            flag("search", help="Match title, SKU, or remote id."),
            flag("limit", type=int, minimum=1, maximum=500, default=100, help="Max results."),
        ),
    ),
    Cmd(
        "products",
        "GET",
        "/agent/stores/{store_id}/listings/products",
        summary=(
            "List the store's catalog one row per Shopify PRODUCT (not per variant). Each row "
            "carries the remote_product_id that `update` and `delete` take, already deduplicated, "
            "plus the product's title, category, variant count, stock and price range. Use this "
            "for anything product-level — reviewing categories, finding uncategorized products, "
            "picking what to delete — instead of `list` plus grouping the variant rows yourself."
        ),
        flags=(
            flag(
                "status",
                choices=("active", "published", "draft", "withdrawn"),
                help="Mirror status to filter the underlying rows by; omit for all live listings.",
            ),
        ),
    ),
    Cmd(
        "summary",
        "GET",
        "/agent/stores/{store_id}/listings/summary",
        summary=(
            "Aggregate stats over the store's Shopify listings (row count, total & zero stock, "
            "price min/max/avg, currencies). Use this instead of listing every row for an overview."
        ),
        flags=(
            flag(
                "status",
                choices=("active", "published", "draft", "withdrawn"),
                help="Mirror status to filter by; omit for all live listings.",
            ),
        ),
    ),
    Cmd(
        "search",
        "GET",
        "/agent/stores/{store_id}/listings/search",
        summary=(
            "Search one store's listings by title, SKU, or remote id. Default: the local mirror "
            "(carries a SellerClaw id for chat cards). Pass --live to query Shopify directly for "
            "current price/stock (no SellerClaw id). To search across all stores, use 'listings'."
        ),
        flags=(
            flag("q", required=True, help="Search text (matched as a substring of title/SKU/remote id)."),
            flag(
                "type",
                help="Live-search field (sku by default); ignored by the mirror, which spans title/SKU/remote id.",
            ),
            flag(
                "live",
                type=bool,
                help="Query the live store instead of the mirror — current price/stock, but no SellerClaw id.",
            ),
            flag("limit", type=int, minimum=1, maximum=500, default=100, help="Max results."),
        ),
    ),
    Cmd(
        "create",
        "POST",
        "/agent/stores/{store_id}/listings",
        summary="Create products directly on Shopify from scratch (not from the catalog). Use this "
        "only for products you are NOT sourcing through SellerClaw — for catalog products use "
        "'publish-product', which creates them as tracked listings the catalog stays in step with. "
        "A product made here is not tracked until the store's listings are next downloaded.",
        body=(
            body_field(
                "items",
                type=dict,
                repeatable=True,
                help="Products to create. Each: title (required), body_html, vendor, product_type, "
                "tags (array), status, images (array of URLs), variants (array of {sku, title, "
                "barcode, price, compare_at_price, meta}).",
            ),
        ),
    ),
    Cmd(
        "update",
        "PUT",
        "/agent/stores/{store_id}/shopify-listings",
        summary="Update Shopify listings, keeping the SellerClaw catalog in step. Target each item by "
        "listing_id (SellerClaw UUID) or product_id (Shopify id) — a tracked listing changes on "
        "Shopify and locally together; one we don't track changes on Shopify directly.",
        body=(
            body_field(
                "items",
                type=dict,
                repeatable=True,
                help="Products to update. Each: listing_id OR product_id (one required), plus any of "
                "title, description, product_type, vendor, tags, status, sell_prices ({SKU: price}), "
                "quantities ({SKU: qty}).",
            ),
        ),
    ),
    Cmd(
        "delete",
        "POST",
        "/agent/stores/{store_id}/shopify-listings/delete",
        summary="Permanently delete Shopify products (irreversible). Target by listing_id (SellerClaw "
        "UUID) or product_id (Shopify id). Tracked listings are kept as REMOVED for history and the "
        "catalog stays in step; to take a listing off sale reversibly use 'withdraw' instead.",
        body=(
            body_field(
                "listing_ids", repeatable=True, help="SellerClaw listing UUIDs to delete."
            ),
            body_field(
                "product_ids", repeatable=True, help="Shopify product ids to delete."
            ),
        ),
    ),
    Cmd(
        "publish",
        "POST",
        "/agent/stores/{store_id}/shopify-listings/publish",
        timeout=LONG_TIMEOUT_SECONDS,
        summary="Put listings (back) on the storefront, keeping the catalog in step. Target by "
        "listing_id (SellerClaw UUID) or product_id (Shopify id). A tracked listing returns at its "
        "existing product/URL (never re-created). Defaults to the Online Store.",
        body=(
            body_field(
                "listing_ids", repeatable=True, help="SellerClaw listing UUIDs to publish."
            ),
            body_field(
                "product_ids", repeatable=True, help="Shopify product ids to publish."
            ),
            body_field(
                "publication_names",
                repeatable=True,
                help="Sales-channel names to publish to; omit to default to the Online Store "
                "(the alias 'online_store' also works). Used only for products not in the catalog.",
            ),
        ),
    ),
    Cmd(
        "unpublish",
        "POST",
        "/agent/stores/{store_id}/shopify-listings/withdraw",
        summary="Take listings off the storefront (WITHDRAWN), keeping the catalog in step. Target by "
        "listing_id (SellerClaw UUID) or product_id (Shopify id). Reversible — the product keeps its "
        "id, URL and reviews. Same endpoint as 'withdraw'. Defaults to the Online Store.",
        body=(
            body_field(
                "listing_ids", repeatable=True, help="SellerClaw listing UUIDs to unpublish."
            ),
            body_field(
                "product_ids", repeatable=True, help="Shopify product ids to unpublish."
            ),
            body_field(
                "publication_names",
                repeatable=True,
                help="Sales-channel names to unpublish from; omit to default to the Online Store "
                "(the alias 'online_store' also works). Used only for products not in the catalog.",
            ),
        ),
    ),
    Cmd(
        "sync-stock",
        "POST",
        "/agent/stores/{store_id}/listings/sync-stock",
        summary="Sync stock to Shopify.",
        body=(
            body_field(
                "items",
                type=dict,
                repeatable=True,
                help="Stock updates. Each: sku (required), quantity (required), and optionally "
                "remote_id, price, compare_at_price.",
            ),
        ),
    ),
    Cmd(
        "list-drafts",
        "GET",
        "/agent/stores/{store_id}/draft-listings",
        summary="List draft listings staged for Shopify.",
        flags=(flag("status", help="Filter by status."),),
    ),
    Cmd(
        "create-drafts",
        "POST",
        "/agent/stores/{store_id}/draft-listings",
        timeout=LONG_TIMEOUT_SECONDS,
        summary="Create draft listings from catalog products. Stock is taken from the catalog and "
        "the channel is the Online Store — you never set them; the optional fields only tweak content.",
        body=(
            body_field(
                "product_ids",
                required=True,
                repeatable=True,
                help="SellerClaw product ids (UUIDs) to stage as draft listings.",
            ),
            *_LISTING_CONTENT_FIELDS,
        ),
    ),
    Cmd(
        "publish-drafts",
        "POST",
        "/agent/stores/{store_id}/draft-listings/publish",
        summary="Publish draft listings.",
        body=(
            body_field(
                "listing_ids",
                required=True,
                repeatable=True,
                help="Draft listing ids (UUIDs) to publish to Shopify.",
            ),
        ),
    ),
    Cmd(
        "withdraw",
        "POST",
        "/agent/stores/{store_id}/shopify-listings/withdraw",
        summary=(
            "Take published Shopify listings off the storefront and keep the catalog in step. Target "
            "by listing_id (SellerClaw UUID) or product_id (Shopify id). Reversible: the product "
            "stays ACTIVE in Shopify with the same id, URL and reviews, and the rows are kept for "
            "history. This is the default take-down — use 'delete' only for an explicit, irreversible "
            "removal."
        ),
        body=(
            body_field(
                "listing_ids",
                repeatable=True,
                help="SellerClaw listing UUIDs to withdraw from the storefront.",
            ),
            body_field(
                "product_ids",
                repeatable=True,
                help="Shopify product ids to withdraw (resolved to your listings where tracked).",
            ),
            body_field(
                "publication_names",
                repeatable=True,
                help="Sales-channel names to withdraw from; omit for the Online Store. Used only "
                "for products not in the catalog.",
            ),
        ),
    ),
    Cmd(
        "publish-product",
        "POST",
        "/agent/stores/{store_id}/draft-listings/publish-product",
        timeout=LONG_TIMEOUT_SECONDS,
        summary="One-shot: create drafts for catalog products AND publish them to the storefront in "
        "a single call. Stock comes from the catalog, the channel is the Online Store, and overselling "
        "is denied — all automatic; you never pass stock or a channel. Returns the same "
        "results[]/errors[] batch shape as publish-drafts.",
        body=(
            body_field(
                "product_ids",
                required=True,
                repeatable=True,
                help="SellerClaw catalog product ids (UUIDs) to publish.",
            ),
            *_LISTING_CONTENT_FIELDS,
        ),
    ),
    Cmd(
        "publications",
        "GET",
        "/agent/stores/{store_id}/publications",
        summary="List the store's sales-channel publications (id + name), e.g. the Online Store. "
        "Use the names with the publish/unpublish commands.",
    ),
    Cmd(
        "inventory",
        "GET",
        "/agent/stores/{store_id}/listings/inventory",
        summary=(
            "Variant-level stock + publication signals to diagnose '0 products' / 'Sold out' pages: "
            "inventory_quantity, inventory_policy (DENY hides at 0), product.status (draft ⇒ hidden), "
            "and published_to_online_store / online_store_url."
        ),
        flags=(
            flag("status", choices=("ACTIVE", "DRAFT", "ARCHIVED"), help="Product status filter."),
            flag("skus", repeatable=True, help="Filter by SKU (repeat for several)."),
            flag("product_ids", repeatable=True, help="Filter by Shopify product id (repeat)."),
            flag("variant_ids", repeatable=True, help="Filter by Shopify variant id (repeat)."),
            flag("limit", type=int, minimum=1, maximum=250, default=100, help="Max variants."),
        ),
    ),
    Cmd(
        "publication-status",
        "GET",
        "/agent/stores/{store_id}/listings/publication-status",
        summary=(
            "Which publications each product is published on — is it live on the Online Store? "
            "Needs the read_product_listings scope (older stores must reconnect to grant it)."
        ),
        flags=(
            flag("skus", repeatable=True, help="Products by SKU (repeat for several)."),
            flag("product_ids", repeatable=True, help="Products by Shopify product id (repeat)."),
        ),
    ),
)

app = build_group(NAME, "Shopify storefront listings (store_id is the first argument).", SPECS)


def register(parent: typer.Typer) -> None:
    parent.add_typer(app, name=NAME)
