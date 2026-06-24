# Capabilities — command group map

The authoritative, always-current list is `sellerclaw_groups` (MCP) or `sellerclaw groups` (CLI).
This map orients you; confirm exact commands with `sellerclaw_describe` / `sellerclaw describe`.
Many groups take an id as the **first positional** (e.g. a store id for `shopify-*` / `ebay-*` /
`amazon-*`, a provider for `suppliers`) — `describe` tells you which.

## Sales channels & stores

| Group | What |
| --- | --- |
| `channels` | Connected sales channels (stores). |
| `integrations` | One-call overview of every integration (stores, ad accounts, suppliers, research). |
| `shopify-store` / `shopify-listings` / `shopify-orders` | Shopify admin, storefront listings, orders & fulfillment. |
| `shopify-collections` / `shopify-pages` / `shopify-menus` / `shopify-themes` | Shopify online-store content. |
| `shopify-finances` | Shopify Payments P&L and cash flow (read-only). |
| `ebay-store` / `ebay-listings` / `ebay-orders` | eBay admin (policies, locations), listings & drafts, orders & fulfillment. |
| `ebay-finances` / `ebay-promoted` | eBay fees/payouts (read-only); Promoted Listings campaigns & reports. |
| `amazon-store` / `amazon-listings` / `amazon-orders` | Amazon account, offers + price/stock sync, orders & merchant-fulfilled shipments. |

## Internal catalog, orders & analytics

| Group | What |
| --- | --- |
| `catalog` | Internal SellerClaw product catalog. |
| `orders` | Internal SellerClaw orders. |
| `listings` | Marketplace listings across all stores, by SellerClaw id. |
| `analytics` | Store sales analytics (read-only). |

## Marketing & ads

| Group | What |
| --- | --- |
| `ad-accounts` | Connected ad accounts and strategy settings. |
| `google-ads` | Campaigns, ad groups, keywords, PMax assets, metrics. |
| `facebook-ads` | Meta campaigns, ad sets, ads, audiences, metrics. |
| `klaviyo` | Email marketing: audiences, analytics, approval-gated campaigns. |

## Suppliers & email

| Group | What |
| --- | --- |
| `suppliers` | Supplier accounts, catalog search, and dropship orders (provider is the first argument). |
| `email` | Read the owner's mailbox; send mail through a draft + approval gate. |

## Research & knowledge

| Group | What |
| --- | --- |
| `research-seo` | SEO / SERP / marketplace keyword & product research. |
| `research-social` | Social / ad-library / Reddit / TikTok / YouTube research. |
| `research-trends` | Google Trends: interest, related queries/topics, comparisons. |
| `research-catalog` | Marketplace catalog research. |
| `kb` | Shared knowledge base (read-only search). |
| `web` | Single-page web scrape. |

## Work management

| Group | What |
| --- | --- |
| `goals` | The owner's single active objective. |
| `team-tasks` / `subagent-tasks` | Supervisor work items; tasks assigned to an executor. |
| `action-requests` | Requests asking the owner to act/approve. |
| `chats` | Owner chats and messages (read-only). |

## Account, files & content

| Group | What |
| --- | --- |
| `account` | Profile, settings, integrations. |
| `files` | View uploaded files; create files via URL or binary upload. |
| `media` | Generate and edit images/videos for the chat. |
| `spreadsheet` | Read, create and edit spreadsheets (xlsx / xlsm / xls / csv). |

## Raw API passthrough (fallback)

When no curated command fits: `shopify` (Admin GraphQL), `ebay` (REST + Trading), `amazon` (SP-API).
Use only after checking the curated groups with `describe`.
