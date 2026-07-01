from __future__ import annotations

import typer

from sellerclaw_cli._command_group import Cmd, build_group, flag

NAME = "ebay-promoted"

SPECS = (
    Cmd(
        "campaigns",
        "GET",
        "/agent/ebay/stores/{store_id}/promoted/campaigns",
        summary="List Promoted Listings campaigns (name, status, funding model, bid %).",
    ),
    Cmd(
        "create-report",
        "POST",
        "/agent/ebay/stores/{store_id}/promoted/reports",
        summary=(
            "Start an async Promoted Listings performance report for a trailing window and get a "
            "report task id back. eBay builds ad reports asynchronously, so poll 'get-report' with "
            "the id until it is COMPLETED to read ROAS/ACOS/spend/ad-sales."
        ),
        flags=(
            flag("days", type=int, param="days", minimum=1, maximum=90, default=7, help="Trailing window in days."),
        ),
    ),
    Cmd(
        "get-report",
        "GET",
        "/agent/ebay/stores/{store_id}/promoted/reports/{report_task_id}",
        summary=(
            "Get a performance report task's status; once COMPLETED it also returns the aggregated "
            "ROAS, ACOS, ad spend and ad sales for the window."
        ),
    ),
    Cmd(
        "effectiveness",
        "GET",
        "/agent/ebay/stores/{store_id}/promoted/reports/{report_task_id}/effectiveness",
        summary=(
            "Get a report task's status; once COMPLETED it also returns the full ad-effectiveness "
            "view: store totals (spend/ad-sales/ROAS/ACOS) plus a breakdown by ad tool (Promoted "
            "Listings vs Advanced) and a per-SKU table, each row labelled scale / watch / cut. Use "
            "the same report task id you polled with 'get-report'."
        ),
    ),
)

app = build_group(NAME, "eBay Promoted Listings (read-only): campaigns and performance reports.", SPECS)


def register(parent: typer.Typer) -> None:
    parent.add_typer(app, name=NAME)
