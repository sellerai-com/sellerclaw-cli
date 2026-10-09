"""Market research: other sellers' listings, keywords and trends, social media and the web."""

from __future__ import annotations

from typing import Any

from sellerclaw_cli._errors import UserInputError
from sellerclaw_cli.chatgpt._action import Param, action, execute, fit, runs, split

_LOCATION = Param("location_name", "string", "Country, e.g. United States (default).")
_LANGUAGE = Param("language_name", "string", "Language, e.g. English.")
_NETWORK = Param(
    "network", "string", "The social network.", required=True,
    choices=("instagram", "tiktok", "youtube", "x", "threads", "facebook", "linkedin"),
)
_HANDLE = Param("handle", "string", "The account's handle, without @.")
_URL = Param("url", "string", "The profile's or page's URL (Facebook, LinkedIn, YouTube).")


def _search_marketplace(values: dict[str, Any], params: tuple[Param, ...]) -> Any:
    _, _, body = split(values, params)
    if values["marketplace"] == "ebay":
        body.pop("marketplace", None)
        command = "ebay-search"
    else:
        command = "listing-search"
    _, kept = fit("research-catalog", command, {}, body)
    return execute("research-catalog", command, None, None, kept)


def _google_trends(values: dict[str, Any]) -> Any:
    keywords = [str(k) for k in values["keywords"]][:5]
    flags = {k: values[k] for k in ("timeframe", "geo", "category") if values.get(k)}
    over_time = execute("research-trends", "interest-over-time", None, {**flags, "keywords": ",".join(keywords)})
    related = {kw: execute("research-trends", "related-queries", None, {**flags, "keyword": kw}) for kw in keywords}
    return {"interest_over_time": over_time, "related_queries": related}


def _who(values: dict[str, Any], *, by_url: bool) -> dict[str, Any]:
    if by_url:
        if not values.get("url"):
            raise UserInputError(f"{values['network']} is looked up by url: pass url.")
        return {"url": values["url"]}
    if not values.get("handle"):
        raise UserInputError("pass handle.")
    return {"handle": str(values["handle"]).lstrip("@")}


def _social_profile(values: dict[str, Any]) -> Any:
    network = values["network"]
    if network == "youtube":
        body = {"url": values["url"]} if values.get("url") else _who(values, by_url=False)
        return execute("research-social", "youtube-channel", None, None, body)
    if network in ("facebook", "linkedin"):
        body = _who(values, by_url=True)
        if network == "facebook":
            return execute("research-social", "facebook-profile", None, None, body)
        command = "linkedin-company" if "/company/" in body["url"] else "linkedin-profile"
        return execute("research-social", command, None, None, body)
    commands = {
        "instagram": "instagram-profile",
        "tiktok": "tiktok-profile",
        "x": "twitter-profile",
        "threads": "threads-profile",
    }
    return execute("research-social", commands[network], None, None, _who(values, by_url=False))


#: Network -> (command, the field its next page is asked for by).
_POSTS = {
    "instagram": ("instagram-posts", "next_max_id"),
    "tiktok": ("tiktok-profile-videos", "max_cursor"),
    "youtube": ("youtube-channel-videos", "continuation_token"),
    "x": ("twitter-user-tweets", None),
    "threads": ("threads-posts", None),
    "facebook": ("facebook-profile-posts", "cursor"),
}


def _social_posts(values: dict[str, Any]) -> Any:
    network = values["network"]
    if network not in _POSTS:
        raise UserInputError(f"posts are not available for {network}; try get_social_profile.")
    command, cursor_field = _POSTS[network]
    body = _who(values, by_url=network == "facebook")
    if cursor_field and values.get("cursor"):
        body[cursor_field] = values["cursor"]
    body["trim"] = True
    _, kept = fit("research-social", command, {}, body)
    return execute("research-social", command, None, None, kept)


def _search_social(values: dict[str, Any]) -> Any:
    commands = {"tiktok": "tiktok-search", "reddit": "reddit-search", "tiktok_shop": "tiktok-shop-search"}
    command = commands[values["source"]]
    body = {k: values[k] for k in ("query", "region", "sort") if values.get(k)}
    if values["source"] == "tiktok" and "sort" in body:
        body["sort_by"] = body.pop("sort")
    body["trim"] = True
    _, kept = fit("research-social", command, {}, body)
    return execute("research-social", command, None, None, kept)


