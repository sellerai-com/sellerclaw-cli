from __future__ import annotations

import typer

from sellerclaw_cli._command_group import Cmd, body_field, build_group

NAME = "sellercart-media"

SPECS = (
    Cmd(
        "list",
        "GET",
        "/agent/sellercart/media",
        summary="Images stored for the storefront: logos, favicons, hero art.",
    ),
    Cmd(
        "add",
        "POST",
        "/agent/sellercart/media/from-url",
        summary=(
            "Copy an image into the storefront by URL and get back a permanent link to use in a block "
            "or in the theme. Copy rather than link straight to somebody else's server: that image "
            "disappears when they tidy up, and the shop breaks with it."
        ),
        body=(
            body_field(
                "url",
                required=True,
                help="Public URL of a PNG, JPEG, WebP, GIF, SVG or ICO image.",
                example="https://example.com/logo.png",
            ),
        ),
    ),
)

app = build_group(NAME, "Images owned by the storefront.", SPECS)


def register(parent: typer.Typer) -> None:
    parent.add_typer(app, name=NAME)
