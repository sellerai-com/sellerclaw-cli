---
name: sellerclaw
description: "Use when the user wants to run their SellerClaw e-commerce business from Claude — view or change products, orders, listings, ads, suppliers, or email, or run marketplace research — or asks to install, connect, or troubleshoot the SellerClaw MCP server or CLI."
---

# SellerClaw

Operate the user's SellerClaw stores through the SellerClaw Agent API. The surface is large (40+
command groups spanning stores, orders, listings, ads, suppliers, email and research), so you don't
memorize it — you discover it at runtime.

## Pick how to call it

- **SellerClaw MCP tools are available** (`sellerclaw_groups` / `sellerclaw_describe` /
  `sellerclaw_run`) → use them. Preferred.
- **No MCP tools, but the `sellerclaw` CLI is installed** (check: run `sellerclaw guide`) → call it
  through the shell. Same model.
- **Neither** → set it up first: see [references/setup.md](references/setup.md).

## The one workflow: discover → describe → run

For any task, always:

1. **Find the command.** MCP: `sellerclaw_groups`. CLI: `sellerclaw groups`, then
   `sellerclaw commands --group <group>`.
2. **Read its schema before the first call.** MCP: `sellerclaw_describe(group, command)`. CLI:
   `sellerclaw describe <group> <command>`. This returns the exact positional arguments, flags and
   body fields (with a ready example) — take them from here, never guess.
3. **Run it.**
   - MCP: `sellerclaw_run(group, command, positionals={…}, flags={…}, body={…})`.
   - CLI: `sellerclaw <group> <command> <positional…> [--flag value] [-b '<json>']`.

## Rules

- **Describe before you guess.** Argument and field names come from `describe`, not memory.
- **Everything is JSON.** Responses are JSON — read them, don't reformat blindly. Errors are JSON
  too and name the exact problem and fix (allowed fields, closest match); read the message and retry.
- **Some writes need approval.** Sending email, launching campaigns and similar actions create an
  approval request the owner must accept — that's expected behavior, not a failure.
- **Find by name, don't dump.** Most groups offer `search` and/or `overview` — prefer them to
  listing everything.
- **Raw fallbacks exist.** When no curated command fits, the `shopify` / `ebay` / `amazon` groups
  pass raw API calls through.

## What it can do

Full group map (what's available and where): [references/capabilities.md](references/capabilities.md).

## Setup & troubleshooting

Install, browser sign-in, connecting Claude Desktop / Claude Code, and fixing "not signed in" or
PATH problems: [references/setup.md](references/setup.md).
