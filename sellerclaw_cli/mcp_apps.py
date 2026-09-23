"""The interactive SellerClaw screens a client can render instead of printing our JSON.

MCP Apps (``io.modelcontextprotocol/ui``) lets a tool say "draw my answer with *this* document".
The host loads the document into a sandboxed iframe, hands it the tool's result, and lets it call
back for more. SellerClaw ships three: the store summary, the order board, and the approval card.

Where the documents come from
-----------------------------
Not from this package. They are built in the SellerClaw web app and served from its own origin, and
this server fetches one when a client reads the resource. That is deliberate:

* the documents reference hashed chunk files, and a UI deploy replaces the whole bundle — a copy
  vendored into a wheel would keep naming chunks that no longer exist and render a blank frame;
* the screens are iterated in the web app's repository, and a CSS fix must not cost a release here.

The cost is a dependency on that origin being reachable, and a fetch on a cold cache. Both are
answered below: the document is cached for :data:`_DOCUMENT_TTL_SECONDS`, and a failure is a plain
refusal rather than a stand-in document — a card that renders "sorry" occupies the conversation and
explains nothing, while an error leaves the tool's own text answer in place.

The one invariant
-----------------
:data:`APPS_BASE_ENV` names the origin this server fetches from *and* the first entry of the
resource's CSP. It must be the same origin the documents were built against (``VITE_MCP_APPS_BASE``
in that deployment's web build). Serving a staging document while declaring the production origin
renders an empty card and reports nothing anywhere.
"""

from __future__ import annotations

import os
import threading
import time
from collections.abc import Callable, Iterator, Sequence
from contextlib import contextmanager
from typing import Any

from sellerclaw_cli._client import DEFAULT_TIMEOUT_SECONDS, Client
from sellerclaw_cli._errors import CliError

#: Where the built screens are served from. The default is production, so a plain
#: ``pip install 'sellerclaw-cli[mcp]'`` gets working screens with nothing to configure.
APPS_BASE_ENV = "SELLERCLAW_MCP_APPS_BASE"
DEFAULT_APPS_BASE = "https://app.sellerclaw.ai"

#: ``<screen>`` is both the document's name on that origin and the ``ui://`` resource's.
SCREENS = ("store-summary", "orders", "approval")

#: How long a fetched document is reused. Not forever: the hosted app keeps a machine warm, so a
#: process outlives several UI deploys, and a permanently cached document would go on naming chunk
#: files that the newest deploy deleted. Fifteen minutes is longer than a conversation and short
#: enough that a deploy heals itself without anyone restarting anything.
_DOCUMENT_TTL_SECONDS = 900.0
DOCUMENT_CACHE_TTL_MS = int(_DOCUMENT_TTL_SECONDS * 1000)

_DOCUMENT_FETCH_TIMEOUT_SECONDS = 10.0

#: How many pending requests the approval card asks for when counting what else is waiting.
#: The Agent API's own maximum; see ``_read_approval`` for what happens at the ceiling.
_PENDING_CAP = 200

#: Everything the screens may load, in one list because the host builds ``script-src``,
#: ``style-src``, ``img-src``, ``font-src`` and ``media-src`` from it — which is why it cannot be
#: widened to ``https://*`` for the sake of a few product photos.
#:
#: Our own origin carries the screens' JavaScript and stylesheet. The rest are the hosts a
#: marketplace serves product images from, which is the only outside content a screen loads
#: (the best-sellers rows on the store summary). A seller whose photos live on their own domain —
#: a self-hosted WooCommerce shop, a custom-domain storefront — is not covered and cannot be
#: without opening script loading to the whole web; the screen draws those rows without a
#: thumbnail, which is what it already does for an image that fails for any other reason.
_IMAGE_CDN_DOMAINS = (
    "https://i.ebayimg.com",
    "https://*.ebayimg.com",
    "https://cdn.shopify.com",
    "https://*.myshopify.com",
    "https://m.media-amazon.com",
    "https://*.media-amazon.com",
    "https://i.etsystatic.com",
    "https://i5.walmartimages.com",
    "https://*.walmartimages.com",
    "https://static.wixstatic.com",
    "https://cdn11.bigcommerce.com",
    "https://*.bigcommerce.com",
    "https://*.tiktokcdn.com",
    "https://media.sellercart.shop",
    "https://media.stg.sellercart.shop",
)


