"""``sellerclaw pdf`` — build branded PDF documents from a described block list.

The agent describes *what* the document contains; the server owns *how* it looks (fonts,
colours, cover, running header, page numbers). There is no styling in the payload on purpose:
every PDF the platform produces has to look like the same product.

Images are referenced by ``file_id`` (a file already in the owner's storage — from an
attachment or ``sellerclaw files upload``), never by local path: the renderer runs in the
cloud and cannot see the agent's disk.
"""

from __future__ import annotations

import typer

from sellerclaw_cli._command_group import Cmd, body_field, build_group

NAME = "pdf"

_BLOCKS_EXAMPLE = [
    {"type": "cover", "title": "Weekly review", "subtitle": "Nordic Home Goods", "date": "13 July 2026"},
    {
        "type": "kpi_row",
        "items": [
            {"label": "Revenue", "value": "$10,720", "delta": "+12.4%", "trend": "up"},
            {"label": "Orders", "value": "184", "delta": "-3", "trend": "down"},
        ],
    },
    {"type": "heading", "text": "How the week went", "level": 1},
    {"type": "paragraph", "text": "Revenue grew **12.4%**, driven by Saturday's promotion."},
    {
        "type": "chart",
        "kind": "bar",
        "labels": ["Mon", "Tue", "Wed"],
        "series": [{"name": "This week", "values": [1180, 1420, 980]}],
        "title": "Revenue by day",
        "y_title": "USD",
    },
    {
        "type": "table",
        "headers": ["SKU", "Units"],
        "rows": [["NH-1042", "38"], ["NH-2210", "31"]],
        "align": ["left", "right"],
    },
]

SPECS = (
    Cmd(
        "create",
        "POST",
        "/agent/pdf",
        summary=(
            "Build a branded PDF from a described document and save it to the owner's files. "
            "Returns file_id, download_url and the page count. "
            "Block types (each block is an object with a `type`): "
            "cover{title,subtitle,date} · heading{text,level:1-3} · paragraph{text} · "
            "list{items[],ordered} · kpi_row{items[{label,value,delta,trend:up|down|flat}]} · "
            "table{headers[],rows[][],align[]:left|center|right} · image{file_id,caption,width:0-1} · "
            "chart{kind:bar|line|pie,labels[],series[{name,values[]}],title,y_title} · "
            "callout{text,tone:info|success|warn} · page_break{}. "
            "paragraph/list/callout text may use **bold** and *italic*. "
            "Images take a file_id (attachment or `sellerclaw files upload`), never a local path. "
            "Styling is not part of the body — the document always comes back in the SellerClaw style."
        ),
        body=(
            body_field(
                "filename",
                required=True,
                help="Output filename; '.pdf' is appended when missing.",
                example="weekly-review.pdf",
            ),
            body_field(
                "title",
                required=True,
                help="Document title; also printed as the running header on body pages.",
                example="Weekly review",
            ),
            body_field(
                "subtitle",
                help="Shown under the title on documents that open without a cover block.",
            ),
            body_field(
                "blocks",
                type=dict,
                repeatable=True,
                required=True,
                help="The document, in order. Each block is an object with a `type` (see above).",
                example=_BLOCKS_EXAMPLE,
            ),
        ),
    ),
)

app = build_group(NAME, "Build branded PDF documents (reports, summaries, one-pagers).", SPECS)


def register(parent: typer.Typer) -> None:
    parent.add_typer(app, name=NAME)
