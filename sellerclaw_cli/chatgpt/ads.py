"""Advertising on Google Ads, Meta and eBay Promoted Listings."""

from __future__ import annotations

from typing import Any

from sellerclaw_cli._errors import UserInputError
from sellerclaw_cli.chatgpt._action import Param, action, execute, fit, runs, split, store_param

_PLATFORM = Param("platform", "string", "Where the campaign runs.", required=True, choices=("google", "meta", "ebay"))
_STORE_EBAY = store_param(required=False)
_STORE = store_param()
_CAMPAIGN = Param("campaign_id", "string", "The campaign's id.", required=True)
_GROUPS = {"google": "google-ads", "meta": "facebook-ads"}
#: Each platform's word for a running and a paused campaign.
_RUNNING = {"google": "ENABLED", "meta": "ACTIVE"}
_PAUSED = "PAUSED"


def _ebay_store(values: dict[str, Any]) -> str:
    store_id = values.get("store_id")
    if not store_id:
        raise UserInputError("eBay Promoted Listings run per store: pass store_id.")
    return str(store_id)


def _rate(value: Any) -> str:
    """eBay's ad rate is a percent string in steps of 0.1, e.g. "5.0"."""
    return f"{round(float(value), 1):.1f}"


def _list_campaigns(values: dict[str, Any]) -> Any:
    platform = values["platform"]
    if platform == "ebay":
        return execute("ebay-promoted", "campaigns", {"store_id": _ebay_store(values)})
    flags = {k: values[k] for k in ("status", "limit") if values.get(k) is not None}
    return execute(_GROUPS[platform], "list-campaigns", None, flags)


def _metrics(values: dict[str, Any]) -> Any:
    platform = values["platform"]
    if platform == "ebay":
        store = {"store_id": _ebay_store(values)}
        if values.get("report_id"):
            return execute("ebay-promoted", "get-report", {**store, "report_task_id": values["report_id"]})
        started = execute(
            "ebay-promoted",
            "create-report",
            store,
            {"days": values.get("days")} if values.get("days") else None,
        )
        return {
            **(started if isinstance(started, dict) else {"report": started}),
            "note": "eBay is preparing the report. Call get_ad_metrics again with this report_id in a "
            "few seconds to read spend, sales, ROAS and ACOS.",
        }
    flags: dict[str, Any] = {k: values[k] for k in ("level", "date_from", "date_to", "breakdown") if values.get(k)}
    if values.get("ids"):
        flags["ids"] = ",".join(str(i) for i in values["ids"])
    return execute(_GROUPS[platform], "metrics", None, flags)


def _set_status(values: dict[str, Any], *, running: bool) -> Any:
    platform = values["platform"]
    campaign_id = values["campaign_id"]
    if platform == "ebay":
        command = "resume-campaign" if running else "pause-campaign"
        return execute("ebay-promoted", command, {"store_id": _ebay_store(values), "campaign_id": campaign_id})
    status = _RUNNING[platform] if running else _PAUSED
    return execute(_GROUPS[platform], "update-campaign", {"campaign_id": campaign_id}, None, {"status": status})


def _set_budget(values: dict[str, Any]) -> Any:
    group = _GROUPS[values["platform"]]
    body = {"daily_budget": values["daily_budget"]}
    return execute(group, "update-campaign", {"campaign_id": values["campaign_id"]}, None, body)


def _launch_google(values: dict[str, Any], params: tuple[Param, ...]) -> Any:
    command = "launch-pmax" if values["campaign_type"] == "performance_max" else "launch-search"
    _, _, body = split(values, params)
    body.pop("campaign_type", None)
    _, kept = fit("google-ads", command, {}, body)
    return execute("google-ads", command, None, None, kept)


def _update_ebay_listings(values: dict[str, Any]) -> Any:
    store = {"store_id": values["store_id"], "campaign_id": values["campaign_id"]}
    added = values.get("add_listing_ids") or []
    removed = values.get("remove_listing_ids") or []
    if not added and not removed:
        raise UserInputError("pass add_listing_ids, remove_listing_ids or both.")
    result: dict[str, Any] = {}
    if added:
        if values.get("ad_rate") is None:
            raise UserInputError("adding listings needs the ad_rate for their ads.")
        body = {"listing_ids": list(added), "bid_percentage": _rate(values["ad_rate"])}
        result["added"] = execute("ebay-promoted", "add-listings", store, None, body)
    if removed:
        result["removed"] = execute("ebay-promoted", "remove-listings", store, None, {"listing_ids": list(removed)})
    return result


