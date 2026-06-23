from __future__ import annotations

import typer

from sellerclaw_cli._command_group import Cmd, build_group

NAME = "amazon-store"

SPECS = (
    Cmd(
        "get-account",
        "GET",
        "/agent/amazon/stores/{store_id}/account",
        summary="Get the Amazon seller account info (seller id, region, marketplaces, currency).",
    ),
    Cmd(
        "list-marketplaces",
        "GET",
        "/agent/amazon/stores/{store_id}/marketplaces",
        summary="List the Amazon marketplaces the seller participates in for this region.",
    ),
)

app = build_group(NAME, "Amazon store admin: account and marketplace participations.", SPECS)


def register(parent: typer.Typer) -> None:
    parent.add_typer(app, name=NAME)