ACTIONS = (
    action(
        "search_marketplace",
        "Search a marketplace",
        "Search other sellers' listings on a marketplace by keywords, with prices and sellers: "
        "eBay (also by barcode or seller), Amazon, Shopify stores, Etsy and other storefronts. Uses "
        "credits.",
        (
            Param(
                "marketplace",
                "string",
                "ebay, amazon, shopify, etsy, walmart, bestbuy, newegg, target…",
                required=True,
            ),
            Param("query", "string", "What to search for."),
            Param("limit", "integer", "Most results."),
            Param("gtin", "string", "eBay: barcode."),
            Param("sellers", "array", "eBay: seller usernames.", items="string"),
            Param("condition_new_only", "boolean", "eBay: only new items."),
            Param("marketplace_id", "string", "eBay site, e.g. EBAY_US (default)."),
            Param("sort", "string", "eBay: result order."),
            Param("page", "integer", "Result page, where the storefront pages."),
            Param("store", "string", "Shopify: one store's domain."),
            Param("country", "string", "Shopify: the buyer's country."),
            Param("currency", "string", "Shopify: the price currency."),
            Param("cursor", "string", "Shopify: next_cursor of the previous page."),
        ),
        _search_marketplace,
        read_only=True,
        open_world=True,
    ),
    action(
        "get_marketplace_listing",
        "Get a marketplace listing",
        "One marketplace listing by URL, or by marketplace and id: price, stock, seller, specs and "
        "variants. Uses credits.",
        (
            Param("url", "string", "The listing's page URL."),
            Param("marketplace", "string", "With listing_id: the marketplace."),
            Param("listing_id", "string", "The marketplace's own id (ASIN, eBay item number…)."),
            Param("include_variants", "boolean", "Also read sizes, colours and their prices."),
            Param("currency", "string", "Display currency where supported."),
        ),
        runs("research-catalog", "listing-get"),
        read_only=True,
        open_world=True,
    ),
    action(
        "get_marketplace_prices",
        "Get marketplace prices",
        "Current prices of up to 5 listings on one marketplace (50 on Shopify). Uses credits.",
        (
            Param("marketplace", "string", "The marketplace the listings are on.", required=True),
            Param("listing_ids", "array", "The listings' ids or URLs.", required=True, items="string"),
            Param("currency", "string", "Shopify: the price currency."),
        ),
        runs("research-catalog", "listing-prices"),
        read_only=True,
        open_world=True,
    ),
    action(
        "keyword_ideas",
        "Get keyword ideas",
        "Keyword ideas for a seed keyword, with monthly search volume and competition. Uses credits.",
        (Param("keyword", "string", "The seed keyword.", required=True), _LOCATION, _LANGUAGE,
         Param("limit", "integer", "Most ideas (1-200).")),
        runs("research-seo", "keyword-ideas"),
        read_only=True,
        open_world=True,
    ),
    action(
        "keyword_volume",
        "Get keyword volume",
        "Monthly search volume of given keywords. Uses credits.",
        (Param("keywords", "array", "The keywords.", required=True, items="string"), _LOCATION, _LANGUAGE),
        runs("research-seo", "keyword-volume"),
        read_only=True,
        open_world=True,
    ),
    action(
        "serp_competitors",
        "Get search competitors",
        "The sites that rank in Google for given keywords, and how often each appears. Uses credits.",
        (Param("keywords", "array", "The keywords.", required=True, items="string"), _LOCATION, _LANGUAGE,
         Param("limit", "integer", "Most sites (1-100).")),
        runs("research-seo", "serp-competitors"),
        read_only=True,
        open_world=True,
    ),
    action(
        "google_trends",
        "Get Google Trends",
        "Google Trends for up to 5 keywords: interest over time compared, and each one's related "
        "rising searches.",
        (
            Param("keywords", "array", "The keywords (1-5).", required=True, items="string"),
            Param("timeframe", "string", "e.g. today 12-m (default), today 3-m."),
            Param("geo", "string", "Country code, e.g. US; omit for worldwide."),
            Param("category", "string", "Trends category id."),
        ),
        _google_trends,
        read_only=True,
        open_world=True,
    ),
    action(
        "get_social_profile",
        "Get a social profile",
        "A public profile on Instagram, TikTok, YouTube, X, Threads, Facebook or LinkedIn: "
        "followers, bio, links and activity. Uses credits.",
        (_NETWORK, _HANDLE, _URL),
        _social_profile,
        read_only=True,
        open_world=True,
    ),
    action(
        "get_social_posts",
        "Get social posts",
        "Recent public posts or videos of an Instagram, TikTok, YouTube, X, Threads or Facebook "
        "account, with engagement. Uses credits.",
        (_NETWORK, _HANDLE, _URL, Param("cursor", "string", "The next page's cursor from the previous answer.")),
        _social_posts,
        read_only=True,
        open_world=True,
    ),
    action(
        "search_social",
        "Search social media",
        "Search TikTok videos, Reddit posts or TikTok Shop products by keywords. Uses credits.",
        (
            Param("source", "string", "Where to search.", required=True, choices=("tiktok", "reddit", "tiktok_shop")),
            Param("query", "string", "What to search for.", required=True),
            Param("region", "string", "TikTok: country code."),
            Param("sort", "string", "Result order, e.g. Reddit relevance, hot, top, new."),
        ),
        _search_social,
        read_only=True,
        open_world=True,
    ),
    action(
        "search_ad_library",
        "Search an ad library",
        "Ads running in the Meta, Google, TikTok or LinkedIn ad library for a brand, product or "
        "keyword. Uses credits.",
        (
            Param(
                "platform",
                "string",
                "Which ad library.",
                required=True,
                choices=("facebook", "google", "tiktok", "linkedin"),
            ),
            Param("query", "string", "Brand, product or keyword.", required=True),
            Param("region", "string", "TikTok, Google: country code."),
            Param("limit", "integer", "TikTok: results per page."),
            Param("cursor", "string", "The next page's cursor from the previous answer."),
        ),
        runs("research-social", "ad-library-search"),
        read_only=True,
        open_world=True,
    ),
    action(
        "scrape_web_page",
        "Read a web page",
        "The content of one public web page, as text or HTML, optionally with a screenshot saved "
        "to the owner's files. Uses credits.",
        (
            Param("url", "string", "The page's URL.", required=True, to="flag"),
            Param("format", "string", "markdown (text, default) or html.", to="flag", choices=("markdown", "html")),
            Param("max_chars", "integer", "Cut the content to this length.", to="flag"),
            Param("screenshot", "boolean", "Also save a full-page picture (costs extra).", to="flag"),
        ),
        runs("web", "scrape"),
        read_only=True,
        open_world=True,
    ),
)
