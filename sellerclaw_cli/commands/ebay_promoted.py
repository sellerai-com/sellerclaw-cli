from __future__ import annotations

import typer

from sellerclaw_cli._command_group import Cmd, body_field, build_group, flag

NAME = "ebay-promoted"

SPECS = (
    Cmd(
        "campaigns",
        "GET",
        "/agent/ebay/stores/{store_id}/promoted/campaigns",
        summary="List Promoted Listings campaigns (name, status, funding model, bid %).",
    ),
    Cmd(
        "create-report",
        "POST",
        "/agent/ebay/stores/{store_id}/promoted/reports",
        summary=(
            "Start an async Promoted Listings performance report for a trailing window and get a "
            "report task id back. eBay builds ad reports asynchronously, so poll 'get-report' with "
            "the id until it is COMPLETED to read ROAS/ACOS/spend/ad-sales."
        ),
        flags=(
            flag("days", type=int, param="days", minimum=1, maximum=90, default=7, help="Trailing window in days."),
        ),
    ),
    Cmd(
        "get-report",
        "GET",
        "/agent/ebay/stores/{store_id}/promoted/reports/{report_task_id}",
        summary=(
            "Get a performance report task's status; once COMPLETED it also returns the aggregated "
            "ROAS, ACOS, ad spend and ad sales for the window."
        ),
    ),
    Cmd(
        "effectiveness",
        "GET",
        "/agent/ebay/stores/{store_id}/promoted/reports/{report_task_id}/effectiveness",
        summary=(
            "Get a report task's status; once COMPLETED it also returns the full ad-effectiveness "
            "view: store totals (spend/ad-sales/ROAS/ACOS) plus a breakdown by ad tool (Promoted "
            "Listings vs Advanced) and a per-SKU table, each row labelled scale / watch / cut. Use "
            "the same report task id you polled with 'get-report'."
        ),
    ),
    # --- Write: campaign management (Promoted Listings Standard) ----------------------
    # Advertising spends real money, so actions that start or increase spend are staged and need
    # the owner's approval before they run; spend-reducing actions (pause/end/remove/lower rate)
    # apply immediately.
    Cmd(
        "prepare-campaign",
        "POST",
        "/agent/ebay/stores/{store_id}/promoted/campaigns/prepare",
        summary=(
            "Stage a new Promoted Listings Standard campaign (pay-on-sale) for the owner's "
            "approval. Nothing goes live here: it returns a pending action with status "
            "'pending_approval'; once the owner approves, run 'apply' with the returned id to "
            "actually create the campaign and start promoting the listings. 'bid_percentage' is "
            'the ad rate as a percent string, e.g. "10.0".'
        ),
        body=(
            body_field("name", type=str, required=True, help="Campaign name.", example="Summer mugs push"),
            body_field("bid_percentage", type=str, required=True, help='Ad rate percent, e.g. "10.0".', example="10.0"),
            body_field(
                "listing_ids",
                type=str,
                required=True,
                repeatable=True,
                help="eBay listing ids to promote.",
                example=["1234567890", "1234567891"],
            ),
        ),
    ),
    Cmd(
        "pending-actions",
        "GET",
        "/agent/ebay/stores/{store_id}/promoted/pending-actions",
        summary=(
            "List staged, spend-affecting ad actions for the store and their status "
            "(pending_approval / applied / rejected / failed). Use an id here with 'apply'."
        ),
    ),
    Cmd(
        "apply",
        "POST",
        "/agent/ebay/stores/{store_id}/promoted/pending-actions/{action_id}/apply",
        summary=(
            "Run a staged ad action against eBay — only works after the owner has approved it. "
            "Fails with 409 while it is still awaiting approval and 403 if the owner declined. "
            "Idempotent once applied."
        ),
    ),
    Cmd(
        "add-listings",
        "POST",
        "/agent/ebay/stores/{store_id}/promoted/campaigns/{campaign_id}/add-listings",
        summary=(
            "Stage adding listings to an existing campaign (this increases ad spend, so it needs "
            "the owner's approval). Returns a pending action; 'apply' it after approval."
        ),
        body=(
            body_field(
                "listing_ids",
                type=str,
                required=True,
                repeatable=True,
                help="eBay listing ids to add to the campaign.",
                example=["1234567890"],
            ),
            body_field("bid_percentage", type=str, required=True, help='Ad rate percent, e.g. "10.0".', example="10.0"),
        ),
    ),
    Cmd(
        "set-ad-rate",
        "POST",
        "/agent/ebay/stores/{store_id}/promoted/campaigns/{campaign_id}/ad-rate",
        summary=(
            "Set an ad's ad-rate percentage. Raising the rate increases spend so it is staged for "
            "the owner's approval (returns status 'pending_approval'); lowering it applies "
            "immediately (returns status 'applied'). The direction is checked against the current "
            "rate on eBay, so an increase can't be applied without approval."
        ),
        body=(
            body_field("ad_id", type=str, required=True, help="The ad id whose rate to change.", example="ad-123"),
            body_field("bid_percentage", type=str, required=True, help='New ad rate percent, e.g. "12.0".', example="12.0"),
        ),
    ),
    Cmd(
        "resume-campaign",
        "POST",
        "/agent/ebay/stores/{store_id}/promoted/campaigns/{campaign_id}/resume",
        summary=(
            "Stage resuming a paused campaign (restarts ad spend, so it needs the owner's "
            "approval). Returns a pending action; 'apply' it after approval."
        ),
    ),
    Cmd(
        "pause-campaign",
        "POST",
        "/agent/ebay/stores/{store_id}/promoted/campaigns/{campaign_id}/pause",
        summary="Pause a running campaign immediately (stops ad spend — no approval needed).",
    ),
    Cmd(
        "end-campaign",
        "POST",
        "/agent/ebay/stores/{store_id}/promoted/campaigns/{campaign_id}/end",
        summary="End a campaign immediately (stops ad spend — no approval needed).",
    ),
    Cmd(
        "remove-listings",
        "POST",
        "/agent/ebay/stores/{store_id}/promoted/campaigns/{campaign_id}/remove-listings",
        summary="Remove listings from a campaign immediately (reduces ad spend — no approval needed).",
        body=(
            body_field(
                "listing_ids",
                type=str,
                required=True,
                repeatable=True,
                help="eBay listing ids to stop promoting.",
                example=["1234567890"],
            ),
        ),
    ),
)

app = build_group(
    NAME,
    "eBay Promoted Listings: campaigns, performance reports, and approval-gated campaign management.",
    SPECS,
)


def register(parent: typer.Typer) -> None:
    parent.add_typer(app, name=NAME)
