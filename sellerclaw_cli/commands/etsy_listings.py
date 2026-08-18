from __future__ import annotations

import typer

from sellerclaw_cli._command_group import Cmd, LONG_TIMEOUT_SECONDS, SYNC_STOCK_PARTIAL_HELP, body_field, build_group, flag

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
                help="Listings to update, each {sku?, remote_id?, quantity?, price?} (sku or remote_id, and "
                "quantity and/or price). " + SYNC_STOCK_PARTIAL_HELP,
            ),
        ),
    ),
    Cmd(
        "draft",
        "POST",
        "/agent/etsy/stores/{store_id}/listings/draft",
        job_poll_path="/agent/stores/{store_id}/bulk-listing-jobs/{job_id}",
        timeout=LONG_TIMEOUT_SECONDS,
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
                help="Etsy taxonomy (category) id — omit to let the system place each product.",
            ),
            # Omitting a policy is the normal case: the server settles it from the store's pinned
            # default, or from the shop's only one of that type. Ambiguous and unpinned, it does not
            # guess — the drafts are still created and the question comes back in `needs_policies`.
            # Named explicitly, the id is SellerClaw's (`etsy-store list-policies`), like every
            # other id on this API — Etsy's own id is a detail of the publish path.
            body_field(
                "shipping_profile_id",
                help=(
                    "Shipping profile, as SellerClaw's id from `etsy-store list-policies` — omit "
                    "to let the shop settle it."
                ),
            ),
            body_field(
                "return_policy_id",
                help=(
                    "Return policy, as SellerClaw's id from `etsy-store list-policies` — omit to "
                    "let the shop settle it (Etsy does not require one)."
                ),
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
        timeout=LONG_TIMEOUT_SECONDS,
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
        "set-policies",
        "POST",
        "/agent/etsy/stores/{store_id}/listings/set-policies",
        summary=(
            "Point many drafts at the same shop policies in one call — the answer to a "
            '`needs_policies` question (body: {"listing_ids": ["<uuid>", ...], '
            '"shipping_profile_id": "..."}). One policy set for the whole list: a policy belongs to '
            "the Etsy shop, not the listing. Take the ids from `needs_policies[].options` or "
            "`etsy-store list-policies` — SellerClaw's ids, not Etsy's own; an omitted policy is "
            "left as it is. Drafts only — a published listing is refused (use `update`, which tells "
            "Etsy). Returns the patched rows with fresh readiness."
        ),
        body=(
            body_field(
                "listing_ids",
                required=True,
                repeatable=True,
                help="Draft listing ids (UUIDs) to point at these policies.",
            ),
            body_field(
                "shipping_profile_id",
                help=(
                    "Shipping profile id from `etsy-store list-policies`; omit to leave it as it is."
                ),
            ),
            body_field(
                "return_policy_id",
                help="Return policy id from `etsy-store list-policies`; omit to leave it as it is.",
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
            "Edit one Etsy listing group — local only, nothing reaches Etsy here. The change is "
            "recorded as owed and the next publish delivers it "
            '(body: {"title"?, "description"?, "sell_prices"?: {sku: price}, "quantities"?: {sku: qty}, '
            '"shipping_profile_id"?, "return_policy_id"?}). To fix the policies on many drafts at '
            "once, use `set-policies` instead."
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
            body_field(
                "shipping_profile_id",
                help=(
                    "Shipping profile id from `etsy-store list-policies`; omit to leave it as it is."
                ),
            ),
            body_field(
                "return_policy_id",
                help="Return policy id from `etsy-store list-policies`; omit to leave it as it is.",
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
