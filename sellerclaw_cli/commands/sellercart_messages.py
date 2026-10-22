from __future__ import annotations

import typer

from sellerclaw_cli._command_group import Cmd, body_field, build_group, flag

NAME = 'sellercart-messages'

SPECS = (
    Cmd('list', 'GET', '/agent/sellercart/conversations',
        summary=("The shop's buyers' conversations: buyer, order, preview, waiting and unread. "
                 "Reading never clears the owner's unread mark."),
        flags=(
            flag('waiting', type=bool, help='Only the conversations waiting for an answer.'),
            flag('order_id', help='Only the conversations about this order.'),
            flag('limit', type=int, minimum=1, maximum=50, default=20, help='Max results.'),
            flag('offset', type=int, minimum=0, default=0, help='Results to skip.'),
        )),
    Cmd('get', 'GET', '/agent/sellercart/conversations/{conversation_id}',
        summary=("Every message in the conversation, with attachment metadata. "
                 "Reading never clears the owner's unread mark.")),
    Cmd('reply', 'POST', '/agent/sellercart/conversations/{conversation_id}/replies',
        summary=("Propose an answer under the owner's CUSTOMER_REPLY policy. "
                 "202 pending_approval waits for the owner; 200 approved_queued is going out. "
                 "reply_already_pending means an answer already waits for their approval."),
        body=(body_field('text', option='--text', required=True, help='The answer to the buyer.'),)),
)

app = build_group(NAME, "Buyers' messages to the shop and approval-gated answers.", SPECS)


def register(parent: typer.Typer) -> None:
    parent.add_typer(app, name=NAME)
