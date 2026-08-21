from __future__ import annotations

import typer

from sellerclaw_cli._command_group import Cmd, LONG_TIMEOUT_SECONDS, SYNC_STOCK_PARTIAL_HELP, body_field, build_group, flag

NAME = "bigcommerce-listings"

# Listing READS come from the unified SellerClaw mirror (/agent/stores/{store_id}/listings),
# warmed on connect + refreshed periodically; pass --live on search to hit BigCommerce directly.
# The publish lifecycle (draft -> publish -> withdraw -> update) is BigCommerce-specific.
SPECS = (
    Cmd(
        "list",
        "GET",
        "/agent/stores/{store_id}/listings",
        summary=(
            "List the store's BigCommerce listings from the SellerClaw mirror. `total` is the "
            "filter-aware match count, not the size of this page — page through the rest with `--offset`."
        ),
        flags=(
            flag(
                "status",
                choices=("active", "published", "draft", "withdrawn"),
                help="Mirror status to filter by; omit for all.",
            ),
            flag("search", help="Match title, SKU, or remote id."),
            flag("limit", type=int, minimum=1, maximum=500, default=100, help="Max results."),
            flag("offset", type=int, minimum=0, default=0, help="Results to skip (paging)."),
        ),
    ),
    Cmd(
        "summary",
        "GET",
        "/agent/stores/{store_id}/listings/summary",
        summary=(
            "Aggregate stats over the store's BigCommerce listings (row count, total & zero stock, "
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
            "Search one store's BigCommerce listings by title, SKU, or remote id. Default: the "
            "local mirror (carries a SellerClaw id for chat cards). Pass --live to query BigCommerce "
            "directly for current price/stock (no SellerClaw id). To search all stores, use 'listings'."
        ),
        flags=(
            flag("q", required=True, help="Search text (matched as a substring of title/SKU/remote id)."),
            flag(
                "type",
                help="Live-search field: sku (default) or remote_id (product / product:variant); mirror ignores it.",
            ),
            flag(
                "live",
                type=bool,
                help="Query BigCommerce live instead of the mirror — current price/stock, but no SellerClaw id.",
            ),
            flag("limit", type=int, minimum=1, maximum=500, default=100, help="Max results."),
        ),
    ),
    Cmd(
        "sync-stock",
        "POST",
        "/agent/stores/{store_id}/listings/sync-stock",
        summary=(
            "Update price and/or stock on existing BigCommerce products/variants "
            '(body: {"items": [{"sku": "...", "quantity": 5, "price": 19.99}]}). '
            "Identify each item by sku or remote_id."
        ),
        body=(
            body_field(
                "items",
                type=dict,
                repeatable=True,
                help="Products to update, each {sku?, remote_id?, quantity?, price?} (sku or remote_id, and "
                "quantity and/or price). " + SYNC_STOCK_PARTIAL_HELP,
            ),
        ),
    ),
    Cmd(
        "draft",
        "POST",
        "/agent/bigcommerce/stores/{store_id}/listings/draft",
        job_poll_path="/agent/stores/{store_id}/bulk-listing-jobs/{job_id}",
        timeout=LONG_TIMEOUT_SECONDS,
        summary=(
            "Create local DRAFT listings from catalog products before publishing "
            '(body: {"product_ids": ["<uuid>", ...]}). One draft row per product variant. Runs in '
            "the background: the answer is the queued job and the command that reads it. Reading "
            "it gives `drafted` (one entry per product with what was decided, the `listing_ids` it "
            "became and `ready` for the group), `not_ready` (only the rows a publish would refuse, "
            "with their issues), and any product the shop had no category for; `--wait` holds on "
            "until then instead."
        ),
        body=(
            body_field(
                "product_ids",
                repeatable=True,
                required=True,
                help="Catalog product UUIDs to stage as BigCommerce drafts.",
            ),
        ),
    ),
    Cmd(
        "publish",
        "POST",
        "/agent/bigcommerce/stores/{store_id}/listings/publish",
        timeout=LONG_TIMEOUT_SECONDS,
        summary=(
            "Publish local DRAFT listings to BigCommerce as live products "
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
        "/agent/bigcommerce/stores/{store_id}/listings/withdraw",
        summary=(
            "Take published BigCommerce listings off the storefront (sets the product hidden) "
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
        "/agent/bigcommerce/stores/{store_id}/listings/{listing_id}",
        summary=(
            "Edit a BigCommerce listing group — local only, nothing reaches BigCommerce here. The "
            "change is recorded as owed and the next publish delivers it "
            '(body: {"title"?, "description"?, "sell_prices"?: {sku: price}, '
            '"quantities"?: {sku: qty}, "category_id"?}).'
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
            body_field(
                "category_id",
                help=(
                    "Which of the shop's own categories to file the product under. Ids come "
                    "from `sellerclaw categories used|search --store-id <id>` — an id the shop "
                    "does not have is refused. Omit to leave the category alone; pass \"\" to "
                    "file it under nothing."
                ),
            ),
        ),
    ),
)

app = build_group(
    NAME,
    "BigCommerce listings: read (mirror, --live on search), sync price/stock, and publish/withdraw.",
    SPECS,
)


def register(parent: typer.Typer) -> None:
    parent.add_typer(app, name=NAME)
