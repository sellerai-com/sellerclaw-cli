from __future__ import annotations

import typer

from sellerclaw_cli._command_group import Cmd, body_field, build_group

NAME = "attributes"

# Every marketplace lets a category define which attributes a listing may carry, splits them into
# variation axes (Colour/Size) vs shared vs per-variation, and often fixes their allowed values.
# `map` does all of that for you: hand it a product and the category you chose, get back the product's
# attributes already matched to the marketplace's system attributes and sorted into those buckets, so
# you never have to guess item specifics. `schema` just shows what a category expects.
#
# Flow: `categories suggest` -> pick a category -> `attributes map` -> build the listing from the
# result. Put `common_attributes` (+ `custom_attributes`) on the listing, declare
# `variation_attributes` as its axes, give each variation its `own_attributes`; act on
# `missing_required` and `warnings` first. Supported today: eBay, Etsy, TikTok Shop.
SPECS = (
    Cmd(
        "map",
        "POST",
        "/agent/attributes/map",
        summary="Match a product's attributes to a category's system attributes (variation/common/own).",
        body=(
            body_field("store_id", required=True, help="Store to publish on (from `channels list`)."),
            body_field(
                "category_external_id",
                required=True,
                help="Marketplace category id you chose (the `external_id` from `categories suggest`).",
            ),
            body_field("product_id", required=True, help="Catalog product to map."),
        ),
    ),
    Cmd(
        "schema",
        "POST",
        "/agent/attributes/schema",
        summary="Show the system attributes a category allows (required, variation-eligible, values).",
        body=(
            body_field("store_id", required=True, help="Store whose marketplace to read."),
            body_field(
                "category_external_id",
                required=True,
                help="Marketplace category id (the `external_id` from `categories suggest`/`search`).",
            ),
        ),
    ),
)

app = build_group(
    NAME,
    "Match a product's attributes to a marketplace category — stop guessing item specifics.",
    SPECS,
)


def register(parent: typer.Typer) -> None:
    parent.add_typer(app, name=NAME)
