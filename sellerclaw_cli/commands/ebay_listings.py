from __future__ import annotations

import typer

from sellerclaw_cli._command_group import Cmd, body_field, build_group, flag

NAME = "ebay-listings"

# Combines the live-eBay listing ops (/agent/ebay/...) with the draft/publish ops
# that live under the store resource (/agent/stores/{store_id}/ebay-*).
SPECS = (
    Cmd(
        "list",
        "GET",
        "/agent/ebay/stores/{store_id}/listings",
        summary="List live eBay listings (a sample page; use 'summary' for full-catalog counts).",
        flags=(
            flag(
                "limit",
                type=int,
                param="limit",
                aliases=("--page-size",),
                minimum=1,
                maximum=200,
                default=200,
                help="Max listings to return (a single sample page; use 'summary' for full-catalog counts).",
            ),
        ),
    ),
    Cmd(
        "summary",
        "GET",
        "/agent/ebay/stores/{store_id}/listings/summary",
        summary=(
            "Aggregate stats over all live eBay listings (listing/variant counts, total & "
            "zero stock, price min/max/avg, currencies). Use this instead of listing every row "
            "when the owner wants an overview of a large catalog."
        ),
    ),
    Cmd(
        "search",
        "POST",
        "/agent/ebay/stores/{store_id}/listings/search",
        summary=(
            "Look up live eBay listings by exact SKU or eBay item id only (body: "
            '{"search_type": "sku"|"remote_id", "search_values": ["..."]}). This is NOT a '
            "title/keyword search — to find a listing by name, use the 'listings search' group, "
            "and to resolve a mentioned listing use 'listings get <id>'."
        ),
        body=(
            body_field(
                "search_type",
                required=True,
                choices=("sku", "remote_id"),
                help="What the values are: exact SKU or eBay item id (remote_id).",
            ),
            body_field(
                "search_values",
                repeatable=True,
                help="List of exact SKUs or eBay item ids to look up.",
            ),
        ),
    ),
    Cmd(
        "sync-stock",
        "POST",
        "/agent/ebay/stores/{store_id}/listings/sync-stock",
        summary="Sync stock to eBay.",
        body=(
            body_field(
                "items",
                type=dict,
                repeatable=True,
                help="Stock items to push, each {sku, quantity, remote_id?, item_id?}.",
            ),
        ),
    ),
    Cmd(
        "publish",
        "POST",
        "/agent/stores/{store_id}/ebay-listings/publish",
        summary="Publish eBay listings.",
        body=(
            body_field(
                "listing_ids",
                required=True,
                repeatable=True,
                help="SellerClaw listing ids (UUIDs) to publish to eBay.",
            ),
        ),
    ),
    Cmd(
        "withdraw",
        "POST",
        "/agent/stores/{store_id}/ebay-listings/withdraw",
        summary="Withdraw eBay listings.",
        body=(
            body_field(
                "listing_ids",
                required=True,
                repeatable=True,
                help="SellerClaw listing ids (UUIDs) to withdraw from eBay.",
            ),
        ),
    ),
    Cmd(
        "update",
        "PATCH",
        "/agent/stores/{store_id}/ebay-listings/{listing_id}",
        summary="Update a published eBay listing.",
        body=(
            body_field("title", help="New listing title (max 80 chars)."),
            body_field("description", help="New listing description (HTML allowed)."),
            body_field("category_id", help="eBay category id."),
            body_field(
                "condition",
                choices=("NEW", "USED", "REFURBISHED"),
                help="Item condition.",
            ),
            body_field("merchant_location_key", help="Inventory location key."),
            body_field("fulfillment_policy_id", help="eBay fulfillment business policy id."),
            body_field("payment_policy_id", help="eBay payment business policy id."),
            body_field("return_policy_id", help="eBay return business policy id."),
            body_field("images", repeatable=True, help="List of image URLs (max 24)."),
            body_field("aspects", type=dict, help="Item specifics, e.g. {\"Color\": [\"Black\"]}."),
        ),
    ),
    Cmd("delete", "DELETE", "/agent/stores/{store_id}/ebay-listings/{listing_id}", summary="Delete a published eBay listing."),
    Cmd(
        "list-drafts",
        "GET",
        "/agent/stores/{store_id}/ebay-draft-listings",
        summary="List eBay draft listings.",
        flags=(flag("status", help="Filter by status."),),
    ),
    Cmd(
        "create-drafts",
        "POST",
        "/agent/stores/{store_id}/ebay-draft-listings",
        summary="Create eBay draft listings.",
        body=(
            body_field(
                "product_ids",
                required=True,
                repeatable=True,
                help="Catalog product ids (UUIDs) to create one draft per product.",
            ),
            body_field("title", required=True, help="Listing title (max 80 chars)."),
            body_field("category_id", required=True, help="eBay category id."),
            body_field(
                "condition",
                required=True,
                choices=("NEW", "USED", "REFURBISHED"),
                help="Item condition.",
            ),
            body_field("merchant_location_key", required=True, help="Inventory location key."),
            body_field("description", help="Listing description (HTML allowed)."),
            body_field(
                "api_kind",
                choices=("trading", "inventory"),
                help="Which eBay API to publish with (defaults to trading).",
            ),
            body_field("fulfillment_policy_id", help="eBay fulfillment business policy id (resolved at publish if omitted)."),
            body_field("payment_policy_id", help="eBay payment business policy id (resolved at publish if omitted)."),
            body_field("return_policy_id", help="eBay return business policy id (resolved at publish if omitted)."),
            body_field("images", repeatable=True, help="List of image URLs (max 24)."),
            body_field("aspects", type=dict, help="Item specifics, e.g. {\"Color\": [\"Black\"]}."),
            body_field("sell_prices", type=dict, help="Override sell prices keyed by SKU/variant."),
        ),
    ),
    Cmd("get-draft", "GET", "/agent/stores/{store_id}/ebay-draft-listings/{listing_id}", summary="Get one eBay draft listing."),
    Cmd(
        "update-draft",
        "PATCH",
        "/agent/stores/{store_id}/ebay-draft-listings/{listing_id}",
        summary="Update an eBay draft listing.",
        body=(
            body_field("title", help="New listing title (max 80 chars)."),
            body_field("description", help="New listing description (HTML allowed)."),
            body_field("category_id", help="eBay category id."),
            body_field(
                "condition",
                choices=("NEW", "USED", "REFURBISHED"),
                help="Item condition.",
            ),
            body_field("merchant_location_key", help="Inventory location key."),
            body_field("fulfillment_policy_id", help="eBay fulfillment business policy id."),
            body_field("payment_policy_id", help="eBay payment business policy id."),
            body_field("return_policy_id", help="eBay return business policy id."),
            body_field("images", repeatable=True, help="List of image URLs (max 24)."),
            body_field("aspects", type=dict, help="Item specifics, e.g. {\"Color\": [\"Black\"]}."),
        ),
    ),
    Cmd(
        "delete-draft",
        "DELETE",
        "/agent/stores/{store_id}/ebay-draft-listings/{listing_id}",
        summary="Delete an eBay draft listing.",
    ),
)

app = build_group(NAME, "eBay listings and drafts (store_id is the first argument).", SPECS)


def register(parent: typer.Typer) -> None:
    parent.add_typer(app, name=NAME)
