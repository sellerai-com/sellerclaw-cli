from __future__ import annotations

import typer

from sellerclaw_cli._command_group import Cmd, build_group, flag

NAME = "listings"

# Channel-agnostic access to the user's mirrored marketplace listings (Shopify, eBay, Amazon, …),
# keyed by the SellerClaw listing id. This is the group that reads ONE listing by id and the group
# that finds listings by any criterion — the per-channel groups (``shopify-listings``, …) own only
# the channel-specific publish/draft operations, because a SellerClaw listing id is not scoped to a
# channel and reading it through a channel group would be a lie.
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
            "Find listings across every connected store by any mix of criteria (all AND-combined). "
            "Free text (--q: title / SKU / marketplace id), the catalog product they were published "
            "from (--product-id — one listing row per variant, so a 4-variant product returns 4), "
            "an exact --sku or --remote-id, one store (--store-id), a whole channel (--platform), "
            "or a lifecycle --status. No criteria = the most recently updated listings. Each result "
            "carries its listing id for a 'get' follow-up; 'total' is the full match count."
        ),
        flags=(
            flag("q", help="Free text: substring of the title, SKU, or marketplace id."),
            flag(
                "product_id",
                help=(
                    "Catalog product id: returns every listing published from it, one row per "
                    "variant. The only product -> listings route there is."
                ),
            ),
            flag("store_id", help="Restrict to one store (sales channel id, see `channels list`)."),
            flag("sku", help="Exact SKU match (case-insensitive)."),
            flag("remote_id", help="Exact marketplace id (Shopify gid, eBay item id, …)."),
            flag(
                "platform",
                help="Restrict to one channel.",
                choices=(
                    "shopify",
                    "ebay",
                    "amazon",
                    "etsy",
                    "walmart",
                    "wix",
                    "woocommerce",
                    "bigcommerce",
                    "tiktok_shop",
                ),
            ),
            flag(
                "status",
                help="Lifecycle status of the mirrored row.",
                choices=("draft", "active", "published", "withdrawn", "removed"),
            ),
            flag("limit", type=int, minimum=1, maximum=200, default=25, help="Max results per page."),
            flag("offset", type=int, minimum=0, default=0, help="Results to skip (paging)."),
        ),
    ),
)

app = build_group(NAME, "Marketplace listings across all stores (by SellerClaw id).", SPECS)


def register(parent: typer.Typer) -> None:
    parent.add_typer(app, name=NAME)
