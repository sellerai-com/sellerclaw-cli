from __future__ import annotations

import typer

from sellerclaw_cli._command_group import Cmd, build_group, flag

NAME = "etsy-finances"

# Etsy has no public Ads-management API (unlike eBay Promoted), so finances is the full money
# surface: a read-only summary of the shop payment-account ledger (fees, credits, debits, net).
SPECS = (
    Cmd(
        "summary",
        "GET",
        "/agent/etsy/stores/{store_id}/finances/summary",
        summary=(
            "Summarise the Etsy shop payment-account ledger (fees, credits, debits, net) for a "
            "period. Etsy has no ads-campaign API; ad spend shows here as ledger entries."
        ),
        flags=(
            flag("days", type=int, minimum=1, maximum=365, default=30, help="Look-back window in days."),
        ),
    ),
)

app = build_group(NAME, "Etsy finances: ledger summary (fees, credits, debits, net) for a period.", SPECS)


def register(parent: typer.Typer) -> None:
    parent.add_typer(app, name=NAME)
