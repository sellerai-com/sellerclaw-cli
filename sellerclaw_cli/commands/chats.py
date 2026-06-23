from __future__ import annotations

import typer

from sellerclaw_cli._command_group import Cmd, build_group, flag

NAME = "chats"

SPECS = (
    Cmd(
        "list",
        "GET",
        "/agent/chat/chats",
        summary="List the owner's chats.",
        flags=(flag("agent_id", help="Filter by agent id."),),
    ),
    Cmd("get", "GET", "/agent/chat/chats/{chat_id}", summary="Get one chat by id."),
    Cmd(
        "list-messages",
        "GET",
        "/agent/chat/chats/{chat_id}/messages",
        summary="List messages in a chat (paginated, truncated previews).",
        flags=(
            flag("offset", type=int, help="Pagination offset."),
            flag("limit", type=int, help="Page size (1-200)."),
            flag("order", help="Sort order: asc or desc."),
            flag("text_preview_chars", type=int, help="Per-message text preview cap."),
        ),
    ),
    Cmd(
        "get-message",
        "GET",
        "/agent/chat/messages/{message_id}",
        summary="Get one message with full text and raw content.",
    ),
)

app = build_group(NAME, "Owner chats and messages (read-only).", SPECS)


def register(parent: typer.Typer) -> None:
    parent.add_typer(app, name=NAME)
