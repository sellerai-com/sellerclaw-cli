from __future__ import annotations

import typer

from sellerclaw_cli._command_group import Cmd, body_field, build_group, flag

NAME = "google-ads"

SPECS = (
    # Campaigns
    Cmd(
        "list-campaigns",
        "GET",
        "/agent/ads/google/campaigns",
        summary="List Google Ads campaigns.",
        flags=(
            flag("status", help="Filter by status."),
            flag("type", help="Filter by campaign type (SEARCH, PERFORMANCE_MAX, SHOPPING)."),
            flag("limit", type=int, help="Max results."),
        ),
    ),
    Cmd("get-campaign", "GET", "/agent/ads/google/campaigns/{campaign_id}", summary="Get one campaign."),
    Cmd(
        "create-campaign",
        "POST",
        "/agent/ads/google/campaigns",
        summary="Create a campaign (expert path). Use --dry-run first to validate.",
        flags=(flag("dry_run", type=bool, help="Validate locally without calling Google Ads."),),
        body=(
            body_field("name", required=True, help="Campaign name shown in Google Ads."),
            body_field(
                "type",
                required=True,
                help="Channel type: SEARCH, SHOPPING, or PERFORMANCE_MAX.",
                example="SEARCH",
            ),
            body_field(
                "daily_budget",
                type=float,
                required=True,
                help="Daily budget in account currency major units (e.g. dollars). > 0.",
            ),
            body_field(
                "bidding_strategy",
                required=True,
                help="Bidding strategy, e.g. MAXIMIZE_CONVERSIONS, TARGET_ROAS, MAXIMIZE_CLICKS.",
                example="MAXIMIZE_CONVERSIONS",
            ),
            body_field("dry_run", type=bool, help="Validate locally and return {ok, errors} without calling Google Ads."),
            body_field("target_roas", type=float, help="Target ROAS (e.g. 4.0). Required for TARGET_ROAS."),
            body_field("target_cpa", type=float, help="Target CPA in account currency major units. Required for TARGET_CPA."),
            body_field("merchant_id", help="Merchant Center account id. Required for SHOPPING."),
            body_field("campaign_priority", type=int, help="Shopping campaign priority (0-2)."),
            body_field("status", help="Ignored — campaigns are always created paused."),
            body_field(
                "geo_target_constants",
                repeatable=True,
                help="Geo target constant ids (e.g. '2840' for the US). Empty = all locations.",
            ),
            body_field(
                "language_constants",
                repeatable=True,
                help="Language constant ids (e.g. '1000' for English). Empty = all languages.",
            ),
            body_field(
                "negative_keywords",
                repeatable=True,
                help="Campaign-level negatives ('text'=BROAD, '\"text\"'=PHRASE, '[text]'=EXACT).",
            ),
            # A campaign with a natural end — a sale, a holiday push — should stop on its own
            # rather than on someone remembering to pause it. The API has taken these all along;
            # undeclared, they were invisible to `describe` and to the MCP tool.
            body_field("start_date", help="First day the campaign may serve, YYYY-MM-DD. Omit to start when enabled."),
            body_field("end_date", help="Last day it serves, YYYY-MM-DD, included. Omit to run until paused."),
            body_field("asset_group", type=dict, help="Asset group definition object. Required for PERFORMANCE_MAX."),
            body_field("ad_group", type=dict, help="Ad group with keywords + responsive search ad. Required for SEARCH."),
        ),
        body_strict=False,
    ),
    Cmd(
        "update-campaign",
        "PATCH",
        "/agent/ads/google/campaigns/{campaign_id}",
        summary="Update a campaign (status, budget, bidding).",
        body=(
            body_field("name", help="New campaign name."),
            body_field("status", help="New status: ENABLED, PAUSED, or REMOVED."),
            body_field(
                "daily_budget",
                type=float,
                help="New daily budget (major units). Increases capped at +20% and at max_daily_budget.",
            ),
            body_field("bidding_strategy", help="New bidding strategy (same values as on create)."),
            body_field("target_roas", type=float, help="New target ROAS for ROAS-based strategies."),
            # A campaign with a natural end — a sale, a holiday push — should stop on its own
            # rather than on someone remembering to pause it. The API has taken these all along;
            # undeclared, they were invisible to `describe` and to the MCP tool.
            body_field("start_date", help="First day the campaign may serve, YYYY-MM-DD. Omit to start when enabled."),
            body_field("end_date", help="Last day it serves, YYYY-MM-DD, included. Omit to run until paused."),
        ),
        body_strict=False,
    ),
    Cmd(
        "launch-search",
        "POST",
        "/agent/ads/google/campaigns/launch-search",
        summary="Launch a SEARCH campaign for a product (one call).",
        body=(
            body_field("product_id", required=True, help="SellerClaw product id (UUID). Drives keywords and the landing page."),
            body_field("daily_budget", type=float, required=True, help="Daily budget in account currency major units. > 0."),
            body_field(
                "headlines",
                repeatable=True,
                help="Write these: 3-15 ad headlines, <=30 chars each. Omitted = product title cut to 30 chars + filler.",
            ),
            body_field(
                "descriptions",
                repeatable=True,
                help="Write these: 2-4 description lines, <=90 chars each. Omitted = first sentences of the product description.",
            ),
            body_field("country", help="Target country (ISO code, English name, or geoTargetConstant id). Default US."),
            body_field("language", help="Ad language (ISO 639-1 / name). Defaults to the user's preferred language."),
            body_field(
                "final_url",
                help=(
                    "Landing page. Omit it: resolved to the product's page on a channel it is live on. "
                    "Never build one from a domain + guessed path; the launch opens the page first and "
                    "refuses a 404 (final_url_not_reachable)."
                ),
            ),
            body_field("objective", help="What to optimize for: 'traffic' (clicks) or 'sales' (conversions).", example="traffic"),
            body_field("name", help="Campaign name. Defaults to 'Search: {product name}'."),
            body_field(
                "keywords",
                repeatable=True,
                help="Override keywords ('text'=BROAD, '\"text\"'=PHRASE, '[text]'=EXACT). Else derived from product.",
            ),
            body_field("negative_keywords", repeatable=True, help="Extra campaign-level negative keywords."),
            body_field("cpc_bid", type=float, help="Optional manual CPC ceiling for the ad group (major units)."),
            body_field("start_date", help="First day the campaign may serve, YYYY-MM-DD. Omit to start when enabled."),
            body_field("end_date", help="Last day it serves, YYYY-MM-DD, included. Omit to run until paused."),
        ),
        body_strict=False,
    ),
    Cmd(
        "launch-pmax",
        "POST",
        "/agent/ads/google/campaigns/launch-pmax",
        summary="Launch a Performance Max campaign for a product (one call).",
        body=(
            body_field("product_id", required=True, help="SellerClaw product id (UUID)."),
            body_field("daily_budget", type=float, required=True, help="Daily budget in account currency major units. > 0."),
            body_field(
                "business_name",
                required=True,
                help="Brand / shop name shown alongside the ad, <=25 chars. Longer is refused, not shortened.",
            ),
            body_field("logo_url", required=True, help="URL of a square (1:1) logo image (>=128x128 px)."),
            body_field(
                "headlines",
                repeatable=True,
                help="Write these: >=3 headlines, <=30 chars each. Omitted = product title cut to length + filler.",
            ),
            body_field("long_headlines", repeatable=True, help="Write these: >=1 long headline, <=90 chars each."),
            body_field("descriptions", repeatable=True, help="Write these: >=2 description lines, <=90 chars each."),
            body_field("country", help="Target country (ISO code / name / constant id). Default US."),
            body_field("language", help="Ad language (ISO 639-1 / name). Defaults to the user's preferred language."),
            body_field(
                "final_url",
                help=(
                    "Landing page. Omit it: resolved to the product's page on a channel it is live on. "
                    "Never build one from a domain + guessed path; the launch opens the page first and "
                    "refuses a 404 (final_url_not_reachable)."
                ),
            ),
            body_field("call_to_action", help="Call-to-action enum (SHOP_NOW / LEARN_MORE / SIGN_UP / ...).", example="SHOP_NOW"),
            body_field("name", help="Campaign name. Defaults to 'PMax: {product name}'."),
            body_field("start_date", help="First day the campaign may serve, YYYY-MM-DD. Omit to start when enabled."),
            body_field("end_date", help="Last day it serves, YYYY-MM-DD, included. Omit to run until paused."),
            body_field("square_image_url", help="Optional explicit square (1:1) marketing image URL — overrides auto-pick."),
        ),
        body_strict=False,
    ),
    # Ad groups + keywords
    Cmd(
        "list-ad-groups",
        "GET",
        "/agent/ads/google/campaigns/{campaign_id}/adgroups",
        summary="List ad groups in a campaign.",
        flags=(flag("status", help="Filter by status."),),
    ),
    Cmd(
        "create-ad-group",
        "POST",
        "/agent/ads/google/adgroups",
        summary="Create an ad group.",
        body=(
            body_field("campaign_id", required=True, help="Parent campaign id (numeric)."),
            body_field("name", required=True, help="Ad group name."),
            body_field("cpc_bid", type=float, help="Manual CPC bid in account currency major units."),
            body_field("status", help="Ignored — ad groups are always created paused."),
        ),
        body_strict=False,
    ),
    Cmd(
        "update-ad-group",
        "PATCH",
        "/agent/ads/google/adgroups/{adgroup_id}",
        summary="Update an ad group.",
        body=(
            body_field("name", help="New ad group name."),
            body_field("status", help="New status: ENABLED, PAUSED, or REMOVED."),
            body_field("cpc_bid", type=float, help="New manual CPC bid in account currency major units."),
        ),
        body_strict=False,
    ),
    Cmd(
        "list-ads",
        "GET",
        "/agent/ads/google/adgroups/{adgroup_id}/ads",
        summary="List the ads in an ad group, with each ad's own on/off switch.",
        flags=(flag("status", help="Filter by status (ENABLED, PAUSED, REMOVED)."),),
    ),
    Cmd(
        "update-ad",
        "PATCH",
        "/agent/ads/google/adgroups/{adgroup_id}/ads/{ad_id}",
        summary="Enable, pause or remove one ad. An enabled campaign shows nothing while its ad is paused.",
        body=(
            body_field(
                "status",
                required=True,
                help="New status: ENABLED, PAUSED, or REMOVED (removal is permanent).",
                example="ENABLED",
            ),
        ),
        body_strict=False,
    ),
    Cmd(
        "list-keywords",
        "GET",
        "/agent/ads/google/adgroups/{adgroup_id}/keywords",
        summary="List keywords in an ad group.",
        flags=(
            flag("status", help="Filter by status."),
            flag("polarity", help="positive | negative | all."),
        ),
    ),
    Cmd(
        "add-keywords",
        "POST",
        "/agent/ads/google/keywords",
        summary="Add positive keywords.",
        body=(
            body_field("ad_group_id", required=True, help="Ad group id (numeric) the keywords belong to."),
            body_field(
                "keywords",
                repeatable=True,
                required=True,
                help="Keywords ('text'=BROAD, '\"text\"'=PHRASE, '[text]'=EXACT). >=1 entry.",
            ),
            body_field("cpc_bid", type=float, help="Optional per-keyword manual CPC bid (major units)."),
        ),
        body_strict=False,
    ),
    Cmd(
        "add-negative-keywords",
        "POST",
        "/agent/ads/google/keywords/negative",
        summary="Add negative keywords (campaign or ad-group level).",
        body=(
            body_field("campaign_id", help="Campaign id for campaign-level negatives. Provide exactly one of campaign_id / ad_group_id."),
            body_field("ad_group_id", help="Ad group id for ad-group-level negatives."),
            body_field(
                "keywords",
                repeatable=True,
                required=True,
                help="Negative keywords (same match-type syntax as positive keywords). >=1 entry.",
            ),
        ),
        body_strict=False,
    ),
    Cmd(
        "remove-keywords",
        "DELETE",
        "/agent/ads/google/keywords",
        summary="Remove keyword criteria by resource name.",
        flags=(flag("resource_names", required=True, help="Comma-separated criterion resource names."),),
    ),
    Cmd(
        "keyword-ideas",
        "POST",
        "/agent/ads/google/keywords/ideas",
        summary="Generate keyword ideas.",
        body=(
            body_field("keywords", repeatable=True, help="Seed keywords to expand (e.g. ['running shoes'])."),
            body_field("language", help="Language criterion resource name (e.g. 'languageConstants/1000')."),
            body_field(
                "geo_target_constants",
                repeatable=True,
                help="Geo target resource names (e.g. ['geoTargetConstants/2840']).",
            ),
        ),
    ),
    # Asset groups (PMax)
    Cmd(
        "list-asset-groups",
        "GET",
        "/agent/ads/google/campaigns/{campaign_id}/asset-groups",
        summary="List asset groups in a PERFORMANCE_MAX campaign.",
    ),
    Cmd(
        "update-asset-group",
        "PATCH",
        "/agent/ads/google/asset-groups/{asset_group_id}",
        summary="Update a PMax asset group.",
        body=(
            body_field("name", help="New asset group name."),
            body_field("status", help="New status: ENABLED, PAUSED, or REMOVED."),
            body_field("final_url", help="New landing page URL for the asset group."),
        ),
        body_strict=False,
    ),
    Cmd(
        "list-assets",
        "GET",
        "/agent/ads/google/asset-groups/{asset_group_id}/assets",
        summary="List assets attached to a PMax asset group.",
    ),
    Cmd(
        "add-asset",
        "POST",
        "/agent/ads/google/asset-groups/{asset_group_id}/assets",
        summary="Add a single asset to a PMax asset group.",
        body=(
            body_field(
                "field_type",
                required=True,
                help=(
                    "Asset field type: HEADLINE, LONG_HEADLINE, DESCRIPTION, BUSINESS_NAME, "
                    "MARKETING_IMAGE, SQUARE_MARKETING_IMAGE, PORTRAIT_MARKETING_IMAGE, LOGO, "
                    "LANDSCAPE_LOGO, YOUTUBE_VIDEO, or CALL_TO_ACTION_SELECTION."
                ),
                example="HEADLINE",
            ),
            body_field("text", help="Text body for text-type assets (HEADLINE/LONG_HEADLINE/DESCRIPTION/BUSINESS_NAME)."),
            body_field("image_url", help="Image URL for image-type assets (MARKETING_IMAGE / SQUARE_MARKETING_IMAGE / ...)."),
            body_field("youtube_video_id", help="YouTube video id for YOUTUBE_VIDEO assets."),
            body_field("call_to_action", help="Call-to-action enum for CALL_TO_ACTION_SELECTION (e.g. SHOP_NOW)."),
        ),
        body_strict=False,
    ),
    Cmd(
        "remove-assets",
        "DELETE",
        "/agent/ads/google/asset-groups/{asset_group_id}/assets",
        summary="Detach assets from a PMax asset group.",
        flags=(flag("resource_names", required=True, help="Comma-separated asset resource names."),),
    ),
    # Catalog + reporting
    Cmd(
        "list-merchant-products",
        "GET",
        "/agent/ads/google/products",
        summary="List products from the linked Merchant Center.",
    ),
    Cmd(
        "metrics",
        "GET",
        "/agent/ads/google/metrics",
        summary="Get performance metrics.",
        flags=(
            flag(
                "level",
                help=(
                    "campaign | ad_group | ad | keyword (spend per keyword) | asset_group "
                    "(Performance Max) | product_group. Any other value is refused, not silently "
                    "read as campaign."
                ),
            ),
            flag("ids", help="Comma-separated resource ids, matching the level."),
            flag("date_from", help="YYYY-MM-DD."),
            flag("date_to", help="YYYY-MM-DD."),
            flag("breakdown", help="Breakdown dimension."),
        ),
    ),
    Cmd(
        "search-terms",
        "GET",
        "/agent/ads/google/search-terms",
        summary="List the queries people typed, with what each one cost.",
        flags=(
            flag("campaign_id", help="Narrow to one campaign."),
            flag("adgroup_id", help="Narrow to one ad group."),
            flag("date_from", help="YYYY-MM-DD. Defaults to 7 days ago."),
            flag("date_to", help="YYYY-MM-DD. Defaults to today."),
            flag("order", help="spend (default) | clicks | impressions | conversions."),
            flag("limit", type=int, help="Rows to return (1-500, default 50)."),
        ),
    ),
    Cmd(
        "targeting",
        "GET",
        "/agent/ads/google/targeting",
        summary="Get targeting criteria: places, languages, devices, schedule, audiences.",
        flags=(
            flag("campaign_id", help="Campaign id. Pass exactly one of campaign_id / adgroup_id."),
            flag("adgroup_id", help="Ad group id. Pass exactly one of campaign_id / adgroup_id."),
        ),
    ),
    Cmd(
        "recommendations",
        "GET",
        "/agent/ads/google/recommendations",
        summary=(
            "Get the optimization recommendations Google is holding for the account, each with the "
            "current vs projected impressions / clicks / conversions / cost where Google predicts one."
        ),
        flags=(flag("campaign_id", help="Only recommendations about this campaign."),),
    ),
    Cmd(
        "action-log",
        "GET",
        "/agent/ads/google/action-log",
        summary="Get the recent Google Ads action log (audit trail).",
        flags=(
            flag("entity_id", help="Filter to one entity."),
            flag("days", type=int, help="Lookback window in days (1-90)."),
        ),
    ),
)

app = build_group(NAME, "Google Ads: campaigns, ad groups, keywords, PMax assets, metrics.", SPECS)


def register(parent: typer.Typer) -> None:
    parent.add_typer(app, name=NAME)
