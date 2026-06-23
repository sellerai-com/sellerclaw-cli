from __future__ import annotations

import typer

from sellerclaw_cli._command_group import Cmd, build_group, flag

NAME = "research-trends"

_TIMEFRAME = flag("timeframe", help="Time window (e.g. 'today 12-m').")
_GEO = flag("geo", help="Geo code (e.g. 'US').")
_CATEGORY = flag("category", help="Category id.")

SPECS = (
    Cmd(
        "interest-over-time",
        "GET",
        "/agent/research/trends/interest-over-time",
        summary="Search interest over time for keywords.",
        flags=(flag("keywords", required=True, help="Comma-separated keywords."), _TIMEFRAME, _GEO, _CATEGORY),
    ),
    Cmd(
        "interest-by-region",
        "GET",
        "/agent/research/trends/interest-by-region",
        summary="Search interest by region for a keyword.",
        flags=(
            flag("keyword", required=True, help="Keyword."),
            _TIMEFRAME,
            _GEO,
            flag("resolution", help="Region resolution (COUNTRY, REGION, ...)."),
        ),
    ),
    Cmd(
        "related-queries",
        "GET",
        "/agent/research/trends/related-queries",
        summary="Related queries for a keyword.",
        flags=(flag("keyword", required=True, help="Keyword."), _TIMEFRAME, _GEO, _CATEGORY),
    ),
    Cmd(
        "related-topics",
        "GET",
        "/agent/research/trends/related-topics",
        summary="Related topics for a keyword.",
        flags=(flag("keyword", required=True, help="Keyword."), _TIMEFRAME, _GEO, _CATEGORY),
    ),
    Cmd(
        "trending",
        "GET",
        "/agent/research/trends/trending",
        summary="Currently trending searches.",
        flags=(_GEO, flag("hours", type=int, help="Lookback window in hours."), _CATEGORY),
    ),
    Cmd(
        "compare",
        "GET",
        "/agent/research/trends/compare",
        summary="Compare search interest across keywords.",
        flags=(flag("keywords", required=True, help="Comma-separated keywords."), _TIMEFRAME, _GEO),
    ),
)

app = build_group(NAME, "Google Trends: interest, related queries/topics, comparisons.", SPECS)


def register(parent: typer.Typer) -> None:
    parent.add_typer(app, name=NAME)
