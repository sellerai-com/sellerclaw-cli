from __future__ import annotations

import typer

from sellerclaw_cli._command_group import Cmd, body_field, build_group, flag

NAME = "catalog-file"

SPECS = (
    Cmd(
        "template",
        "GET",
        "/agent/products/catalog-file/template",
        summary=(
            "Get the blank catalog file to send the owner, plus the text explaining the columns. "
            "Hand them both; a file filled in to this shape imports without a mapping."
        ),
        flags=(
            flag(
                "fmt",
                help="xlsx (default) or csv.",
                choices=("xlsx", "csv"),
            ),
        ),
    ),
    Cmd(
        "check",
        "POST",
        "/agent/products/catalog-file/check",
        summary=(
            "Can this file be read as a catalog? Run it first on a file in the owner's own "
            "wording: a refusal quotes the heading row and three rows back, which is what you "
            "write the columns mapping from. Writes nothing at all."
        ),
        body=(
            body_field("file_id", required=True, help="Uploaded file to read."),
            body_field(
                "columns",
                type=dict,
                help=(
                    'File heading -> template column, e.g. {"Артикул":"SKU","Наименование":"Name"}. '
                    "Not remembered anywhere — send it again with preview and apply."
                ),
                example={"Артикул": "SKU", "Наименование": "Name", "Остаток": "Quantity"},
            ),
        ),
    ),
    Cmd(
        "preview",
        "POST",
        "/agent/products/catalog-file/preview",
        summary=(
            "What this file would do, doing none of it: which products it would create, which it "
            "would change and how, which rows could not be read (with row numbers), which groups "
            "were refused and why, and which catalog products it never mentioned. Show this "
            "before applying."
        ),
        body=(
            body_field("file_id", required=True, help="Uploaded file to read."),
            body_field("columns", type=dict, help="File heading -> template column, if needed."),
        ),
    ),
    Cmd(
        "apply",
        "POST",
        "/agent/products/catalog-file/apply",
        summary=(
            "Create the products the file adds and change the ones it changes. Nothing is deleted "
            "and nothing is taken out of sale: a product the file did not mention comes back "
            "under plan.untouched, and a column it left blank keeps what it had. Check "
            "refused_at_write — those groups did not land."
        ),
        body=(
            body_field("file_id", required=True, help="Uploaded file to read."),
            body_field("columns", type=dict, help="File heading -> template column, if needed."),
        ),
    ),
)

app = build_group(
    NAME,
    "Build or correct the catalog from a spreadsheet: hand out the template, read it back, apply it.",
    SPECS,
)


def register(parent: typer.Typer) -> None:
    parent.add_typer(app, name=NAME)
