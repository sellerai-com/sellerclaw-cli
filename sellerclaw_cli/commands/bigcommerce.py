from __future__ import annotations

import typer

from sellerclaw_cli._command_group import Cmd, body_field, build_group

NAME = "bigcommerce"

# Raw BigCommerce REST passthrough — the fallback when no curated bigcommerce-* command fits. Pins
# to the seller's store; path is a v3 catalog path like /catalog/products/123 or a v2 orders path
# like /orders/456 (the backend routes each to the right API version).
SPECS = (
    Cmd(
        "request",
        "POST",
        "/agent/bigcommerce/stores/{store_id}/request",
        summary=(
            "Raw BigCommerce REST passthrough. Pins to the seller's store; path is a v3 catalog "
            "path like /catalog/products/123 or a v2 orders path like /orders/456."
        ),
        body=(
            body_field(
                "path",
                required=True,
                help="BigCommerce REST path, e.g. /catalog/products/123 (v3) or /orders/456 (v2).",
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

app = build_group(NAME, "Raw BigCommerce REST passthrough (fallback for uncovered operations).", SPECS)


def register(parent: typer.Typer) -> None:
    parent.add_typer(app, name=NAME)
