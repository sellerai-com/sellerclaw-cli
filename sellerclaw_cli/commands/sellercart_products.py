from __future__ import annotations

import typer

from sellerclaw_cli._command_group import Cmd, body_field, build_group, flag

NAME = "sellercart-products"

#: The same sentence for every write that changes what buyers see — see `sellercart changes`.
_NOTE_HELP = (
    "One sentence for the owner about why, in their language — shown beside this change while it "
    "waits in the draft of a live shop, and kept with the version it is published in. Ignored "
    "before the shop first opens."
)

SPECS = (
    Cmd(
        "list",
        "GET",
        "/agent/sellercart/products",
        summary=(
            "What is on the storefront right now — ONE ENTRY PER PRODUCT, not per variation: its "
            "'listing_id' (the id a publish, a bulk-update and a withdraw take), title, price "
            "('price_min'/'price_max' instead when the variations differ), status, image and url, "
            "plus 'variations' with only what tells the variations apart — "
            "each one's own 'variation_id' (the id 'remove' takes), its sku, its stock, the "
            "changing option axes, and any price / status / picture that differs. A product of one "
            "variation has no 'variations': its sku, price and stock are on the entry. 'total' "
            "counts products, matching the entries. Shows what a buyer sees, so a shelf staged while "
            "the shop was still a draft reads as empty here — pass `--status draft` to see what is "
            "staged and not yet published, or `--status all` for the whole shelf."
        ),
        flags=(
            flag(
                "status",
                choices=("published", "draft", "withdrawn", "all"),
                default="published",
                help="Shelf state to list; 'draft' is staged-not-published, 'all' is everything.",
            ),
            flag("limit", type=int, minimum=1, maximum=50, default=25, help="Max results."),
            flag("offset", type=int, minimum=0, default=0, help="Skip this many."),
            flag("search", help="Match against title or SKU."),
        ),
    ),
    Cmd(
        "add",
        "POST",
        "/agent/sellercart/products",
        summary=(
            "Put catalog products on the storefront, one listing per variation — the answer comes "
            "back one entry per product, each variation named by its own id inside it. Price "
            "defaults to the shop's markup over the catalog cost; pass 'prices' to override. A "
            "product with no cost, "
            "or a shop with no markup set, is refused rather than listed at zero — get a markup on "
            "the shop (the owner approves it) or pass an explicit price first. Copy for the shop "
            "goes in 'products' and lands on the listing; the catalog product keeps its own."
        ),
        body=(
            body_field(
                "products",
                type=list,
                help=(
                    "List of {product_id, title?, description?, images?} — this shop's own copy "
                    "for each product, written onto its listing. Omit a field to take the catalog's."
                ),
                example=[
                    {"product_id": "<uuid>", "description": "<the shop's own copy>"},
                    {"product_id": "<uuid>"},
                ],
            ),
            body_field(
                "product_ids",
                type=list,
                help="Shorthand: catalog product ids to put on the shelf with the catalog's own copy.",
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
        "/agent/sellercart/products/{variation_id}",
        summary=(
            "Take ONE VARIATION off the storefront, reversibly: buyers stop seeing that size, the "
            "row is kept and a publish naming its id in 'variation_ids' puts it back. Takes the "
            "variation's own id — the 'variation_id' in a list entry's 'variations'; the listing's "
            "id is refused here with the variations to pick from, because removing the whole "
            "product is a withdraw job (`listings bulk-publish <store_id>` with body kind "
            "'withdraw'). The default "
            "reading of 'убери это'. To get rid of it for good use 'delete'."
        ),
    ),
    Cmd(
        "seo",
        "PUT",
        "/agent/sellercart/products/{reference}/seo",
        summary=(
            "Write what a search engine should read about one product: the title of its search "
            "result and the description under it. Without these the shop falls back to the "
            "product's own name and the supplier's copy, shortened. A patch — a field left out "
            "keeps what it had, a field sent empty is cleared. Name the product by its catalog "
            "product id or the listing's own id: these words speak for the whole product, and a "
            "variation's own id is refused with the listing id to use instead. The answer names the "
            "id the words were stored under."
        ),
        body=(
            body_field(
                "title",
                clearable=True,
                option="--title",
                help=(
                    "The headline of the search result. Aim for roughly sixty characters — past "
                    "that a result is cut, and where it is cut is not ours to decide."
                ),
            ),
            body_field(
                "description",
                clearable=True,
                option="--description",
                help=(
                    "The sentence under the headline: what this product is and who it is for. "
                    "Aim for roughly a hundred and fifty characters."
                ),
            ),
            body_field(
                "note",
                option="--note",
                help=_NOTE_HELP,
            ),
        ),
    ),
    Cmd(
        "clear-seo",
        "DELETE",
        "/agent/sellercart/products/{reference}/seo",
        summary=(
            "Forget what was written about a product for search, so its page describes itself "
            "from the product again."
        ),
        flags=(flag("note", help=_NOTE_HELP),),
    ),
    Cmd(
        "delete",
        "POST",
        "/agent/sellercart/products/delete",
        summary=(
            "Get rid of products for good (irreversible). One id per product, and it takes the "
            "LISTING'S OWN id — the whole variation "
            "group goes, and a variation's id is refused with the listing id to use instead. Rows "
            "are kept as REMOVED for history, but nothing can be put back: "
            "shelving the product again drafts new rows at today's prices, losing any price or copy "
            "hand-written on these. Only on an explicit instruction from the owner; for a "
            "reversible take-down use 'remove'. A draft was never on the shelf — delete it with "
            "'listings delete-drafts'."
        ),
        body=(
            body_field(
                "listing_ids",
                type=list,
                required=True,
                help=(
                    "The listings' own UUIDs, one per product, to delete for good. A variation's id "
                    "is refused with the listing id to use instead (use_instead)."
                ),
            ),
        ),
    ),
)

app = build_group(NAME, "Products on the seller's own storefront.", SPECS)


def register(parent: typer.Typer) -> None:
    parent.add_typer(app, name=NAME)
