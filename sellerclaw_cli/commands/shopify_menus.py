from __future__ import annotations

import typer

from sellerclaw_cli._command_group import Cmd, body_field, build_group, flag

NAME = "shopify-menus"

SPECS = (
    Cmd(
        "list",
        "GET",
        "/agent/stores/{store_id}/navigation/menus",
        summary="List navigation menus.",
        flags=(flag("limit", type=int, help="Max results."), flag("after", help="Cursor."), flag("query", help="Search query.")),
    ),
    Cmd(
        "create",
        "POST",
        "/agent/stores/{store_id}/navigation/menus",
        summary="Create a navigation menu.",
        body=(
            body_field("title", required=True, help="Menu title."),
            body_field("handle", required=True, help="Menu handle/slug."),
            body_field(
                "items",
                type=dict,
                repeatable=True,
                help="Menu items. Each is an object, e.g. {title, url, type, items}.",
            ),
        ),
    ),
    Cmd(
        "update",
        "PUT",
        "/agent/stores/{store_id}/navigation/menus/{menu_id}",
        summary="Update a navigation menu.",
        body=(
            body_field("title", required=True, help="New menu title."),
            body_field("handle", help="New menu handle/slug."),
            body_field(
                "items",
                type=dict,
                repeatable=True,
                help="Menu items. Each is an object, e.g. {title, url, type, items}.",
            ),
        ),
    ),
    Cmd("delete", "DELETE", "/agent/stores/{store_id}/navigation/menus/{menu_id}", summary="Delete a navigation menu."),
)

app = build_group(NAME, "Shopify online-store navigation menus.", SPECS)


def register(parent: typer.Typer) -> None:
    parent.add_typer(app, name=NAME)
