"""Requests waiting on the owner, how the business is doing, and how a storefront looks to search."""

from __future__ import annotations

from typing import Any

from sellerclaw_cli._errors import UserInputError
from sellerclaw_cli.chatgpt._action import Param, action, execute, runs

_REQUEST = Param("request_id", "string", "The request's id.", required=True, to="path")
_ANALYTICS_STORE = Param(
    "store_id", "string", "A store's id from list_connections, or all for every store.", required=True, to="path"
)
#: The period every analytics tool takes, and the store selection beside it.
_WINDOW = (
    Param(
        "period", "string", "Window ending now.", to="flag",
        choices=("last_7d", "last_30d", "last_90d", "this_month", "last_month", "this_year"),
    ),
    Param("week", "integer", "Instead of period, a completed week: 0 = last week, 1 = the one before.", to="flag"),
    Param("month", "integer", "Instead of period, a completed month: 0 = last month, 1 = the one before.", to="flag"),
    Param("date_from", "string", "Instead of period, YYYY-MM-DD; with date_to.", to="flag"),
    Param("date_to", "string", "YYYY-MM-DD, included.", to="flag"),
    Param("store", "array", "More stores to fold into the same answer.", items="string", to="flag"),
)
_CURRENCY = Param("currency", "string", "Show money in this currency, e.g. USD.", to="flag")


def _audit_site(values: dict[str, Any]) -> Any:
    url = values["url"]
    speed = {"url": url, **({"strategy": values["strategy"]} if values.get("strategy") else {})}
    return {
        "speed": execute("store-audit", "pagespeed", None, None, speed),
        "seo": execute("store-audit", "onpage", None, None, {"url": url}),
    }


def _ai_visibility(values: dict[str, Any]) -> Any:
    place = {k: values[k] for k in ("location_code", "language_code") if values.get(k)}
    if values.get("prompts"):
        body = {"prompts": list(values["prompts"]), **place}
        if values.get("engines"):
            body["engines"] = list(values["engines"])
        return execute("store-audit", "ai-answers", None, None, body)
    if not values.get("target"):
        raise UserInputError("pass prompts (buyer questions) or target (a brand, store domain or niche).")
    return execute("store-audit", "ai-mentions", None, None, {"target": values["target"], **place})


ACTIONS = (
    action(
        "list_action_requests",
        "List action requests",
        "Requests waiting on the owner — to approve, pay, connect or provide something — newest "
        "first, with their status.",
        (
            Param("status", "string", "Only this state; pending = still waiting.", to="flag",
                  choices=("pending", "resolved", "rejected", "cancelled")),
            Param("limit", "integer", "Most requests.", to="flag"),
        ),
        runs("action-requests", "list"),
        read_only=True,
    ),
    action(
        "answer_action_request",
        "Answer an action request",
        "Close a request with the answer the owner gave in this conversation, quoted word for word. "
        "Only for a plain yes or no they actually said; anything else is refused.",
        (_REQUEST, Param("quote", "string", "The owner's own words, one sentence.", required=True)),
        runs("action-requests", "confirm"),
        read_only=False,
    ),
    action(
        "cancel_action_request",
        "Cancel an action request",
        "Withdraw a request that is no longer needed.",
        (_REQUEST,),
        runs("action-requests", "cancel"),
        read_only=False,
        destructive=True,
    ),
    action(
        "get_store_metrics",
        "Get store metrics",
        "Sales and profit for a period: revenue, orders, average order value and the change against "
        "the previous period, profit and margin, top and sleeping SKUs, sales by category. "
        "coverage.window_complete false means the history is partial.",
        (
            _ANALYTICS_STORE,
            *_WINDOW,
            _CURRENCY,
            Param("top", "integer", "How many top SKUs.", to="flag"),
            Param("with_fees", "boolean", "Also subtract marketplace fees (slower).", to="flag"),
        ),
        runs("analytics", "metrics"),
        read_only=True,
    ),
    action(
        "get_sales_timeseries",
        "Get sales over time",
        "Revenue, orders and units by day, week or month over a period, oldest first.",
        (
            _ANALYTICS_STORE,
            *_WINDOW,
            _CURRENCY,
            Param("granularity", "string", "Bucket size.", to="flag", choices=("day", "week", "month")),
            Param("buckets", "integer", "A fixed number of buckets, e.g. 12 months.", to="flag"),
        ),
        runs("analytics", "timeseries"),
        read_only=True,
    ),
    action(
        "get_inventory_health",
        "Get inventory health",
        "What is out of stock or running out while still listed, the revenue it costs, and how much "
        "to reorder given sales and the store's restock lead time.",
        (_ANALYTICS_STORE, *_WINDOW, _CURRENCY, Param("top", "integer", "Rows per list.", to="flag")),
        runs("analytics", "inventory"),
        read_only=True,
    ),
    action(
        "get_order_geography",
        "Get order geography",
        "Where orders go: each country's share and its change against the previous period, and the "
        "main country's regions.",
        (_ANALYTICS_STORE, *_WINDOW),
        runs("analytics", "geography"),
        read_only=True,
    ),
    action(
        "audit_store_site",
        "Audit a storefront page",
        "Speed scores and Core Web Vitals, and an on-page SEO audit (meta tags, links, checks, "
        "score) of a storefront page.",
        (
            Param("url", "string", "The page's URL.", required=True),
            Param("strategy", "string", "Device for the speed test.", choices=("mobile", "desktop")),
        ),
        _audit_site,
        read_only=True,
        open_world=True,
    ),
    action(
        "check_ai_visibility",
        "Check AI visibility",
        "How AI assistants answer buyer-style questions and whether the store shows up, or how they "
        "mention a brand, domain or niche. Uses credits.",
        (
            Param("prompts", "array", "1-5 buyer-style questions to ask the assistants.", items="string"),
            Param("target", "string", "Instead: a brand, domain or niche to look up."),
            Param("engines", "array", "Which assistants (default ChatGPT and Perplexity).", items="string"),
            Param("location_code", "integer", "Location code, e.g. 2840 = United States."),
            Param("language_code", "string", "Language code, e.g. en."),
        ),
        _ai_visibility,
        read_only=True,
        open_world=True,
    ),
)
