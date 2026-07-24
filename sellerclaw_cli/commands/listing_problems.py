from __future__ import annotations

import typer

from sellerclaw_cli._command_group import Cmd, body_field, build_group, flag

NAME = "listing-problems"

SPECS = (
    Cmd(
        "list",
        "GET",
        "/agent/listing-problems",
        summary=(
            "List everything a marketplace has refused or flagged across the seller's stores — "
            "failed publishes, rejected price/stock syncs, withdrawals that didn't land. Errors "
            "first, newest first. Each row's `id` is what `hide` takes. Narrow with the filters."
        ),
        flags=(
            flag("sales_channel_id", type=str, help="Only problems on this store (channel id)."),
            flag("product_id", type=str, help="Only problems about this product, across every store."),
            flag(
                "severity",
                choices=("error", "warning"),
                help="Filter by severity: 'error' (it didn't happen) or 'warning' (it did, with a note).",
            ),
            flag(
                "action",
                choices=("publish", "sync", "withdraw"),
                help="Filter by the attempt that hit it: 'publish', 'sync' (price & stock) or 'withdraw'.",
            ),
        ),
    ),
    Cmd(
        "list-hidden",
        "GET",
        "/agent/listing-problems/hidden",
        summary=(
            "List problems the seller has hidden but that are still open (the Hidden tab). A hidden "
            "problem that fixed itself is gone from here. Use `unhide` to bring one back. Same "
            "filters as `list`."
        ),
        flags=(
            flag("sales_channel_id", type=str, help="Only hidden problems on this store (channel id)."),
            flag("product_id", type=str, help="Only hidden problems about this product."),
            flag("severity", choices=("error", "warning"), help="Filter by severity: 'error' or 'warning'."),
            flag(
                "action",
                choices=("publish", "sync", "withdraw"),
                help="Filter by attempt: 'publish', 'sync' or 'withdraw'.",
            ),
        ),
    ),
    Cmd(
        "hide",
        "POST",
        "/agent/listing-problems/hide",
        summary=(
            "Hide problems so they drop off the main list and the counters, onto the Hidden tab. Pass "
            "one or more problem ids (from `list`). A folded problem in the UI covers many rows — pass "
            "all of that problem's ids to hide it whole. Hiding a problem that keeps recurring leaves "
            "it hidden; only `unhide` brings it back."
        ),
        body=(
            body_field(
                "problem_ids",
                type=str,
                repeatable=True,
                required=True,
                help="Problem id(s) to hide, from `list` (repeat -b problem_ids=<id> for several).",
            ),
        ),
    ),
    Cmd(
        "unhide",
        "POST",
        "/agent/listing-problems/unhide",
        summary="Restore hidden problems back onto the main list. Pass the id(s) from `list-hidden`.",
        body=(
            body_field(
                "problem_ids",
                type=str,
                repeatable=True,
                required=True,
                help="Problem id(s) to restore, from `list-hidden`.",
            ),
        ),
    ),
)

app = build_group(
    NAME,
    "Marketplace problems on the seller's listings — what a channel refused or flagged — plus the "
    "power to hide the ones you've dealt with and restore them later.",
    SPECS,
)


def register(parent: typer.Typer) -> None:
    parent.add_typer(app, name=NAME)
