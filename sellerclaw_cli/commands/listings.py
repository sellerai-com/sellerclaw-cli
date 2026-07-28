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
            "Take the marketplace's current version of one listing as the desired state — the "
            "counterpart to publishing. A publish sends your local edits out to the channel; this "
            "does the opposite, copying what the last download read from the marketplace into the "
            "fields you edit, so 'what you see is what publishes' holds again. Local and instant: it "
            "calls no marketplace. It DISCARDS this listing's unpublished local edits (an edit is "
            "recorded locally and only leaves on publish) — that is the point: you are choosing the "
            "channel's version over your own. Reach for it when the listing drifted (the marketplace "
            "moved under you) and you would rather keep the marketplace's values than push yours. "
            "Needs a prior download of this listing to have something to take — refresh the store's "
            "listings first (`listings sync`) if it has never been read."
        ),
    ),
    Cmd(
        "search",
        "GET",
        "/agent/listings/search",
        summary=(
            "Find listings across every connected store by any mix of criteria (all AND-combined). "
            "Free text (--q: title / SKU / marketplace id), the catalog product they were published "
            "from (--product-id — one listing row per variant, so a 4-variant product returns 4), "
            "an exact --sku or --remote-id, one store (--store-id), a whole channel (--platform), "
            "or a lifecycle --status. No criteria = the most recently updated listings. Each result "
            "carries its listing id for a 'get' follow-up; 'total' is the full match count."
        ),
        flags=(
            flag("q", help="Free text: substring of the title, SKU, or marketplace id."),
            flag(
                "product_id",
                help=(
                    "Catalog product id: returns every listing published from it, one row per "
                    "variant. The only product -> listings route there is."
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
            "Get one product's WHOLE variable listing on one store — every variation folded under a "
            "single header (status span, price range, total stock) plus each variation's own price / "
            "stock / sale-blockers, and the listing's open problems. A multi-variant publish makes "
            "one storefront product with N variations; 'search --product-id' returns them as N flat "
            "rows, this returns them as the one listing they are. Needs the catalog product "
            "(--product-id) and the store (--store-id, its id or its domain). Report it to the owner "
            "as ONE variable listing (one card), never as N separate rows."
        ),
        flags=(
            flag(
                "product_id",
                required=True,
                help="Catalog product id — the variable listing is this product on the store.",
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
            "List one store's draft listings — the ones prepared locally but not yet published. Each "
            "row carries a quick 'ready' flag plus 'issue_count' and 'blocking_fields', so you can see "
            "which drafts still need work before a bulk publish. Scoped to one store (--store-id is "
            "required): you work a store at a time, and a store already fixes the channel. For the "
            "full, product-group-aware readiness (the same one a publish enforces) use "
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
            "Apply per-listing changes to many DRAFT listings at once and get each draft's fresh "
            "readiness back in the same call. Body: 'items' is a list of "
            "{listing_id, patch:{title?, description?, sell_prices?, quantities?}} — sell_prices / "
            "quantities are keyed by SKU. eBay takes title/description only here; Amazon takes "
            "price/stock only. One failing item does not sink the rest."
        ),
        body=(
            body_field(
                "items",
                type=list,
                required=True,
                help=(
                    "List of {listing_id, patch}. patch keys: title, description, sell_prices "
                    "(SKU->price), quantities (SKU->qty)."
                ),
                example=[
                    {"listing_id": "<uuid>", "patch": {"title": "New title"}},
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
