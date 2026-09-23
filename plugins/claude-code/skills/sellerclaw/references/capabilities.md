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
| `shopify-finances` | Shopify Payments P&L and cash flow (read-only). |
| `ebay-store` / `ebay-listings` / `ebay-orders` | eBay admin (policies, locations), listings & drafts, orders & fulfillment. |
| `ebay-finances` / `ebay-promoted` | eBay fees/payouts (read-only); Promoted Listings campaigns & reports. |
| `amazon-store` / `amazon-listings` / `amazon-orders` | Amazon account, offers + price/stock sync, orders & merchant-fulfilled shipments. |
| `etsy-store` / `etsy-listings` / `etsy-orders` | Etsy shop admin (shipping profiles, return policies), listings & drafts, receipts & shipment confirmation. |
| `etsy-finances` | Etsy ledger summary — fees, credits, debits, net over a period (read-only). |
| `woocommerce-store` / `woocommerce-listings` / `woocommerce-orders` | WooCommerce store admin, listings & drafts, orders & tracking. |
| `wix-store` / `wix-listings` / `wix-orders` | Wix site admin, listings & drafts, orders & tracking. |
| `bigcommerce-store` / `bigcommerce-listings` / `bigcommerce-orders` | BigCommerce store admin, listings & drafts, orders & tracking. |
| `walmart-store` / `walmart-listings` / `walmart-orders` | Walmart store admin, listings & drafts (publishing reports back asynchronously — read `publish-status`), orders & fulfillment. |
| `tiktok-shop-store` / `tiktok-shop-listings` / `tiktok-shop-orders` | TikTok Shop admin (categories, category attributes, brands, locations), listings & drafts, orders & fulfillment. |
| `amazon-fba` | Amazon's own warehouse: bind listings to FBA, inbound shipments, stock held there. |
| `shopify-collections` / `shopify-pages` / `shopify-menus` / `shopify-themes` | Shopify storefront content: collections, pages, navigation, theme files. |
| `reviews` / `ebay-feedback` | Customer reviews and ratings on a store (WooCommerce / Wix / Etsy; BigCommerce per product); eBay feedback, its negatives and approval-gated replies. |
| `ebay-shipping` | eBay shipment tracking and the shipping report. |

## The owner's own storefront (SellerCart)

| Group | What |
| --- | --- |
| `sellercart` | The shop itself: create it, theme it, preview and screenshot it, review the draft, publish or close it. |
| `sellercart-pages` / `sellercart-menus` / `sellercart-media` | Pages built from blocks, header/footer navigation, the shop's image library. |
| `sellercart-products` | What is on the shelves, and each product's search title and description. |
| `sellercart-payouts` | Stripe onboarding, delivery terms and tax — what has to be true before checkout opens. |
| `sellercart-domain` | A domain the seller owns: attach it, read out the DNS record, re-check it. |

## Internal catalog, orders & analytics

| Group | What |
| --- | --- |
| `catalog` | Internal SellerClaw product catalog. |
| `orders` | Internal SellerClaw orders. |
| `listings` | Marketplace listings across all stores, by SellerClaw id. |
| `categories` / `attributes` | Place a product in a marketplace category and fill the item specifics that category demands — the two things a refused publish is usually missing. |
| `listing-problems` | Everything a channel refused or flagged across every store, with the power to hide what is dealt with. |
| `catalog-file` / `price-list` | Build or correct the catalog from a spreadsheet, and load a supplier's own price list — each with `check` and `preview` before `apply`. |
| `analytics` | Sales, trends, stock health, geography and tied-up capital (read-only). One period contract across the group — `--period`, or `--week`/`--month` for a completed week/month, or `--from`/`--to` — and `all` in place of a store id covers every store at once. |

## Marketing & ads

| Group | What |
| --- | --- |
| `ad-accounts` | Connected ad accounts and strategy settings. |
| `google-ads` | Campaigns, ad groups, ads, keywords, PMax assets, metrics. |
| `facebook-ads` | Meta campaigns, ad sets, ads, audiences, metrics. |
| `klaviyo` | Email marketing: audiences, analytics, approval-gated campaigns. |

## Suppliers & email

| Group | What |
| --- | --- |
| `suppliers` | Supplier accounts, catalog search, and dropship orders (provider is the first argument). |
| `email` | Read the owner's mailbox; send mail through a draft + approval gate. |
| `social` | Instagram / WhatsApp conversations: read a thread, draft a reply, send it through the same gate. |

## Research & knowledge

| Group | What |
| --- | --- |
| `research-seo` | SEO / SERP / marketplace keyword & product research. |
| `research-social` | Ad libraries, Reddit, TikTok/YouTube trends, and a competitor's public social presence (profile stats, posts, comments, audience split). |
| `research-trends` | Google Trends: interest, related queries/topics, comparisons. |
| `research-catalog` | Marketplace catalog research, including a scan of one seller's storefront. |
| `competitors` | A standing watch list of rival listings per store, with price snapshots and the undercutting report. |
| `web` | Read one specific page as text. |
| `store-audit` | Rates a storefront's SEO and AI-search visibility and returns an action plan. |
| `kb` | Shared knowledge base (read-only search). |

## Producing things

| Group | What |
| --- | --- |
| `media` | Generate and edit images and video — listing photography, ad creatives, banners. |
| `files` | The owner's file library: list, fetch one by id, pull one in from a URL, upload a local path. |
| `spreadsheet` / `sheets` / `pdf` | Build a spreadsheet, read and write the owner's Google Sheets, produce a PDF. |

## Account

| Group | What |
| --- | --- |
| `account` | Profile, settings, integrations. |
| `action-requests` | What is waiting on the owner, and closing one with their own answer (`confirm` with a `quote`) so a gated action never ends in "go to the website". |

## Raw API passthrough (fallback)

When no curated command fits: `shopify` (Admin GraphQL), `ebay` (REST + Trading), `amazon` (SP-API),
`etsy` (Open API), `woocommerce` (REST), `wix` (REST), `bigcommerce` (REST), `walmart` (REST).
Use only after checking the curated groups with `describe`: they resolve SellerClaw's own ids, apply
the owner's pricing and check a listing before it goes out, and a raw call does none of that.