def apps_base() -> str:
    """The origin the screens are served from, without a trailing slash."""
    return (os.environ.get(APPS_BASE_ENV, "").strip() or DEFAULT_APPS_BASE).rstrip("/")


def resource_uri(screen: str) -> str:
    return f"ui://sellerclaw/{screen}.html"


def document_url(screen: str) -> str:
    return f"{apps_base()}/mcp-apps/{screen}.html"


# ---------------------------------------------------------------------------------------------
# The documents
# ---------------------------------------------------------------------------------------------

#: ``{url: (fetched_at, html)}``, guarded because the SDK reads resources on a worker thread and a
#: plain dict would be mutated from several at once. The lock covers the lookup and the store, not
#: the fetch in between: two clients opening the same card on a cold cache do both fetch, which
#: costs one extra request against holding every reader behind one ten-second timeout.
_documents: dict[str, tuple[float, str]] = {}
_documents_lock = threading.Lock()


def _screen_fault(html: str, screen: str, base: str) -> str | None:
    """Why this document cannot be served as the screen, or ``None`` if it can.

    Two different failures, and neither announces itself:

    * **Not the screen at all.** A missing path is a 404, but a proxy, a captive portal or a
      misconfigured origin can answer 200 with anything — and a document without the entry script
      is a blank card with nothing in the logs. This also catches a web build that stopped emitting
      the entry under the name the resource promises.
    * **Built for somewhere else.** The host inlines this document into a sandbox whose origin is
      opaque, so a root-relative ``src`` resolves against nothing. A build that did not bake in an
      absolute origin — or baked in a different one than this server names in the CSP — renders an
      empty frame and reports nothing anywhere. It is the single most likely way to get this wrong,
      because both halves look healthy on their own.
    """
    entry = f"/mcp-apps/{screen}.js"
    if '<script type="module"' not in html or entry not in html:
        return f"did not answer with the built {screen} screen"
    if f"{base}{entry}" not in html:
        return (
            f"was built for a different origin than {base} — its scripts are addressed relatively "
            f"or elsewhere, and inside the sandbox they would resolve to nothing"
        )
    return None


def fetch_document(screen: str) -> str:
    """The built document for one screen, freshly fetched or from the short-lived cache.

    Raises:
        ResourceError: the origin refused, was unreachable, or answered with something that is not
            the screen. Never a stand-in document: the client reports that the app did not load and
            the tool's own text answer stays in the conversation, which is more than a card saying
            "sorry" would leave.
    """
    import httpx
    from mcp.server.mcpserver.exceptions import ResourceError

    base = apps_base()
    url = f"{base}/mcp-apps/{screen}.html"
    now = time.monotonic()
    with _documents_lock:
        cached = _documents.get(url)
        if cached is not None and now - cached[0] < _DOCUMENT_TTL_SECONDS:
            return cached[1]

    try:
        response = httpx.get(
            url,
            timeout=_DOCUMENT_FETCH_TIMEOUT_SECONDS,
            trust_env=False,
            follow_redirects=True,
        )
    except httpx.HTTPError as exc:
        raise ResourceError(f"Could not reach the SellerClaw screen at {url}: {exc}") from exc
    if response.status_code != 200:
        raise ResourceError(
            f"The SellerClaw screen at {url} answered {response.status_code}."
        )
    html = response.text
    fault = _screen_fault(html, screen, base)
    if fault is not None:
        raise ResourceError(
            f"{url} {fault}. Check that {APPS_BASE_ENV} names the deployment that serves these "
            f"screens, and that its web build set VITE_MCP_APPS_BASE to the same origin."
        )

    # Only a good answer is remembered: a thirty-second outage must not blind the server for the
    # whole cache window.
    with _documents_lock:
        _documents[url] = (time.monotonic(), html)
    return html


def _forget_documents() -> None:
    """Drop the cache. For tests; nothing in the server calls it."""
    with _documents_lock:
        _documents.clear()


