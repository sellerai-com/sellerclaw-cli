from __future__ import annotations

import typer

from sellerclaw_cli._command_group import Cmd, body_field, build_group

NAME = "research-catalog"

SPECS = (
    Cmd(
        "ebay-search",
        "POST",
        "/agent/research/catalog/ebay/search",
        summary="Search the eBay product catalog for research.",
        body=(
            body_field("query", help="Free-text search (e.g. 'brand + model'). Provide query, gtin or sellers."),
            body_field("gtin", help="Barcode: EAN, UPC, GTIN, or ISBN. Digits only (8-14 chars)."),
            body_field("marketplace_id", help="eBay marketplace, e.g. EBAY_US, EBAY_GB, EBAY_DE. Defaults to EBAY_US."),
            body_field("limit", type=int, help="Max results (1-200). Defaults to 20."),
            body_field("condition_new_only", type=bool, help="If true, restrict to NEW condition listings."),
            body_field(
                "sellers",
                repeatable=True,
                example=["rival_store"],
                help=(
                    "eBay seller usernames (max 10). Alone: that seller's listings up to 'limit' "
                    "(one page, not a full export); with query: search inside their store."
                ),
            ),
            body_field(
                "sort",
                choices=("price", "-price", "newlyListed"),
                help="Result order. Default is eBay best match; there is no best-selling order.",
            ),
        ),
    ),
)

app = build_group(NAME, "Marketplace catalog research.", SPECS)


def register(parent: typer.Typer) -> None:
    parent.add_typer(app, name=NAME)
