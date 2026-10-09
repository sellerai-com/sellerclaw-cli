---
name: sellerclaw-ads
description: "Use when the user wants to view, launch, pause, resume or adjust advertising through SellerClaw — Google Ads, Meta (Facebook and Instagram) ads, or eBay Promoted Listings — or see what their ads spend and bring in."
---

# SellerClaw — ads

## How the ads are doing

- `sellerclaw_ads` shows spend, results and every campaign across Google Ads, Meta and eBay.
- Live figures: `get_ad_metrics` by platform. For eBay the first call starts a report; call again
  with its `report_id` to read it.
- Google Ads: `get_google_ads_search_terms` for what people searched and what it cost, and
  `get_google_ads_recommendations` for Google's own advice.

## Change spend

- `pause_ad_campaign` stops spend at once on any of the three.
- `resume_ad_campaign` and `set_ad_campaign_budget`: restarting or raising spend may wait for the
  owner's approval — read the answer's `status`. Budget raises go up at most 20% at a time.
- Wasted searches: `add_google_ads_negative_keywords`.

## Launch

- Google Ads for a catalog product: `launch_google_ads_campaign`, `search` or `performance_max`.
  Write the headlines and descriptions yourself; the landing page comes from where the product is
  live.
- eBay Promoted Listings: `launch_ebay_promoted_campaign` with the listings' eBay item numbers and
  an ad rate, which is charged only when an item sells through the ad — weigh it against the
  margin.

## eBay: approved, then applied

On eBay, launching, adding listings (`update_ebay_campaign_listings`), raising an ad rate
(`set_ebay_ad_rate`) and resuming wait for the owner's approval and then run with
`apply_approved_ebay_ad_action` and the staged action's id.
