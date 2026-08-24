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
            # Budget lives at exactly one level: on the campaign (budget optimization) or on the
            # ad set. Demanding the pair here made an ad set under a budgeted campaign impossible
            # to create at all — every attempt was one Meta rejects.
            body_field(
                "daily_budget",
                type=float,
                help="Daily budget in the account currency (50 = $50). Omit under campaign budget optimization.",
            ),
            body_field(
                "bid_strategy",
                help="Bid strategy, e.g. LOWEST_COST_WITHOUT_CAP, COST_CAP, LOWEST_COST_WITH_BID_CAP. Goes with daily_budget.",
                example="LOWEST_COST_WITHOUT_CAP",
            ),
            body_field(
                "bid_amount",
                type=float,
                help="Bid cap / cost target in the account currency. Required for COST_CAP and LOWEST_COST_WITH_BID_CAP.",
            ),
            body_field(
                "billing_event",
                help="What Meta charges for: IMPRESSIONS (default), LINK_CLICKS, THRUPLAY.",
                example="IMPRESSIONS",
            ),
            body_field(
                "optimization_goal",
                required=True,
                help="Optimization goal, e.g. OFFSITE_CONVERSIONS, LINK_CLICKS, IMPRESSIONS.",
                example="OFFSITE_CONVERSIONS",
            ),
            body_field(
                "promoted_object",
                type=dict,
                help='What to optimize towards: {"pixel_id": ..., "custom_event_type": "PURCHASE"} or {"page_id": ...}.',
            ),
            body_field(
                "targeting",
                type=dict,
                required=True,
                help="Targeting spec: geo_locations.countries, age_min/age_max, interests, genders ([1] men, [2] women).",
            ),
            body_field("start_time", help="ISO-8601 start, e.g. 2026-09-01T00:00:00-0700."),
            body_field("end_time", help="ISO-8601 end. Meta requires it with a lifetime budget."),
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
                help="Override daily budget for the copy, in the account currency (50 = $50).",
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
                help=(
                    "The words and picture: {title, body, description, link_url, image_hash, "
                    'call_to_action} — a plain button name like "SHOP_NOW" is fine. Assembled into '
                    "the object_story_spec Meta requires; pass one yourself to control the whole "
                    "shape. page_id names the Page the ad runs from (list-pages); omit it and the "
                    "ad account's own Page is used. image_hash comes from upload-image."
                ),
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
    Cmd(
        "list-pages",
        "GET",
        "/agent/ads/facebook/pages",
        summary="List the Meta Pages this ad account can advertise from (an ad runs as a Page).",
    ),
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
        summary="Upload an image file to the ad account; returns the image_hash a creative needs.",
        # The picture itself, not a description of it. Declared as an upload rather than a JSON
        # body: sending the file as JSON is what a `-b` body invited, and every real image died on
        # its first byte before the request was ever made.
        upload_file=True,
        flags=(flag("filename", help="Name to store it under (default: the local file's name)."),),
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
