from __future__ import annotations

import typer

from sellerclaw_cli._command_group import Cmd, build_group

NAME = "etsy-store"

SPECS = (
    Cmd(
        "get-info",
        "GET",
        "/agent/stores/{store_id}/info",
        summary="Get the Etsy shop info (name, currency, shop id).",
    ),
    Cmd(
        "list-policies",
        "GET",
        "/agent/stores/{store_id}/policies",
        summary=(
            "List the shop's policies (shipping profiles, return policies). Each row's 'id' is "
            "SellerClaw's, and it is the one every command naming a policy takes — drafts, "
            "set-policies, `channels set-default-policies`. 'is_default' marks the one a listing "
            "uses when it names none."
        ),
    ),
    Cmd(
        "refresh-policies",
        "POST",
        "/agent/stores/{store_id}/policies/refresh",
        summary=(
            "Re-read shipping profiles and return policies from Etsy now — for one the seller just "
            "created there. Otherwise the mirror only refreshes daily. Pin one as the shop's "
            "default with `channels set-default-policies` (the owner's call — ask first)."
        ),
    ),
)

app = build_group(NAME, "Etsy shop admin: shop name, currency and id.", SPECS)


def register(parent: typer.Typer) -> None:
    parent.add_typer(app, name=NAME)
