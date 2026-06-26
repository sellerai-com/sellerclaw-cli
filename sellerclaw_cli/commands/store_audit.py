from __future__ import annotations

import typer

from sellerclaw_cli._command_group import Cmd, body_field, build_group

NAME = "store-audit"

# Rate a storefront's SEO (PageSpeed + On-Page) and GEO (AI visibility). Each op POSTs to a
# concrete path matching the command name, backed by its own request model.
SPECS = (
    Cmd(
        "pagespeed",
        "POST",
        "/agent/store-audit/pagespeed",
        summary="PageSpeed Insights scores + Core Web Vitals for a storefront URL (free).",
        body=(
            body_field("url", required=True, help="Absolute storefront/page URL to audit.", example="https://shop.example"),
            body_field("strategy", choices=("mobile", "desktop"), help="Device strategy. Defaults to mobile."),
        ),
    ),
    Cmd(
        "onpage",
        "POST",
        "/agent/store-audit/onpage",
        summary="On-page/technical SEO audit of a storefront URL (meta, links, score, checks).",
        body=(
            body_field("url", required=True, help="Absolute storefront/page URL to audit.", example="https://shop.example"),
            body_field("enable_javascript", type=bool, help="Render JS before auditing (Shopify needs it). Defaults to true."),
        ),
    ),
    Cmd(
        "ai-answers",
        "POST",
        "/agent/store-audit/ai-answers",
        summary="GEO: ask AI engines buyer-style prompts and see if/how the store surfaces.",
        body=(
            body_field(
                "prompts",
                repeatable=True,
                required=True,
                help="Buyer-style questions to ask the AI engines (1-5).",
                example=["best dog leash stores", "where to buy a durable dog leash"],
            ),
            body_field(
                "engines",
                repeatable=True,
                choices=("chatgpt", "claude", "gemini", "perplexity"),
                help="AI engines to query. Defaults to chatgpt + perplexity.",
            ),
            body_field("location_code", type=int, help="Numeric location code (e.g. 2840 = United States)."),
            body_field("language_code", help="Language code (e.g. 'en')."),
        ),
    ),
    Cmd(
        "ai-mentions",
        "POST",
        "/agent/store-audit/ai-mentions",
        summary="GEO: how a keyword/niche, brand, or domain is mentioned/cited across AI engines.",
        body=(
            body_field(
                "target",
                required=True,
                help="Keyword/niche, brand, or domain to look up. Query by CATEGORY for small stores.",
                example="dog leash",
            ),
            body_field("location_code", type=int, help="Numeric location code (e.g. 2840 = United States)."),
            body_field("language_code", help="Language code (e.g. 'en')."),
        ),
    ),
)

app = build_group(NAME, "Rate a storefront's SEO (PageSpeed + On-Page) and GEO / AI visibility.", SPECS)


def register(parent: typer.Typer) -> None:
    parent.add_typer(app, name=NAME)
