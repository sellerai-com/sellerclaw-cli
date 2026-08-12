from __future__ import annotations

import typer

from sellerclaw_cli._command_group import Cmd, body_field, build_group, flag

NAME = "categories"

# Every marketplace makes you file a product under one of its categories before it will list it, and
# each one has tens of thousands of them. `suggest` is the command that exists so you never have to
# know that: hand it a product and a store, get back the categories it actually belongs in.
#
# The other commands are for the case where the OWNER names a category ("put it under Running
# Shoes") — not for routine publishing. Never type a category id from memory: it will be wrong, and
# you will only find out when the marketplace rejects the listing.
#
# `refresh` is for one situation only: the owner says they *just* made a category on their own store
# (WooCommerce, Wix, BigCommerce) and wants it used now. Drafting reads our copy of their store, which
# updates itself daily, so every other time it is a wasted call.
#
# `create` and `rename` write to the owner's own store, so they exist only for those three: a
# marketplace hands every seller the same fixed tree, and Shopify's category is free text. Create a
# category when the OWNER asks for one — not because a product matched nothing. A shop's pages are
# built on the categories it already has, and a second near-identical one is a page nobody links to
# (which is why a name the store already keeps comes back as `created: false` instead).
SPECS = (
    Cmd(
        "suggest",
        "POST",
        "/agent/categories/suggest",
        summary="Where does this product belong on this store? Returns a shortlist to pick from.",
        body=(
            body_field("store_id", required=True, help="Store to publish on (from `channels list`)."),
            body_field("product_id", required=True, help="Catalog product to place."),
            body_field(
                "requires_variations",
                type=bool,
                help=(
                    "Only offer categories that accept multi-variation listings. Follows the product "
                    "by default (on when it has more than one variation)."
                ),
            ),
        ),
    ),
    Cmd(
        "confirm",
        "POST",
        "/agent/categories/confirm",
        summary="Remember the category you chose, so the next product like it needs no suggesting.",
        body=(
            body_field("store_id", required=True, help="Store the category belongs to."),
            body_field("product_id", required=True, help="Product you placed."),
            body_field(
                "category_id",
                required=True,
                help="The `category_id` of the category you picked (from `suggest`/`search`/`used`).",
            ),
        ),
    ),
    Cmd(
        "used",
        "GET",
        "/agent/categories/used",
        summary="Categories this store already sells in, busiest first.",
        flags=(
            flag("store_id", required=True, help="Store to inspect."),
            flag("limit", type=int, minimum=1, maximum=200, help="Max categories to return (default 60)."),
        ),
    ),
    Cmd(
        "search",
        "GET",
        "/agent/categories/search",
        summary="Find a category by name — use when the owner names one outright.",
        flags=(
            flag("store_id", required=True, help="Store whose marketplace to search."),
            flag("q", required=True, help="Words from the category name or its path.", aliases=("--query",)),
            flag("leaf_only", type=bool, help="Only categories you may publish into (default true)."),
            flag(
                "supports_variations",
                type=bool,
                help="Only categories that accept multi-variation listings (default false).",
            ),
            flag("limit", type=int, minimum=1, maximum=100, help="Max results (default 20)."),
        ),
    ),
    Cmd(
        "children",
        "GET",
        "/agent/categories/children",
        summary="Walk the category tree one level down. Rarely needed — prefer `suggest`.",
        flags=(
            flag("store_id", required=True, help="Store whose marketplace to walk."),
            flag("parent_id", help="Marketplace category id; omit for the top level."),
            flag("tree_id", help="Which tree, when the store has several (e.g. eBay Motors)."),
        ),
    ),
    Cmd(
        "trees",
        "GET",
        "/agent/categories/trees",
        summary="Which category trees serve this store, and when they were last refreshed.",
        flags=(flag("store_id", required=True, help="Store to inspect."),),
    ),
    Cmd(
        "refresh",
        "POST",
        "/agent/categories/refresh",
        summary="Owner just made a category and wants it used now? Re-read the store's categories.",
        flags=(
            flag(
                "store_id",
                required=True,
                help="The store whose own categories to re-read (from `channels list`).",
            ),
        ),
    ),
    Cmd(
        "create",
        "POST",
        "/agent/categories/create",
        summary=(
            "Make a new category on your own store (WooCommerce, Wix, BigCommerce). "
            "A name the store already has is returned instead of a duplicate."
        ),
        body=(
            body_field("store_id", required=True, help="Your store (from `channels list`)."),
            body_field("name", required=True, help="What the category is called."),
            body_field(
                "parent_id",
                help="Category to nest this one under (an `external_id`); omit for a top-level one.",
            ),
        ),
    ),
    Cmd(
        "rename",
        "POST",
        "/agent/categories/rename",
        summary="Rename one of your own store's categories. What is filed in it stays filed.",
        body=(
            body_field("store_id", required=True, help="Your store (from `channels list`)."),
            body_field(
                "category_id",
                required=True,
                help="The `external_id` of the category to rename (from `search`/`used`).",
            ),
            body_field("name", required=True, help="The new name."),
        ),
    ),
)

app = build_group(
    NAME,
    "Place a product in the right marketplace category — never guess a category id.",
    SPECS,
)


def register(parent: typer.Typer) -> None:
    parent.add_typer(app, name=NAME)
