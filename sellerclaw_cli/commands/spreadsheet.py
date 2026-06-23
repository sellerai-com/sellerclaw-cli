"""``sellerclaw spreadsheet`` — read, create, and edit tabular files owned by the user.

Files are identified by ``file_id`` (a UserFile already living in S3). When the agent has
only a local path, ``sellerclaw files upload`` mints the file_id first; the spreadsheet
commands then operate by id.

The backend enforces strict size and row limits per call; ``read`` is paginated and ``--full``
is rejected for anything larger than a small file. Errors come back as the standard CLI
error envelope with a stable ``code`` field documented in the backend.
"""

from __future__ import annotations

import typer

from sellerclaw_cli._command_group import Cmd, body_field, build_group, flag

NAME = "spreadsheet"

SPECS = (
    Cmd(
        "info",
        "GET",
        "/agent/spreadsheet/{file_id}",
        summary="Workbook metadata (sheets, dimensions, dialect for CSV) — cheap, no row data.",
    ),
    Cmd(
        "read",
        "GET",
        "/agent/spreadsheet/{file_id}/rows",
        summary=(
            "Read rows with offset/limit pagination. Default limit is 100 rows; max is 1000. "
            "Use --full only after `info` confirms the file is small."
        ),
        flags=(
            flag("sheet", help="Sheet name (xlsx). Defaults to the first sheet."),
            flag("offset", type=int, help="Row offset (0-based, header excluded).", default=0),
            flag(
                "limit",
                type=int,
                help="Page size. Default 100, max 1000.",
                minimum=1,
                maximum=1000,
            ),
            flag(
                "columns",
                help="Comma-separated subset of column names to return (case-insensitive).",
            ),
            flag(
                "full",
                type=bool,
                help="Read everything in one call. Only allowed for small files (≤5 MB and ≤5000 rows).",
            ),
        ),
    ),
    Cmd(
        "create",
        "POST",
        "/agent/spreadsheet",
        summary=(
            "Create a new xlsx or csv from JSON rows. Body: "
            '{"filename": "report.xlsx", "rows": [["a",1],["b",2]], "headers": ["x","y"], '
            '"sheet": "Sheet1", "format": "xlsx"}.'
        ),
        body=(
            body_field("filename", required=True, help="Output filename, e.g. report.xlsx."),
            body_field(
                "rows",
                type=list,
                repeatable=True,
                required=True,
                help="Data rows; each row is an array of cell values.",
                example=[["a", 1], ["b", 2]],
            ),
            body_field("headers", repeatable=True, help="Optional column header names."),
            body_field("sheet", help="Sheet name. Defaults to Sheet1."),
            body_field(
                "format",
                choices=("xlsx", "xlsm", "xls", "csv"),
                help="Output format. Inferred from the filename extension when omitted.",
            ),
        ),
    ),
    Cmd(
        "edit",
        "POST",
        "/agent/spreadsheet/{file_id}/edits",
        summary=(
            "Modify an xlsx/xlsm file. Body picks the op: "
            '{"op":"append-rows","rows":[["x","y"]]} | '
            '{"op":"insert-rows","before_row":5,"rows":[...]} | '
            '{"op":"delete-rows","from_row":5,"count":3} | '
            '{"op":"set-cells","patch":{"A5":"foo","B6":123}}. Returns a new file_id.'
        ),
        body_freeform=True,
    ),
)

app = build_group(NAME, "Read, create, and edit spreadsheets (xlsx / xlsm / xls / csv).", SPECS)


def register(parent: typer.Typer) -> None:
    parent.add_typer(app, name=NAME)
