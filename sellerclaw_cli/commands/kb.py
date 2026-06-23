from __future__ import annotations

import typer

from sellerclaw_cli._command_group import Cmd, build_group, flag

NAME = "kb"

SPECS = (
    Cmd(
        "search",
        "GET",
        "/agent/kb/search",
        summary=(
            "Search the shared knowledge base for grounded, citable facts about selling platforms "
            "(e.g. ad policies, cross-border taxes). Use this before answering factual questions in "
            "covered domains instead of relying on memory; cite the returned source. Returns the "
            "most relevant passages with their score and source metadata. A backend/Ragie outage "
            "exits non-zero (never an empty result) — treat that as a data gap and verify, do not "
            "guess."
        ),
        flags=(
            flag(
                "query",
                required=True,
                help="Natural-language question to search for.",
            ),
            flag(
                "filter",
                help=(
                    "Optional metadata filter as a JSON object, e.g. "
                    '\'{"scope": {"$eq": "ads_policy"}}\'. Filterable keys: scope, title, '
                    "source_url, jurisdiction, version, retrieved_date."
                ),
            ),
        ),
    ),
)

app = build_group(NAME, "Shared knowledge base (read-only search).", SPECS)


def register(parent: typer.Typer) -> None:
    parent.add_typer(app, name=NAME)
