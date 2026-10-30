"""What a card hands ChatGPT: exactly what the card draws.

ChatGPT shows its model a card's whole payload, and OpenAI's rules hold it to what the request needs.
The owner's decision (30.10.2026) is that the model sees what the owner sees on the card — no more:
an order board carries the buyer's name and town, not their email, street or phone, because the
board draws only those.

Each spec below lists the fields a card's screen reads (``frontend/src/mcp-apps/screens`` in the
sellerclaw repo), buttons included. ``True`` keeps a value whole; a nested spec is applied to a dict,
or to each item of a list. A field the server did not send stays absent — several screens tell
"unknown" from "empty" by whether a key is there, so nothing is ever added.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from sellerclaw_cli.chatgpt._answers import credits_only, without

Spec = Mapping[str, Any]


def _fields(*names: str, **nested: Any) -> dict[str, Any]:
    return {**dict.fromkeys(names, True), **nested}


_STORE = _fields("id", "platform", "display_name")
_PROBLEM = _fields(
    "id", "severity", "display_title", "display_message", "message", "fix", "occurrence_count", "last_seen_at"
)

_ORDERS = _fields(
    "filters",
    "sole_match",
    "item_images",
    orders=_fields(
        "total",
        "offset",
        items=_fields(
            "id", "remote_order_name", "remote_order_id", "status", "remote_created_at", "total_revenue",
            "currency", "has_unresolved_items", "customer_name", "store_name", "platform",
            shipping_address=_fields("city", "country_code"),
        ),
    ),
    overview=_fields("total", "by_status", "unresolved"),
    stores=_STORE,
    # One order opened: the address the card prints for packing, never the buyer's email or phone.
    order=_fields(
        "id", "remote_order_name", "remote_order_id", "status", "remote_created_at", "platform", "store_name",
        "currency", "total_revenue", "supplier_cost", "cost_currency", "has_unresolved_items", "customer_name",
        "supplier_provider", "supplier_order_id", "tracking_number", "tracking_carrier", "tracking_url",
        shipping_address=_fields(
            "full_name", "address1", "address2", "city", "province", "zip_code", "country_code"
        ),
        line_items=_fields("remote_line_item_id", "title", "quantity", "sell_price", "listing_id", "product_id"),
        shipping_label=_fields(
            "status", "test", "carrier_name", "service_name", "amount", "currency", "label_url", "error",
            tracking=_fields("status", "action_required"),
        ),
        shipping_label_offer=_fields("available"),
        shipments=_fields(
            "id", "position", "status", "provider", "supplier_provider", "line_indexes", "tracking_number",
            "tracking_carrier", "tracking_url",
        ),
    ),
)

_STORE_SUMMARY = _fields(
    "store_name",
    metrics=_fields(
        "store_id", "period", "currency", "revenue", "revenue_previous", "revenue_trend_pct", "order_count",
        "order_trend_pct", "gross_profit", "gross_margin_pct", "aov", "aov_trend_pct", "cost_coverage_pct",
        net=_fields("net_profit", "net_margin_pct"),
        coverage=_fields("store_ids", "history_status", "window_complete", "currency", "source_currencies"),
        top_skus=_fields("sku", "title", "revenue", "units", "revenue_share", "image_url"),
    ),
    timeseries=_fields(points=_fields("period_start", "revenue")),
)

_ATTENTION = _fields(
    summary=_fields(
        "status", "in_app_offers", "ops_as_of", "degraded_blocks",
        attention=_fields(
            "kind", "severity", "title", "detail", "store_name", "amount", "currency", "deadline_at",
            "days_overdue", "target_id", "target_kind", "open_url",
        ),
        metrics=_fields(
            "available", "currency", "revenue", "revenue_trend_pct", "profit", "margin_pct", "orders",
            "orders_trend_pct", "ad_spend", "roas",
        ),
    ),
)

_LISTINGS = _fields(
    "filters",
    "sole_match",
    stores=_STORE,
    listings=_fields(
        "total",
        items=_fields(
            "listing_id", "sales_channel_id", "platform", "title", "image_url", "price_min", "price_max",
            "currency", "total_quantity", "variation_count", "sale_state", "statuses",
        ),
    ),
    listing=_fields(
        "title", "image_url", "images", "videos", "sales_channel_id", "platform", "url", "price", "currency",
        "quantity", "status", "sale_state", "last_seen_at", "product_id", "group_id",
        sale_blockers=_fields("code", "message"),
    ),
    group=_fields(
        "listing_id", "product_id", "sales_channel_id", "platform", "title", "image_url", "images", "videos",
        "url", "currency", "price_min", "price_max", "total_quantity", "statuses", "sale_state", "last_seen_at",
        variations=_fields("variation_id", "options", "sku", "price", "quantity", "sale_state"),
        problems=_PROBLEM,
    ),
    problems=_fields(items=_PROBLEM),
    elsewhere=_fields(
        items=_fields(
            "listing_id", "sales_channel_id", "platform", "title", "price_min", "price_max", "currency",
            "sale_state", "statuses",
        )
    ),
)

_COSTS = ("purchase_price", "shipping_cost", "landed_cost", "purchase_currency", "shipping_quotes")
_PRODUCTS = _fields(
    "filters",
    "sole_match",
    products=_fields(
        "total",
        items=_fields(
            "id", "name", "image_url", "status", "supplier_provider", "supplier_name", "purchase_price_min",
            "purchase_price_max", "purchase_currency", "total_stock",
        ),
    ),
    product=_fields(
        "id", "name", "images", "status", "supplier_provider", "supplier_name", "supplier_product_url",
        "supplier_price_unconfirmed", "supplier_stock_unconfirmed", "last_supplier_stock_check_at",
        "last_supplier_price_check_at",
        category=_fields("leaf"),
        variations=_fields("sku", "name", "attributes", "available_quantity", *_COSTS),
        variation_common=_fields(*_COSTS),
    ),
    listings=_fields(
        items=_fields(
            "listing_id", "sales_channel_id", "platform", "price_min", "price_max", "currency", "total_quantity",
            "statuses", "sale_state", "sale_blocker_codes", "url",
        )
    ),
    problems=_fields(items={**_PROBLEM, "sales_channel_id": True}),
    stores=_STORE,
)

_AD_METRICS = _fields("spend", "conversion_value", "roas", "clicks", "currency")
_ADS = _fields(
    overview=_fields(
        "window_days",
        totals=_fields("currency", metrics=_AD_METRICS),
        accounts=_fields(
            "metrics", "metrics_window_days", "campaigns_total", account=_fields("display_name", "status")
        ),
    ),
    campaigns=_fields(
        items=_fields(
            "id", "external_id", "name", "status", "platform", "daily_budget", "bid_percentage", "manage_url",
            "delivery_reasons", "metrics_window_days",
            metrics=_AD_METRICS,
            review=_fields("disapproved", "in_review"),
            account=_fields("id", "platform", "platform_account_id", "display_name"),
        )
    ),
)

_CONNECTIONS = _fields(
    "filters",
    integrations=_fields(
        "kind",
        "display_name",
        connections=_fields(
            "id", "name", "custom_name", "status", "health_error", "fix_url", "connected_at",
            setup_warning=_fields("message", "how_to_fix"),
        ),
    ),
)

_APPROVAL = _fields(
    "pending_count",
    request=_fields(
        "id", "title", "summary", "description", "status", "mode", "cta_label", "created_at", "deadline",
        "blocking",
        # What the owner is deciding on — an email's recipients and text included — is the card.
        details=_fields("label", "value", "type", "url"),
        options=_fields("id", "label"),
        execution=_fields("handler", "status", "message"),
    ),
)

_MEDIA = _fields(
    "filters",
    "asked",
    library=_fields(
        "next", files=_fields("id", "category", "filename", "download_url"), totals=_fields("image", "video")
    ),
    jobs=_fields("id", "kind", "status", "prompt", "model", "params", "photos", "result_url", "error", "created_at"),
)

_MEDIA_STUDIO = _fields(
    "draft",
    "can_upload",
    recent_images=_fields("download_url", "filename"),
    models=_fields(
        tasks=_fields(
            "task",
            "max_references",
            tiers=_fields("tier", "model"),
            models=_fields(
                "id", "name", "platform_name", "kind", "unit", "price_credits", "clip_seconds",
                "price_credits_per_clip", "notes", "tier", "sound", "is_default",
                choice_prices=_fields("param", "choice", "price_credits"),
                params=_fields(
                    "name", "label", "kind", "choices", "minimum", "maximum", "default", "help", "choice_labels"
                ),
                rules=_fields("when", "equals", "then", "allowed", "message"),
            ),
        )
    ),
)

#: Card tool -> the fields its screen reads. A button's tool answers its card's screen.
_SPECS: Mapping[str, Spec] = {
    "sellerclaw_orders": _ORDERS,
    "sellerclaw_store_summary": _STORE_SUMMARY,
    "sellerclaw_attention": _ATTENTION,
    "sellerclaw_listings": _LISTINGS,
    "sellerclaw_products": _PRODUCTS,
    "sellerclaw_ads": _ADS,
    "sellerclaw_connections": _CONNECTIONS,
    "sellerclaw_approval": _APPROVAL,
    "sellerclaw_approval_decide": _APPROVAL,
    "sellerclaw_media": _MEDIA,
    "sellerclaw_media_generate": _MEDIA,
    "sellerclaw_media_studio": _MEDIA_STUDIO,
    "sellerclaw_media_set_default": _MEDIA_STUDIO,
}

_FAILED_JOB = "The generation failed; try again or pick another model."


def _pick(value: Any, spec: Any) -> Any:
    if spec is True:
        return value
    if isinstance(value, list):
        return [_pick(item, spec) for item in value]
    if isinstance(value, Mapping):
        return {key: _pick(value[key], inner) for key, inner in spec.items() if key in value}
    return value


def _plain_failures(payload: dict[str, Any]) -> dict[str, Any]:
    """A failed media job reads as failed — not as the provider's HTTP status and model names."""
    jobs = payload.get("jobs")
    if not isinstance(jobs, list):
        return payload
    return {
        **payload,
        "jobs": [
            {**job, "error": _FAILED_JOB} if isinstance(job, Mapping) and job.get("error") else job for job in jobs
        ],
    }


def shape_payload(tool: str, payload: dict[str, Any]) -> dict[str, Any]:
    """The payload ``tool`` hands ChatGPT: what its card draws. A paused account keeps its paywall."""
    if "paywall" in payload:
        return payload
    if tool == "sellerclaw_billing":
        return {"billing": credits_only(payload.get("billing"))}
    spec = _SPECS.get(tool)
    shaped = _pick(payload, spec) if spec is not None else payload
    return without(_plain_failures(shaped))
