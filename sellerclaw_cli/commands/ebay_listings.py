from __future__ import annotations

import typer

from sellerclaw_cli._command_group import Cmd, LONG_TIMEOUT_SECONDS, SYNC_STOCK_PARTIAL_HELP, body_field, build_group, flag

NAME = "ebay-listings"

# Listing READS come from the unified SellerClaw mirror (/agent/stores/{store_id}/listings),
# warmed on connect + refreshed periodically; pass --live on search to hit eBay directly. The
# draft/publish ops stay under the store resource (/agent/stores/{store_id}/ebay-*).

# The "lazy" draft body: only product_ids is required — the server places the category and fills the
# item specifics when they are omitted. Shared by create-drafts and preview-drafts.
_LAZY_DRAFT_BODY = (
    body_field(
        "product_ids",
        required=True,
        repeatable=True,
        help="Catalog product ids (UUIDs); one draft per product.",
    ),
    body_field(
        "category_id",
        # A `categories search` row carries two ids and this field wants eBay's. Naming both spellings
        # is cheaper than the round trip a wrong one used to cost: the mirror UUID reached eBay
        # unresolved and came back as a rejection that named neither the field nor the reason.
        help=(
            "eBay category id — the 'external_id' of a `categories search` row (its SellerClaw "
            "'category_id' is accepted too). Omit to let the system place each product."
        ),
    ),
    body_field("title", help="Listing title (max 80 chars); defaults to the product name."),
    body_field(
        "condition",
        choices=("NEW", "USED", "REFURBISHED"),
        help="Item condition (defaults to NEW).",
    ),
    body_field(
        "merchant_location_key",
        help=(
            "Ship-from warehouse, as SellerClaw's id from `ebay-store list-locations` — omit to "
            "let the store settle it."
        ),
    ),
    body_field("description", help="Listing description (HTML allowed)."),
    body_field(
        "api_kind",
        choices=("trading", "inventory"),
        help="Which eBay API to publish with (defaults to trading).",
    ),
    # Omitting a policy is the normal case: the server settles it from the store's pinned default,
    # or from the account's only policy of that type. Ambiguous and unpinned, it does not guess —
    # the drafts are still created and the question comes back in `needs_policies`.
    # Named explicitly, the id is SellerClaw's (`ebay-store list-policies`), like every other id on
    # this API — eBay's own id is a detail of the publish path, not something to type here.
    body_field(
        "fulfillment_policy_id",
        help=(
            "Fulfillment policy, as SellerClaw's id from `ebay-store list-policies` — omit to let "
            "the store settle it."
        ),
    ),
    body_field(
        "payment_policy_id",
        help=(
            "Payment policy, as SellerClaw's id from `ebay-store list-policies` — omit to let the "
            "store settle it."
        ),
    ),
    body_field(
        "return_policy_id",
        help=(
            "Return policy, as SellerClaw's id from `ebay-store list-policies` — omit to let the "
            "store settle it."
        ),
    ),
    body_field("images", repeatable=True, help="List of image URLs (max 24)."),
    body_field("aspects", type=dict, help="Item specifics; omit to auto-fill from the product."),
    body_field("sell_prices", type=dict, help="Override sell prices keyed by SKU/variant."),
)

# The parcel, shared by the two edit commands. eBay prices calculated postage from it and refuses a
# listing that carries no weight — and it lives on the listing, so this is how an existing draft or a
# live listing is fixed, without deleting and re-creating anything.
_PACKAGE_BODY = (
    body_field(
        "package_weight_grams",
        type=int,
        help=(
            "What one packed unit weighs, in grams. Required by eBay under a calculated-rate "
            "shipping policy; omit it if nobody knows, never send 0 or a guess."
        ),
    ),
    body_field(
        "package_length_mm",
        type=int,
        help="Package length in millimetres. Send all three sides or none — eBay refuses a partial box.",
    ),
    body_field("package_width_mm", type=int, help="Package width in millimetres."),
    body_field("package_height_mm", type=int, help="Package height in millimetres."),
)

