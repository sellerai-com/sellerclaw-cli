from __future__ import annotations

import typer

from sellerclaw_cli._command_group import Cmd, LONG_TIMEOUT_SECONDS, body_field, build_group

NAME = "sellercart-media"

SPECS = (
    Cmd(
        "list",
        "GET",
        "/agent/sellercart/media",
        summary="Files stored for the storefront: logos, favicons, hero art, and the videos its pages play.",
    ),
    Cmd(
        "add",
        "POST",
        "/agent/sellercart/media/from-url",
        summary=(
            "Copy an image — or a video for a page, up to 20 MB — into the storefront by URL and get "
            "back a permanent link to use in a block or in the theme. A page plays only videos copied "
            "in this way. Copy rather than link straight to somebody else's server: that file "
            "disappears when they tidy up, and the shop breaks with it."
        ),
        body=(
            body_field(
                "url",
                required=True,
                help="Public URL of a PNG, JPEG, WebP, GIF or ICO image, or of an MP4, MOV or WEBM video.",
                example="https://example.com/logo.png",
            ),
        ),
        # A video is fetched whole from wherever it lives and stored before the answer comes back.
        timeout=LONG_TIMEOUT_SECONDS,
    ),
    Cmd(
        "delete",
        "DELETE",
        "/agent/sellercart/media/{media_id}",
        summary=(
            "Drop an image from the shop's library. Nothing checks whether a page still points at it: "
            "a block holding the deleted path renders a hole, so look at the pages first, or replace "
            "the image instead of deleting it."
        ),
    ),
)

app = build_group(NAME, "Images and videos owned by the storefront.", SPECS)


def register(parent: typer.Typer) -> None:
    parent.add_typer(app, name=NAME)
