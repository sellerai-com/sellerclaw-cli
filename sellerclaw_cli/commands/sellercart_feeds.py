from __future__ import annotations

import typer

from sellerclaw_cli._command_group import Cmd, body_field, build_group, flag

NAME = "sellercart-feeds"

_PRODUCTS_HELP = (
    "Product ids: a catalog product's id or the SellerCart listing's own id (the 'id', "
    "'product_id' or 'listing_id' that `sellercart-feeds status` names). Not a variation's own id. "
    "Up to 500."
)

SPECS = (
    Cmd(
        "status",
        "GET",
        "/agent/sellercart/feeds",
        summary=(
            "The shop's three product feeds — the files ChatGPT Ads Manager, Google Merchant Center "
            "and Meta Commerce Manager download to show its products as ads. Read this instead of "
            "opening a feed's address: a download counts as the platform picking the feed up. Per "
            "platform: 'url' (the link the owner pastes into that platform), 'products_in', "
            "'last_fetched_at' (null while the platform never came), 'marked_added_at' (the owner "
            "said they pasted it) and 'left_out' — the products the feed leaves out, grouped by "
            "'reason' with a 'total': 'no_brand' (ChatGPT and Google need a brand; Meta takes a "
            "brand or a valid barcode), 'no_image', 'no_description', 'excluded' (the owner kept it "
            "out). Each product names its 'listing_id' and 'product_id', where a brand, a photo or "
            "a description is written. A BRAND COMES ONLY FROM THE OWNER — ask for it, never guess "
            "one, never use the shop's name. 'delivers_to' is the countries the ChatGPT feed is "
            "shown to — the shop's delivery zones — and 'store_country' where the shop is based "
            "(`sellercart update` `country`). 'unavailable' instead of feeds: 'catalog', "
            "'not_published' or 'closed'."
        ),
        flags=(
            flag(
                "limit",
                type=int,
                minimum=1,
                maximum=500,
                default=100,
                help="How many products to name per reason; 'total' counts them all.",
            ),
        ),
    ),
    Cmd(
        "keep-out",
        "POST",
        "/agent/sellercart/feeds/keep-out",
        summary=(
            "Keep products out of all three product feeds, at the owner's request — they stay on "
            "sale in the shop. Applies at once, no publish. Each product answers on its own: "
            "'kept_out', 'unchanged' (it already was), or an 'error' (a product the shop does not "
            "sell, a variation's id) while the rest go through."
        ),
        body=(
            body_field(
                "products",
                type=list,
                required=True,
                help=_PRODUCTS_HELP,
                example=["<product or listing id>"],
            ),
        ),
    ),
    Cmd(
        "put-back",
        "POST",
        "/agent/sellercart/feeds/put-back",
        summary=(
            "Undo 'keep-out': the products go back into each feed whose rules they meet. "
            "'put_back', 'unchanged' (it was not kept out), or an 'error', per product."
        ),
        body=(
            body_field(
                "products",
                type=list,
                required=True,
                help=_PRODUCTS_HELP,
                example=["<product or listing id>"],
            ),
        ),
    ),
)

app = build_group(NAME, "Product feeds for ads in ChatGPT, Google and Meta.", SPECS)


def register(parent: typer.Typer) -> None:
    parent.add_typer(app, name=NAME)
