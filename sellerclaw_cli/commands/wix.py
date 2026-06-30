from __future__ import annotations

import typer

from sellerclaw_cli._command_group import Cmd, body_field, build_group

NAME = "wix"

# Raw Wix REST passthrough — the fallback when no curated wix-* command fits. Pins to the seller's
# site; path is a Stores Catalog path (/stores/v3/... or legacy /stores/v1/...), an eCommerce path
# (/ecom/v1/orders/...), or inventory (/stores/v3/inventory-items). The backend pins the site id.
SPECS = (
    Cmd(
        "request",
        "POST",
        "/agent/wix/stores/{store_id}/request",
        summary=(
            "Raw Wix REST passthrough. Pins to the seller's site; path is a Stores Catalog path "
            "(/stores/v3/products/query or legacy /stores/v1/...) or an eCommerce path "
            "(/ecom/v1/orders/search)."
        ),
        body=(
            body_field(
                "path",
                required=True,
                help="Wix REST path, e.g. /stores/v3/products/query or /ecom/v1/orders/search.",
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

app = build_group(NAME, "Raw Wix REST passthrough (fallback for uncovered operations).", SPECS)


def register(parent: typer.Typer) -> None:
    parent.add_typer(app, name=NAME)