# ---------------------------------------------------------------------------------------------
# Reading the Agent API
# ---------------------------------------------------------------------------------------------

#: A screen re-reads its whole payload after acting, so the tools are chattier than one call each.
#: These budgets are the Agent API's own: analytics can genuinely take a while on a cold mirror.
_READ_TIMEOUT_SECONDS = 60.0

ClientFactory = Callable[[float], Client]


def _query(**params: Any) -> dict[str, Any]:
    """Query parameters with the unset ones dropped.

    The screens send their filters as ``null`` when they mean "no filter", and a literal
    ``status=None`` on the wire is a 422 rather than the whole board.
    """
    return {key: value for key, value in params.items() if value is not None}


def _one_or_many(store: str | list[str] | None) -> tuple[str, list[str]]:
    """The store selection as the Agent API takes it: one in the path, the rest repeated in query.

    ``all`` when nothing was named — the screens open on everything the account has, and narrow
    from there.
    """
    if store is None:
        return "all", []
    if isinstance(store, str):
        return store, []
    if not store:
        return "all", []
    return store[0], list(store[1:])


def _store_display_name(client: Client, store: str) -> str | None:
    """The owner's own name for a store, when the answer is about exactly one.

    Turns the card's title from "Store summary" into the shop's name. Best-effort on purpose: the
    summary is the point, and a store whose row cannot be read should not cost the whole card.
    """
    try:
        channel = client.request("GET", f"/agent/sales-channels/{store}", read_only=True)
    except CliError:
        # Only the API saying no, or not answering. A failure of ours belongs in the open, where
        # the refusal guard turns it into something the card can show.
        return None
    name = (channel or {}).get("display_name") if isinstance(channel, dict) else None
    return name or None


# ---------------------------------------------------------------------------------------------
# What the model is told
# ---------------------------------------------------------------------------------------------
#
# The card carries the whole payload; the model gets a couple of sentences. Two reasons, and the
# second is the one that matters: an order board with fifty orders and their line items is tens of
# kilobytes of context spent on something the person is looking at, and the model only needs enough
# to talk about it. The same rule the screens follow applies here — a figure that is not there is
# left out, never rendered as zero.


#: What the order board treats as "still owed to the buyer" — the same set the screen leads with.
_AWAITING_SHIPMENT_STATUSES = frozenset(
    {"new", "pending_approval", "approved", "purchasing", "purchased", "awaiting_payment"}
)

#: How every summary ends. Deliberately conditional: a client that did not negotiate MCP Apps gets
#: these same answers with no card at all, and telling its model "the owner is looking at it" would
#: be a plain untruth. The full payload is in the structured result either way.
_SHOWN_TO_THE_OWNER = (
    "If this client shows SellerClaw cards, the owner is looking at this one and can act on it "
    "there; the full figures are in the structured result."
)


def _money(value: Any, currency: str | None) -> str | None:
    if value is None:
        return None
    return f"{value} {currency}" if currency else str(value)


def _summarize_store_summary(payload: dict[str, Any]) -> str:
    metrics = payload.get("metrics") or {}
    currency = metrics.get("currency")
    # No name means the answer covers more than one shop, or a store row we could not read.
    # "The store" would put several shops' figures under a singular that names none of them.
    name = payload.get("store_name")
    period = metrics.get("period") or "the period"
    lines = [f"{name}, {period}." if name else f"Store summary, {period}."]

    revenue = _money(metrics.get("revenue"), currency)
    if revenue is not None:
        orders = metrics.get("order_count")
        lines.append(
            f"Revenue {revenue} across {orders} orders." if orders is not None
            else f"Revenue {revenue}."
        )
    net = (metrics.get("net") or {}).get("net_profit")
    profit = _money(net, currency) or _money(metrics.get("gross_profit"), currency)
    if profit is not None:
        lines.append(f"Profit {profit}.")
    lines.append(_SHOWN_TO_THE_OWNER)
    return " ".join(lines)


