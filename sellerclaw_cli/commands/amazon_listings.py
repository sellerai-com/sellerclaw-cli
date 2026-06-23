from __future__ import annotations

import typer

from sellerclaw_cli._command_group import Cmd, body_field, build_group, flag

NAME = "amazon-listings"

# Read-only listing ops for Amazon (v1): live reads from SP-API plus price/stock sync on existing
# offers. Publishing new listings is not available yet.
SPECS = (
    Cmd(
        "list",
        "GET",
        "/agent/amazon/stores/{store_id}/listings",
        summary="List live Amazon offers (a sample page; use 'summary' for full-catalog counts).",
        flags=(
            flag(
                "limit",
                type=int,
                minimum=1,
                maximum=500,
                default=100,
                help="Max offers to return (a single sample page; use 'summary' for full-catalog counts).",
            ),
        ),
    ),
    Cmd(
        "summary",
        "GET",
        "/agent/amazon/stores/{store_id}/listings/summary",
        summary=(
            "Aggregate stats over the store's live Amazon offers (counts collapsed by ASIN, total "
            "& zero stock, price min/max/avg, currencies). Use this instead of listing every row "
            "for an overview of a large catalog."
        ),
    ),
    Cmd(
        "search",
        "POST",
        "/agent/amazon/stores/{store_id}/listings/search",
        summary=(
            "Look up live Amazon offers by exact SKU or ASIN only "
            '(body: {"search_type": "sku"|"asin", "search_values": ["..."]}).'
        ),
        body=(
            body_field(
                "search_type",
                required=True,
                choices=("sku", "asin"),
                help="What the values are: exact SKU or ASIN.",
            ),
            body_field(
                "search_values",
                repeatable=True,
                help="List of exact SKUs or ASINs to look up.",
            ),
        ),
    ),
    Cmd(
        "sync-stock",
        "POST",
        "/agent/amazon/stores/{store_id}/listings/sync-stock",
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
                help="Offers to update, each {sku, quantity?, price?, currency?}.",
            ),
        ),
    ),
)

app = build_group(NAME, "Amazon listings: read offers and sync price/stock (store_id is the first argument).", SPECS)


def register(parent: typer.Typer) -> None:
    parent.add_typer(app, name=NAME)
