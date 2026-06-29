from __future__ import annotations

import typer

from sellerclaw_cli._command_group import Cmd, body_field, build_group

NAME = "etsy"

# Raw Etsy Open API v3 passthrough — the fallback when no curated etsy-* command fits. Pins to the
# seller's shop; path is relative to /v3/application, e.g. /shops/<shop_id>/listings.
SPECS = (
    Cmd(
        "request",
        "POST",
        "/agent/etsy/stores/{store_id}/request",
        summary=(
            "Raw Etsy Open API v3 passthrough. Pins to the seller's shop; path is relative to "
            "/v3/application, e.g. /shops/<shop_id>/listings or /shops/<shop_id>/receipts."
        ),
        body=(
            body_field(
                "path",
                required=True,
                help="Etsy Open API v3 path (relative to /v3/application), e.g. /shops/123/listings.",
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

app = build_group(NAME, "Raw Etsy Open API passthrough (fallback for uncovered operations).", SPECS)


def register(parent: typer.Typer) -> None:
    parent.add_typer(app, name=NAME)
