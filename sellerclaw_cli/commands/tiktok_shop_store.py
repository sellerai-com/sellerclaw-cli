from __future__ import annotations

import typer

from sellerclaw_cli._command_group import Cmd, build_group, flag

NAME = "tiktok-shop-store"

# TikTok publishing is category-driven: you must publish under a LEAF category and fill that
# category's required attributes. These reads surface the taxonomy the manager needs before it
# can build a draft to publish.
SPECS = (
    Cmd(
        "get-info",
        "GET",
        "/agent/stores/{store_id}/info",
        summary="Get the TikTok Shop store info (shop name, region, currency).",
    ),
    Cmd(
        "categories",
        "GET",
        "/agent/tiktok-shop/stores/{store_id}/categories",
        summary=(
            "List the shop's TikTok category tree. Publishing requires a LEAF category "
            "(a node whose is_leaf is true); pick one and pass its id to 'category-attributes'."
        ),
    ),
    Cmd(
        "category-attributes",
        "GET",
        "/agent/tiktok-shop/stores/{store_id}/category-attributes",
        summary=(
            "List a leaf category's product attributes. Fill the required ones on the draft before "
            "publishing, or TikTok rejects the product."
        ),
        flags=(
            flag(
                "category_id",
                required=True,
                help="Leaf TikTok category id (from 'categories').",
            ),
        ),
    ),
    Cmd(
        "brands",
        "GET",
        "/agent/tiktok-shop/stores/{store_id}/brands",
        summary="List brands available to the shop, optionally narrowed to a category.",
        flags=(flag("category_id", help="Narrow brands to this leaf category id."),),
    ),
    Cmd(
        "list-locations",
        "GET",
        "/agent/stores/{store_id}/locations",
        summary="List the shop's warehouses; 'is_default' marks the one stock is written to.",
    ),
    Cmd(
        "refresh-locations",
        "POST",
        "/agent/stores/{store_id}/locations/refresh",
        summary=(
            "Re-read warehouses from TikTok now — for one the seller just created in Seller Center. "
            "Otherwise the mirror only refreshes daily."
        ),
    ),
)

app = build_group(
    NAME,
    "TikTok Shop store: info plus the publish taxonomy (categories, attributes, brands).",
    SPECS,
)


def register(parent: typer.Typer) -> None:
    parent.add_typer(app, name=NAME)
