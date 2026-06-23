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
)

app = build_group(NAME, "Shopify online-store collections.", SPECS)


def register(parent: typer.Typer) -> None:
    parent.add_typer(app, name=NAME)
