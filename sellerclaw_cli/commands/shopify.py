from __future__ import annotations

import typer

from sellerclaw_cli._command_group import Cmd, build_group

NAME = "shopify"

# Raw Shopify Admin GraphQL passthrough — the fallback when no curated command fits
# (rare operations, fields not surfaced by shopify-listings, or working around a gap).
# Body is {"query": "<document>", "variables": {...}}; ids are GraphQL GIDs.
SPECS = (
    Cmd(
        "graphql",
        "POST",
        "/agent/stores/{store_id}/graphql",
        summary="Execute a raw Shopify Admin GraphQL query/mutation.",
        body_freeform=True,
    ),
)

app = build_group(NAME, "Raw Shopify Admin GraphQL passthrough (fallback for uncovered operations).", SPECS)


def register(parent: typer.Typer) -> None:
    parent.add_typer(app, name=NAME)
