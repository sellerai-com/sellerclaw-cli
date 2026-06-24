---
name: sellerclaw-research
description: "Use when the user wants market, keyword, trend, competitor, or social research before listing or pricing — SEO/SERP, Google Trends, marketplace catalog, social/ad-library research, or scraping a single page through SellerClaw."
---

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

# Scrape one specific page (consumes credits — use deliberately)
sellerclaw_run(group="web", command="scrape",
  flags={"url": "https://example.com/product", "max_chars": 5000})
```

## Where to look

- `research-trends` — `interest-over-time`, `interest-by-region`, `related-queries`,
  `related-topics`, `trending`, `compare`.
- `research-seo` — `keyword-ideas`, `keyword-volume`, `autocomplete`, `people-also-ask`,
  `serp-competitors`, `amazon-products`, `amazon-reviews`, `product-search`, `content-sentiment`.
- `research-social` — ad-library / Reddit / TikTok / YouTube research.
- `research-catalog` — marketplace catalog research.
- `kb` — search the shared knowledge base (read-only).

## Watch for

- **`web` scrape and some research calls consume credits** — be deliberate; don't loop over many URLs
  without reason.
- Research is read-only — it informs the listing/pricing decision, it doesn't change the store. Turn
  raw rows into a recommendation rather than dumping them.
