from __future__ import annotations

import typer

from sellerclaw_cli._command_group import Cmd, body_field, build_group, flag

NAME = "sellercart-products"

SPECS = (
    Cmd(
        "list",
        "GET",
        "/agent/sellercart/products",
        summary="What is on the storefront right now.",
        flags=(
            flag("limit", type=int, minimum=1, maximum=200, default=25, help="Max results."),
            flag("offset", type=int, minimum=0, default=0, help="Skip this many."),
            flag("search", help="Match against title or SKU."),
        ),
    ),
    Cmd(
        "add",
        "POST",
        "/agent/sellercart/products",
        summary=(
            "Put catalog products on the storefront, one listing per variation. Price defaults to the "
            "shop's markup over the catalog cost; pass 'prices' to override. A product with no cost, "
            "or a shop with no markup set, is refused rather than listed at zero — set the shop's "
            "markup or pass an explicit price first."
        ),
        body=(
            body_field(
                "product_ids",
                type=list,
                required=True,
                help="Catalog product ids to put on the shelf.",
            ),
            body_field(
                "prices",
                type=dict,
                help=(
                    "Optional explicit sell prices, keyed by SKU. Plain numbers, like every other "
                    "money field in this CLI — a quoted string is refused where the field is checked."
                ),
                example={"SKU-1": 19.99},
            ),
        ),
    ),
    Cmd(
        "remove",
        "DELETE",
        "/agent/sellercart/products/{listing_id}",
        summary="Take a product off the storefront. Buyers stop seeing it; the row is kept for history.",
    ),
)

app = build_group(NAME, "Products on the seller's own storefront.", SPECS)


def register(parent: typer.Typer) -> None:
    parent.add_typer(app, name=NAME)
