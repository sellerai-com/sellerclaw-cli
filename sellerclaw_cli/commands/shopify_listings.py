from __future__ import annotations

import typer

from sellerclaw_cli._command_group import Cmd, LONG_TIMEOUT_SECONDS, SYNC_STOCK_PARTIAL_HELP, body_field, build_group, flag

NAME = "shopify-listings"

# Optional content overrides for `create-drafts`. The agent never passes stock or a sales channel:
# stock is always taken from the catalog and the channel is always the Online Store. These fields
# only tweak the listing content / prices.
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
        summary=(
            "List the store's Shopify listings from the SellerClaw mirror. `total` is the filter-aware "
            "match count, not the size of this page — page through the rest with `--offset`."
        ),
        flags=(
            flag(
                "status",
                choices=("active", "published", "draft", "withdrawn"),
                help="Mirror status to filter by; omit for all live listings.",
            ),
            flag("search", help="Match title, SKU, or remote id."),
            flag("limit", type=int, minimum=1, maximum=500, default=100, help="Max results."),
            flag("offset", type=int, minimum=0, default=0, help="Results to skip (paging)."),
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
        "'create-drafts' then 'publish-drafts', which creates them as tracked listings the catalog "
        "stays in step with. A product made here is not tracked until the store's listings are next "
        "downloaded.",
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
        summary="Update Shopify listings — local only, nothing reaches Shopify here. The change is "
        "recorded as owed and the next publish delivers it. Target each item by listing_id "
        "(SellerClaw UUID) or by product_id (Shopify id), which is resolved to the listing that "
        "mirrors it. A Shopify product that is not one of your listings is refused by name: only "
        "active products are mirrored, so a draft or archived one is changed in Shopify itself.",
        body=(
            body_field(
                "items",
                type=dict,
                repeatable=True,
                help="Listings to update. Each: listing_id OR product_id (one required), plus any "
                "of title, description, product_type, sell_prices ({SKU: price}), "
                "quantities ({SKU: qty}). Use `publish` / `withdraw` to change a product's status.",
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
        "sync-stock",
        "POST",
        "/agent/stores/{store_id}/listings/sync-stock",
        summary=(
            "Update price and/or stock on existing Shopify variants "
            '(body: {"items": [{"sku": "...", "quantity": 5, "price": 19.99}]}). '
            "Identify each item by sku or remote_id (the variant id)."
        ),
        body=(
            body_field(
                "items",
                type=dict,
                repeatable=True,
                help="Variants to update, each {sku?, remote_id?, quantity?, price?, "
                "compare_at_price?} (sku or remote_id, and quantity and/or price). "
                + SYNC_STOCK_PARTIAL_HELP,
            ),
        ),
    ),
    Cmd(
        "list-drafts",
        "GET",
        "/agent/stores/{store_id}/draft-listings",
        summary=(
            "List this store's Shopify listings — every status, not only drafts (filter with "
            "--status). ONE ENTRY PER LISTING, not per variation: each carries 'listing_ids' "
            "(every variation's id — what publish-drafts takes), 'variation_count', the price "
            "range, the total stock and the statuses it spans. 'sku' and 'remote_id' appear only "
            "on a listing with exactly one variation. 'total' counts listings, 'variation_rows' "
            "the rows behind them; page with --limit / --offset. For each variation's own price "
            "and stock use 'listings variable'."
        ),
        flags=(
            flag("status", help="Filter by status."),
            flag("limit", type=int, minimum=1, maximum=200, default=50, help="Max listings."),
            flag("offset", type=int, minimum=0, default=0, help="Listings to skip (paging)."),
        ),
    ),
    Cmd(
        "create-drafts",
        "POST",
        "/agent/stores/{store_id}/draft-listings",
        job_poll_path="/agent/stores/{store_id}/bulk-listing-jobs/{job_id}",
        timeout=LONG_TIMEOUT_SECONDS,
        summary="Create draft listings from catalog products. Nothing reaches Shopify: publishing "
        "is a separate step, after you have read the drafts back. Stock is taken from the catalog "
        "and the channel is the Online Store — you never set them; the optional fields only tweak "
        "content. Runs in the background: the answer is the queued job and the command that reads "
        "it. Reading it gives `drafted` (what was decided per product, with the `listing_ids` it "
        "became and `ready` for the group), `not_ready` (only the rows a publish would refuse, with "
        "their issues), and any category a product introduced; `--wait` holds on until then instead.",
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
        "publications",
        "GET",
        "/agent/stores/{store_id}/publications",
        summary="List the store's sales-channel publications (id + name), e.g. the Online Store. "
        "Use the names with the publish/withdraw commands.",
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
