from __future__ import annotations

import typer

from sellerclaw_cli._command_group import Cmd, body_field, build_group, flag

NAME = "email"

SPECS = (
    Cmd(
        "mailboxes",
        "GET",
        "/agent/email/mailboxes",
        summary="List the owner's connected mailboxes (id, email address, status).",
    ),
    Cmd(
        "list",
        "GET",
        "/agent/email/messages",
        summary="List stored emails, newest first; filter by mailbox and folder, or search text.",
        flags=(
            flag("mailbox", param="mailbox_id", help="Restrict to one mailbox id."),
            flag(
                "folder",
                choices=("inbox", "sent", "pending", "all"),
                default="all",
                help=(
                    "inbox = incoming received; sent = delivered; "
                    "pending = your drafts awaiting the owner's approval."
                ),
            ),
            flag("search", help="Case-insensitive substring over subject, sender and body."),
            flag("limit", type=int, minimum=1, maximum=200, default=50, help="Page size."),
            flag("offset", type=int, minimum=0, default=0, help="Page offset (for paging)."),
        ),
    ),
    Cmd(
        "read",
        "GET",
        "/agent/email/messages/{email_id}",
        summary="Read one stored email by id (full subject and body).",
    ),
    Cmd(
        "thread",
        "GET",
        "/agent/email/threads/{thread_id}",
        summary="Read every stored email in one thread, oldest first.",
    ),
    Cmd(
        "draft",
        "POST",
        "/agent/email/drafts",
        summary=(
            "Create an outgoing draft and raise an approval request to the owner — the email is "
            "NOT sent. Returns the draft id and the linked action_request_id. "
            'Body: {"mailbox_id": "...", "to": ["a@b.com"], "subject": "...", '
            '"body_text": "...", "cc"?: [...], "bcc"?: [...], "in_reply_to"?: "<provider-msg-id>", '
            '"attachments"?: ["<file_id>"]}.'
        ),
        body=(
            body_field("mailbox_id", required=True, help="Id of the mailbox to send from (UUID)."),
            body_field("to", type=str, repeatable=True, required=True, help="Recipient email addresses."),
            body_field("subject", required=True, help="Email subject line."),
            body_field("body_text", required=True, help="Plain-text email body."),
            body_field("cc", type=str, repeatable=True, help="CC email addresses."),
            body_field("bcc", type=str, repeatable=True, help="BCC email addresses."),
            body_field("in_reply_to", help="Provider message id this draft replies to."),
            body_field(
                "attachments",
                type=str,
                repeatable=True,
                help=(
                    "File ids to attach as real files (from `sellerclaw files upload` / "
                    "`files list`). Attach files this way — never paste a file link into body_text."
                ),
            ),
        ),
    ),
    Cmd(
        "send",
        "POST",
        "/agent/email/drafts/{email_id}/send",
        summary=(
            "Deliver an already-approved draft. Refused until the owner approves the linked "
            "request (the draft stays pending), and rejected if they declined it."
        ),
    ),
)

app = build_group(
    NAME,
    "Email: read the owner's mailbox and send mail through a draft + approval gate.",
    SPECS,
)


def register(parent: typer.Typer) -> None:
    parent.add_typer(app, name=NAME)
