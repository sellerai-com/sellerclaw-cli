from __future__ import annotations

import typer

from sellerclaw_cli._command_group import Cmd, body_field, build_group, flag

NAME = "klaviyo"

SPECS = (
    # Audiences & profiles (read)
    Cmd(
        "segments",
        "GET",
        "/agent/klaviyo/segments",
        summary="List audience segments.",
        flags=(flag("limit", type=int, minimum=1, maximum=100, help="Max results."),),
    ),
    Cmd(
        "lists",
        "GET",
        "/agent/klaviyo/lists",
        summary="List subscriber lists.",
        flags=(flag("limit", type=int, minimum=1, maximum=100, help="Max results."),),
    ),
    Cmd(
        "profiles",
        "GET",
        "/agent/klaviyo/profiles",
        summary="List customer profiles (optionally within a segment or by email).",
        flags=(
            flag("segment_id", help="Restrict to profiles in this segment id."),
            flag("email", help="Look up a profile by email."),
            flag("limit", type=int, minimum=1, maximum=100, help="Max results."),
        ),
    ),
    # Campaigns & flows (read)
    Cmd(
        "campaigns",
        "GET",
        "/agent/klaviyo/campaigns",
        summary="List email campaigns in the account.",
        flags=(flag("limit", type=int, minimum=1, maximum=100, help="Max results."),),
    ),
    Cmd(
        "flows",
        "GET",
        "/agent/klaviyo/flows",
        summary="List automated flows (read-only).",
        flags=(flag("limit", type=int, minimum=1, maximum=100, help="Max results."),),
    ),
    Cmd(
        "metrics",
        "GET",
        "/agent/klaviyo/metrics",
        summary="Get a campaign's performance (opens, clicks, revenue) over the last 30 days.",
        flags=(flag("campaign_id", required=True, help="Klaviyo campaign id."),),
    ),
    # Campaign preparation & sending (approval-gated)
    Cmd(
        "draft-campaign",
        "POST",
        "/agent/klaviyo/campaigns",
        summary="Prepare an email campaign as a draft and request the owner's approval to send.",
        body=(
            body_field("name", required=True, help="Internal campaign name."),
            body_field("subject", required=True, help="Email subject line."),
            body_field("audience_id", required=True, help="Klaviyo segment or list id to send to."),
            body_field("body_html", required=True, help="HTML email body."),
            body_field("from_email", help="Sender email address (defaults to the account's)."),
            body_field("from_label", help="Sender display name."),
        ),
    ),
    Cmd(
        "send-campaign",
        "POST",
        "/agent/klaviyo/campaigns/{campaign_id}/send",
        summary="Send a prepared campaign (only succeeds once the owner has approved it).",
    ),
    Cmd(
        "prepared-campaigns",
        "GET",
        "/agent/klaviyo/prepared-campaigns",
        summary="List campaigns you prepared and their approval/send status.",
        flags=(
            flag("limit", type=int, minimum=1, maximum=100, help="Max results."),
            flag("offset", type=int, minimum=0, help="Pagination offset."),
        ),
    ),
)

app = build_group(
    NAME,
    "Klaviyo email marketing: audiences, analytics, and approval-gated email campaigns.",
    SPECS,
)


def register(parent: typer.Typer) -> None:
    parent.add_typer(app, name=NAME)
