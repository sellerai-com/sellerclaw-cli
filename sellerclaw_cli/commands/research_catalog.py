from __future__ import annotations

import typer

from sellerclaw_cli._command_group import Cmd, body_field, build_group

NAME = "research-catalog"

#: Storefronts whose listings can be read one by one. Keyword search is a shorter list — several of
#: these publish no search we can reach — so the two are declared separately per command.
_ALL_STOREFRONTS = (
    "amazon",
    "ebay",
    "etsy",
    "bestbuy",
    "newegg",
    "target",
    "ikea",
    "nike",
    "allbirds",
)

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
    Cmd(
        "listing-get",
        "POST",
        "/agent/research/catalog/listings/get",
        summary="Read one marketplace listing as data: price, stock, seller, specs, variants.",
        body=(
            body_field(
                "url",
                example="https://www.amazon.com/dp/B09B8V1LZ3",
                help="The listing's page URL. The storefront is recognised from it.",
            ),
            body_field(
                "marketplace",
                choices=_ALL_STOREFRONTS,
                help="Storefront, when addressing a listing by id instead of URL.",
            ),
            body_field(
                "listing_id",
                help=(
                    "The storefront's own id: Amazon ASIN, eBay item number, Etsy listing id, "
                    "Best Buy SKU, Newegg item number, Nike style-colour. A product URL also works."
                ),
            ),
            body_field(
                "include_variants",
                type=bool,
                help=(
                    "Also read sizes/colours and their prices. On eBay, Etsy, Target, IKEA and "
                    "Allbirds this is a second call and costs twice as much."
                ),
            ),
            body_field("currency", help="Preferred display currency where supported (Etsy)."),
        ),
    ),
    Cmd(
        "listing-search",
        "POST",
        "/agent/research/catalog/listings/search",
        summary="Find listings on one storefront by keyword.",
        body=(
            body_field(
                "marketplace",
                required=True,
                choices=("amazon", "bestbuy", "newegg", "nike", "allbirds"),
                help="Storefront to search. eBay has its own richer command: ebay-search.",
            ),
            body_field("query", required=True, help="What to search for."),
            body_field("limit", type=int, help="Max rows (1-50). Defaults to 10."),
            body_field(
                "page",
                type=int,
                help="Result page, on storefronts that page (amazon, bestbuy, newegg).",
            ),
        ),
    ),
    Cmd(
        "listing-prices",
        "POST",
        "/agent/research/catalog/listings/prices",
        summary="Re-check what up to 5 known listings cost right now, on one storefront.",
        body=(
            body_field(
                "marketplace",
                required=True,
                choices=_ALL_STOREFRONTS,
                help="Storefront the ids belong to — one storefront per call.",
            ),
            body_field(
                "listing_ids",
                repeatable=True,
                required=True,
                example=["B09B8V1LZ3", "B07QK2SPP7"],
                help=(
                    "Up to 5 storefront ids, or product URLs. Amazon checks all of them in one "
                    "call; other storefronts are read one at a time and charged per listing. "
                    "target, ikea and allbirds take the product URL."
                ),
            ),
        ),
    ),
)

app = build_group(NAME, "Marketplace catalog research.", SPECS)


def register(parent: typer.Typer) -> None:
    parent.add_typer(app, name=NAME)
