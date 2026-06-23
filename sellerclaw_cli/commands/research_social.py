from __future__ import annotations

import typer

from sellerclaw_cli._command_group import Cmd, body_field, build_group

NAME = "research-social"

# Each op is a POST to a concrete path matching the command name, backed by its own request model.
SPECS = (
    Cmd(
        "ad-library-search",
        "POST",
        "/agent/research/social/ad-library-search",
        summary="ad library search research.",
        body=(
            body_field("platform", required=True, choices=("facebook", "google"), help="Ad library vendor."),
            body_field("query", required=True, help="Search text (brand, product, keyword)."),
        ),
    ),
    Cmd(
        "ad-library-company-ads",
        "POST",
        "/agent/research/social/ad-library-company-ads",
        summary="ad library company ads research.",
        body=(
            body_field("platform", required=True, choices=("facebook", "google"), help="Ad library vendor."),
            body_field("page_id", help="Facebook page id (Facebook: page_id or company_name required)."),
            body_field("company_name", help="Facebook company/page name (Facebook: page_id or company_name required)."),
            body_field("domain", help="Advertiser domain (Google: domain or advertiser_id required)."),
            body_field("advertiser_id", help="Google advertiser id (Google: domain or advertiser_id required)."),
            body_field("country", help="Country filter (Facebook)."),
            body_field("region", help="Region filter (Google)."),
            body_field("status", help="Ad status filter (Facebook)."),
            body_field("cursor", help="Pagination cursor."),
            body_field("topic", help="Topic filter (Google)."),
            body_field("start_date", help="Start date filter (ISO-8601)."),
            body_field("end_date", help="End date filter (ISO-8601)."),
            body_field("media_type", help="Media type filter (Facebook)."),
            body_field("language", help="Language filter (Facebook)."),
            body_field("trim", type=bool, help="Trim the response payload."),
        ),
    ),
    Cmd(
        "reddit-search",
        "POST",
        "/agent/research/social/reddit-search",
        summary="reddit search research.",
        body=(
            body_field("query", required=True, help="Search text."),
            body_field("sort", help="Sort order (e.g. relevance, hot, top, new)."),
            body_field("timeframe", help="Time window (e.g. day, week, month, year, all)."),
            body_field("after", help="Pagination cursor."),
            body_field("trim", type=bool, help="Trim the response payload."),
        ),
    ),
    Cmd(
        "reddit-comments",
        "POST",
        "/agent/research/social/reddit-comments",
        summary="reddit comments research.",
        body=(
            body_field("url", required=True, help="Reddit post URL."),
            body_field("cursor", help="Pagination cursor."),
            body_field("trim", type=bool, help="Trim the response payload."),
        ),
    ),
    Cmd(
        "reddit-subreddit",
        "POST",
        "/agent/research/social/reddit-subreddit",
        summary="reddit subreddit research.",
        body=(
            body_field("subreddit", required=True, help="Subreddit name (without r/)."),
            body_field("timeframe", help="Time window (e.g. day, week, month, year, all)."),
            body_field("sort", help="Sort order (e.g. hot, top, new)."),
            body_field("after", help="Pagination cursor."),
            body_field("trim", type=bool, help="Trim the response payload."),
        ),
    ),
    Cmd(
        "tiktok-search",
        "POST",
        "/agent/research/social/tiktok-search",
        summary="tiktok search research.",
        body=(
            body_field("query", required=True, help="Search keyword."),
            body_field("date_posted", help="Date-posted filter."),
            body_field("sort_by", help="Sort order."),
            body_field("region", help="Region/country code."),
            body_field("cursor", help="Pagination cursor."),
            body_field("trim", type=bool, help="Trim the response payload."),
        ),
    ),
    Cmd(
        "tiktok-trending",
        "POST",
        "/agent/research/social/tiktok-trending",
        summary="tiktok trending research.",
        body=(
            body_field("region", help="Region/country code."),
            body_field("trim", type=bool, help="Trim the response payload."),
        ),
    ),
    Cmd(
        "tiktok-popular-videos",
        "POST",
        "/agent/research/social/tiktok-popular-videos",
        summary="tiktok popular videos research.",
        body=(
            body_field("period", type=int, help="Window in days, 7 or 30."),
            body_field("page", type=int, help="Page number."),
            body_field("order_by", help="Sort field: like, hot, comment, repost."),
            body_field("country_code", help="Country code filter."),
        ),
    ),
    Cmd(
        "tiktok-popular-hashtags",
        "POST",
        "/agent/research/social/tiktok-popular-hashtags",
        summary="tiktok popular hashtags research.",
        body=(
            body_field("period", type=int, help="Window in days, 7 or 30."),
            body_field("page", type=int, help="Page number."),
            body_field("country_code", help="Country code filter."),
            body_field("new_on_board", type=bool, help="Only newly trending hashtags."),
        ),
    ),
    Cmd(
        "tiktok-shop-search",
        "POST",
        "/agent/research/social/tiktok-shop-search",
        summary="tiktok shop search research.",
        body=(
            body_field("query", required=True, help="Search keyword."),
            body_field("page", type=int, help="Page number."),
            body_field("region", help="Region/country code."),
        ),
    ),
    Cmd(
        "tiktok-shop-product",
        "POST",
        "/agent/research/social/tiktok-shop-product",
        summary="tiktok shop product research.",
        body=(
            body_field("url", required=True, help="TikTok Shop product URL."),
            body_field("get_related_videos", type=bool, help="Also fetch related videos."),
            body_field("region", help="Region/country code."),
        ),
    ),
    Cmd(
        "tiktok-shop-reviews",
        "POST",
        "/agent/research/social/tiktok-shop-reviews",
        summary="tiktok shop reviews research.",
        body=(
            body_field("url", help="TikTok Shop product URL (provide url or product_id)."),
            body_field("product_id", help="TikTok Shop product id (provide url or product_id)."),
            body_field("page", type=int, help="Page number."),
        ),
    ),
    Cmd(
        "youtube-trending-shorts",
        "POST",
        "/agent/research/social/youtube-trending-shorts",
        summary="youtube trending shorts research.",
    ),
)

app = build_group(NAME, "Social / ad-library / Reddit / TikTok / YouTube research.", SPECS)


def register(parent: typer.Typer) -> None:
    parent.add_typer(app, name=NAME)
