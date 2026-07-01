from __future__ import annotations

import typer

from sellerclaw_cli._command_group import Cmd, body_field, build_group, flag

NAME = "ebay-feedback"

# eBay buyer feedback (the eBay equivalent of reviews): the recent negative/neutral feedback, the
# by-type trend + detailed seller ratings (DSR), and posting a public reply. Replying is a public,
# hard-to-undo reputation write — confirm the wording with the owner before calling 'reply'.
SPECS = (
    Cmd(
        "negative",
        "GET",
        "/agent/ebay/stores/{store_id}/feedback/negative",
        summary="Recent Negative/Neutral buyer feedback + the current feedback score.",
        flags=(
            flag(
                "days",
                type=int,
                minimum=1,
                maximum=90,
                default=1,
                help="Trailing window in days (default 1 = since yesterday).",
            ),
        ),
    ),
    Cmd(
        "insights",
        "GET",
        "/agent/ebay/stores/{store_id}/feedback/insights",
        summary=(
            "Feedback counts by type this window vs the previous one (trend) + the four detailed "
            "seller ratings (DSR) with the dragging dimension flagged."
        ),
        flags=(
            flag(
                "weeks",
                type=int,
                minimum=1,
                maximum=12,
                default=1,
                help="Window length in weeks; the previous equal window is the baseline.",
            ),
        ),
    ),
    Cmd(
        "reply",
        "POST",
        "/agent/ebay/stores/{store_id}/feedback/reply",
        summary=(
            "Draft a public reply to a buyer's feedback and raise an owner-approval request. "
            "Nothing is posted yet — returns a reply_id; the owner approves, then call 'send-reply'."
        ),
        body=(
            body_field("feedback_id", required=True, help="eBay feedback id to reply to."),
            body_field("target_user", required=True, help="The buyer who left the feedback (their eBay username)."),
            body_field("response_text", required=True, help="The public reply text (max 500 chars)."),
            body_field("item_id", help="eBay item id (optional; helps eBay target the reply)."),
            body_field("transaction_id", help="eBay transaction id (optional)."),
        ),
    ),
    Cmd(
        "send-reply",
        "POST",
        "/agent/ebay/stores/{store_id}/feedback/reply/{reply_id}/send",
        summary=(
            "Post a drafted reply once the owner has approved it (409 if still pending, 403 if "
            "declined). Idempotent once sent."
        ),
    ),
)

app = build_group(NAME, "eBay buyer feedback: reports + public reply (store_id is the first argument).", SPECS)


def register(parent: typer.Typer) -> None:
    parent.add_typer(app, name=NAME)
