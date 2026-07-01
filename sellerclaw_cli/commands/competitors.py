from __future__ import annotations

import typer

from sellerclaw_cli._command_group import Cmd, body_field, build_group, flag

NAME = "competitors"

SPECS = (
    Cmd(
        "add-watch",
        "POST",
        "/agent/competitors/stores/{store_id}/watches",
        summary=(
            "Track a competitor's eBay listing for a store so its price is polled and shown in the "
            "undercutting report. Get the competitor_item_id from `research-catalog ebay-search` "
            "(the eBay Browse item id, e.g. 'v1|123456789|0'). Link your matching SKU via our_sku so "
            "the report can compare the rival's price against your cost floor. Idempotent on the "
            "competitor item id — re-adding refreshes the label/SKU and reactivates it."
        ),
        body=(
            body_field(
                "competitor_item_id",
                required=True,
                help="eBay Browse item id to track (from research-catalog ebay-search), e.g. 'v1|123456789|0'.",
                example="v1|123456789|0",
            ),
            body_field(
                "marketplace_id",
                help="eBay marketplace the rival sells on (EBAY_US, EBAY_GB, EBAY_DE, ...). Defaults to EBAY_US.",
                example="EBAY_US",
            ),
            body_field(
                "our_sku",
                help="Your SKU of the matching product; links the watch to your cost-of-goods floor.",
            ),
            body_field(
                "our_product_id",
                help="Optional id of your product this competitor maps to.",
            ),
            body_field("competitor_title", help="Optional label for the competitor listing."),
            body_field("competitor_epid", help="Optional eBay product id (ePID) of the rival listing."),
        ),
    ),
    Cmd(
        "list-watches",
        "GET",
        "/agent/competitors/stores/{store_id}/watches",
        summary="List the competitor listings tracked for a store (active only by default).",
        flags=(
            flag(
                "include_inactive",
                type=bool,
                help="Also show paused watches, not just the active (polled) ones.",
            ),
        ),
    ),
    Cmd(
        "remove-watch",
        "DELETE",
        "/agent/competitors/stores/{store_id}/watches/{watch_id}",
        summary="Stop tracking a competitor listing for a store (by watch id from list-watches).",
    ),
    Cmd(
        "poll",
        "POST",
        "/agent/competitors/stores/{store_id}/poll",
        summary=(
            "Poll live competitor prices for a store now and record a price snapshot per watch. A "
            "background job does this every few hours; use this for an immediate refresh (e.g. right "
            "after adding watches) so the report has a fresh 'now' point. Needs the store's eBay "
            "integration; returns how many snapshots were written."
        ),
    ),
    Cmd(
        "report",
        "GET",
        "/agent/competitors/stores/{store_id}/report",
        summary=(
            "Competitor undercutting ('dumping') report for a store: for each tracked rival, its "
            "price now vs the previous snapshot ('was -> now', delta and %), a flag when it dropped "
            "sharply, and whether it's priced below your cost-of-goods floor (can't be matched "
            "profitably). Most urgent rows first. Run `poll` first if there are no snapshots yet."
        ),
    ),
)

app = build_group(
    NAME,
    "eBay competitor price monitoring: watch list, price snapshots, and the undercutting report.",
    SPECS,
)


def register(parent: typer.Typer) -> None:
    parent.add_typer(app, name=NAME)
