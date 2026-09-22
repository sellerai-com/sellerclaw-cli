from __future__ import annotations

import typer

from sellerclaw_cli._command_group import Cmd, body_field, build_group

NAME = "sellercart-menus"

#: The same sentence for every write that changes what buyers see — see `sellercart changes`.
_NOTE_HELP = (
    "One sentence for the owner about why, in their language — shown beside this change while it "
    "waits in the draft of a live shop, and kept with the version it is published in. Ignored "
    "before the shop first opens."
)

SPECS = (
    Cmd(
        "list",
        "GET",
        "/agent/sellercart/menus",
        summary="The storefront's header and footer menus.",
    ),
    Cmd(
        "update",
        "PUT",
        "/agent/sellercart/menus/{location}",
        summary=(
            "Replace the menu at this location (header or footer). Sending items replaces the whole "
            "list, so include every link you want to keep."
        ),
        body=(
            body_field(
                "items",
                type=list,
                required=True,
                help="Ordered links: objects with 'label' and 'href'.",
                example=[
                    {"label": "Catalog", "href": "/catalog"},
                    {"label": "Delivery", "href": "/delivery"},
                ],
            ),
            body_field("note", help=_NOTE_HELP, example="Led with free delivery, as you asked"),
        ),
    ),
)

app = build_group(NAME, "Storefront navigation.", SPECS)


def register(parent: typer.Typer) -> None:
    parent.add_typer(app, name=NAME)
