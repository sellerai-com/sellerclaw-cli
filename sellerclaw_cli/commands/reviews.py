from __future__ import annotations

import typer

from sellerclaw_cli._command_group import Cmd, build_group, flag

NAME = "reviews"

# Customer reviews READ from the SellerClaw mirror (warmed on connect + refreshed periodically);
# pass --fresh to bypass the mirror and fetch live from the marketplace. Works for WooCommerce, Wix
# and Etsy stores; an unsupported platform returns an empty list. eBay uses the 'ebay-feedback'
# group. BigCommerce reviews are per-product, so they have their own subcommand.
SPECS = (
    Cmd(
        "list",
        "GET",
        "/agent/stores/{store_id}/reviews",
        summary=(
            "List a store's customer reviews (rating, text, author, product, any existing reply), "
            "newest first. WooCommerce / Wix / Etsy; eBay uses 'ebay-feedback'."
        ),
        flags=(
            flag(
                "limit",
                type=int,
                aliases=("--page-size",),
                minimum=1,
                maximum=500,
                default=100,
                help="Max results.",
            ),
            flag(
                "fresh",
                type=bool,
                help="Bypass the mirror and fetch live from the marketplace (slower).",
            ),
        ),
    ),
    Cmd(
        "bigcommerce",
        "GET",
        "/agent/bigcommerce/stores/{store_id}/reviews",
        summary="List reviews for one BigCommerce product (reviews are per-product there).",
        flags=(
            flag("product_id", required=True, help="BigCommerce product id whose reviews to fetch."),
            flag("limit", type=int, minimum=1, maximum=500, default=100, help="Max results."),
        ),
    ),
)

app = build_group(NAME, "Customer reviews and ratings (store_id is the first argument).", SPECS)


def register(parent: typer.Typer) -> None:
    parent.add_typer(app, name=NAME)