SPECS = (
    Cmd(
        "list",
        "GET",
        "/agent/stores/{store_id}/listings",
        summary=(
            "List the store's eBay listings from the SellerClaw mirror. `total` is the filter-aware match "
            "count, not the size of this page — page through the rest with `--offset`."
        ),
        flags=(
            flag(
                "status",
                choices=("active", "published", "draft", "withdrawn"),
                help="Mirror status to filter by; omit for all.",
            ),
            flag("search", help="Match title, SKU, or remote id."),
            flag(
                "limit",
                type=int,
                aliases=("--page-size",),
                minimum=1,
                maximum=500,
                default=100,
                help="Max results.",
            ),
            flag("offset", type=int, minimum=0, default=0, help="Results to skip (paging)."),
        ),
    ),
    Cmd(
        "summary",
        "GET",
        "/agent/stores/{store_id}/listings/summary",
        summary=(
            "Aggregate stats over the store's eBay listings (listing/variant counts, total & "
            "zero stock, price min/max/avg, currencies). Use this instead of listing every row "
            "when the owner wants an overview of a large catalog."
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
            "Search one store's eBay listings by title, SKU, or remote id. Default: the local "
            "mirror (carries a SellerClaw id for chat cards). Pass --live to query eBay directly "
            "for current price/stock (no SellerClaw id). To search across all stores, use 'listings'."
        ),
        flags=(
            flag("q", required=True, help="Search text (matched as a substring of title/SKU/remote id)."),
            flag(
                "type",
                help="Live-search field: sku (default) or remote_id (eBay item id); ignored by the mirror.",
            ),
            flag(
                "live",
                type=bool,
                help="Query eBay live instead of the mirror — current price/stock, but no SellerClaw id.",
            ),
            flag("limit", type=int, minimum=1, maximum=500, default=100, help="Max results."),
        ),
    ),
    Cmd(
        "performance",
        "GET",
        "/agent/ebay/stores/{store_id}/listing-performance",
        summary=(
            "Listing performance audit (mockup 16): organic funnel + content completeness for the "
            "store's top listings by impressions. Per card, returns eBay's Traffic Report funnel "
            "(impressions, ctr, views, conversion_rate, transactions) plus a transparent SellerClaw "
            "completeness index (completeness_pct 0..1 = filled fields / all — NOT an eBay score) and "
            "`gaps` (what's missing: photos, item specifics, description, video). Cards that get traffic "
            "but convert below the store's own catalog median are flagged `underperforming` with an "
            "`opportunity` (est. $ uplift to the median). Summary fields: `listings_to_improve`, "
            "`avg_completeness_pct`, `lost_traffic_views`, `opportunity_total`, `median_conversion_rate`, "
            "`currency`, `last_updated` (eBay data-freshness date). Weak-but-trafficked cards come first. "
            "Fix flagged cards with `ebay-listings update` / `update-draft` (title, aspects, description, "
            "images). The window ends ~3 days back so eBay's lagging traffic data is already settled."
        ),
        flags=(
            flag(
                "days",
                type=int,
                minimum=1,
                maximum=90,
                default=7,
                help="Trailing window length in days (the window ends ~3 days back).",
            ),
            flag(
                "top_n",
                type=int,
                minimum=1,
                maximum=50,
                default=20,
                help="How many top-traffic listings to audit for content.",
            ),
        ),
    ),
    Cmd(
        "sync-stock",
        "POST",
        "/agent/stores/{store_id}/listings/sync-stock",
        summary=(
            "Update price and/or stock on existing eBay offers "
            '(body: {"items": [{"sku": "...", "quantity": 5, "price": 19.99}]}). '
            "Identify each item by sku or remote_id (the eBay listing id)."
        ),
        body=(
            body_field(
                "items",
                type=dict,
                repeatable=True,
                help="Offers to update, each {sku?, remote_id?, quantity?, price?, "
                "compare_at_price?} (sku or remote_id, and quantity and/or price). " + SYNC_STOCK_PARTIAL_HELP,
            ),
        ),
    ),
    Cmd(
        "publish",
        "POST",
        "/agent/stores/{store_id}/ebay-listings/publish",
        timeout=LONG_TIMEOUT_SECONDS,
        summary="Publish eBay listings.",
        body=(
            body_field(
                "listing_ids",
                required=True,
                repeatable=True,
                help="SellerClaw listing ids (UUIDs) to publish to eBay.",
            ),
        ),
    ),
    Cmd(
        "withdraw",
        "POST",
        "/agent/stores/{store_id}/ebay-listings/withdraw",
        summary="Withdraw eBay listings.",
        body=(
            body_field(
                "listing_ids",
                required=True,
                repeatable=True,
                help="SellerClaw listing ids (UUIDs) to withdraw from eBay.",
            ),
        ),
    ),
    Cmd(
        "update",
        "PATCH",
        "/agent/stores/{store_id}/ebay-listings/{listing_id}",
        summary=(
            "Edit an eBay listing — local only, nothing reaches eBay here. The change is recorded "
            "as owed and the next publish delivers it."
        ),
        body=(
            body_field("title", help="New listing title (max 80 chars)."),
            body_field("description", help="New listing description (HTML allowed)."),
            body_field(
                "category_id",
                help=(
                    "eBay category id — the 'external_id' of a `categories search` row (its "
                    "SellerClaw 'category_id' is accepted too)."
                ),
            ),
            body_field(
                "condition",
                choices=("NEW", "USED", "REFURBISHED"),
                help="Item condition.",
            ),
            # Ids as SellerClaw reports them (`ebay-store list-locations` / `list-policies`) —
            # eBay's own ids belong to the publish path, not to this API.
            body_field(
                "merchant_location_key",
                help="Ship-from warehouse id from `ebay-store list-locations`.",
            ),
            body_field(
                "fulfillment_policy_id",
                help="Fulfillment policy id from `ebay-store list-policies`.",
            ),
            body_field("payment_policy_id", help="Payment policy id from `ebay-store list-policies`."),
            body_field("return_policy_id", help="Return policy id from `ebay-store list-policies`."),
            body_field("images", repeatable=True, help="List of image URLs (max 24)."),
            body_field("aspects", type=dict, help="Item specifics, e.g. {\"Color\": [\"Black\"]}."),
            *_PACKAGE_BODY,
        ),
    ),
    Cmd("delete", "DELETE", "/agent/stores/{store_id}/ebay-listings/{listing_id}", summary="Delete a published eBay listing."),
    Cmd(
        "list-drafts",
        "GET",
        "/agent/stores/{store_id}/ebay-draft-listings",
        summary=(
            "List this store's eBay listings — despite the name, every status, not only drafts "
            "(filter with --status). ONE ENTRY PER LISTING, not per variation: each carries "
            "'listing_ids' (every variation's id — what publish and update-draft take), "
            "'variation_count', the price range, the total stock and the statuses it spans. 'sku' "
            "and 'remote_id' appear only on a listing with exactly one variation. 'total' counts "
            "listings, 'variation_rows' the rows behind them; page with --limit / --offset. For "
            "each variation's own price and stock use 'listings variable'."
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
        "/agent/stores/{store_id}/ebay-draft-listings",
        job_poll_path="/agent/stores/{store_id}/bulk-listing-jobs/{job_id}",
        timeout=LONG_TIMEOUT_SECONDS,
        summary=(
            "Create eBay draft listings (category and item specifics are filled for you). Nothing "
            "reaches eBay: publishing is a separate step, after you have read the drafts back. Runs "
            "in the background: the answer is the queued job and the command that reads it. Read "
            "that once the work has plausibly finished — `drafted` says what was decided per "
            "product (category, item specifics, price range, the `listing_ids` it became and "
            "`ready` for the group), `not_ready` names only the rows a publish would refuse and "
            "why — or add `--wait` to hold on until then."
        ),
        # Only product_ids is required, matching every other channel's draft command and the server,
        # which fills the rest: it places the category, resolves the item specifics off the product,
        # takes the title from the catalog, defaults the condition and reads the location from the
        # eBay account. Requiring them here used to reject the very body the server wants.
        body=_LAZY_DRAFT_BODY,
    ),
    Cmd(
        "preview-drafts",
        "POST",
        "/agent/stores/{store_id}/ebay-draft-listings/preview",
        timeout=LONG_TIMEOUT_SECONDS,
        summary="Preview what drafting products would set (category + item specifics) — creates nothing.",
        body=_LAZY_DRAFT_BODY,
    ),
    Cmd(
        "set-policies",
        "POST",
        "/agent/stores/{store_id}/ebay-draft-listings/set-policies",
        summary=(
            "Point many drafts at the same business policies in one call — the answer to a "
            '`needs_policies` question (body: {"listing_ids": ["<uuid>", ...], '
            '"fulfillment_policy_id": "..."}). One policy set for the whole list: a policy belongs '
            "to the eBay account, not the listing. Take the ids from `needs_policies[].options` or "
            "`ebay-store list-policies` — SellerClaw's ids, not eBay's own; an omitted policy is "
            "left as it is. Drafts only — a published listing is refused (use `update`, which tells "
            "eBay). Returns the patched rows with fresh readiness."
        ),
        body=(
            body_field(
                "listing_ids",
                required=True,
                repeatable=True,
                help="Draft listing ids (UUIDs) to point at these policies.",
            ),
            body_field(
                "fulfillment_policy_id",
                help=(
                    "Fulfillment policy id from `ebay-store list-policies`; omit to leave it as "
                    "it is."
                ),
            ),
            body_field(
                "payment_policy_id",
                help="Payment policy id from `ebay-store list-policies`; omit to leave it as it is.",
            ),
            body_field(
                "return_policy_id",
                help="Return policy id from `ebay-store list-policies`; omit to leave it as it is.",
            ),
        ),
    ),
    Cmd("get-draft", "GET", "/agent/stores/{store_id}/ebay-draft-listings/{listing_id}", summary="Get one eBay draft listing."),
    Cmd(
        "update-draft",
        "PATCH",
        "/agent/stores/{store_id}/ebay-draft-listings/{listing_id}",
        summary="Update an eBay draft listing.",
        body=(
            body_field("title", help="New listing title (max 80 chars)."),
            body_field("description", help="New listing description (HTML allowed)."),
            body_field(
                "category_id",
                help=(
                    "eBay category id — the 'external_id' of a `categories search` row (its "
                    "SellerClaw 'category_id' is accepted too)."
                ),
            ),
            body_field(
                "condition",
                choices=("NEW", "USED", "REFURBISHED"),
                help="Item condition.",
            ),
            # Ids as SellerClaw reports them (`ebay-store list-locations` / `list-policies`) —
            # eBay's own ids belong to the publish path, not to this API.
            body_field(
                "merchant_location_key",
                help="Ship-from warehouse id from `ebay-store list-locations`.",
            ),
            body_field(
                "fulfillment_policy_id",
                help="Fulfillment policy id from `ebay-store list-policies`.",
            ),
            body_field("payment_policy_id", help="Payment policy id from `ebay-store list-policies`."),
            body_field("return_policy_id", help="Return policy id from `ebay-store list-policies`."),
            body_field("images", repeatable=True, help="List of image URLs (max 24)."),
            body_field("aspects", type=dict, help="Item specifics, e.g. {\"Color\": [\"Black\"]}."),
            *_PACKAGE_BODY,
        ),
    ),
    Cmd(
        "delete-draft",
        "DELETE",
        "/agent/stores/{store_id}/ebay-draft-listings/{listing_id}",
        summary="Delete an eBay draft listing.",
    ),
)

app = build_group(NAME, "eBay listings and drafts (store_id is the first argument).", SPECS)


def register(parent: typer.Typer) -> None:
    parent.add_typer(app, name=NAME)
