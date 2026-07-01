from __future__ import annotations

import typer

from sellerclaw_cli._command_group import Cmd, build_group, flag

NAME = "ebay-shipping"

# eBay delivery / shipping report. eBay gives the tracking number, carrier and its own estimated
# delivery date, but NOT carrier scan movement — so there is no real-time "delivered" signal.
# "overdue" is therefore a best-effort proxy (past eBay's estimate, or stuck N+ days in transit).
SPECS = (
    Cmd(
        "report",
        "GET",
        "/agent/ebay/stores/{store_id}/shipping/report",
        summary=(
            "Delivery overview for a store: orders split into awaiting-shipment / in-transit / "
            "overdue, each with tracking number, carrier and a ready public tracking URL, plus the "
            "carrier mix and destination country. 'overdue' = eBay's estimated delivery date has "
            "passed (or, when eBay gave no estimate, in transit at least --stuck-after-days). eBay "
            "reports no carrier scans, so this is a best-effort 'needs a look' flag, not a confirmed "
            "failure. Most overdue first; use it to chase stuck parcels in the morning ops check."
        ),
        flags=(
            flag(
                "window_days",
                type=int,
                minimum=1,
                maximum=90,
                default=30,
                help="Trailing order-creation window in days to scan (default 30).",
            ),
            flag(
                "stuck_after_days",
                type=int,
                minimum=1,
                maximum=60,
                default=10,
                help="Days in transit before a shipment with no eBay estimate is flagged overdue (default 10).",
            ),
        ),
    ),
    Cmd(
        "tracking",
        "GET",
        "/agent/ebay/stores/{store_id}/orders/{order_id}/tracking",
        summary=(
            "Carrier + tracking number (with a ready public tracking URL) for one order's registered "
            "shipments. Use it to answer 'where is order X'."
        ),
    ),
)

app = build_group(
    NAME,
    "eBay delivery: what's in transit, what's overdue, carrier tracking links (store_id first).",
    SPECS,
)


def register(parent: typer.Typer) -> None:
    parent.add_typer(app, name=NAME)
