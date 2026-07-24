from __future__ import annotations

import typer

from sellerclaw_cli._command_group import Cmd, body_field, build_group

NAME = "sellercart"

SPECS = (
    Cmd(
        "status",
        "GET",
        "/agent/sellercart",
        summary="Show the seller's SellerCart storefront: address, live/draft state, theme. Returns null when they have none yet.",
    ),
    Cmd(
        "create",
        "POST",
        "/agent/sellercart",
        summary="Create the storefront. One per seller. Also creates its sales channel and its default pages (home, catalog, about, delivery, returns, contacts) as drafts.",
        body=(
            body_field("name", required=True, help="Shop name shown to buyers.", example="Acme Gear"),
            body_field(
                "slug",
                required=True,
                help="Address of the shop: <slug>.sellercart.shop. Lowercase letters, digits, hyphens.",
                example="acme-gear",
            ),
            body_field("currency", help="ISO currency the shop prices in.", example="USD"),
            body_field(
                "markup_percent",
                type=float,
                help=(
                    "Markup percent over catalog cost, e.g. 30 for +30% (0-500). Optional — a shop "
                    "starts with no markup, and products aren't priced until you set one."
                ),
                example=30,
            ),
        ),
    ),
    Cmd(
        "publish",
        "POST",
        "/agent/sellercart/publish",
        summary="Take the storefront live. Refused until the home page is published — its address would 404 otherwise.",
    ),
    Cmd(
        "blocks",
        "GET",
        "/agent/sellercart/blocks",
        summary="List every block a page can be built from, with the schema of each block's props. Read this before writing a page: a block type that is not here cannot be saved.",
    ),
    Cmd(
        "theme",
        "PATCH",
        "/agent/sellercart/theme",
        summary="Set design tokens. Omitted fields keep their current value.",
        body=(
            body_field("primary", help="Brand color, hex.", example="#ff5722"),
            body_field("neutral", help="Neutral color for text and surfaces, hex.", example="#64748b"),
            body_field(
                "font",
                help="Typeface.",
                choices=("Inter", "Manrope", "Lora", "Playfair Display", "Roboto Mono"),
            ),
            body_field("radius", help="Corner rounding.", choices=("none", "sm", "md", "lg", "xl")),
            body_field("logo_url", help="Logo image URL (upload it with `sellercart-media upload`)."),
            body_field("favicon_url", help="Favicon image URL."),
        ),
    ),
)

app = build_group(NAME, "The seller's own storefront: create it, theme it, take it live.", SPECS)


def register(parent: typer.Typer) -> None:
    parent.add_typer(app, name=NAME)
