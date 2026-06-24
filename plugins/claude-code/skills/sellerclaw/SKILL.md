---
name: sellerclaw
description: "Use when the user wants to run their SellerClaw e-commerce business from Claude — view or change products, orders, listings, ads, suppliers, or email, or run marketplace research — or asks to install, connect, or troubleshoot the SellerClaw MCP server or CLI."
---

# SellerClaw

Operate the user's SellerClaw stores through the SellerClaw Agent API. The surface is large (40+
command groups), but you don't need to memorize it or inspect every command — this skill and its task
recipes carry ready-to-run examples. Run them directly.

## Pick how to call it

- **SellerClaw MCP tools available** (`sellerclaw_groups` / `sellerclaw_describe` / `sellerclaw_run`)
  → use them. Preferred. **Examples in these skills use this form.**
- **No MCP tools, but the `sellerclaw` CLI is installed** (check: `sellerclaw guide`) → call it
  through the shell.
- **Neither** → set it up: [references/setup.md](references/setup.md).

`sellerclaw_run` takes the group, the command, `positionals` as a `{name: value}` map for path
arguments, `flags` as a `{name: value}` map of filters, and `body` as the JSON payload. The CLI is the
same surface 1:1 — the call below is `sellerclaw <group> <command> <positionals…> [--flag v] -b '<json>'`
if you're going through the shell instead.

## Run directly; describe only as a fallback

For common jobs the task recipes give concrete example calls — use them, don't re-derive every command
with `sellerclaw_describe` first. That round-trip is only worth it when:

- you need a command no recipe covers — find it with `sellerclaw_groups` / `sellerclaw groups`, then
  `sellerclaw_describe(group, command)` for its exact fields; or
- a call fails with a field error — the error names the allowed fields and the closest match; read it
  and retry.

The group map (what exists and where) is in [references/capabilities.md](references/capabilities.md).

## Rules

- **Everything is JSON.** Responses and errors are JSON — read them, don't reformat blindly. Errors
  name the exact problem and fix.
- **Store id comes first.** Channel groups (`shopify-*`, `ebay-*`, `amazon-*`) need a store id in
  `positionals` — get it from `sellerclaw_run(group="channels", command="list")` or the `integrations`
  overview.
- **Find by name, don't dump.** Most groups offer `search` and/or `summary` — prefer them to listing
  everything.
- **Some writes need approval.** Sending email and launching ad/Klaviyo campaigns create an approval
  request the owner accepts — expected behavior, not a failure.
- **Raw fallbacks exist.** `shopify` / `ebay` / `amazon` pass raw API calls through when no curated
  command fits.

## Task recipes

Focused recipes load on their own when relevant: `sellerclaw-listings`, `sellerclaw-orders`,
`sellerclaw-ads`, `sellerclaw-research`.

## Setup & troubleshooting

Install, browser sign-in, connecting Claude Desktop / Claude Code, and fixing "not signed in" or PATH
problems: [references/setup.md](references/setup.md).
