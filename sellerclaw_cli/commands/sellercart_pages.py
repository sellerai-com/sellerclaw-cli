from __future__ import annotations

import typer

from sellerclaw_cli._command_group import Cmd, body_field, build_group

NAME = "sellercart-pages"

_LAYOUT_HELP = (
    "The page itself: an ordered list of blocks, each an object with a 'type' and that type's props. "
    "Run `sellerclaw sellercart blocks` for the available types and their schemas — an unknown type or "
    "an invented prop is rejected."
)

_LAYOUT_EXAMPLE = [
    {"type": "hero", "headline": "Gear that lasts", "cta_label": "Shop", "cta_href": "/catalog"},
    {"type": "productGrid", "title": "Bestsellers", "source": "all", "limit": 6, "columns": 3},
]

SPECS = (
    Cmd(
        "list",
        "GET",
        "/agent/sellercart/pages",
        summary="List the storefront's pages, drafts included.",
    ),
    Cmd(
        "get",
        "GET",
        "/agent/sellercart/pages/{slug}",
        summary="Get one page with its blocks.",
    ),
    Cmd(
        "create",
        "POST",
        "/agent/sellercart/pages",
        summary="Create a page from a list of blocks.",
        body=(
            body_field("slug", required=True, help="URL of the page, e.g. 'lookbook'.", example="lookbook"),
            body_field("title", required=True, help="Page title.", example="Lookbook"),
            body_field("layout", type=list, help=_LAYOUT_HELP, example=_LAYOUT_EXAMPLE),
            body_field("seo", type=dict, help="Optional: title, description, og_image_url."),
            body_field(
                "published",
                type=bool,
                help="Publish immediately (default true). A draft page is invisible to buyers.",
            ),
        ),
    ),
    Cmd(
        "update",
        "PUT",
        "/agent/sellercart/pages/{slug}",
        summary="Update a page. Sending 'layout' replaces the whole block list — send the blocks you want to keep.",
        body=(
            body_field("title", help="New page title."),
            body_field("layout", type=list, help=_LAYOUT_HELP, example=_LAYOUT_EXAMPLE),
            body_field("seo", type=dict, help="Optional: title, description, og_image_url."),
            body_field("published", type=bool, help="Publish or unpublish the page."),
        ),
    ),
    Cmd(
        "delete",
        "DELETE",
        "/agent/sellercart/pages/{slug}",
        summary="Delete a page. The home page cannot be deleted — it is the shop's front door.",
    ),
)

app = build_group(NAME, "Storefront pages, built from blocks.", SPECS)


def register(parent: typer.Typer) -> None:
    parent.add_typer(app, name=NAME)
