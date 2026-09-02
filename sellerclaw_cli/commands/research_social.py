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
            body_field(
                "platform",
                required=True,
                choices=("facebook", "google", "tiktok", "linkedin"),
                help=(
                    "Ad library vendor. TikTok reads Creative Center Top Ads, which is often down — "
                    "an empty result there means 'unknown', not 'no ads'."
                ),
            ),
            body_field("query", required=True, help="Search text (brand, product, keyword)."),
            body_field("region", help="TikTok/Google: country code, e.g. US."),
            body_field("period", type=int, help="TikTok: window in days — 7, 30 or 180."),
            body_field("order_by", help="TikTok: for_you, impression, play_2s_rate, cvr, ctr, like."),
            body_field("industry", help="TikTok: industry filter."),
            body_field("objective", help="TikTok: campaign objective, e.g. product_sales."),
            body_field("ad_format", choices=("spark_ads", "non_spark_ads"), help="TikTok: ad format."),
            body_field("ad_language", help="TikTok: ad language code, e.g. en."),
            body_field("countries", help="LinkedIn: comma-separated country codes, e.g. US,CA."),
            body_field("start_date", help="LinkedIn: YYYY-MM-DD."),
            body_field("end_date", help="LinkedIn: YYYY-MM-DD."),
            body_field("cursor", help="Pagination cursor from the previous response."),
            body_field("limit", type=int, help="TikTok: results per page, max 50."),
        ),
    ),
    Cmd(
        "ad-library-company-ads",
        "POST",
        "/agent/research/social/ad-library-company-ads",
        summary="ad library company ads research. Not available for TikTok — use ad-library-search there.",
        body=(
            body_field(
                "platform",
                required=True,
                choices=("facebook", "google", "linkedin"),
                help="Ad library vendor. TikTok has no ads-by-company view.",
            ),
            body_field("page_id", help="Facebook page id (Facebook: page_id or company_name required)."),
            body_field(
                "company_name",
                help="Company/page name (Facebook: page_id or company_name; LinkedIn: required).",
            ),
            body_field("countries", help="LinkedIn: comma-separated country codes, e.g. US,CA."),
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
    # --- Public profiles and their public content ---
    Cmd(
        "instagram-profile",
        "POST",
        "/agent/research/social/instagram-profile",
        summary="Instagram profile: followers, bio, links, post count.",
        body=(
            body_field("handle", required=True, help="Instagram handle, without the @."),
            body_field("trim", type=bool, help="Trim the response payload."),
        ),
    ),
    Cmd(
        "instagram-posts",
        "POST",
        "/agent/research/social/instagram-posts",
        summary="Instagram posts of one account.",
        body=(
            body_field("handle", required=True, help="Instagram handle, without the @."),
            body_field("next_max_id", help="Pagination cursor from the previous response."),
            body_field("trim", type=bool, help="Trim the response payload."),
        ),
    ),
    Cmd(
        "instagram-reels",
        "POST",
        "/agent/research/social/instagram-reels",
        summary="Instagram reels of one account.",
        body=(
            body_field("handle", help="Instagram handle (provide handle or user_id)."),
            body_field("user_id", help="Instagram user id — faster than a handle."),
            body_field("max_id", help="Pagination cursor from the previous response."),
            body_field("trim", type=bool, help="Trim the response payload."),
        ),
    ),
    Cmd(
        "instagram-post-comments",
        "POST",
        "/agent/research/social/instagram-post-comments",
        summary="Comments under one Instagram post or reel.",
        body=(
            body_field("url", required=True, help="Instagram post or reel URL."),
            body_field("cursor", help="Pagination cursor."),
        ),
    ),
    Cmd(
        "tiktok-profile",
        "POST",
        "/agent/research/social/tiktok-profile",
        summary="TikTok profile: followers, likes, video count.",
        body=(body_field("handle", required=True, help="TikTok handle, without the @."),),
    ),
    Cmd(
        "tiktok-profile-videos",
        "POST",
        "/agent/research/social/tiktok-profile-videos",
        summary="Videos posted by one TikTok account.",
        body=(
            body_field("handle", required=True, help="TikTok handle, without the @."),
            body_field("user_id", help="TikTok user id — faster than a handle."),
            body_field("sort_by", choices=("latest", "popular"), help="Order of the videos."),
            body_field("max_cursor", help="Pagination cursor from the previous response."),
            body_field("trim", type=bool, help="Trim the response payload."),
        ),
    ),
    Cmd(
        "tiktok-video-comments",
        "POST",
        "/agent/research/social/tiktok-video-comments",
        summary="Comments under one TikTok video.",
        body=(
            body_field("url", required=True, help="TikTok video URL."),
            body_field("cursor", help="Pagination cursor."),
            body_field("trim", type=bool, help="Trim the response payload."),
        ),
    ),
    Cmd(
        "tiktok-audience-demographics",
        "POST",
        "/agent/research/social/tiktok-audience-demographics",
        summary="Where a TikTok account's audience is, by country. Costs ~26 credits.",
        body=(body_field("handle", required=True, help="TikTok handle, without the @."),),
    ),
    Cmd(
        "tiktok-followers",
        "POST",
        "/agent/research/social/tiktok-followers",
        summary="One page of a TikTok account's followers — summarize, never hand over as a list.",
        body=(
            body_field("handle", help="TikTok handle (provide handle or user_id)."),
            body_field("user_id", help="TikTok user id — faster than a handle."),
            body_field("min_time", help="Pagination cursor from the previous response."),
            body_field("trim", type=bool, help="Trim the response payload."),
        ),
    ),
    Cmd(
        "tiktok-following",
        "POST",
        "/agent/research/social/tiktok-following",
        summary="One page of the accounts a TikTok account follows.",
        body=(
            body_field("handle", required=True, help="TikTok handle, without the @."),
            body_field("min_time", help="Pagination cursor from the previous response."),
            body_field("trim", type=bool, help="Trim the response payload."),
        ),
    ),
    Cmd(
        "youtube-channel",
        "POST",
        "/agent/research/social/youtube-channel",
        summary="YouTube channel: subscribers, views, description.",
        body=(
            body_field("channel_id", help="Channel id (provide channel_id, handle or url)."),
            body_field("handle", help="Channel handle, e.g. RivalTV."),
            body_field("url", help="Channel URL."),
        ),
    ),
    Cmd(
        "youtube-channel-videos",
        "POST",
        "/agent/research/social/youtube-channel-videos",
        summary="Videos of one YouTube channel.",
        body=(
            body_field("channel_id", help="Channel id (provide channel_id or handle)."),
            body_field("handle", help="Channel handle, e.g. RivalTV."),
            body_field("sort", choices=("latest", "popular"), help="Order of the videos."),
            body_field("continuation_token", help="Pagination cursor from the previous response."),
        ),
    ),
    Cmd(
        "youtube-video-comments",
        "POST",
        "/agent/research/social/youtube-video-comments",
        summary="Comments under one YouTube video.",
        body=(
            body_field("url", required=True, help="YouTube video URL."),
            body_field("order", choices=("top", "newest"), help="Comment order."),
            body_field("continuation_token", help="Pagination cursor from the previous response."),
        ),
    ),
    Cmd(
        "facebook-profile",
        "POST",
        "/agent/research/social/facebook-profile",
        summary="Facebook page or profile: followers, category, contact details.",
        body=(
            body_field("url", required=True, help="Facebook page or profile URL."),
            body_field("get_business_hours", type=bool, help="Also fetch business hours."),
        ),
    ),
    Cmd(
        "facebook-profile-posts",
        "POST",
        "/agent/research/social/facebook-profile-posts",
        summary="Posts of one Facebook page or profile — about 3 per call; page with cursor for more.",
        body=(
            body_field("url", help="Facebook page or profile URL (provide url or page_id)."),
            body_field("page_id", help="Facebook page id — faster than a URL."),
            body_field("cursor", help="Pagination cursor."),
        ),
    ),
    Cmd(
        "twitter-profile",
        "POST",
        "/agent/research/social/twitter-profile",
        summary="X/Twitter profile: followers, tweet count, bio.",
        body=(body_field("handle", required=True, help="X/Twitter handle, without the @."),),
    ),
    Cmd(
        "twitter-user-tweets",
        "POST",
        "/agent/research/social/twitter-user-tweets",
        summary="Tweets of one X/Twitter account (its most popular, not its newest).",
        body=(
            body_field("handle", required=True, help="X/Twitter handle, without the @."),
            body_field("trim", type=bool, help="Trim the response payload."),
        ),
    ),
    Cmd(
        "threads-profile",
        "POST",
        "/agent/research/social/threads-profile",
        summary="Threads profile: followers and bio.",
        body=(body_field("handle", required=True, help="Threads handle, without the @."),),
    ),
    Cmd(
        "threads-posts",
        "POST",
        "/agent/research/social/threads-posts",
        summary="Recent posts of one Threads account.",
        body=(
            body_field("handle", required=True, help="Threads handle, without the @."),
            body_field("trim", type=bool, help="Trim the response payload."),
        ),
    ),
    Cmd(
        "pinterest-user-boards",
        "POST",
        "/agent/research/social/pinterest-user-boards",
        summary="Boards of one Pinterest account.",
        body=(
            body_field("handle", required=True, help="Pinterest username."),
            body_field("trim", type=bool, help="Trim the response payload."),
        ),
    ),
    Cmd(
        "linkedin-profile",
        "POST",
        "/agent/research/social/linkedin-profile",
        summary="LinkedIn person profile: followers and public activity.",
        body=(body_field("url", required=True, help="LinkedIn profile URL."),),
    ),
    Cmd(
        "linkedin-company",
        "POST",
        "/agent/research/social/linkedin-company",
        summary="LinkedIn company page: followers, employees, description.",
        body=(body_field("url", required=True, help="LinkedIn company page URL."),),
    ),
)

app = build_group(
    NAME,
    "Social / ad-library / Reddit / TikTok / YouTube research.",
    SPECS,
    provider_reads=True,
)


def register(parent: typer.Typer) -> None:
    parent.add_typer(app, name=NAME)
