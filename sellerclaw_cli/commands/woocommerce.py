from __future__ import annotations

import typer

from sellerclaw_cli._command_group import Cmd, body_field, build_group

NAME = "woocommerce"

# Raw WooCommerce REST passthrough — the fallback when no curated woocommerce-* command fits. Pins
# to the seller's store; the path is a wc/v3 path like /products/123 or /orders.
SPECS = (
    Cmd(
        "request",
        "POST",
        "/agent/woocommerce/stores/{store_id}/request",
        summary=(
            "Raw WooCommerce REST passthrough. Pins to the seller's store; "
            "path is a wc/v3 path like /products/123 or /orders."
        ),
        body=(
            body_field(
                "path",
                required=True,
                help="WooCommerce REST path under wc/v3, e.g. /products/123.",
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

app = build_group(NAME, "Raw WooCommerce REST passthrough (fallback for uncovered operations).", SPECS)


def register(parent: typer.Typer) -> None:
    parent.add_typer(app, name=NAME)
