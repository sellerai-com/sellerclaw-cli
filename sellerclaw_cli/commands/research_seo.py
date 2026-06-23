from __future__ import annotations

import typer

from sellerclaw_cli._command_group import Cmd, body_field, build_group

NAME = "research-seo"

# Each op is a POST to a concrete path matching the command name, backed by its own request model.
SPECS = (
    Cmd(
        "keyword-ideas",
        "POST",
        "/agent/research/seo/keyword-ideas",
        summary="keyword ideas research.",
        body=(
            body_field("keyword", required=True, help="Seed keyword."),
            body_field("location_name", help="Location name (e.g. 'United States')."),
            body_field("location_code", type=int, help="Numeric location code (overrides name)."),
            body_field("language_name", help="Language name (e.g. 'English')."),
            body_field("language_code", help="Language code (e.g. 'en')."),
            body_field("limit", type=int, help="Max ideas (1-200). Defaults to 50."),
        ),
    ),
    Cmd(
        "keyword-volume",
        "POST",
        "/agent/research/seo/keyword-volume",
        summary="keyword volume research.",
        body=(
            body_field("keywords", repeatable=True, required=True, help="Keywords to look up (at least one)."),
            body_field("location_name", help="Location name (e.g. 'United States')."),
            body_field("location_code", type=int, help="Numeric location code (overrides name)."),
            body_field("language_name", help="Language name (e.g. 'English')."),
            body_field("language_code", help="Language code (e.g. 'en')."),
        ),
    ),
    Cmd(
        "keyword-trends",
        "POST",
        "/agent/research/seo/keyword-trends",
        summary="keyword trends research.",
        body=(
            body_field("keywords", repeatable=True, required=True, help="Keywords to chart (1-5)."),
            body_field("location_name", help="Location name (e.g. 'United States')."),
            body_field("location_code", type=int, help="Numeric location code (overrides name)."),
            body_field("language_name", help="Language name (e.g. 'English')."),
            body_field("language_code", help="Language code (e.g. 'en')."),
            body_field("time_range", help="Preset range. Defaults to past_12_months."),
            body_field("type", help="Trends type: web, news, youtube, images, froogle. Defaults to web."),
            body_field("category_code", type=int, help="Google Trends category code."),
            body_field("date_from", help="Custom range start (ISO-8601)."),
            body_field("date_to", help="Custom range end (ISO-8601)."),
        ),
    ),
    Cmd(
        "autocomplete",
        "POST",
        "/agent/research/seo/autocomplete",
        summary="autocomplete research.",
        body=(
            body_field("keyword", required=True, help="Seed keyword to autocomplete."),
            body_field("location_name", help="Location name (e.g. 'United States')."),
            body_field("location_code", type=int, help="Numeric location code (overrides name)."),
            body_field("language_name", help="Language name (e.g. 'English')."),
            body_field("language_code", help="Language code (e.g. 'en')."),
        ),
    ),
    Cmd(
        "people-also-ask",
        "POST",
        "/agent/research/seo/people-also-ask",
        summary="people also ask research.",
        body=(
            body_field("keyword", required=True, help="Query to fetch related questions for."),
            body_field("location_name", help="Location name (e.g. 'United States')."),
            body_field("location_code", type=int, help="Numeric location code (overrides name)."),
            body_field("language_name", help="Language name (e.g. 'English')."),
            body_field("language_code", help="Language code (e.g. 'en')."),
            body_field("device", help="Device: desktop or mobile. Defaults to desktop."),
            body_field("os", help="Operating system filter."),
        ),
    ),
    Cmd(
        "serp-competitors",
        "POST",
        "/agent/research/seo/serp-competitors",
        summary="serp competitors research.",
        body=(
            body_field("domain", required=True, help="Seed domain to find competitors for."),
            body_field("location_name", help="Location name (e.g. 'United States')."),
            body_field("location_code", type=int, help="Numeric location code (overrides name)."),
            body_field("language_name", help="Language name (e.g. 'English')."),
            body_field("language_code", help="Language code (e.g. 'en')."),
            body_field("limit", type=int, help="Max competitors (1-100). Defaults to 20."),
        ),
    ),
    Cmd(
        "amazon-products",
        "POST",
        "/agent/research/seo/amazon-products",
        summary="amazon products research.",
        body=(
            body_field("keyword", required=True, help="Search keyword for Amazon products."),
            body_field("location_name", help="Location name (e.g. 'United States')."),
            body_field("location_code", type=int, help="Numeric location code (overrides name)."),
            body_field("language_name", help="Language name (e.g. 'English')."),
            body_field("language_code", help="Language code (e.g. 'en')."),
        ),
    ),
    Cmd(
        "amazon-reviews",
        "POST",
        "/agent/research/seo/amazon-reviews",
        summary="amazon reviews research.",
        body=(
            body_field("asin", required=True, help="Amazon ASIN (10 characters)."),
            body_field("location_name", help="Location name (e.g. 'United States')."),
            body_field("location_code", type=int, help="Numeric location code (overrides name)."),
            body_field("language_name", help="Language name (e.g. 'English')."),
            body_field("language_code", help="Language code (e.g. 'en')."),
            body_field("depth", type=int, help="Number of reviews to fetch (1-100). Defaults to 10."),
        ),
    ),
    Cmd(
        "product-search",
        "POST",
        "/agent/research/seo/product-search",
        summary="product search research.",
        body=(
            body_field("keyword", required=True, help="Search keyword for Google Shopping products."),
            body_field("location_name", help="Location name (e.g. 'United States')."),
            body_field("location_code", type=int, help="Numeric location code (overrides name)."),
            body_field("language_name", help="Language name (e.g. 'English')."),
            body_field("language_code", help="Language code (e.g. 'en')."),
        ),
    ),
    Cmd(
        "content-sentiment",
        "POST",
        "/agent/research/seo/content-sentiment",
        summary="content sentiment research.",
        body=(
            body_field("keyword", required=True, help="Keyword to analyze sentiment for."),
            body_field("internal_list_limit", type=int, help="Items to sample (1-1000). Defaults to 10."),
        ),
    ),
)

app = build_group(NAME, "SEO / SERP / marketplace keyword and product research.", SPECS)


def register(parent: typer.Typer) -> None:
    parent.add_typer(app, name=NAME)