def _summarize_orders(payload: dict[str, Any]) -> str:
    overview = payload.get("overview") or {}
    shown = len((payload.get("orders") or {}).get("items") or [])
    total = overview.get("total")
    lines = [f"Showing {shown} orders." if total is None else f"Showing {shown} of {total} orders."]
    by_status = overview.get("by_status") or {}
    waiting = sum(
        count for status, count in by_status.items() if status in _AWAITING_SHIPMENT_STATUSES
    )
    if waiting:
        # Said as "across the account" because that is what it is: the overview counts every order,
        # while the rows above may be one filtered page of them.
        lines.append(f"{waiting} across the account are waiting to ship.")
    lines.append(_SHOWN_TO_THE_OWNER)
    return " ".join(lines)


def _summarize_approval(payload: dict[str, Any]) -> str:
    request = payload.get("request") or {}
    title = request.get("title") or "a request"
    status = request.get("status")
    if status and status != "pending":
        return f'"{title}" is already {status}.'
    lines = [f'Waiting on the owner: "{title}".']
    waiting = payload.get("pending_count")
    if waiting:
        lines.append(f"{waiting} more also waiting.")
    lines.append(
        "Only they can answer it: you have no tool that closes it. If this client shows the "
        "card, they press the button on it; if they answer you in words instead, close it with "
        "`action-requests confirm` quoting what they said. Never decide for them."
    )
    return " ".join(lines)


def _result(payload: dict[str, Any], summary: str) -> Any:
    from mcp.types import CallToolResult, TextContent

    return CallToolResult(
        content=[TextContent(type="text", text=summary)],
        structured_content=payload,
    )


@contextmanager
def _refusals_in_their_own_words() -> Iterator[None]:
    """Let the Agent API's refusal reach the card instead of a generic failure.

    The SDK repeats the message of a ``ToolError`` to the client and replaces anything else with
    "Error executing tool <name>". That difference is the whole value of some of these answers: a
    channel refusing an order tells the seller which command would create the shipment first, and
    an approval refused for a caller the owner has not trusted tells them where to grant it.
    Swallowing those into a generic failure leaves a screen with a red box and no way forward.
    """
    from mcp.server.mcpserver.exceptions import ToolError

    try:
        yield
    except CliError as exc:
        raise ToolError(str(exc)) from exc


# ---------------------------------------------------------------------------------------------
# The extension
# ---------------------------------------------------------------------------------------------

_STORE_SUMMARY_DESC = """\
How a store is doing, as an interactive card the owner can act on: revenue, orders, average order
value, profit and margin, with a revenue chart, best sellers and category mix in the full view. They
can switch the period on the card itself.

Prefer this over running an analytics command for the same question — it answers it and shows it.
The text you get back is a summary for you; the owner is reading the card.

`store` takes one store id or several; omit it for every store on the account. `period` is one of
last_7d, last_30d, last_90d, this_month, last_month, this_year.\
"""

_ORDERS_DESC = """\
The order board as an interactive card: who is waiting, for how long, and for how much, oldest wait
first. The owner can filter by status and mark an order shipped on the card itself.

Prefer this over running an orders command for the same question. Pass `status` to open on one
status; omit it for the whole board.\
"""

_ORDER_MARK_SHIPPED_DESC = """\
Close one order as shipped and hand back the board. Records a shipment that already exists on the
sales channel — it does not create one there.

Pass the `status` the board is currently filtered to, so the answer comes back through the same
filter the person is looking at.\
"""

_APPROVAL_DESC = """\
Show one thing waiting on the owner as an interactive card: what will happen, the details behind it,
and the buttons to approve or decline.

The owner answers on the card. Do not decide for them, and do not ask them to type the answer to you
instead — you have no way to close the request yourself.\
"""

_APPROVAL_DECIDE_DESC = """\
Record the owner's press on the approval card and hand the card back.\
"""


