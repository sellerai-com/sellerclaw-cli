from __future__ import annotations

import typer

from sellerclaw_cli._command_group import Cmd, body_field, build_group

NAME = "amazon"

# Raw Amazon SP-API passthrough — the fallback when no curated amazon-* command fits (rare
# operations, fields not surfaced by amazon-listings/amazon-store, or working around a gap). Pins
# to the seller's region endpoint; the path is an SP-API path like /orders/v0/orders.
SPECS = (
    Cmd(
        "request",
        "POST",
        "/agent/amazon/stores/{store_id}/request",
        summary=(
            "Raw Amazon SP-API passthrough. Pins to the seller's region endpoint; "
            "path like /orders/v0/orders or /listings/2021-08-01/items/{sellerId}/{sku}."
        ),
        body=(
            body_field(
                "path",
                required=True,
                help="SP-API path, e.g. /orders/v0/orders/123-1234567-1234567.",
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

app = build_group(NAME, "Raw Amazon SP-API passthrough (fallback for uncovered operations).", SPECS)


def register(parent: typer.Typer) -> None:
    parent.add_typer(app, name=NAME)
