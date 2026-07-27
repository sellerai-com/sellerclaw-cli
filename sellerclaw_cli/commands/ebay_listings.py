from __future__ import annotations

import typer

from sellerclaw_cli._command_group import Cmd, body_field, build_group, flag

NAME = "ebay-listings"

# Listing READS come from the unified SellerClaw mirror (/agent/stores/{store_id}/listings),
# warmed on connect + refreshed periodically; pass --live on search to hit eBay directly. The
# draft/publish ops stay under the store resource (/agent/stores/{store_id}/ebay-*).

# The "lazy" draft body: only product_ids is required — the server places the category and fills the
# item specifics when they are omitted. Shared by preview-drafts and publish-product.
_LAZY_DRAFT_BODY = (
    body_field(
        "product_ids",
        required=True,
        repeatable=True,
        help="Catalog product ids (UUIDs); one draft per product.",
    ),
    body_field("category_id", help="eBay category id — omit to let the system place each product."),
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

SPECS = (
    Cmd(
        "list",
        "GET",
        "/agent/stores/{store_id}/listings",
        summary="List the store's eBay listings from the SellerClaw mirror.",
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
        summary="Sync stock to eBay.",
        body=(
            body_field(
                "items",
                type=dict,
                repeatable=True,
                help="Stock items to push, each {sku, quantity, remote_id?, price?, compare_at_price?}.",
            ),
        ),
    ),
    Cmd(
        "publish",
        "POST",
        "/agent/stores/{store_id}/ebay-listings/publish",
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
        summary="Update a published eBay listing.",
        body=(
            body_field("title", help="New listing title (max 80 chars)."),
            body_field("description", help="New listing description (HTML allowed)."),
            body_field("category_id", help="eBay category id."),
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
        ),
    ),
    Cmd("delete", "DELETE", "/agent/stores/{store_id}/ebay-listings/{listing_id}", summary="Delete a published eBay listing."),
    Cmd(
        "list-drafts",
        "GET",
        "/agent/stores/{store_id}/ebay-draft-listings",
        summary="List eBay draft listings.",
        flags=(flag("status", help="Filter by status."),),
    ),
    Cmd(
        "create-drafts",
        "POST",
        "/agent/stores/{store_id}/ebay-draft-listings",
        summary="Create eBay draft listings (category and item specifics are filled for you).",
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
        summary="Preview what drafting products would set (category + item specifics) — creates nothing.",
        body=_LAZY_DRAFT_BODY,
    ),
    Cmd(
        "publish-product",
        "POST",
        "/agent/stores/{store_id}/ebay-draft-listings/publish-product",
        summary="One shot: draft products (auto category + specifics) and publish the ready ones.",
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
            body_field("category_id", help="eBay category id."),
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
