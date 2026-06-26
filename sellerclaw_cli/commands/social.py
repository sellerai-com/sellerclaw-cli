from __future__ import annotations

import typer

from sellerclaw_cli._command_group import Cmd, body_field, build_group, flag

NAME = "social"

SPECS = (
    Cmd(
        "accounts",
        "GET",
        "/agent/social/accounts",
        summary="List the owner's connected social accounts (id, channel, handle, status).",
    ),
    Cmd(
        "conversations",
        "GET",
        "/agent/social/conversations",
        summary=(
            "List DM conversations, most-recent activity first — one row per chat with the "
            "counterparty, last message and status. Use the chat_id to read or reply."
        ),
        flags=(
            flag("limit", type=int, minimum=1, maximum=100, default=20, help="Page size."),
            flag("offset", type=int, minimum=0, default=0, help="Page offset (for paging)."),
        ),
    ),
    Cmd(
        "thread",
        "GET",
        "/agent/social/conversations/{chat_id}/messages",
        summary="Read every message in one DM conversation, oldest first.",
    ),
    Cmd(
        "draft",
        "POST",
        "/agent/social/drafts",
        summary=(
            "Draft a text reply into an existing chat and raise an approval request to the owner — "
            "the message is NOT sent. Returns the draft id and the linked action_request_id. "
            'Body: {"social_account_id": "...", "chat_id": "...", "body_text": "..."}.'
        ),
        body=(
            body_field(
                "social_account_id",
                required=True,
                help="Id of the connected social account to reply from (UUID).",
            ),
            body_field(
                "chat_id",
                required=True,
                help="Id of the existing conversation to reply into (from `social conversations`).",
            ),
            body_field("body_text", required=True, help="Plain-text reply to send to the buyer."),
        ),
    ),
    Cmd(
        "send",
        "POST",
        "/agent/social/drafts/{message_id}/send",
        summary=(
            "Deliver an already-approved draft reply. Refused until the owner approves the linked "
            "request (the draft stays pending), and rejected if they declined it."
        ),
    ),
)

app = build_group(
    NAME,
    "Social DMs: read Instagram/WhatsApp conversations and reply through a draft + approval gate.",
    SPECS,
)


def register(parent: typer.Typer) -> None:
    parent.add_typer(app, name=NAME)
