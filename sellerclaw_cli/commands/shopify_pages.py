from __future__ import annotations

import typer

from sellerclaw_cli._command_group import Cmd, body_field, build_group, flag

NAME = "shopify-pages"

SPECS = (
    Cmd(
        "list",
        "GET",
        "/agent/stores/{store_id}/pages",
        summary="List online-store pages.",
        flags=(flag("limit", type=int, help="Max results."), flag("after", help="Cursor."), flag("query", help="Search query.")),
    ),
    Cmd(
        "create",
        "POST",
        "/agent/stores/{store_id}/pages",
        summary="Create a page.",
        body=(
            body_field("title", required=True, help="Page title."),
            body_field("body", help="Page body HTML."),
            body_field("handle", help="URL handle/slug."),
            body_field("is_published", type=bool, help="Whether the page is published."),
            body_field("template_suffix", help="Theme template suffix to render the page with."),
        ),
    ),
    Cmd(
        "update",
        "PUT",
        "/agent/stores/{store_id}/pages/{page_id}",
        summary="Update a page.",
        body=(
            body_field("title", help="New page title."),
            body_field("body", help="New page body HTML."),
            body_field("handle", help="New URL handle/slug."),
            body_field("is_published", type=bool, help="Whether the page is published."),
            body_field("template_suffix", help="Theme template suffix to render the page with."),
        ),
    ),
    Cmd("delete", "DELETE", "/agent/stores/{store_id}/pages/{page_id}", summary="Delete a page."),
)

app = build_group(NAME, "Shopify online-store pages.", SPECS)


def register(parent: typer.Typer) -> None:
    parent.add_typer(app, name=NAME)
