from __future__ import annotations

import typer

from sellerclaw_cli._command_group import Cmd, body_field, build_group

NAME = "walmart"

# Raw Walmart Marketplace REST passthrough — the fallback when no curated walmart-* command fits.
# Pins to the seller's account; path is a Walmart REST path like /v3/items or /v3/feeds/{feedId}.
SPECS = (
    Cmd(
        "request",
        "POST",
        "/agent/walmart/stores/{store_id}/request",
        summary=(
            "Raw Walmart Marketplace REST passthrough. Pins to the seller's account; path is a "
            "Walmart REST path like /v3/items or /v3/feeds/{feedId}."
        ),
        body=(
            body_field(
                "path",
                required=True,
                help="Walmart REST path, e.g. /v3/items or /v3/feeds/{feedId}.",
            ),
            body_field(
                "method",
                choices=("GET", "POST", "PUT", "PATCH", "DELETE"),
                help="HTTP method [default GET].",
            ),
            body_field("params", type=dict, help="Query-string params as a flat string->string object."),
            body_field("body", type=dict, help="JSON request body (for POST/PUT/PATCH)."),
        ),
    ),
)

app = build_group(NAME, "Raw Walmart REST passthrough (fallback for uncovered operations).", SPECS)


def register(parent: typer.Typer) -> None:
    parent.add_typer(app, name=NAME)
