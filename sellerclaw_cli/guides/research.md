# SellerClaw — research

Gathering market signal to inform listings, pricing, and content via `sellerclaw_run`. Run the examples
directly; reach for `sellerclaw_describe` only for a command not shown here, or when a call errors.

## Common calls

```text
# Google Trends interest over time. keywords is comma-separated; timeframe / geo optional.
sellerclaw_run(group="research-trends", command="interest-over-time",
  flags={"keywords": "wireless mouse, bluetooth mouse", "timeframe": "today 12-m", "geo": "US"})
sellerclaw_run(group="research-trends", command="related-queries", flags={"keywords": "wireless mouse"})

# SEO / keyword research (body-driven)
sellerclaw_run(group="research-seo", command="keyword-ideas",    body={"keyword": "wireless mouse"})
sellerclaw_run(group="research-seo", command="serp-competitors", body={"keyword": "wireless mouse"})

# What the marketplace itself already lists (query, gtin, or a competitor's storefront)
sellerclaw_run(group="research-catalog", command="ebay-search",
  body={"query": "wireless mouse", "marketplace_id": "EBAY_US", "limit": 20})
sellerclaw_run(group="research-catalog", command="ebay-search",
  body={"sellers": ["rival_store"], "limit": 50})

# A competitor's social presence: the account, then what it publishes
sellerclaw_run(group="research-social", command="instagram-profile", body={"handle": "rivalbrand"})
sellerclaw_run(group="research-social", command="tiktok-profile-videos",
  body={"handle": "rivalbrand", "sort_by": "popular"})
```

## Where to look

- `research-trends` — `interest-over-time`, `interest-by-region`, `related-queries`,
  `related-topics`, `trending`, `compare`.
- `research-seo` — `keyword-ideas`, `keyword-volume`, `autocomplete`, `people-also-ask`,
  `serp-competitors`, `amazon-products`, `amazon-reviews`, `product-search`, `content-sentiment`.
- `research-social` — ad libraries (Facebook, Google, TikTok, LinkedIn), Reddit, TikTok/YouTube
  trends, and a named account's public presence: `<platform>-profile` for follower counts and bio,
  `…-posts` / `…-videos` for what it publishes, `…-comments` for what its audience says,
  `tiktok-audience-demographics` for where that audience sits.
- `research-catalog` — `ebay-search` over the marketplace's own catalog; pass `sellers` to scan a
  competitor's storefront instead of the whole marketplace.
- `kb` — search the shared knowledge base (read-only).

## Watch for

- **Research calls consume credits** — be deliberate; don't loop over dozens of keywords or pages
  without a reason to.
- **Reading one specific page** is not part of this surface — use whatever web browsing the client
  itself has, or the `sellerclaw web scrape` CLI command outside it.
- Research is read-only — it informs the listing/pricing decision, it doesn't change the store. Turn
  raw rows into a recommendation rather than dumping them.
