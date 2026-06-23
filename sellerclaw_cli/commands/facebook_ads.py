from __future__ import annotations

import typer

from sellerclaw_cli._command_group import Cmd, body_field, build_group, flag

NAME = "facebook-ads"

SPECS = (
    # Campaigns (mirror of google-ads)
    Cmd(
        "list-campaigns",
        "GET",
        "/agent/ads/facebook/campaigns",
        summary="List Meta Ads campaigns.",
        flags=(
            flag("status", help="Filter by status."),
            flag("limit", type=int, help="Max results."),
        ),
    ),
    Cmd("get-campaign", "GET", "/agent/ads/facebook/campaigns/{campaign_id}", summary="Get one campaign."),
    Cmd(
        "create-campaign",
        "POST",
        "/agent/ads/facebook/campaigns",
        summary="Create a campaign.",
        body=(
            body_field("name", required=True, help="Campaign name shown in Ads Manager."),
            body_field(
                "objective",
                required=True,
                help="Campaign objective, e.g. OUTCOME_SALES, OUTCOME_TRAFFIC, OUTCOME_LEADS.",
                example="OUTCOME_SALES",
            ),
            body_field("status", help="Ignored — campaigns are always created paused; activate via PATCH."),
        ),
        body_strict=False,
    ),
    Cmd(
        "update-campaign",
        "PATCH",
        "/agent/ads/facebook/campaigns/{campaign_id}",
        summary="Update a campaign (status, budget, …).",
        body_freeform=True,
    ),
    # Ad sets
    Cmd(
        "list-adsets",
        "GET",
        "/agent/ads/facebook/campaigns/{campaign_id}/adsets",
        summary="List ad sets in a campaign.",
        flags=(flag("status", help="Filter by status."),),
    ),
    Cmd(
        "create-adset",
        "POST",
        "/agent/ads/facebook/adsets",
        summary="Create an ad set.",
        body=(
            body_field("campaign_id", required=True, help="Parent campaign id."),
            body_field("name", required=True, help="Ad set name."),
            body_field(
                "daily_budget",
                type=float,
                required=True,
                help="Daily budget in account currency minor units (e.g. cents).",
            ),
            body_field(
                "bid_strategy",
                required=True,
                help="Bid strategy, e.g. LOWEST_COST_WITHOUT_CAP, COST_CAP, LOWEST_COST_WITH_BID_CAP.",
                example="LOWEST_COST_WITHOUT_CAP",
            ),
            body_field(
                "optimization_goal",
                required=True,
                help="Optimization goal, e.g. OFFSITE_CONVERSIONS, LINK_CLICKS, IMPRESSIONS.",
                example="OFFSITE_CONVERSIONS",
            ),
            body_field(
                "targeting",
                type=dict,
                required=True,
                help="Full targeting spec (geo_locations, age_min/age_max, genders, interests, ...).",
            ),
            body_field("status", help="Ignored — ad sets are always created paused."),
        ),
        body_strict=False,
    ),
    Cmd(
        "update-adset",
        "PATCH",
        "/agent/ads/facebook/adsets/{adset_id}",
        summary="Update an ad set.",
        body_freeform=True,
    ),
    Cmd(
        "duplicate-adset",
        "POST",
        "/agent/ads/facebook/adsets/{adset_id}/duplicate",
        summary="Duplicate an ad set.",
        body=(
            body_field("name", help="Override the copy's name (optional)."),
            body_field("campaign_id", help="Target campaign for the copy. Omit to duplicate within the same campaign."),
            body_field(
                "daily_budget",
                type=float,
                help="Override daily budget for the copy (account currency minor units).",
            ),
        ),
        body_strict=False,
    ),
    # Ads
    Cmd(
        "create-ad",
        "POST",
        "/agent/ads/facebook/ads",
        summary="Create an ad.",
        body=(
            body_field("ad_set_id", required=True, help="Parent ad set id."),
            body_field("name", required=True, help="Ad name."),
            body_field(
                "creative",
                type=dict,
                required=True,
                help="Ad creative spec, e.g. {title, body, link_url, image_hash, call_to_action} or {object_story_spec}.",
            ),
            body_field("status", help="Ignored — ads are always created paused."),
        ),
        body_strict=False,
    ),
    Cmd(
        "update-ad",
        "PATCH",
        "/agent/ads/facebook/ads/{ad_id}",
        summary="Update an ad.",
        body_freeform=True,
    ),
    # Creatives, audiences, images, targeting
    Cmd("list-creatives", "GET", "/agent/ads/facebook/adcreatives", summary="List ad creatives."),
    Cmd("list-audiences", "GET", "/agent/ads/facebook/audiences", summary="List custom audiences."),
    Cmd(
        "create-lookalike-audience",
        "POST",
        "/agent/ads/facebook/audiences/lookalike",
        summary="Create a lookalike audience.",
        body=(
            body_field("name", required=True, help="Name for the new lookalike audience."),
            body_field("source_audience_id", required=True, help="Seed custom/pixel audience id to model from."),
            body_field("country", required=True, help="ISO-3166 alpha-2 country code where to build it (e.g. 'US')."),
            body_field(
                "ratio",
                type=float,
                required=True,
                help="Similarity ratio in (0.0, 0.2]. Lower = more similar but smaller (e.g. 0.01 = top 1%).",
            ),
        ),
    ),
    Cmd(
        "upload-image",
        "POST",
        "/agent/ads/facebook/images",
        summary="Upload an image to the ad account.",
        body_freeform=True,
    ),
    Cmd(
        "search-interests",
        "GET",
        "/agent/ads/facebook/targeting/interests",
        summary="Search targeting interests.",
        flags=(flag("q", required=True, help="Search text."),),
    ),
    Cmd(
        "search-locations",
        "GET",
        "/agent/ads/facebook/targeting/locations",
        summary="Search targeting locations.",
        flags=(flag("q", required=True, help="Search text."),),
    ),
    # Reporting (mirror of google-ads)
    Cmd(
        "metrics",
        "GET",
        "/agent/ads/facebook/metrics",
        summary="Get performance metrics.",
        flags=(
            flag("level", help="campaign | adset | ad."),
            flag("ids", help="Comma-separated resource ids."),
            flag("date_from", help="YYYY-MM-DD."),
            flag("date_to", help="YYYY-MM-DD."),
            flag("breakdown", help="Breakdown dimension."),
        ),
    ),
    Cmd(
        "action-log",
        "GET",
        "/agent/ads/facebook/action-log",
        summary="Get the recent Meta Ads action log (audit trail).",
        flags=(
            flag("entity_id", help="Filter to one entity."),
            flag("days", type=int, help="Lookback window in days."),
        ),
    ),
)

app = build_group(NAME, "Meta (Facebook) Ads: campaigns, ad sets, ads, audiences, metrics.", SPECS)


def register(parent: typer.Typer) -> None:
    parent.add_typer(app, name=NAME)
