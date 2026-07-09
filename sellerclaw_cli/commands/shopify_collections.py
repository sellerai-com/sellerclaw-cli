from __future__ import annotations

import typer

from sellerclaw_cli._command_group import Cmd, body_field, build_group, flag

NAME = "shopify-collections"

_PAGING = (
    flag("limit", type=int, help="Max results."),
    flag("after", help="Pagination cursor."),
    flag("query", help="Search query."),
)

SPECS = (
    Cmd("list", "GET", "/agent/stores/{store_id}/collections", summary="List collections.", flags=_PAGING),
    Cmd(
        "create",
        "POST",
        "/agent/stores/{store_id}/collections",
        summary="Create a collection.",
        body=(
            body_field("title", required=True, help="Collection title."),
        ),
        body_strict=False,
    ),
    Cmd(
        "update",
        "PUT",
        "/agent/stores/{store_id}/collections/{collection_id}",
        summary="Update a collection.",
        body_freeform=True,
    ),
    Cmd("delete", "DELETE", "/agent/stores/{store_id}/collections/{collection_id}", summary="Delete a collection."),
    Cmd(
        "add-products",
        "POST",
        "/agent/stores/{store_id}/collections/{collection_id}/products",
        summary="Add products to a collection.",
        body=(
            body_field(
                "product_ids",
                required=True,
                repeatable=True,
                help="Shopify product ids to add to the collection.",
            ),
        ),
    ),
    Cmd(
        "remove-products",
        "POST",
        "/agent/stores/{store_id}/collections/{collection_id}/products/remove",
        summary="Remove products from a collection.",
        body=(
            body_field(
                "product_ids",
                required=True,
                repeatable=True,
                help="Shopify product ids to remove from the collection.",
            ),
        ),
    ),
    Cmd(
        "publish",
        "POST",
        "/agent/stores/{store_id}/collections/{collection_id}/publish",
        summary=(
            "Publish a collection to the Online Store — fixes a /collections/<handle> page that "
            "404s because the collection exists but isn't published. No raw GraphQL needed."
        ),
        body=(
            body_field(
                "publication_names",
                repeatable=True,
                help="Publications to publish to; omit for the Online Store. List them with "
                "`sellerclaw shopify-listings publications <store_id>`.",
            ),
        ),
        body_strict=False,
    ),
    Cmd(
        "unpublish",
        "POST",
        "/agent/stores/{store_id}/collections/{collection_id}/unpublish",
        summary="Unpublish a collection from the Online Store (hide its page).",
        body=(
            body_field(
                "publication_names",
                repeatable=True,
                help="Publications to unpublish from; omit for the Online Store.",
            ),
        ),
        body_strict=False,
    ),
)

app = build_group(NAME, "Shopify online-store collections.", SPECS)


def register(parent: typer.Typer) -> None:
    parent.add_typer(app, name=NAME)
