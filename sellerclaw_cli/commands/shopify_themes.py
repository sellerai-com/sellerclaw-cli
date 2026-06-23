from __future__ import annotations

import typer

from sellerclaw_cli._command_group import Cmd, body_field, build_group, flag

NAME = "shopify-themes"

SPECS = (
    Cmd(
        "list",
        "GET",
        "/agent/stores/{store_id}/themes",
        summary="List themes.",
        flags=(flag("limit", type=int, help="Max results."), flag("after", help="Cursor.")),
    ),
    Cmd("get", "GET", "/agent/stores/{store_id}/themes/{theme_id}", summary="Get one theme."),
    Cmd(
        "create",
        "POST",
        "/agent/stores/{store_id}/themes",
        summary="Create a theme.",
        body=(
            body_field("source", required=True, help="URL of the theme ZIP to import."),
            body_field("name", help="Display name for the new theme."),
            body_field("role", help="Theme role, e.g. unpublished or main."),
        ),
    ),
    Cmd("delete", "DELETE", "/agent/stores/{store_id}/themes/{theme_id}", summary="Delete a theme."),
    Cmd(
        "get-files",
        "GET",
        "/agent/stores/{store_id}/themes/{theme_id}/files",
        summary="Read theme files.",
        flags=(flag("limit", type=int, help="Max results."), flag("after", help="Cursor.")),
    ),
    Cmd(
        "upsert-files",
        "PUT",
        "/agent/stores/{store_id}/themes/{theme_id}/files",
        summary="Create or update theme files.",
        body=(
            body_field(
                "files",
                type=dict,
                repeatable=True,
                required=True,
                help="Files to write (max 50). Each: filename and body {type, value}.",
            ),
        ),
    ),
    Cmd(
        "delete-files",
        "DELETE",
        "/agent/stores/{store_id}/themes/{theme_id}/files",
        summary="Delete theme files.",
        body=(
            body_field(
                "filenames",
                repeatable=True,
                required=True,
                help="Theme file paths to delete (max 50).",
            ),
        ),
    ),
    Cmd("publish", "POST", "/agent/stores/{store_id}/themes/{theme_id}/publish", summary="Publish a theme."),
)

app = build_group(NAME, "Shopify online-store themes and theme files.", SPECS)


def register(parent: typer.Typer) -> None:
    parent.add_typer(app, name=NAME)
