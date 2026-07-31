from __future__ import annotations

import typer

from sellerclaw_cli._command_group import Cmd, body_field, build_group, flag

NAME = "price-list"

SPECS = (
    Cmd(
        "template",
        "GET",
        "/agent/suppliers/price-list/template",
        summary=(
            "Get the blank price-list file to send the owner, plus the text explaining the "
            "columns. Hand them both; a file filled in to this shape imports without a mapping."
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
        "/agent/suppliers/price-list/check",
        summary=(
            "Can this file be read as a price list? Run it first on a file in the supplier's own "
            "wording: a refusal quotes the heading row and three rows back, which is what you "
            "write the --columns mapping from. Nothing is written except a mapping that worked."
        ),
        body=(
            body_field(
                "supplier_id",
                required=True,
                help="Which supplier the file is from (sellerclaw id, from suppliers list-accounts).",
            ),
            body_field("file_id", required=True, help="Uploaded file to read."),
            body_field(
                "columns",
                type=dict,
                help=(
                    "File heading -> template column, e.g. {\"Артикул\":\"SKU\",\"Цена\":\"Cost\"}. "
                    "Remembered on the supplier once a file it was used on passes, so later files "
                    "in the same format need it only if the supplier changes their export."
                ),
                example={"Артикул": "SKU", "Цена": "Cost", "Остаток": "Quantity"},
            ),
        ),
    ),
    Cmd(
        "preview",
        "POST",
        "/agent/suppliers/price-list/preview",
        summary=(
            "What this file would change, changing nothing: which positions move and by how much, "
            "which rows match nothing, which rows could not be read (with row numbers), and which "
            "positions the file never mentioned. Show this before applying."
        ),
        body=(
            body_field("supplier_id", required=True, help="Supplier the file is from."),
            body_field("file_id", required=True, help="Uploaded file to read."),
            body_field("columns", type=dict, help="File heading -> template column, if needed."),
        ),
    ),
    Cmd(
        "apply",
        "POST",
        "/agent/suppliers/price-list/apply",
        summary=(
            "Store the file as this supplier's price list and apply what it changes to the "
            "catalog. Nothing is taken out of sale: positions the file did not mention come back "
            "under plan.untouched, and acting on that list is a separate, explicit request."
        ),
        body=(
            body_field("supplier_id", required=True, help="Supplier the file is from."),
            body_field("file_id", required=True, help="Uploaded file to read."),
            body_field("columns", type=dict, help="File heading -> template column, if needed."),
        ),
    ),
    Cmd(
        "out-of-sale",
        "POST",
        "/agent/suppliers/price-list/out-of-sale",
        summary=(
            "Set the stock of the named positions to zero, on the owner's word. The product stays "
            "in the catalog. Only run this when the owner asked for these positions — an upload "
            "never takes anything off sale by itself."
        ),
        body=(
            body_field("supplier_id", required=True, help="Whose positions these are."),
            body_field(
                "codes",
                type=str,
                repeatable=True,
                required=True,
                help="SKUs or barcodes of the positions to zero.",
            ),
        ),
    ),
    Cmd(
        "create-products",
        "POST",
        "/agent/suppliers/price-list/create-products",
        summary=(
            "Turn stored price-list lines that match nothing in the catalog into products. They "
            "are drafts: the line's codes, cost and stock, no description and no photos. Check "
            "`remaining` — a batch is capped, and the rest wait for the next call."
        ),
        body=(
            body_field("supplier_id", required=True, help="Whose price list to source from."),
            body_field(
                "codes",
                type=str,
                repeatable=True,
                help="Only these SKUs/barcodes. Omit to take every line with no product yet.",
            ),
            body_field("limit", type=int, help="Cap this batch (default 200)."),
        ),
    ),
)

app = build_group(
    NAME,
    "Price lists from suppliers with no API: hand out the template, read the file back, apply it.",
    SPECS,
)


def register(parent: typer.Typer) -> None:
    parent.add_typer(app, name=NAME)
