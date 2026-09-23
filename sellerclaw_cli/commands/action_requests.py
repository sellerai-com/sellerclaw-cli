from __future__ import annotations

import typer

from sellerclaw_cli._command_group import Cmd, body_field, build_group, flag

NAME = "action-requests"

SPECS = (
    Cmd(
        "list",
        "GET",
        "/agent/goals/action-requests",
        summary=(
            "Everything waiting on the owner, newest first — every ask raised on this account, "
            "whoever raised it, not only your own. `--status pending` is what still needs them; "
            "narrow further with --limit."
        ),
        flags=(
            flag(
                "status",
                choices=("pending", "resolved", "rejected", "cancelled"),
                help="Keep only requests in this state. Omit for every state.",
            ),
            flag("limit", type=int, minimum=1, maximum=200, help="Max requests to return."),
        ),
    ),
    Cmd(
        "get",
        "GET",
        "/agent/goals/action-requests/{request_id}",
        summary="Get one action request by id (check its status, and which option was chosen).",
    ),
    Cmd(
        "create",
        "POST",
        "/agent/goals/action-requests",
        summary="Ask the owner to decide on or carry out something (approve, pay, connect, provide info).",
        body=(
            body_field(
                "kind",
                help="Request kind.",
                choices=("approval", "payment", "input", "connect", "review", "generic"),
                example="generic",
            ),
            body_field(
                "mode",
                help=(
                    "Who acts after the owner responds. 'decision': you can do it yourself but "
                    "need a go-ahead (owner approves/rejects, then you act). 'delegation': only "
                    "the owner can do it (they do it and report back). Omit to default from kind "
                    "(approval/review -> decision, else delegation) \u2014 or, with `options`, to decision, "
                    "the only mode a choice can have."
                ),
                choices=("decision", "delegation"),
                example="decision",
            ),
            body_field("title", required=True, help="Short, action-oriented title."),
            body_field("description", required=True, help="What you need the owner to do and why."),
            body_field(
                "summary",
                help=(
                    "Optional one-line statement of exactly what you're asking, shown to the owner "
                    "above the details (e.g. 'Approve sending this email before it goes out')."
                ),
            ),
            body_field(
                "details",
                type=dict,
                repeatable=True,
                help=(
                    "The facts the owner decides on, as named rows: an array of "
                    '{"label": "...", "value": "...", "type"?: "text"|"body"|"link"|"file", '
                    '"url"?: "..."}. Use these instead of packing the numbers into `description` — '
                    "the owner sees one row per fact (Order, Customer, They paid, Supplier cost, "
                    "Profit) and can check them at a glance, where a paragraph has to be read "
                    "through. `description` then only has to say what you want to do and why. "
                    "Always give them on anything about money."
                ),
            ),
            body_field(
                "options",
                type=dict,
                repeatable=True,
                help=(
                    "Turn the ask into a CHOICE instead of a yes/no — an array of "
                    '{"label": "...", "description"?: "..."}. Use it when the blocker has several '
                    "right answers (which shipping policy, which markup): two to eight of them, "
                    "`label` is the button and `description` the one line the owner decides on. "
                    "Ids are issued by the server (\"1\", \"2\", ...) — read them off the reply. "
                    'Only a decision can offer them, and they cannot be combined with staged work.'
                ),
                example=[
                    {"label": "Musurok Shipping", "description": "4 days, free — on 101 listings"},
                    {"label": "Chulkov Shipping from US", "description": "4 days, flat rate"},
                ],
            ),
            body_field(
                "allow_custom_option",
                type=bool,
                help=(
                    "With `options`, let the owner answer in their own words instead of picking "
                    "one. Their wording comes back in `resolution_note` with no selected option."
                ),
            ),
            body_field("goal_id", help="Related goal id (UUID), if any."),
            body_field("team_task_id", help="Related team task id (UUID), if any."),
            body_field("cta_label", help="Optional button label for the owner."),
            body_field("cta_url", help="Optional link the owner should open."),
            body_field("blocking", type=bool, help="Whether work is blocked until the owner acts (default true)."),
            body_field("deadline", help="ISO-8601 deadline, e.g. 2026-06-20T00:00:00Z."),
        ),
    ),
    Cmd(
        "confirm",
        "POST",
        "/agent/goals/action-requests/{request_id}/confirm-from-chat",
        summary=(
            "Close a request with the owner's own answer instead of sending them to the app to "
            "press a button. Two forms, exactly one per call: `quote` — what they just said to "
            "you, when you are talking to them somewhere SellerClaw cannot read (Claude, a "
            "terminal); or `chat_id` + `message_id`, when they answered in SellerClaw's own chat. "
            "Quote them verbatim and only once they have actually answered: the cloud judges those "
            "words against the action that would really run, and anything short of a plain yes or "
            "no comes back as an error rather than an approval."
        ),
        body=(
            body_field(
                "quote",
                help=(
                    "What the owner said, in their words, in the conversation you are having with "
                    "them. One sentence — their answer, not the exchange around it, and never "
                    "words you supplied for them."
                ),
                example="yes, go ahead and send it",
            ),
            body_field(
                "chat_id",
                help="Chat the owner answered in, for a reply inside SellerClaw (from `chats list`).",
            ),
            body_field(
                "message_id",
                help=(
                    "The owner's message that answers this request (from `chats list-messages`). "
                    "Point at their reply — not your own question, and not an earlier line."
                ),
            ),
        ),
    ),
    Cmd(
        "cancel",
        "POST",
        "/agent/goals/action-requests/{request_id}/cancel",
        summary="Withdraw an action request that is no longer needed.",
    ),
)

app = build_group(
    NAME,
    "Action requests: what is waiting on the owner, and closing one with their answer.",
    SPECS,
)


def register(parent: typer.Typer) -> None:
    parent.add_typer(app, name=NAME)
