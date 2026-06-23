from __future__ import annotations

import typer

from sellerclaw_cli._command_group import Cmd, build_group, flag

NAME = "web"

SPECS = (
    Cmd(
        "scrape",
        "GET",
        "/agent/web/scrape",
        summary=(
            "Fetch one web page and return its main content as clean markdown, billed to the "
            "user's credits. Use this when no first-party integration/API covers the data and a "
            "web search alone is not enough: it is cheaper and faster than driving a browser. "
            "Priority for gathering information: integration API -> web search -> web scrape -> "
            "browser. A missing key or failed fetch exits non-zero (never an empty result) — treat "
            "that as a data gap and verify, do not guess."
        ),
        flags=(
            flag("url", required=True, help="Absolute URL of the page to scrape."),
            flag(
                "max_chars",
                type=int,
                minimum=1,
                help="Optionally truncate the returned content to this many characters.",
            ),
        ),
    ),
)

app = build_group(NAME, "Web tools (single-page scrape).", SPECS)


def register(parent: typer.Typer) -> None:
    parent.add_typer(app, name=NAME)
