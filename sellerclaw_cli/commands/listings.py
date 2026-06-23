from __future__ import annotations

import typer

from sellerclaw_cli._command_group import Cmd, build_group, flag

NAME = "listings"

# Channel-agnostic access to the user's mirrored marketplace listings (Shopify and eBay alike),
# keyed by the SellerClaw listing id. Use this to resolve a listing the owner mentioned in chat
# (fetch by id) or to find one by name without knowing its store (search). Channel-specific
# publish/draft operations stay in the ``shopify-listings`` / ``ebay-listings`` groups.
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
        "search",
        "GET",
        "/agent/listings/search",
        summary=(
            "Find listings across all connected stores by title, SKU, or remote id "
            "(case-insensitive substring). Each result carries its listing id for a 'get' follow-up."
        ),
        flags=(
            flag("q", required=True, help="Search text (matched as a substring of title/SKU/remote id)."),
            flag("limit", type=int, minimum=1, maximum=200, default=25, help="Max results."),
        ),
    ),
)

app = build_group(NAME, "Marketplace listings across all stores (by SellerClaw id).", SPECS)


def register(parent: typer.Typer) -> None:
    parent.add_typer(app, name=NAME)
