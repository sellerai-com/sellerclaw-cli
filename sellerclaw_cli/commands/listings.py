from __future__ import annotations

import typer

from sellerclaw_cli._command_group import Cmd, body_field, build_group, flag

NAME = "listings"

# Channel-agnostic access to the user's mirrored marketplace listings (Shopify, eBay, Amazon, …),
# keyed by the SellerClaw listing id. This is the group that reads ONE listing by id and the group
# that finds listings by any criterion — the per-channel groups (``shopify-listings``, …) own only
# the channel-specific publish/draft operations, because a SellerClaw listing id is not scoped to a
# channel and reading it through a channel group would be a lie.
SPECS = (
    Cmd(
        "get",
        "GET",
        "/agent/listings/{listing_id}",
        summary=(
            "Get one listing by its SellerClaw id, from any connected store. Use this to resolve "
            "a listing the owner referenced (e.g. an @-mentioned listing card carries this id)."
        ),
    ),
    Cmd(
        "adopt-marketplace-version",
        "POST",
        "/agent/listings/{listing_id}/adopt-marketplace-version",
        summary=(
            "Throw away this listing's unpublished local edits and keep what the last download read "
            "from the marketplace. Local and instant: it calls no marketplace. NOT needed to follow "
            "the channel — a download already adopts whatever the marketplace changed on its own, so "
            "reach for this only to abandon edits you would otherwise publish (an edit is recorded "
            "locally and only leaves on publish; this is the one place one disappears unsent). Say "
            "which pending edits it will drop before running it. Needs a prior download of this "
            "listing to have something to keep — refresh the store's listings first "
            "(`listings sync`) if it has never been read."
        ),
    ),
    Cmd(
        "search",
        "GET",
        "/agent/listings/search",
        summary=(
            "Find listings across every connected store by any mix of criteria (all AND-combined). "
            "Free text (--q: title / SKU / marketplace id), the catalog product they were published "
            "from (--product-id), an exact --sku or --remote-id, one store (--store-id), a whole "
            "channel (--platform), or a lifecycle --status. No criteria = the most recently updated "
            "listings. ONE ENTRY PER LISTING, not per variation: a 4-variant product is one result, "
            "carrying 'listing_ids' (every variation's id — what a publish or an update takes), "
            "'variation_count', the price range and the total stock, plus 'ready' / "
            "'blocking_fields' / 'not_ready_listing_ids' for the group as a whole. A matched listing "
            "comes back whole, so searching one SKU returns that listing with all its variations "
            "named. 'total' counts listings; 'variation_rows' counts the rows behind them. For each "
            "variation's own price and stock use 'listings variable'."
        ),
        flags=(
            flag("q", help="Free text: substring of the title, SKU, or marketplace id."),
            flag(
                "product_id",
                help=(
                    "Catalog product id: returns every listing published from it, one entry each "
                    "with its variations folded. The only product -> listings route there is."
                ),
            ),
            flag("store_id", help="Restrict to one store (sales channel id, see `channels list`)."),
            flag("sku", help="Exact SKU match (case-insensitive)."),
            flag("remote_id", help="Exact marketplace id (Shopify gid, eBay item id, …)."),
            flag(
                "platform",
                help="Restrict to one channel.",
                choices=(
                    "shopify",
                    "ebay",
                    "amazon",
                    "etsy",
                    "walmart",
                    "wix",
                    "woocommerce",
                    "bigcommerce",
                    "tiktok_shop",
                ),
            ),
            flag(
                "status",
                help=(
                    "Lifecycle status of the row. A draft is a listing you have not published yet "
                    "-- the same row, not a separate object; publishing moves it to 'published'. "
                    "'withdrawn' (taken off sale, restorable) and 'removed' are NOT 'unpublished'."
                ),
                choices=("draft", "active", "published", "withdrawn", "removed"),
            ),
            flag(
                "has_unpublished_changes",
                type=bool,
                help=(
                    "true = listings with edits recorded locally that have not reached the channel "
                    "yet. This is the set to publish, and the first step of updating live listings."
                ),
            ),
            flag(
                "changed_since",
                help=(
                    "Only listings something actually changed on since this moment (ISO-8601). "
                    "Read from the change history, not the row's updated_at -- the background "
                    "stock sync bumps that on rows nobody touched."
                ),
            ),
            flag(
                "changed_by",
                repeatable=True,
                help=(
                    "Who changed it; repeat the flag to combine (e.g. --changed-by owner "
                    "--changed-by agent = 'changed by a person')."
                ),
                choices=("owner", "agent", "sync", "marketplace", "unknown"),
            ),
            flag("limit", type=int, minimum=1, maximum=200, default=25, help="Max results per page."),
            flag("offset", type=int, minimum=0, default=0, help="Results to skip (paging)."),
        ),
    ),
    Cmd(
        "history",
        "GET",
        "/agent/listings/history",
        summary=(
            "What has changed on your listings, newest first -- who changed it and whether it "
            "reached the channel. The question a listing row cannot answer: a price on the row is "
            "just a number, here it is 'the agent set it at 14:02 and it reached eBay at 14:06', or "
            "'the supplier sync moved it'. Use it to check your own work after an edit "
            "(--changed-by is on 'search'; here use --source agent --since), to explain a value "
            "(--field price), and to find what is still owed to the channel (--only-undelivered). "
            "Entries are never deleted: a delivered edit keeps its delivered_at, and an edit "
            "dropped by taking the marketplace's version stays as 'discarded'."
        ),
        flags=(
            flag("listing_id", help="One listing's history (SellerClaw listing id)."),
            flag("store_id", help="Restrict to one store (sales channel id, see `channels list`)."),
            flag(
                "field",
                repeatable=True,
                help="Only these fields (e.g. price, quantity, title, status). Repeat to combine.",
            ),
            flag(
                "source",
                repeatable=True,
                help=(
                    "Who made the change. 'sync' is our own upkeep (supplier stock, markup "
                    "recompute); 'marketplace' is their own value as a download read it; 'unknown' "
                    "means the write path did not declare itself. Repeat to combine."
                ),
                choices=("owner", "agent", "sync", "marketplace", "unknown"),
            ),
            flag("since", help="Only changes at or after this moment (ISO-8601)."),
            flag("until", help="Only changes at or before this moment (ISO-8601)."),
            flag(
                "only_undelivered",
                type=bool,
                help="Only edits still waiting for a publish to carry them to the channel.",
            ),
            flag("limit", type=int, minimum=1, maximum=200, default=50, help="Max results per page."),
            flag("offset", type=int, minimum=0, default=0, help="Results to skip (paging)."),
        ),
    ),
    Cmd(
        "variable",
        "GET",
        "/agent/listings/variable",
        summary=(
            "Get one WHOLE variable listing on one store — every variation folded under a single "
            "header (status span, price range, total stock) plus each variation's own price / "
            "stock / sale-blockers, and the listing's open problems. 'search' also answers one "
            "entry per listing, but only the header of it; this is where each variation's own "
            "figures and the listing's problems are. Name it with --group-id (every row and every "
            "search entry carries it) plus --store-id (its id or its domain). Report it to the "
            "owner as ONE variable listing (one card), never as N separate rows."
        ),
        flags=(
            flag(
                "group_id",
                help=(
                    "Variation group id — what says 'these rows are one listing'. Read it off any "
                    "search row. Works for a listing found on the store as well as one published "
                    "from the catalog, and it does not change when a draft goes live."
                ),
            ),
            flag(
                "product_id",
                help=(
                    "Catalog product id — the older way to name the listing, still accepted. Only "
                    "resolves a listing published from the catalog; prefer --group-id."
                ),
            ),
            flag(
                "store_id",
                required=True,
                help="The store: its sales channel id or its domain (see `channels list`).",
            ),
        ),
    ),
    Cmd(
        "sync",
        "POST",
        "/agent/stores/{store_id}/listings/sync",
        summary=(
            "Re-read one store's catalog from its marketplace into the SellerClaw mirror. Reads "
            "otherwise come from the mirror, which refreshes on a schedule and can be hours or days "
            "behind. Queues the job and returns the mirror's current synced_at: poll the store's "
            "listings until synced_at moves past it. Use before an irreversible step, or after a "
            "change made outside SellerClaw that should be reflected back."
        ),
    ),
    # --- Bulk draft workflow: see drafts -> check readiness -> bulk-fix -> bulk publish ---
    Cmd(
        "drafts",
        "GET",
        "/agent/listings/drafts",
        summary=(
            "List one store's draft listings — the ones prepared locally but not yet published. One "
            "entry per listing with its variations folded, carrying a quick 'ready' flag plus "
            "'blocking_fields' and 'not_ready_listing_ids', so you can see which drafts still need "
            "work before a bulk publish. 'ready' is true only when EVERY variation would publish, "
            "because that is what a publish judges. Scoped to one store (--store-id is required): "
            "you work a store at a time, and a store already fixes the channel. For the full, "
            "product-group-aware readiness (the same one a publish enforces) use "
            "'listings readiness'."
        ),
        flags=(
            flag(
                "store_id",
                required=True,
                help="The store to list drafts for (sales channel id, see `channels list`).",
            ),
            flag("limit", type=int, minimum=1, maximum=200, default=50, help="Max results per page."),
            flag("offset", type=int, minimum=0, default=0, help="Results to skip (paging)."),
        ),
    ),
    Cmd(
        "readiness",
        "POST",
        "/agent/listings/readiness",
        summary=(
            "Dry-run publish readiness for a set of listings — no marketplace call, no changes. For "
            "each id: 'ready' plus the blocking 'issues' that would stop a publish (the same checks "
            "the real publish runs, so the answer can't drift) and soft 'hints' worth fixing first "
            "(e.g. no image). Product-group-aware: one broken variant marks the whole product "
            "not-ready. Run this before a bulk publish to see exactly what to fix."
        ),
        body=(
            body_field(
                "listing_ids",
                repeatable=True,
                required=True,
                help="SellerClaw listing ids to check.",
            ),
        ),
    ),
    Cmd(
        "check",
        "POST",
        "/agent/listings/consistency-check",
        summary=(
            "Flag the odd-one-out in a batch before publishing: a price far from the batch median "
            "(a likely typo), or the only listing missing an image or a description when the others "
            "have them. Advisory only — nothing here blocks a publish. Set 'group_by_category' to "
            "compare each listing only against others in its own marketplace category."
        ),
        body=(
            body_field(
                "listing_ids",
                repeatable=True,
                required=True,
                help="SellerClaw listing ids to compare.",
            ),
            body_field(
                "group_by_category",
                type=bool,
                help="Compare each listing only against others in its marketplace category.",
            ),
        ),
    ),
    Cmd(
        "bulk-update",
        "POST",
        "/agent/listings/bulk-update",
        summary=(
            "Apply per-listing changes to many listings at once — published ones too, not only "
            "drafts — and get each one's fresh readiness back in the same call. Body: 'items' is a "
            "list of {listing_id, patch:{title?, description?, sell_prices?, quantities?, images?, "
            "variation_images?}} — sell_prices / quantities are keyed by SKU. Nothing reaches a "
            "marketplace here: each edit is written locally and recorded as owed, and the next "
            "publish delivers it. eBay takes title/description/images only; Amazon takes "
            "price/stock only (its copy and photos belong to the ASIN card). One failing item does "
            "not sink the rest."
        ),
        body=(
            body_field(
                "items",
                type=list,
                required=True,
                help=(
                    "List of {listing_id, patch}. patch keys: title, description, sell_prices "
                    "(SKU->price), quantities (SKU->qty), images (the listing's whole gallery in "
                    "publish order — the first is the cover, and the list replaces what was "
                    "there), variation_images (variation listing id -> photo URL, null clears one), "
                    "package_weight_grams (what one packed unit weighs, in grams — eBay prices "
                    "calculated postage from it and refuses a listing without it) and "
                    "package_length_mm / package_width_mm / package_height_mm (the box; all three "
                    "or none)."
                ),
                example=[
                    {"listing_id": "<uuid>", "patch": {"title": "New title"}},
                    {
                        "listing_id": "<uuid>",
                        "patch": {"images": ["https://.../front.jpg", "https://.../back.jpg"]},
                    },
                    {"listing_id": "<uuid>", "patch": {"package_weight_grams": 28}},
                ],
            ),
        ),
    ),
    Cmd(
        "delete-drafts",
        "POST",
        "/agent/listings/delete-drafts",
        summary=(
            "Delete draft listings — draft-only, and purely local. A draft was never pushed to a "
            "marketplace, so this removes only the local row and calls no marketplace. Anything that "
            "is not a draft is left untouched and reported with the reason, so a live listing is never "
            "torn down here by mistake — remove a published listing through its own store's listings "
            "command. Ids that aren't yours come back in 'unknown_ids'."
        ),
        body=(
            body_field(
                "listing_ids",
                repeatable=True,
                required=True,
                help="SellerClaw listing ids of the drafts to delete.",
            ),
        ),
    ),
    Cmd(
        "create-drafts",
        "POST",
        "/agent/stores/{store_id}/create-drafts",
        job_poll_path="/agent/stores/{store_id}/bulk-listing-jobs/{job_id}",
        summary=(
            "Draft catalog products onto ANY store — one command for every marketplace. Body: "
            "'products' is a list of {product_id, title?, description?, images?, attributes?, "
            "category_id?} — everything describing the goods is stated per product, so a batch of "
            "ten gets ten descriptions, not one repeated. 'product_ids' is the shorthand when the "
            "catalog's own text will do. 'channel' carries what belongs to the account rather than "
            "the goods (eBay policies and api_kind, Etsy who_made, Walmart item spec) and is "
            "validated against this store's platform. Returns the job; poll 'listings bulk-job'."
        ),
        body=(
            body_field(
                "products",
                type=list,
                help=(
                    "List of {product_id, title?, description?, images?, attributes?, category_id?}. "
                    "The description is the listing's own copy — the catalog product's text is a "
                    "seed, not a description. images is the whole gallery in publish order, first "
                    "one the cover. category_id is where to file this one product; omit it and the "
                    "product is placed for you."
                ),
                example=[
                    {
                        "product_id": "<uuid>",
                        "description": "<the listing's own copy>",
                        "category_id": "<marketplace category id>",
                    },
                    {"product_id": "<uuid>"},
                ],
            ),
            body_field(
                "product_ids",
                repeatable=True,
                help="Shorthand: catalog product UUIDs to draft with the catalog's own copy.",
            ),
            body_field(
                "channel",
                type=dict,
                help=(
                    "This marketplace's own fields, settled once for the batch — eBay: api_kind, "
                    "fulfillment_policy_id, payment_policy_id, return_policy_id, "
                    "merchant_location_key, condition, sell_prices; Etsy: taxonomy_id, "
                    "shipping_profile_id, return_policy_id, who_made, when_made, is_supply; "
                    "Walmart: the item spec; TikTok: category_id; Amazon: asins, condition_type. A "
                    "field another marketplace uses is refused by name."
                ),
                example={"api_kind": "trading"},
            ),
        ),
    ),
    Cmd(
        "bulk-publish",
        "POST",
        "/agent/stores/{store_id}/bulk-listing-jobs",
        job_poll_path="/agent/stores/{store_id}/bulk-listing-jobs/{job_id}",
        summary=(
            "Publish or withdraw many listings on one store in the background, resumably. Body: "
            "'kind' (publish/withdraw), 'listing_ids', and 'only_ready' (default true) which, on a "
            "publish, skips listings that would be rejected — they are recorded as failed up front "
            "with their readiness issues and never sent, so the ready ones still go out. Returns the "
            "job immediately; poll 'listings bulk-job' for per-listing progress. Re-running a job "
            "skips items already done."
        ),
        body=(
            body_field(
                "kind",
                required=True,
                choices=("publish", "withdraw"),
                help="publish drafts, or withdraw live listings.",
            ),
            body_field(
                "listing_ids",
                repeatable=True,
                required=True,
                help="SellerClaw listing ids to publish/withdraw.",
            ),
            body_field(
                "only_ready",
                type=bool,
                help="On publish: skip (and report) listings that aren't publishable. Default true.",
            ),
        ),
    ),
    Cmd(
        "bulk-jobs",
        "GET",
        "/agent/stores/{store_id}/bulk-listing-jobs",
        summary="List recent bulk publish/withdraw jobs for a store.",
    ),
    Cmd(
        "bulk-job",
        "GET",
        "/agent/stores/{store_id}/bulk-listing-jobs/{job_id}",
        summary=(
            "Get one bulk job's status and per-listing outcomes (succeeded / failed with the "
            "reason, still pending). Poll this after 'bulk-publish' until nothing is pending."
        ),
    ),
)

app = build_group(NAME, "Marketplace listings across all stores (by SellerClaw id).", SPECS)


def register(parent: typer.Typer) -> None:
    parent.add_typer(app, name=NAME)
