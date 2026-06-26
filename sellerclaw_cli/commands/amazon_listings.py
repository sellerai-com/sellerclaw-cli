from __future__ import annotations

import typer

from sellerclaw_cli._command_group import Cmd, body_field, build_group, flag

NAME = "amazon-listings"

# Amazon listings: reads come from the unified SellerClaw mirror (warmed on connect + refreshed
# periodically); pass --live on search to hit Amazon directly. Stock sync is always live.
SPECS = (
    Cmd(
        "list",
        "GET",
        "/agent/stores/{store_id}/listings",
        summary="List the store's Amazon listings from the SellerClaw mirror.",
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
            "Aggregate stats over the store's Amazon listings (row count, total & zero stock, "
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
            flag("limit", type=int, minimum=1, maximum=500, default=100, help="Max results."),
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
                help="Offers to update, each {sku (required), quantity?, price?, remote_id?}.",
            ),
        ),
    ),
)

app = build_group(NAME, "Amazon listings: read offers (mirror, --live on search) and sync price/stock.", SPECS)


def register(parent: typer.Typer) -> None:
    parent.add_typer(app, name=NAME)