def build_extension(client_for_tool: ClientFactory) -> Any:
    """The MCP Apps extension: three screens and the five tools bound to them.

    ``client_for_tool`` builds an Agent API client carrying whoever is on the other end of this
    request — passed in rather than imported so this module never has to know how the server
    authenticates.

    Registration order matters: the SDK checks every tool's ``resource_uri`` against the registered
    resources when the server is constructed, so a screen that is never registered fails at startup
    instead of on someone's card.
    """
    from mcp.server.apps import Apps, ResourceCsp
    from mcp.server.mcpserver.resources import FunctionResource
    from mcp.types import ToolAnnotations

    apps = Apps()
    csp = ResourceCsp(
        # The screens make no requests of their own: everything they need arrives from the host,
        # and everything they do goes back through it as a tool call. Stated as an empty list
        # rather than left unset so the intent is on the record.
        connect_domains=[],
        resource_domains=[apps_base(), *_IMAGE_CDN_DOMAINS],
    )
    for screen in SCREENS:
        apps.add_resource(
            FunctionResource(
                uri=resource_uri(screen),
                name=f"sellerclaw-{screen}",
                title=f"SellerClaw {screen.replace('-', ' ')}",
                description=f"The interactive SellerClaw {screen.replace('-', ' ')} screen.",
                mime_type="text/html;profile=mcp-app",
                # ``FunctionResource`` calls this at read time, on a worker thread — the fetch never
                # blocks the event loop, and listing resources costs nothing.
                fn=lambda screen=screen: fetch_document(screen),  # type: ignore[misc]
                meta={
                    "ui": {
                        "csp": csp.model_dump(by_alias=True, exclude_none=True),
                        # The screens draw their own frame; a second one from the host would
                        # double it.
                        "prefersBorder": False,
                    }
                },
            )
        )

    def _reads_only(title: str) -> ToolAnnotations:
        return ToolAnnotations(
            title=title,
            read_only_hint=True,
            destructive_hint=False,
            idempotent_hint=True,
            # Unlike the discovery tools, these reach the owner's account.
            open_world_hint=True,
        )

    def _acts(title: str) -> ToolAnnotations:
        return ToolAnnotations(
            title=title,
            read_only_hint=False,
            # Neither of these destroys anything, and repeating one is refused rather than doubled:
            # a shipped order is already shipped, an answered request is already answered.
            destructive_hint=False,
            idempotent_hint=True,
            open_world_hint=True,
        )

    def _read_store_summary(
        client: Client, store: str | list[str] | None, period: str | None
    ) -> dict[str, Any]:
        primary, extra = _one_or_many(store)
        window = _query(period=period)
        metrics = client.request(
            "GET",
            f"/agent/analytics/stores/{primary}/metrics",
            # Marketplace fees are what turns "revenue" into money the owner keeps; the card drops
            # the profit tiles rather than showing a gross figure as if it were net.
            params={**window, "with_fees": True, **({"store": extra} if extra else {})},
            read_only=True,
        )
        timeseries = client.request(
            "GET",
            f"/agent/analytics/stores/{primary}/timeseries",
            params={**window, "granularity": "week", **({"store": extra} if extra else {})},
            read_only=True,
        )
        payload: dict[str, Any] = {"metrics": metrics, "timeseries": timeseries}
        if not extra and primary != "all":
            name = _store_display_name(client, primary)
            if name is not None:
                payload["store_name"] = name
        return payload

    def _read_orders(client: Client, status: str | None, limit: int | None) -> dict[str, Any]:
        return {
            "orders": client.request(
                "GET", "/agent/orders", params=_query(status=status, limit=limit), read_only=True
            ),
            "overview": client.request("GET", "/agent/orders/overview", read_only=True),
        }

    def _read_approval(
        client: Client, request_id: str, known: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        # ``known`` is the row the write already returned. Re-reading it would cost a round trip to
        # learn what we were just told, and would let a change landing in between show the owner a
        # card that disagrees with the press they just made.
        payload: dict[str, Any] = {
            "request": known
            if known is not None
            else client.request(
                "GET", f"/agent/goals/action-requests/{request_id}", read_only=True
            )
        }
        pending = client.request(
            "GET",
            "/agent/goals/action-requests",
            params={"status": "pending", "limit": _PENDING_CAP},
            read_only=True,
        )
        items = (pending or {}).get("items") or []
        # At the cap the real number is unknown, and a card saying "3 more waiting" when there are
        # two hundred is worse than one that says nothing.
        if len(items) < _PENDING_CAP:
            payload["pending_count"] = len([item for item in items if item.get("id") != request_id])
        return payload

    @apps.tool(
        resource_uri=resource_uri("store-summary"),
        visibility=["model", "app"],
        name="sellerclaw_store_summary",
        title="Show the store summary",
        description=_STORE_SUMMARY_DESC,
        annotations=_reads_only("Show the store summary"),
    )
    def sellerclaw_store_summary(
        store: str | list[str] | None = None, period: str | None = None
    ) -> Any:
        with _refusals_in_their_own_words(), client_for_tool(_READ_TIMEOUT_SECONDS) as client:
            payload = _read_store_summary(client, store, period)
        return _result(payload, _summarize_store_summary(payload))

    @apps.tool(
        resource_uri=resource_uri("orders"),
        visibility=["model", "app"],
        name="sellerclaw_orders",
        title="Show the order board",
        description=_ORDERS_DESC,
        annotations=_reads_only("Show the order board"),
    )
    def sellerclaw_orders(status: str | None = None, limit: int | None = None) -> Any:
        with _refusals_in_their_own_words(), client_for_tool(DEFAULT_TIMEOUT_SECONDS) as client:
            payload = _read_orders(client, status, limit)
        return _result(payload, _summarize_orders(payload))

    @apps.tool(
        resource_uri=resource_uri("orders"),
        # The board's own button, not a second way for a model to close an order: that verb already
        # exists on ``sellerclaw_run`` with its full schema and the channel rule spelled out.
        visibility=["app"],
        name="sellerclaw_order_mark_shipped",
        title="Mark an order shipped",
        description=_ORDER_MARK_SHIPPED_DESC,
        annotations=_acts("Mark an order shipped"),
    )
    def sellerclaw_order_mark_shipped(
        order: str, status: str | None = None, limit: int | None = None
    ) -> Any:
        with _refusals_in_their_own_words(), client_for_tool(DEFAULT_TIMEOUT_SECONDS) as client:
            # A refusal here is the channel saying it holds no shipment, and its wording names the
            # command that would create one. Let it travel: the board shows it verbatim.
            client.request("POST", f"/agent/orders/{order}/shipped")
            # Re-read through the board's *own* filter. Answering with everything would leave the
            # card showing every status under a chip that still says "awaiting shipment".
            payload = _read_orders(client, status, limit)
        return _result(payload, _summarize_orders(payload))

    @apps.tool(
        resource_uri=resource_uri("approval"),
        visibility=["model", "app"],
        name="sellerclaw_approval",
        title="Show a request waiting on the owner",
        description=_APPROVAL_DESC,
        annotations=_reads_only("Show a request waiting on the owner"),
    )
    def sellerclaw_approval(request: str) -> Any:
        with _refusals_in_their_own_words(), client_for_tool(DEFAULT_TIMEOUT_SECONDS) as client:
            payload = _read_approval(client, request)
        return _result(payload, _summarize_approval(payload))

    @apps.tool(
        resource_uri=resource_uri("approval"),
        # Only the card may call this, and that is the whole point: the owner's answer has to come
        # from the owner pressing the button, never from a model deciding on their behalf. The
        # cloud does not take this on trust — it checks the caller's own standing too — but nothing
        # here should make it look callable.
        visibility=["app"],
        name="sellerclaw_approval_decide",
        title="Record the owner's answer",
        description=_APPROVAL_DECIDE_DESC,
        annotations=_acts("Record the owner's answer"),
    )
    def sellerclaw_approval_decide(
        request: str, decision: str, option: str | None = None
    ) -> Any:
        with _refusals_in_their_own_words(), client_for_tool(DEFAULT_TIMEOUT_SECONDS) as client:
            answered = client.request(
                "POST",
                f"/agent/goals/action-requests/{request}/decide",
                json=_query(decision=decision, option_id=option),
            )
            payload = _read_approval(client, request, known=answered)
        return _result(payload, _summarize_approval(payload))

    return apps



def tool_names() -> Sequence[str]:
    """The tools this extension adds, for the server's own tests and docs."""
    return (
        "sellerclaw_store_summary",
        "sellerclaw_orders",
        "sellerclaw_order_mark_shipped",
        "sellerclaw_approval",
        "sellerclaw_approval_decide",
    )
