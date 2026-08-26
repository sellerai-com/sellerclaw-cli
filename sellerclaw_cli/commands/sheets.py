"""``sellerclaw sheets`` — read and write Google Sheets the seller shared with SellerClaw.

Access is not an OAuth connection: SellerClaw has one service account, and the seller grants it
access in Google's own Share dialog. ``info`` reports the address to share with, so a refusal can
always be turned into a concrete instruction instead of "no access".

Every command takes ``--link`` — the URL copied from the browser (``.../spreadsheets/d/<id>/edit``)
or the bare id. It is a flag rather than a positional because a URL carries slashes and would not
survive being spliced into the request path.
"""

from __future__ import annotations

import typer

from sellerclaw_cli._command_group import Cmd, body_field, build_group, flag

NAME = "sheets"

_LINK_HELP = "Spreadsheet link as copied from the browser, or the bare spreadsheet id."

SPECS = (
    Cmd(
        "info",
        "GET",
        "/agent/sheets/info",
        summary=(
            "Title, tabs and whether SellerClaw may edit the spreadsheet. Run it before a big "
            "export: it also returns service_account_email, the address the seller must share "
            "the sheet with. can_edit is null when the check could not run — that means unknown, "
            "so try the write rather than reporting the sheet as read-only."
        ),
        flags=(flag("link", required=True, help=_LINK_HELP),),
    ),
    Cmd(
        "read",
        "GET",
        "/agent/sheets/values",
        summary=(
            "Read one page of a tab. Row 1 is treated as the header row and comes back as "
            "'columns'. Default page is 100 rows, max 1000 — page with --offset while has_more "
            "is true. Dates arrive as Google's serial numbers, not text."
        ),
        flags=(
            flag("link", required=True, help=_LINK_HELP),
            flag("tab", help="Tab title. Defaults to the tab in the link, else the first one."),
            flag("offset", type=int, default=0, minimum=0, help="Data rows to skip (the header is not a data row)."),
            flag("limit", type=int, default=100, minimum=1, maximum=1000, help="Page size."),
            flag("columns", help="Comma-separated subset of header names, in the order wanted."),
        ),
    ),
    Cmd(
        "write",
        "POST",
        "/agent/sheets/values",
        summary=(
            "Write rows into a tab. mode=replace wipes the whole tab first and mirrors exactly "
            "what is sent; mode=append adds after the last filled row and skips the header when "
            "the tab already has one. A write with no headers and no rows is refused rather than "
            "silently wiping the tab."
        ),
        body=(
            body_field("link", required=True, help=_LINK_HELP),
            body_field("tab", help="Tab title. Defaults to the tab in the link, else the first one."),
            body_field(
                "mode",
                choices=("replace", "append"),
                help="replace = wipe the tab and write; append = add after the last filled row. Default replace.",
            ),
            body_field(
                "headers",
                repeatable=True,
                help="Header row written above the data.",
                example=["sku", "qty"],
            ),
            body_field(
                "rows",
                type=list,
                repeatable=True,
                help="Data rows; each row is an array of cell values.",
                example=[["A1", 5], ["B2", 7]],
            ),
            body_field(
                "create_tab",
                type=bool,
                help="Create the tab named in 'tab' when the spreadsheet has no such tab.",
            ),
        ),
    ),
)

app = build_group(NAME, "Read and write Google Sheets shared with SellerClaw.", SPECS)


def register(parent: typer.Typer) -> None:
    parent.add_typer(app, name=NAME)
