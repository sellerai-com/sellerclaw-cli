from __future__ import annotations

import typer

from sellerclaw_cli._command_group import Cmd, body_field, build_group, flag

NAME = "shopify-listings"

SPECS = (
    Cmd(
        "list",
        "GET",
        "/agent/stores/{store_id}/listings",
        summary="List the store's Shopify listings from the SellerClaw mirror.",
        flags=(
            flag(
                "status",
                choices=("active", "published", "draft", "withdrawn"),
                help="Mirror status to filter by; omit for all live listings.",
            ),
            flag("search", help="Match title, SKU, or remote id."),
            flag("limit", type=int, minimum=1, maximum=500, default=100, help="Max results."),
        ),
    ),
    Cmd(
        "summary",
        "GET",
        "/agent/stores/{store_id}/listings/summary",
        summary=(
            "Aggregate stats over the store's Shopify listings (row count, total & zero stock, "
            "price min/max/avg, currencies). Use this instead of listing every row for an overview."
        ),
        flags=(
            flag(
                "status",
                choices=("active", "published", "draft", "withdrawn"),
                help="Mirror status to filter by; omit for all live listings.",
            ),
        ),
    ),
    Cmd(
        "search",
        "GET",
        "/agent/stores/{store_id}/listings/search",
        summary=(
            "Search one store's listings by title, SKU, or remote id. Default: the local mirror "
            "(carries a SellerClaw id for chat cards). Pass --live to query Shopify directly for "
            "current price/stock (no SellerClaw id). To search across all stores, use 'listings'."
        ),
        flags=(
            flag("q", required=True, help="Search text (matched as a substring of title/SKU/remote id)."),
            flag(
                "type",
                help="Live-search field (sku by default); ignored by the mirror, which spans title/SKU/remote id.",
            ),
            flag(
                "live",
                type=bool,
                help="Query the live store instead of the mirror — current price/stock, but no SellerClaw id.",
            ),
            flag("limit", type=int, minimum=1, maximum=500, default=100, help="Max results."),
        ),
    ),
    Cmd(
        "create",
        "POST",
        "/agent/stores/{store_id}/listings",
        summary="Publish products as Shopify listings.",
        body=(
            body_field(
                "items",
                type=dict,
                repeatable=True,
                help="Products to create. Each: title (required), body_html, vendor, product_type, "
                "tags (array), status, images (array of URLs), variants (array of {sku, title, "
                "barcode, price, compare_at_price, meta}).",
            ),
        ),
    ),
    Cmd(
        "update",
        "PUT",
        "/agent/stores/{store_id}/listings",
        summary="Update Shopify listings.",
        body=(
            body_field(
                "items",
                type=dict,
                repeatable=True,
                help="Products to update. Each: product_id (required), plus any of title, body_html, "
                "vendor, product_type, tags, status, images, variants.",
            ),
        ),
    ),
    Cmd(
        "delete",
        "DELETE",
        "/agent/stores/{store_id}/listings",
        summary="Delete Shopify listings.",
        body=(
            body_field("product_ids", repeatable=True, help="Shopify product ids to delete."),
        ),
    ),
    Cmd(
        "publish",
        "POST",
        "/agent/stores/{store_id}/listings/publish",
        summary="Publish listings.",
        body=(
            body_field("product_ids", repeatable=True, help="Shopify product ids to publish."),
            body_field(
                "publication_names",
                repeatable=True,
                help="Sales-channel names to publish to; omit for all.",
            ),
        ),
    ),
    Cmd(
        "unpublish",
        "POST",
        "/agent/stores/{store_id}/listings/unpublish",
        summary="Unpublish listings.",
        body=(
            body_field("product_ids", repeatable=True, help="Shopify product ids to unpublish."),
            body_field(
                "publication_names",
                repeatable=True,
                help="Sales-channel names to unpublish from; omit for all.",
            ),
        ),
    ),
    Cmd(
        "sync-stock",
        "POST",
        "/agent/stores/{store_id}/listings/sync-stock",
        summary="Sync stock to Shopify.",
        body=(
            body_field(
                "items",
                type=dict,
                repeatable=True,
                help="Stock updates. Each: sku (required), quantity (required), and optionally "
                "remote_id, price, compare_at_price.",
            ),
        ),
    ),
    Cmd(
        "list-drafts",
        "GET",
        "/agent/stores/{store_id}/draft-listings",
        summary="List draft listings staged for Shopify.",
        flags=(flag("status", help="Filter by status."),),
    ),
    Cmd(
        "create-drafts",
        "POST",
        "/agent/stores/{store_id}/draft-listings",
        summary="Create draft listings.",
        body=(
            body_field(
                "product_ids",
                required=True,
                repeatable=True,
                help="SellerClaw product ids (UUIDs) to stage as draft listings.",
            ),
            body_field("product_type", help="Override the product type applied to the drafts."),
        ),
    ),
    Cmd(
        "publish-drafts",
        "POST",
        "/agent/stores/{store_id}/draft-listings/publish",
        summary="Publish draft listings.",
        body=(
            body_field(
                "listing_ids",
                required=True,
                repeatable=True,
                help="Draft listing ids (UUIDs) to publish to Shopify.",
            ),
        ),
    ),
)

app = build_group(NAME, "Shopify storefront listings (store_id is the first argument).", SPECS)


def register(parent: typer.Typer) -> None:
    parent.add_typer(app, name=NAME)
