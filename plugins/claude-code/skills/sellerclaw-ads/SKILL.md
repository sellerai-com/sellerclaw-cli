---
name: sellerclaw-ads
description: "Use when the user wants to view, launch, adjust, or report on advertising — Google Ads, Meta/Facebook ads, eBay Promoted Listings — or run email marketing campaigns via Klaviyo through SellerClaw."
---

# SellerClaw — ads & marketing

Running and reporting on paid campaigns via `sellerclaw_run`. Reads are direct; launching a campaign
is a rare, approval-gated write — `sellerclaw_describe` its body, then run.

## Accounts & reads (run directly)

```text
sellerclaw_run(group="ad-accounts",  command="list")    # connected ad accounts and their ids
sellerclaw_run(group="integrations", command="list")    # one-call overview across everything connected
```

Channels and their command groups:

- `google-ads` — campaigns, ad groups, keywords, PMax assets, metrics.
- `facebook-ads` — campaigns, ad sets, ads, audiences, metrics.
- `ebay-promoted` — Promoted Listings campaigns and performance reports (read-only).
- `klaviyo` — `segments`, `lists`, `profiles`, `campaigns`, `flows`, `metrics`.

Pull metrics/reports freely — they're read-only. Find the right command with `sellerclaw_groups`.

## Launching / sending (approval-gated — describe then run)

Campaign launches and email sends create an action request the **owner must approve** — report them as
"pending approval", not a failure. Because they're rare and high-stakes, read the exact body first:

```text
sellerclaw_describe(group="klaviyo", command="draft-campaign")   # then sellerclaw_run(... body={…})
sellerclaw_describe(group="klaviyo", command="send-campaign")
```

The same pattern applies to `google-ads` / `facebook-ads` create/update commands: describe the command,
build the body it specifies, then `sellerclaw_run`.
