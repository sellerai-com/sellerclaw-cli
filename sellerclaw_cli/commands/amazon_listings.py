from __future__ import annotations

import typer

from sellerclaw_cli._command_group import Cmd, LONG_TIMEOUT_SECONDS, SYNC_STOCK_PARTIAL_HELP, body_field, build_group, flag
from sellerclaw_cli.commands._listing_shape import LISTING_ENTRY_SHAPE

NAME = "amazon-listings"

# Amazon listings: reads come from the unified SellerClaw mirror (warmed on connect + refreshed
# periodically); pass --live on search to hit Amazon directly. Stock sync is always live.
SPECS = (
    Cmd(
        "list",
        "GET",
        "/agent/stores/{store_id}/listings",
        summary=(
            f"{LISTING_ENTRY_SHAPE} "
            "List the store's Amazon listings from the SellerClaw mirror. `total` is the filter-aware "
            "match count, not the size of this page — page through the rest with `--offset`."
        ),
        flags=(
            flag(
                "status",
                choices=("active", "published", "draft", "withdrawn"),
                help="Mirror status to filter by; omit for all.",
            ),
            flag("search", help="Match title, SKU, or remote id."),
            flag("limit", type=int, minimum=1, maximum=100, default=25, help="Max listings per page."),
            flag("offset", type=int, minimum=0, default=0, help="Results to skip (paging)."),
        ),
    ),
    Cmd(
        "summary",
        "GET",
        "/agent/stores/{store_id}/listings/summary",
        summary=(
            "Aggregate stats over the store's Amazon listings (row count, total & zero stock, "
            "price min/max/avg, currencies). FBA offers, stocked in Amazon's warehouse, count in "
            "amazon_warehouse_rows, not as zero stock. Use this instead of listing every row for an "
            "overview."
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
            f"{LISTING_ENTRY_SHAPE} "
            "Search one store's Amazon listings by title, SKU, or remote id. Default: the local "
            "mirror (carries a SellerClaw id for chat cards). Pass --live to query Amazon directly "
            "for current price/stock (no SellerClaw id)."
        ),
        flags=(
            flag("q", required=True, help="Search text (matched as a substring of title/SKU/remote id)."),
            flag(
                "type",
                help="Live-search field: sku (default) or asin; ignored by the mirror.",
            ),
            flag(
                "live",
                type=bool,
                help="Query Amazon live instead of the mirror — current price/stock, but no SellerClaw id.",
            ),
            flag("limit", type=int, minimum=1, maximum=100, default=25, help="Max listings per page."),
        ),
    ),
    Cmd(
        "sync-stock",
        "POST",
        "/agent/stores/{store_id}/listings/sync-stock",
        summary=(
            "Update price and/or merchant quantity on existing Amazon offers "
            '(body: {"items": [{"sku": "...", "quantity": 5, "price": 19.99}]}). '
            "Amazon manages FBA quantity itself."
        ),
        body=(
            body_field(
                "items",
                type=dict,
                repeatable=True,
                help="Offers to update, each {sku, quantity?, price?} (remote_id works for an "
                "offer we already mirror). " + SYNC_STOCK_PARTIAL_HELP,
            ),
        ),
    ),
    Cmd(
        "find-asin",
        "POST",
        "/agent/amazon/stores/{store_id}/catalog/search",
        summary=(
            "Find the Amazon catalog item (ASIN) to sell on — the first step of publishing. "
            "Search by barcode for an exact match, or by keywords for candidates. Keyword hits are "
            "candidates only: confirm the right one before drafting, because offering on the wrong "
            "catalog item can get the seller suspended."
        ),
        body=(
            body_field("keywords", help="Product name or search text, e.g. 'wireless earbuds ANC'."),
            body_field(
                "identifiers",
                repeatable=True,
                help="Exact lookup by product identifier (a barcode, or an ASIN itself).",
            ),
            body_field(
                "identifiers_type",
                help="Kind of identifier passed: ASIN, UPC, EAN, GTIN, ISBN, JAN, MINSAN, SKU.",
            ),
            body_field("limit", type=int, help="Max candidates to return (1-20, default 10)."),
        ),
    ),
    Cmd(
        "draft",
        "POST",
        "/agent/amazon/stores/{store_id}/listings/draft",
        job_poll_path="/agent/stores/{store_id}/bulk-listing-jobs/{job_id}",
        timeout=LONG_TIMEOUT_SECONDS,
        summary=(
            "Create local DRAFT offers from catalog products before publishing. Amazon sells on "
            "shared catalog items, so every variation must name the ASIN it will be offered on "
            "(use 'find-asin' first) — each variation needs its OWN ASIN, and an ASIN the store "
            "already sells is rejected. The catalog item owns the title, images and description; "
            "the offer only carries price, quantity and condition."
        ),
        body=(
            body_field(
                "product_ids",
                repeatable=True,
                required=True,
                help="Catalog product UUIDs to stage as Amazon drafts.",
            ),
            body_field(
                "asins",
                type=dict,
                help='ASIN to sell on, keyed by variation SKU, e.g. {"SKU-1": "B07N4M94X4"}.',
            ),
            body_field(
                "asin_titles",
                type=dict,
                help="Catalog titles of the chosen ASINs, keyed by SKU — kept as proof of what was matched.",
            ),
            body_field(
                "condition_type",
                help="Condition of the goods, e.g. new_new (default), used_good, refurbished_refurbished.",
            ),
        ),
    ),
    Cmd(
        "publish",
        "POST",
        "/agent/amazon/stores/{store_id}/listings/publish",
        timeout=LONG_TIMEOUT_SECONDS,
        summary=(
            "Publish DRAFT offers to Amazon "
            '(body: {"listing_ids": ["<uuid>", ...]}). Async: Amazon only *accepts* the submission, '
            "so rows stay draft (publish_state 'submitted') until the offer actually goes live — "
            "poll publish-status for the result. A row the seller is not allowed to list fails on "
            "its own without failing the batch."
        ),
        body=(
            body_field(
                "listing_ids",
                repeatable=True,
                required=True,
                help="The listings' own ids ('listing_id' from list/search; a variation's id is refused) to publish to the store.",
            ),
        ),
    ),
    Cmd(
        "publish-status",
        "GET",
        "/agent/amazon/stores/{store_id}/listings/{listing_id}/publish-status",
        summary=(
            "Check where an offer got to: publish_state is submitted (still settling), done (live — "
            "check 'suppressed', which means Amazon accepted it but shoppers cannot buy it), error "
            "(see 'issues', and 'restrictions' for the Seller Central approval link), or timeout."
        ),
    ),
    Cmd(
        "withdraw",
        "POST",
        "/agent/amazon/stores/{store_id}/listings/withdraw",
        summary=(
            "Remove our offers from Amazon (body: {\"listing_ids\": [...], \"variation_ids\": [...]}, "
            "at least one). 'listing_ids' takes every offer of each listing off; 'variation_ids' takes "
            "single offers off (a variation's own id from list/search). The catalog items stay — they "
            "were never ours. The rows are kept for history. Returns one entry per listing."
        ),
        body=(
            body_field(
                "listing_ids",
                repeatable=True,
                help="The listings' own ids ('listing_id' from list/search): every offer of each is withdrawn.",
            ),
            body_field(
                "variation_ids",
                repeatable=True,
                help="Single offers to withdraw, by the variation's own id ('variation_id' from list/search).",
            ),
        ),
    ),
    Cmd(
        "update",
        "PATCH",
        "/agent/amazon/stores/{store_id}/listings/{variation_id}",
        summary=(
            "Change the price or quantity of one Amazon offer, named by its own id (a 'variation_id' "
            "from list/search; a single-offer listing's 'listing_id' works too) "
            '(body: {"sell_price"?: 19.99, "quantity"?: 5}). Pushed to Amazon immediately when the '
            "offer is live. The ASIN cannot be changed — withdraw and draft again instead."
        ),
        body=(
            body_field("sell_price", type=float, help="New price for this offer."),
            body_field("quantity", type=int, help="New merchant-fulfilled stock quantity."),
        ),
    ),
)

app = build_group(
    NAME,
    "Amazon listings: read offers (mirror, --live on search), sync price/stock, and publish an "
    "offer onto an existing Amazon catalog item (find-asin → draft → publish).",
    SPECS,
)


def register(parent: typer.Typer) -> None:
    parent.add_typer(app, name=NAME)
