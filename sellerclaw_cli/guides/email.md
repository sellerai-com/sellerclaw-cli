# SellerClaw — email

Reading the owner's mailbox and sending mail via `sellerclaw_run`. Run the examples directly; reach
for `sellerclaw_describe` only for a command not shown here, or when a call errors on a field.

## Read

```text
sellerclaw_run(group="email", command="mailboxes")                                  # ids + addresses
sellerclaw_run(group="email", command="list", flags={"mailbox": MAILBOX_ID, "limit": 20})
sellerclaw_run(group="email", command="list", flags={"search": "refund", "limit": 20})
sellerclaw_run(group="email", command="read", positionals={"email_id": EMAIL_ID})
sellerclaw_run(group="email", command="thread", positionals={"thread_id": THREAD_ID})  # whole conversation
```

## Send — draft first, the owner approves, then deliver

```text
# 1. Write the draft. This does NOT send: it raises an approval request to the owner and returns
#    the draft id plus the linked action_request_id.
sellerclaw_run(group="email", command="draft",
  body={"mailbox_id": MAILBOX_ID, "to": ["buyer@example.com"],
        "subject": "Your order has shipped",
        "body_text": "Hi Jane,\n\nYour order is on its way — tracking: 1Z999AA10123456784.",
        "in_reply_to": PROVIDER_MESSAGE_ID,      # optional: keeps it in the same thread
        "attachments": [FILE_ID]})               # optional: file ids, never inline data

# 2. After the owner approves, deliver it.
sellerclaw_run(group="email", command="send", positionals={"email_id": DRAFT_ID})
```

## Watch for

- **The gate is the point, not a bug.** `send` is refused while the request is still pending and
  rejected outright if the owner declined. Report "waiting for your approval" — do not retry in a
  loop, and never look for a way around it.
- **Reply, don't start over.** For an answer to an existing email pass `in_reply_to` with that
  message's provider id, so the buyer sees one thread.
- **Attachments are file ids**, uploaded beforehand — putting a link or base64 in the body instead
  is how attachments get lost.
- Sending on the owner's behalf carries their name. Match their tone, keep it short, and state facts
  you actually read from the order — do not invent tracking numbers or dates.
