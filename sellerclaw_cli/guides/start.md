# SellerClaw — start here

Operate the owner's SellerClaw stores through the SellerClaw tools. The surface is large (40+ command
groups), but you don't have to memorize it or inspect it command by command: the task guides carry
ready-to-run examples, and `sellerclaw_groups` / `sellerclaw_describe` cover whatever they don't.

## How a call is shaped

`sellerclaw_run` takes the `group`, the `command`, `positionals` as a `{name: value}` map for the path
arguments, `flags` as a `{name: value}` map of filters, and `body` as the JSON payload for writes.
Names come from `sellerclaw_describe` — or, for the common jobs, from the guides.

```text
sellerclaw_run(group="channels", command="list")                                   # connected stores
sellerclaw_run(group="orders", command="list", flags={"limit": 20})                # a filtered read
sellerclaw_run(group="shopify-listings", command="sync-stock",
  positionals={"store_id": STORE_ID}, body={"items": [{"sku": "WM-01", "quantity": 42}]})
```

## Run directly; describe only as a fallback

Take the example from the guide for the job at hand and run it. The `sellerclaw_describe` round-trip
is worth it only when:

- no guide covers what you need — find the command with `sellerclaw_groups`, then
  `sellerclaw_describe(group, command)` for its exact fields; or
- a call fails with a field error — the error names the allowed fields and the closest match, so read
  it and retry rather than guessing again.

## Rules that apply to every job

- **Everything is JSON.** Responses and errors are JSON — read them. An error names the exact problem
  and its fix.
- **Store id comes first.** Channel groups (`shopify-*`, `ebay-*`, `amazon-*`) need a store id in
  `positionals` — take it from `sellerclaw_run(group="channels", command="list")`.
- **Find by name, don't dump.** Most groups offer `search` and/or `summary` — prefer them to listing
  everything and filtering by hand.
- **An empty result is not an error.** No rows means none matched, not a failure.
- **Some writes need the owner's approval.** Sending email and launching ad or Klaviyo campaigns
  create an approval request the owner accepts — expected behavior, so report it as pending, not as
  a failure.
- **Ownership settings are the owner's call.** Pinning a store's default policies, warehouse or
  markup changes how every future listing behaves — ask before setting them.
- **Raw fallbacks exist.** The `shopify` / `ebay` / `amazon` groups pass raw marketplace API calls
  through when no curated command fits. Check the curated groups first.

## The other guides

`listings` (publish and maintain marketplace listings) · `orders` (find, fulfill, ship, cancel) ·
`catalog` (the owner's own products and their cost) · `suppliers` (source products, dropship orders)
· `email` (read the mailbox, send through the approval gate) · `ads` (Google, Meta, eBay Promoted,
Klaviyo campaigns) · `research` (keywords, trends, competitors, social) · `analytics` (how the
business is doing: sales, profit, stock, geography).