ACTIONS = (
    action(
        "list_ad_campaigns",
        "List ad campaigns",
        "Campaigns on Google Ads, Meta, or a store's eBay Promoted Listings, with status and budget "
        "or ad rate.",
        (
            _PLATFORM,
            _STORE_EBAY,
            Param("status", "string", "Google, Meta: only this status."),
            Param("limit", "integer", "Google, Meta: most campaigns."),
        ),
        _list_campaigns,
        read_only=True,
    ),
    action(
        "get_ad_metrics",
        "Get ad metrics",
        "Spend, clicks, conversions and return on ad spend over a period. Google Ads and Meta by "
        "campaign, ad group or ad; eBay per store from a report eBay prepares, read with a second "
        "call.",
        (
            _PLATFORM,
            Param(
                "level",
                "string",
                "Google: campaign, ad_group, ad, keyword, asset_group, product_group; Meta: campaign, adset, ad.",
            ),
            Param("ids", "array", "Only these ids at that level.", items="string"),
            Param("date_from", "string", "YYYY-MM-DD."),
            Param("date_to", "string", "YYYY-MM-DD."),
            Param("breakdown", "string", "Google, Meta: a breakdown dimension."),
            _STORE_EBAY,
            Param("days", "integer", "eBay: how many days back (default 7)."),
            Param("report_id", "string", "eBay: the report to read."),
        ),
        _metrics,
        read_only=True,
    ),
    action(
        "pause_ad_campaign",
        "Pause an ad campaign",
        "Pause a campaign on Google Ads, Meta or eBay; spend stops straight away.",
        (_PLATFORM, _CAMPAIGN, _STORE_EBAY),
        lambda values: _set_status(values, running=False),
        read_only=False,
    ),
    action(
        "resume_ad_campaign",
        "Resume an ad campaign",
        "Resume a paused campaign on Google Ads, Meta or eBay. On Meta and eBay restarting spend "
        "waits for the owner's approval; on eBay it then needs apply_approved_ebay_ad_action.",
        (_PLATFORM, _CAMPAIGN, _STORE_EBAY),
        lambda values: _set_status(values, running=True),
        read_only=False,
        open_world=True,
    ),
    action(
        "set_ad_campaign_budget",
        "Set an ad campaign budget",
        "Change a campaign's daily budget, in the ad account's currency. A raise is capped at +20% "
        "a time; on Meta it waits for the owner's approval. Google Ads, Meta.",
        (
            Param("platform", "string", "Where the campaign runs.", required=True, choices=("google", "meta")),
            _CAMPAIGN,
            Param("daily_budget", "number", "New daily budget, e.g. 12.5.", required=True),
        ),
        _set_budget,
        read_only=False,
        destructive=True,
    ),
    action(
        "launch_google_ads_campaign",
        "Launch a Google Ads campaign",
        "Launch a Search or Performance Max campaign for one catalog product. Keywords, headlines "
        "and the landing page come from the product unless given. It spends once Google approves "
        "the ads.",
        (
            Param("campaign_type", "string", "Kind of campaign.", required=True, choices=("search", "performance_max")),
            Param("product_id", "string", "The catalog product to advertise.", required=True),
            Param("daily_budget", "number", "Daily budget in the account's currency.", required=True),
            Param("headlines", "array", "Ad headlines, up to 30 characters each.", items="string"),
            Param("long_headlines", "array", "Performance Max: up to 90 characters each.", items="string"),
            Param("descriptions", "array", "Description lines, up to 90 characters each.", items="string"),
            Param("business_name", "string", "Performance Max: shop name, up to 25 characters."),
            Param("logo_url", "string", "Performance Max: a square logo image."),
            Param("square_image_url", "string", "Performance Max: a square marketing image."),
            Param("call_to_action", "string", "Performance Max: e.g. SHOP_NOW."),
            Param("keywords", "array", "Search: keywords; \"phrase\", [exact], plain = broad.", items="string"),
            Param("negative_keywords", "array", "Search: negative keywords.", items="string"),
            Param("cpc_bid", "number", "Search: highest cost per click."),
            Param("objective", "string", "Search: traffic or sales."),
            Param("country", "string", "Target country (default US)."),
            Param("language", "string", "Ad language."),
            Param("final_url", "string", "Landing page; omit to use the product's live page."),
            Param("name", "string", "Campaign name."),
            Param("start_date", "string", "YYYY-MM-DD; omit to start now."),
            Param("end_date", "string", "YYYY-MM-DD; omit to run until paused."),
        ),
        _launch_google,
        read_only=False,
        open_world=True,
    ),
    action(
        "launch_ebay_promoted_campaign",
        "Launch an eBay Promoted campaign",
        "Prepare an eBay Promoted Listings campaign, paid only when an item sells through the ad, "
        "for chosen listings at an ad rate. It goes live after the owner approves and "
        "apply_approved_ebay_ad_action runs.",
        (
            _STORE,
            Param("name", "string", "Campaign name, unique on the account, up to 80 characters.", required=True),
            Param(
                "ad_rate",
                "number",
                "Percent of the sale price, 2-100 in steps of 0.1.",
                required=True,
                key="bid_percentage",
            ),
            Param("listing_ids", "array", "eBay item numbers to promote.", required=True, items="string"),
        ),
        lambda values: execute(
            "ebay-promoted",
            "prepare-campaign",
            {"store_id": values["store_id"]},
            None,
            {
                "name": values["name"],
                "bid_percentage": _rate(values["ad_rate"]),
                "listing_ids": list(values["listing_ids"]),
            },
        ),
        read_only=False,
        open_world=True,
    ),
    action(
        "update_ebay_campaign_listings",
        "Update eBay campaign listings",
        "Add listings to an eBay Promoted Listings campaign, which waits for the owner's approval, "
        "or remove them, which applies straight away.",
        (
            _STORE,
            _CAMPAIGN,
            Param("add_listing_ids", "array", "eBay item numbers to add.", items="string"),
            Param("ad_rate", "number", "Ad rate for added listings, in percent."),
            Param("remove_listing_ids", "array", "eBay item numbers to stop promoting.", items="string"),
        ),
        _update_ebay_listings,
        read_only=False,
        open_world=True,
    ),
    action(
        "set_ebay_ad_rate",
        "Set an eBay ad rate",
        "Change one eBay ad's rate. A raise waits for the owner's approval; a cut applies straight away.",
        (
            _STORE,
            _CAMPAIGN,
            Param("ad_id", "string", "The ad's id, not the listing's.", required=True),
            Param("ad_rate", "number", "New rate in percent, 2-100 in steps of 0.1.", required=True),
        ),
        lambda values: execute(
            "ebay-promoted", "set-ad-rate",
            {"store_id": values["store_id"], "campaign_id": values["campaign_id"]}, None,
            {"ad_id": values["ad_id"], "bid_percentage": _rate(values["ad_rate"])},
        ),
        read_only=False,
        destructive=True,
    ),
    action(
        "apply_approved_ebay_ad_action",
        "Apply an approved eBay ad action",
        "Carry out an eBay ad change the owner approved: a new campaign, added listings, a higher "
        "ad rate or a resumed campaign. Refused while it still waits for approval.",
        (_STORE, Param("action_id", "string", "The staged action's id.", required=True, to="path")),
        runs("ebay-promoted", "apply"),
        read_only=False,
        open_world=True,
    ),
    action(
        "get_google_ads_recommendations",
        "Get Google Ads recommendations",
        "Google's optimisation recommendations for the account or one campaign, with their "
        "projected effect.",
        (Param("campaign_id", "string", "Only this campaign.", to="flag"),),
        runs("google-ads", "recommendations"),
        read_only=True,
    ),
    action(
        "get_google_ads_search_terms",
        "Get Google Ads search terms",
        "The searches that triggered the ads, with clicks, cost and conversions for each.",
        (
            Param("campaign_id", "string", "Only this campaign.", to="flag"),
            Param("ad_group_id", "string", "Only this ad group.", to="flag", key="adgroup_id"),
            Param("date_from", "string", "YYYY-MM-DD (default 7 days ago).", to="flag"),
            Param("date_to", "string", "YYYY-MM-DD (default today).", to="flag"),
            Param("order", "string", "Sort by.", to="flag", choices=("spend", "clicks", "impressions", "conversions")),
            Param("limit", "integer", "Rows (1-500).", to="flag"),
        ),
        runs("google-ads", "search-terms"),
        read_only=True,
    ),
    action(
        "add_google_ads_negative_keywords",
        "Add Google Ads negative keywords",
        "Stop a Google Ads campaign or ad group from showing for these searches.",
        (
            Param("campaign_id", "string", "The campaign; or pass ad_group_id."),
            Param("ad_group_id", "string", "The ad group."),
            Param("keywords", "array", "Negative keywords.", required=True, items="string"),
        ),
        runs("google-ads", "add-negative-keywords"),
        read_only=False,
    ),
)
