"""The interactive screens: how they are wired, where their HTML comes from, what they call.

Three things here are worth a test each and would fail silently otherwise:

* **Visibility.** ``sellerclaw_approval_decide`` exists so the *owner* can answer, on a card they
  are looking at. If it were ever offered to the model, the model could approve on their behalf.
* **The document.** It is fetched from the web app at read time, so every way that can go wrong —
  unreachable, 404, a proxy's own page, a build made for another origin — has to come back as a
  refusal naming the fix, and not as a blank card.
* **What each tool asks the Agent API.** A screen redraws itself from these answers; a dropped
  filter or a missing second call is a board that quietly shows the wrong thing.
"""

from __future__ import annotations

import asyncio
import time
from typing import Any

import httpx
import pytest
import respx
from mcp.server.mcpserver.exceptions import ResourceError, ToolError

from sellerclaw_cli import mcp_apps
from sellerclaw_cli.cli import app  # noqa: F401 — importing registers every group into REGISTRY
from sellerclaw_cli.mcp_server import build_http_server, build_server

pytestmark = pytest.mark.unit

APPS_BASE = "https://app.test.sellerclaw.ai"
REQUEST_ID = "44444444-4444-4444-8444-444444444444"
ORDER_ID = "22222222-2222-4222-8222-222222222222"
STORE_ID = "11111111-1111-4111-8111-111111111111"


def _document(screen: str, *, base: str = APPS_BASE) -> str:
    """What the web app's build actually emits, down to the absolute entry URL."""
    return (
        "<!doctype html><html><head>"
        f'<script type="module" crossorigin src="{base}/mcp-apps/{screen}.js"></script>'
        f'<link rel="stylesheet" href="{base}/mcp-apps/bridge.css">'
        "</head><body><div id='screen'></div></body></html>"
    )


@pytest.fixture(autouse=True)
def apps_base(monkeypatch: pytest.MonkeyPatch) -> str:
    monkeypatch.setenv(mcp_apps.APPS_BASE_ENV, APPS_BASE)
    # The cache is module state and outlives a test; a stale entry would make the next one pass
    # without ever reaching its mocked origin.
    mcp_apps._forget_documents()
    return APPS_BASE


@pytest.fixture
def env_pointing_at_fake_api(
    monkeypatch: pytest.MonkeyPatch,
    fake_api_url: str,
    fake_token: str,
) -> None:
    monkeypatch.setenv("SELLERCLAW_API_URL", fake_api_url)
    monkeypatch.setenv("SELLERCLAW_TOKEN", fake_token)


def _call(name: str, arguments: dict[str, Any]) -> Any:
    return asyncio.run(build_server().call_tool(name, arguments))


# --------------------------------------------------------------------------- wiring


@pytest.mark.parametrize(
    "builder",
    [
        pytest.param(build_server, id="stdio"),
        pytest.param(
            lambda: build_http_server(
                issuer_url="https://issuer.test", resource_url=None, api_url="https://api.test"
            ),
            id="hosted-http",
        ),
    ],
)
def test_both_ways_of_building_the_server_carry_the_screens(builder: Any) -> None:
    """Two constructors, one surface.

    An extension can only be passed when the server is built, so there is no shared step to add it
    to afterwards — the two call sites have to agree, and nothing but this would notice if the
    hosted one drifted into serving a surface with no cards in it.
    """
    server = builder()

    assert "io.modelcontextprotocol/ui" in server._lowlevel_server.extensions
    listed = {str(resource.uri) for resource in asyncio.run(server.list_resources())}
    assert listed == {
        "ui://sellerclaw/attention.html",
        "ui://sellerclaw/store-summary.html",
        "ui://sellerclaw/orders.html",
        "ui://sellerclaw/listings.html",
        "ui://sellerclaw/ads.html",
        "ui://sellerclaw/connections.html",
        "ui://sellerclaw/approval.html",
    }
    assert {tool.name for tool in asyncio.run(server.list_tools())} >= set(mcp_apps.tool_names())


def test_the_model_cannot_answer_an_approval_for_the_owner() -> None:
    """The safety claim of this whole feature, written down.

    Approving is the owner's act. The card is how they do it, and the tool behind the card is
    declared callable by the app alone — a model that never sees it cannot decide to spend their
    money. The cloud checks the caller's standing too, because visibility is a convention of
    whoever hosts the card rather than a boundary we own; this test guards the half that is ours.
    """
    by_name = {tool.name: tool for tool in asyncio.run(build_server().list_tools())}

    visibility = {
        name: (by_name[name].meta or {})["ui"]["visibility"] for name in mcp_apps.tool_names()
    }
    assert visibility == {
        "sellerclaw_attention": ["model", "app"],
        "sellerclaw_store_summary": ["model", "app"],
        "sellerclaw_orders": ["model", "app"],
        # The board's own button. The model already has this verb on sellerclaw_run, with the
        # channel rule spelled out in its description.
        "sellerclaw_order_mark_shipped": ["app"],
        "sellerclaw_listings": ["model", "app"],
        "sellerclaw_ads": ["model", "app"],
        "sellerclaw_connections": ["model", "app"],
        "sellerclaw_approval": ["model", "app"],
        "sellerclaw_approval_decide": ["app"],
    }


def test_the_cards_that_only_show_things_are_read_only() -> None:
    """Only two tools a card calls change anything, and both are the card's alone.

    Everything the new cards offer beyond reading is a request to Claude or a link to our website,
    so their tools must say they read — a client asking permission per write would otherwise put a
    confirmation in front of opening a list.
    """
    by_name = {tool.name: tool for tool in asyncio.run(build_server().list_tools())}

    writes = {
        name for name in mcp_apps.tool_names() if not by_name[name].annotations.read_only_hint
    }
    assert writes == {"sellerclaw_order_mark_shipped", "sellerclaw_approval_decide"}


def test_every_screen_tool_points_at_a_resource_that_exists() -> None:
    """A tool advertising a ``ui://`` that 404s renders nothing and explains nothing.

    The SDK refuses to build such a server at all, so reaching this assertion is most of the proof;
    it is spelled out because the failure it prevents is invisible from the outside.
    """
    server = build_server()
    registered = {str(resource.uri) for resource in asyncio.run(server.list_resources())}

    for tool in asyncio.run(server.list_tools()):
        ui = (tool.meta or {}).get("ui")
        if ui is not None:
            assert ui["resourceUri"] in registered, tool.name


def test_the_resource_declares_our_origin_and_asks_for_no_network() -> None:
    """The CSP is the only thing standing between a sandboxed card and a blank frame.

    ``resourceDomains`` governs scripts and styles as well as images, which is why it names hosts
    one by one instead of allowing the web. ``connectDomains`` is empty because the screens make no
    requests of their own: everything arrives from the host and everything goes back as a tool call.
    """
    resources = {str(r.uri): r for r in asyncio.run(build_server().list_resources())}
    meta = resources["ui://sellerclaw/orders.html"].meta or {}

    csp = meta["ui"]["csp"]
    assert csp["connectDomains"] == []
    assert csp["resourceDomains"][0] == APPS_BASE
    assert "https://i.ebayimg.com" in csp["resourceDomains"]
    # A draft built from a CJ product still shows CJ's photos until it is published.
    assert "https://*.cjdropshipping.com" in csp["resourceDomains"]
    assert not any(domain in ("https://*", "*") for domain in csp["resourceDomains"])
    assert meta["ui"]["prefersBorder"] is False
    assert resources["ui://sellerclaw/orders.html"].mime_type == "text/html;profile=mcp-app"


# --------------------------------------------------------------------------- the document


@respx.mock
def test_the_screen_is_served_exactly_as_the_web_app_built_it() -> None:
    html = _document("store-summary")
    respx.get(f"{APPS_BASE}/mcp-apps/store-summary.html").mock(
        return_value=httpx.Response(200, text=html)
    )

    contents = asyncio.run(build_server().read_resource("ui://sellerclaw/store-summary.html"))

    assert len(contents) == 1
    assert contents[0].content == html
    assert contents[0].mime_type == "text/html;profile=mcp-app"
    # The CSP has to ride along on the read: hosts take it from here, not from the listing.
    assert (contents[0].meta or {})["ui"]["csp"]["resourceDomains"][0] == APPS_BASE


@respx.mock
def test_a_second_reader_inside_the_window_costs_no_second_fetch() -> None:
    """Every conversation that opens a card reads this resource; the document changes on deploys."""
    route = respx.get(f"{APPS_BASE}/mcp-apps/orders.html").mock(
        return_value=httpx.Response(200, text=_document("orders"))
    )
    server = build_server()

    asyncio.run(server.read_resource("ui://sellerclaw/orders.html"))
    asyncio.run(server.read_resource("ui://sellerclaw/orders.html"))

    assert route.call_count == 1


@respx.mock
def test_the_cache_lets_go_once_the_window_passes(monkeypatch: pytest.MonkeyPatch) -> None:
    """A UI deploy has to heal itself; nobody restarts the MCP server for a CSS fix."""
    route = respx.get(f"{APPS_BASE}/mcp-apps/orders.html").mock(
        return_value=httpx.Response(200, text=_document("orders"))
    )
    server = build_server()
    asyncio.run(server.read_resource("ui://sellerclaw/orders.html"))

    # Relative to the real clock the first read stamped, not an absolute number: a fake epoch far
    # below it would look like the past and the entry would never expire.
    later = time.monotonic() + mcp_apps._DOCUMENT_TTL_SECONDS + 1.0
    monkeypatch.setattr(mcp_apps.time, "monotonic", lambda: later)
    asyncio.run(server.read_resource("ui://sellerclaw/orders.html"))

    assert route.call_count == 2


@pytest.mark.parametrize(
    ("mocked", "expected"),
    [
        pytest.param(
            httpx.Response(404),
            "answered 404",
            id="the-path-is-gone",
        ),
        pytest.param(
            httpx.Response(200, text="<html><body>Sign in to continue</body></html>"),
            "did not answer with the built store-summary screen",
            id="something-elses-page",
        ),
        pytest.param(
            httpx.Response(200, text=_document("store-summary", base="")),
            "built for a different origin",
            id="built-without-an-absolute-origin",
        ),
        pytest.param(
            httpx.Response(200, text=_document("store-summary", base="https://elsewhere.test")),
            "built for a different origin",
            id="built-for-another-deployment",
        ),
    ],
)
@respx.mock
def test_a_screen_that_cannot_be_served_refuses_and_names_the_fix(
    mocked: httpx.Response, expected: str
) -> None:
    """Never a stand-in document.

    A card rendering "sorry" occupies the conversation and tells nobody what broke, while a refusal
    leaves the tool's own text answer in place and puts the reason where someone will read it. The
    origin check is the one that earns its keep: a server pointed at one deployment while the
    documents were built for another produces an empty frame and no error anywhere.
    """
    respx.get(f"{APPS_BASE}/mcp-apps/store-summary.html").mock(return_value=mocked)

    with pytest.raises(ResourceError) as excinfo:
        asyncio.run(build_server().read_resource("ui://sellerclaw/store-summary.html"))

    message = str(excinfo.value)
    assert expected in message
    assert mcp_apps.APPS_BASE_ENV in message or "store-summary" in message


@respx.mock
def test_an_origin_that_was_briefly_down_is_not_written_off() -> None:
    """Caching a failure would turn thirty seconds of trouble into fifteen minutes of it."""
    route = respx.get(f"{APPS_BASE}/mcp-apps/approval.html")
    route.mock(side_effect=httpx.ConnectError("boom"))
    server = build_server()
    with pytest.raises(ResourceError):
        asyncio.run(server.read_resource("ui://sellerclaw/approval.html"))

    route.mock(return_value=httpx.Response(200, text=_document("approval")))
    contents = asyncio.run(server.read_resource("ui://sellerclaw/approval.html"))

    assert contents[0].content == _document("approval")


@pytest.mark.parametrize(
    "configured",
    [
        pytest.param("https://app.test.sellerclaw.ai", id="bare"),
        pytest.param("https://app.test.sellerclaw.ai/", id="trailing-slash"),
    ],
)
def test_the_origin_reads_the_same_with_or_without_a_trailing_slash(
    monkeypatch: pytest.MonkeyPatch, configured: str
) -> None:
    """One character in a deploy config must not become a doubled slash in every screen URL."""
    monkeypatch.setenv(mcp_apps.APPS_BASE_ENV, configured)

    assert mcp_apps.apps_base() == APPS_BASE
    assert mcp_apps.document_url("orders") == f"{APPS_BASE}/mcp-apps/orders.html"


def test_an_unconfigured_server_still_points_at_production(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """``pip install 'sellerclaw-cli[mcp]'`` has no deploy config behind it, and should still draw."""
    monkeypatch.delenv(mcp_apps.APPS_BASE_ENV, raising=False)

    assert mcp_apps.apps_base() == "https://app.sellerclaw.ai"


# --------------------------------------------------------------------------- what the tools call


@respx.mock
def test_the_store_summary_asks_for_the_figures_and_the_chart_behind_them(
    env_pointing_at_fake_api: None, fake_api_url: str
) -> None:
    """One card, two reads — plus the store's own name, which is what titles it."""
    metrics = respx.get(f"{fake_api_url}/agent/analytics/stores/{STORE_ID}/metrics").mock(
        return_value=httpx.Response(200, json={"currency": "USD", "revenue": "1200.00"})
    )
    respx.get(f"{fake_api_url}/agent/analytics/stores/{STORE_ID}/timeseries").mock(
        return_value=httpx.Response(200, json={"points": []})
    )
    respx.get(f"{fake_api_url}/agent/sales-channels/{STORE_ID}").mock(
        return_value=httpx.Response(200, json={"display_name": "Pawpilot Supply"})
    )

    result = _call("sellerclaw_store_summary", {"store": STORE_ID, "period": "last_90d"})

    payload = result.structured_content
    assert set(payload) == {"metrics", "timeseries", "store_name"}
    assert payload["store_name"] == "Pawpilot Supply"
    asked = dict(metrics.calls[0].request.url.params)
    assert asked["period"] == "last_90d"
    # Without the fees the card would have to show gross profit where it says net, or nothing.
    assert asked["with_fees"] == "true"


@respx.mock
def test_a_summary_over_several_stores_names_them_all_and_titles_none(
    env_pointing_at_fake_api: None, fake_api_url: str
) -> None:
    """The first store goes in the path and the rest alongside it — the API adds them up itself.

    No display name: the answer is about several shops, and borrowing the first one's name would
    put a figure under a heading it does not belong to.
    """
    other = "55555555-5555-4555-8555-555555555555"
    metrics = respx.get(f"{fake_api_url}/agent/analytics/stores/{STORE_ID}/metrics").mock(
        return_value=httpx.Response(200, json={"revenue": "1.00"})
    )
    respx.get(f"{fake_api_url}/agent/analytics/stores/{STORE_ID}/timeseries").mock(
        return_value=httpx.Response(200, json={"points": []})
    )
    channel = respx.get(f"{fake_api_url}/agent/sales-channels/{STORE_ID}")

    result = _call("sellerclaw_store_summary", {"store": [STORE_ID, other]})

    assert "store_name" not in result.structured_content
    assert channel.call_count == 0
    assert metrics.calls[0].request.url.params.get_list("store") == [other]


@respx.mock
def test_the_whole_account_is_the_default_view(
    env_pointing_at_fake_api: None, fake_api_url: str
) -> None:
    """Nothing named means every store, which is what the Agent API's ``all`` is for."""
    respx.get(f"{fake_api_url}/agent/analytics/stores/all/metrics").mock(
        return_value=httpx.Response(200, json={"revenue": "1.00"})
    )
    respx.get(f"{fake_api_url}/agent/analytics/stores/all/timeseries").mock(
        return_value=httpx.Response(200, json={"points": []})
    )

    result = _call("sellerclaw_store_summary", {})

    assert "store_name" not in result.structured_content


@respx.mock
def test_the_order_board_carries_its_own_totals(
    env_pointing_at_fake_api: None, fake_api_url: str
) -> None:
    orders = respx.get(f"{fake_api_url}/agent/orders").mock(
        return_value=httpx.Response(200, json={"items": [{"id": ORDER_ID}], "total": 1})
    )
    respx.get(f"{fake_api_url}/agent/orders/overview").mock(
        return_value=httpx.Response(200, json={"total": 1, "by_status": {"new": 1}})
    )

    result = _call("sellerclaw_orders", {"status": "new"})

    assert set(result.structured_content) == {"orders", "overview"}
    assert dict(orders.calls[0].request.url.params) == {"status": "new"}


@respx.mock
def test_an_unfiltered_board_does_not_ask_for_the_status_none(
    env_pointing_at_fake_api: None, fake_api_url: str
) -> None:
    """The screen sends ``null`` when it means "every status", and ``status=None`` is a 422."""
    orders = respx.get(f"{fake_api_url}/agent/orders").mock(
        return_value=httpx.Response(200, json={"items": []})
    )
    respx.get(f"{fake_api_url}/agent/orders/overview").mock(
        return_value=httpx.Response(200, json={"total": 0, "by_status": {}})
    )

    _call("sellerclaw_orders", {"status": None})

    assert dict(orders.calls[0].request.url.params) == {}


@respx.mock
def test_marking_an_order_shipped_hands_back_the_whole_board(
    env_pointing_at_fake_api: None, fake_api_url: str
) -> None:
    """A single changed row would leave the card with nothing to draw around it."""
    shipped = respx.post(f"{fake_api_url}/agent/orders/{ORDER_ID}/shipped").mock(
        return_value=httpx.Response(200, json={"id": ORDER_ID, "status": "shipped"})
    )
    board = respx.get(f"{fake_api_url}/agent/orders").mock(
        return_value=httpx.Response(200, json={"items": []})
    )
    respx.get(f"{fake_api_url}/agent/orders/overview").mock(
        return_value=httpx.Response(200, json={"total": 0, "by_status": {}})
    )

    result = _call("sellerclaw_order_mark_shipped", {"order": ORDER_ID, "status": "new"})

    assert shipped.call_count == 1
    assert set(result.structured_content) == {"orders", "overview"}
    # Through the board's own filter. Answering with every status would redraw the card with rows
    # the chip above them excludes.
    assert dict(board.calls[0].request.url.params) == {"status": "new"}


@respx.mock
def test_the_channels_refusal_to_ship_reaches_the_card_in_its_own_words(
    env_pointing_at_fake_api: None, fake_api_url: str
) -> None:
    """The refusal names the command that would create the shipment. Rewording it loses the way out."""
    respx.post(f"{fake_api_url}/agent/orders/{ORDER_ID}/shipped").mock(
        return_value=httpx.Response(
            409,
            json={
                "detail": {
                    "code": "channel_has_no_shipment",
                    "message": (
                        "Pawpilot Supply holds no shipment for order #1001. Create it there first "
                        "with `shopify-orders create-fulfillment`, then record it here."
                    ),
                }
            },
        )
    )

    with pytest.raises(ToolError) as excinfo:
        _call("sellerclaw_order_mark_shipped", {"order": ORDER_ID})

    assert "shopify-orders create-fulfillment" in str(excinfo.value)


@respx.mock
def test_the_approval_card_says_how_much_else_is_waiting(
    env_pointing_at_fake_api: None, fake_api_url: str
) -> None:
    """Counting the *others*: the card the owner is reading is not "one more waiting for you"."""
    respx.get(f"{fake_api_url}/agent/goals/action-requests/{REQUEST_ID}").mock(
        return_value=httpx.Response(200, json={"id": REQUEST_ID, "title": "Send the email"})
    )
    respx.get(f"{fake_api_url}/agent/goals/action-requests").mock(
        return_value=httpx.Response(
            200, json={"items": [{"id": REQUEST_ID}, {"id": "other-1"}, {"id": "other-2"}]}
        )
    )

    result = _call("sellerclaw_approval", {"request": REQUEST_ID})

    assert result.structured_content["pending_count"] == 2


@respx.mock
def test_a_count_that_hit_the_ceiling_is_left_out_rather_than_guessed(
    env_pointing_at_fake_api: None, fake_api_url: str
) -> None:
    """At the cap the real number is unknown, and "200 more waiting" would be a figure we invented."""
    respx.get(f"{fake_api_url}/agent/goals/action-requests/{REQUEST_ID}").mock(
        return_value=httpx.Response(200, json={"id": REQUEST_ID, "title": "Send the email"})
    )
    respx.get(f"{fake_api_url}/agent/goals/action-requests").mock(
        return_value=httpx.Response(
            200, json={"items": [{"id": f"r{n}"} for n in range(mcp_apps._PENDING_CAP)]}
        )
    )

    result = _call("sellerclaw_approval", {"request": REQUEST_ID})

    assert "pending_count" not in result.structured_content


@respx.mock
def test_the_owners_press_is_reported_as_a_decision_not_as_words(
    env_pointing_at_fake_api: None, fake_api_url: str
) -> None:
    """The card posts to the route built for a press; the quote route is for what they *said*."""
    decide = respx.post(f"{fake_api_url}/agent/goals/action-requests/{REQUEST_ID}/decide").mock(
        return_value=httpx.Response(200, json={"id": REQUEST_ID, "status": "resolved"})
    )
    reread = respx.get(f"{fake_api_url}/agent/goals/action-requests/{REQUEST_ID}")
    respx.get(f"{fake_api_url}/agent/goals/action-requests").mock(
        return_value=httpx.Response(200, json={"items": []})
    )

    result = _call(
        "sellerclaw_approval_decide",
        {"request": REQUEST_ID, "decision": "approve", "option": "ups"},
    )

    # The write already answered with the updated row; reading it back would spend a round trip to
    # learn what we were just told, and could hand the owner a card that disagrees with their press.
    assert reread.call_count == 0

    import json

    assert json.loads(decide.calls[0].request.content) == {
        "decision": "approve",
        "option_id": "ups",
    }
    assert result.structured_content["request"]["status"] == "resolved"


@respx.mock
def test_a_plain_yes_carries_no_option(
    env_pointing_at_fake_api: None, fake_api_url: str
) -> None:
    """``option: null`` on the wire is a field the API has to reject rather than ignore."""
    decide = respx.post(f"{fake_api_url}/agent/goals/action-requests/{REQUEST_ID}/decide").mock(
        return_value=httpx.Response(200, json={"id": REQUEST_ID, "status": "rejected"})
    )
    respx.get(f"{fake_api_url}/agent/goals/action-requests/{REQUEST_ID}").mock(
        return_value=httpx.Response(200, json={"id": REQUEST_ID, "status": "rejected"})
    )
    respx.get(f"{fake_api_url}/agent/goals/action-requests").mock(
        return_value=httpx.Response(200, json={"items": []})
    )

    _call("sellerclaw_approval_decide", {"request": REQUEST_ID, "decision": "reject"})

    import json

    assert json.loads(decide.calls[0].request.content) == {"decision": "reject"}


LISTING_ID = "66666666-6666-4666-8666-666666666666"
PRODUCT_ID = "77777777-7777-4777-8777-777777777777"
OTHER_LISTING = "88888888-8888-4888-8888-888888888888"


@respx.mock
def test_what_needs_the_owner_is_the_home_pages_own_answer(
    env_pointing_at_fake_api: None, fake_api_url: str
) -> None:
    """One read of the same summary the web home page draws — never a second opinion assembled here."""
    summary = respx.get(f"{fake_api_url}/agent/dashboard/summary").mock(
        return_value=httpx.Response(200, json={"status": "all_clear", "attention": []})
    )

    result = _call("sellerclaw_attention", {})

    assert summary.call_count == 1
    assert result.structured_content == {"summary": {"status": "all_clear", "attention": []}}


@respx.mock
def test_one_order_opens_with_its_items_pictured_by_their_listings(
    env_pointing_at_fake_api: None, fake_api_url: str
) -> None:
    """An order line names the listing it came from; the picture is the listing's. A listing that no
    longer reads costs that line its thumbnail and nothing else, and a listing sold twice in one
    order is read once."""
    respx.get(f"{fake_api_url}/agent/orders/{ORDER_ID}").mock(
        return_value=httpx.Response(
            200,
            json={
                "id": ORDER_ID,
                "line_items": [
                    {"title": "Harness", "listing_id": LISTING_ID},
                    {"title": "Harness again", "listing_id": LISTING_ID},
                    {"title": "Bowl", "listing_id": OTHER_LISTING},
                    {"title": "Unlinked", "listing_id": None},
                ],
            },
        )
    )
    harness = respx.get(f"{fake_api_url}/agent/listings/{LISTING_ID}").mock(
        return_value=httpx.Response(200, json={"image_url": "https://i.ebayimg.com/h.jpg"})
    )
    respx.get(f"{fake_api_url}/agent/listings/{OTHER_LISTING}").mock(
        return_value=httpx.Response(404, json={"detail": "Listing not found"})
    )
    board = respx.get(f"{fake_api_url}/agent/orders")

    result = _call("sellerclaw_orders", {"order": ORDER_ID})

    assert result.structured_content["item_images"] == {LISTING_ID: "https://i.ebayimg.com/h.jpg"}
    assert harness.call_count == 1
    assert board.call_count == 0


@respx.mock
def test_an_order_without_pictures_carries_no_empty_map(
    env_pointing_at_fake_api: None, fake_api_url: str
) -> None:
    respx.get(f"{fake_api_url}/agent/orders/{ORDER_ID}").mock(
        return_value=httpx.Response(200, json={"id": ORDER_ID, "line_items": [{"title": "Harness"}]})
    )

    result = _call("sellerclaw_orders", {"order": ORDER_ID})

    assert set(result.structured_content) == {"order"}


@respx.mock
def test_marking_shipped_from_one_order_answers_with_that_order(
    env_pointing_at_fake_api: None, fake_api_url: str
) -> None:
    """Pressed on the one-order view, the card must come back as that order — not as a board the
    person was not looking at."""
    respx.post(f"{fake_api_url}/agent/orders/{ORDER_ID}/shipped").mock(
        return_value=httpx.Response(200, json={"id": ORDER_ID, "status": "shipped"})
    )
    respx.get(f"{fake_api_url}/agent/orders/{ORDER_ID}").mock(
        return_value=httpx.Response(200, json={"id": ORDER_ID, "status": "shipped", "line_items": []})
    )
    board = respx.get(f"{fake_api_url}/agent/orders")

    result = _call("sellerclaw_order_mark_shipped", {"order": ORDER_ID, "return_to": "order"})

    assert result.structured_content["order"]["status"] == "shipped"
    assert board.call_count == 0


@respx.mock
def test_the_listing_list_asks_only_for_the_filters_it_was_given(
    env_pointing_at_fake_api: None, fake_api_url: str
) -> None:
    """And hands the card each store's id, platform and name — not its categories and settings."""
    search = respx.get(f"{fake_api_url}/agent/listings/search").mock(
        return_value=httpx.Response(200, json={"items": [], "total": 0})
    )
    respx.get(f"{fake_api_url}/agent/sales-channels").mock(
        return_value=httpx.Response(
            200,
            json=[
                {
                    "id": STORE_ID,
                    "platform": "ebay",
                    "display_name": "Pawpilot Supply",
                    "categories": [{"id": 1}] * 40,
                    "specifics": {"a": 1},
                }
            ],
        )
    )

    result = _call("sellerclaw_listings", {"store": STORE_ID, "status": "draft", "query": "harness"})

    assert dict(search.calls[0].request.url.params) == {
        "q": "harness",
        "store_id": STORE_ID,
        "status": "draft",
    }
    assert result.structured_content["stores"] == [
        {"id": STORE_ID, "platform": "ebay", "display_name": "Pawpilot Supply"}
    ]
    assert result.structured_content["filters"] == {
        "store": STORE_ID,
        "status": "draft",
        "query": "harness",
    }


@respx.mock
def test_one_listing_brings_its_refusals_and_the_same_product_elsewhere(
    env_pointing_at_fake_api: None, fake_api_url: str
) -> None:
    respx.get(f"{fake_api_url}/agent/listings/{LISTING_ID}").mock(
        return_value=httpx.Response(
            200,
            json={"id": LISTING_ID, "product_id": PRODUCT_ID, "sales_channel_id": STORE_ID, "title": "Bowl"},
        )
    )
    problems = respx.get(f"{fake_api_url}/agent/listing-problems").mock(
        return_value=httpx.Response(200, json={"items": [{"id": "p1"}]})
    )
    elsewhere = respx.get(f"{fake_api_url}/agent/listings/search").mock(
        return_value=httpx.Response(200, json={"items": [], "total": 0})
    )
    respx.get(f"{fake_api_url}/agent/sales-channels").mock(return_value=httpx.Response(200, json=[]))

    result = _call("sellerclaw_listings", {"listing": LISTING_ID})

    assert set(result.structured_content) == {"listing", "problems", "elsewhere", "stores", "filters"}
    assert dict(problems.calls[0].request.url.params) == {
        "product_id": PRODUCT_ID,
        "sales_channel_id": STORE_ID,
    }
    assert dict(elsewhere.calls[0].request.url.params) == {"product_id": PRODUCT_ID, "limit": "50"}


@pytest.mark.parametrize(
    "variations_key",
    [
        pytest.param("variations", id="compact-variations"),
        pytest.param("variants", id="server-older-than-this-client"),
    ],
)
@respx.mock
def test_a_variation_group_is_handed_over_as_a_group(
    env_pointing_at_fake_api: None, fake_api_url: str, variations_key: str
) -> None:
    """The same route answers a row or a whole group; the card is told which, rather than guessing.
    A group already carries its own refusals, so they are not read twice."""
    respx.get(f"{fake_api_url}/agent/listings/{LISTING_ID}").mock(
        return_value=httpx.Response(
            200,
            json={"title": "Blanket", "product_id": PRODUCT_ID, variations_key: [], "problems": []},
        )
    )
    problems = respx.get(f"{fake_api_url}/agent/listing-problems")
    respx.get(f"{fake_api_url}/agent/listings/search").mock(
        return_value=httpx.Response(200, json={"items": [], "total": 0})
    )
    respx.get(f"{fake_api_url}/agent/sales-channels").mock(return_value=httpx.Response(200, json=[]))

    result = _call("sellerclaw_listings", {"listing": LISTING_ID})

    assert "group" in result.structured_content
    assert "listing" not in result.structured_content
    assert problems.call_count == 0


@respx.mock
def test_a_listing_still_opens_when_what_surrounds_it_cannot_be_read(
    env_pointing_at_fake_api: None, fake_api_url: str
) -> None:
    """Refusals, other stores and store names are sections around the listing: losing one costs
    that section, not the card."""
    respx.get(f"{fake_api_url}/agent/listings/{LISTING_ID}").mock(
        return_value=httpx.Response(200, json={"title": "Bowl", "product_id": PRODUCT_ID})
    )
    respx.get(f"{fake_api_url}/agent/listing-problems").mock(
        return_value=httpx.Response(404, json={"detail": "not found"})
    )
    respx.get(f"{fake_api_url}/agent/listings/search").mock(
        return_value=httpx.Response(404, json={"detail": "not found"})
    )
    respx.get(f"{fake_api_url}/agent/sales-channels").mock(
        return_value=httpx.Response(403, json={"detail": "no"})
    )

    result = _call("sellerclaw_listings", {"listing": LISTING_ID})

    assert result.structured_content["listing"]["title"] == "Bowl"
    assert "problems" not in result.structured_content
    assert "elsewhere" not in result.structured_content
    assert result.structured_content["stores"] == []


@respx.mock
def test_the_ads_card_reads_both_halves_for_the_same_window(
    env_pointing_at_fake_api: None, fake_api_url: str
) -> None:
    """Totals and campaigns from one window — the card must never show a 30-day total over 7-day
    campaign rows."""
    overview = respx.get(f"{fake_api_url}/agent/ads/overview").mock(
        return_value=httpx.Response(200, json={"window_days": 30, "totals": [], "accounts": []})
    )
    campaigns = respx.get(f"{fake_api_url}/agent/ads/campaigns").mock(
        return_value=httpx.Response(200, json={"window_days": 30, "items": []})
    )

    result = _call("sellerclaw_ads", {"days": 30, "account": STORE_ID})

    assert dict(overview.calls[0].request.url.params) == {"window_days": "30"}
    assert dict(campaigns.calls[0].request.url.params) == {"window_days": "30", "account_id": STORE_ID}
    assert set(result.structured_content) == {"overview", "campaigns"}


@respx.mock
def test_the_connections_card_is_the_agents_own_overview(
    env_pointing_at_fake_api: None, fake_api_url: str
) -> None:
    respx.get(f"{fake_api_url}/agent/integrations").mock(
        return_value=httpx.Response(200, json=[{"kind": "ebay_store", "connections": []}])
    )

    result = _call("sellerclaw_connections", {})

    assert result.structured_content == {"integrations": [{"kind": "ebay_store", "connections": []}]}


# --------------------------------------------------------------------------- what the model reads


@respx.mock
def test_the_model_gets_a_sentence_while_the_owner_gets_the_card(
    env_pointing_at_fake_api: None, fake_api_url: str
) -> None:
    """A board of fifty orders is tens of kilobytes; the model only needs enough to talk about it."""
    respx.get(f"{fake_api_url}/agent/orders").mock(
        return_value=httpx.Response(
            200, json={"items": [{"id": f"o{n}", "status": "new"} for n in range(50)], "total": 50}
        )
    )
    respx.get(f"{fake_api_url}/agent/orders/overview").mock(
        return_value=httpx.Response(200, json={"total": 50, "by_status": {"new": 7, "shipped": 43}})
    )

    result = _call("sellerclaw_orders", {})

    text = result.content[0].text
    assert "7 across the account are waiting to ship" in text
    assert len(text) < 500
    # The payload is still whole — it is the card's, not the model's.
    assert len(result.structured_content["orders"]["items"]) == 50


def test_a_figure_the_account_does_not_have_is_left_out_of_the_summary() -> None:
    """The same rule the screens follow: no profit line rather than a profit of zero."""
    without_cost = mcp_apps._summarize_store_summary(
        {"metrics": {"currency": "USD", "revenue": "1200.00", "order_count": 14, "period": "last_30d"}}
    )

    assert "Revenue 1200.00 USD across 14 orders." in without_cost
    assert "Profit" not in without_cost

    with_cost = mcp_apps._summarize_store_summary(
        {
            "metrics": {
                "currency": "USD",
                "revenue": "1200.00",
                "order_count": 14,
                "net": {"net_profit": "310.00"},
            }
        }
    )
    assert "Profit 310.00 USD." in with_cost


def test_the_model_is_told_the_owner_answers_the_card_themselves() -> None:
    """Left to itself a model will offer to approve, or ask them to type "yes" — neither works."""
    summary = mcp_apps._summarize_approval(
        {"request": {"title": "Send the email", "status": "pending"}, "pending_count": 3}
    )

    assert "Send the email" in summary
    assert "3 more also waiting" in summary
    assert "you have no tool that closes it" in summary
    # The fallback for a client with no card, so the model is never left stuck.
    assert "action-requests confirm" in summary
    assert "Never decide for them" in summary


@respx.mock
def test_a_refusal_the_owner_can_act_on_is_not_flattened_into_a_generic_failure(
    env_pointing_at_fake_api: None, fake_api_url: str
) -> None:
    """The SDK repeats a ``ToolError``'s message and replaces anything else with "Error executing
    tool <name>". Everything worth reading is in the message: which command creates the shipment,
    where to grant an app the standing to answer. A screen showing the generic line leaves the
    person with a red box and no way forward."""
    respx.get(f"{fake_api_url}/agent/goals/action-requests/{REQUEST_ID}").mock(
        return_value=httpx.Response(
            403,
            json={
                "detail": {
                    "code": "owner_click_not_trusted",
                    "message": "Ask them to trust this app for approvals in their settings.",
                }
            },
        )
    )

    with pytest.raises(ToolError) as excinfo:
        _call("sellerclaw_approval", {"request": REQUEST_ID})

    assert "trust this app for approvals" in str(excinfo.value)


def test_a_summary_covering_several_shops_does_not_speak_of_one() -> None:
    """"The store" over five shops' combined figures names a shop that does not exist."""
    many = mcp_apps._summarize_store_summary({"metrics": {"period": "last_30d", "revenue": "9.00"}})
    one = mcp_apps._summarize_store_summary(
        {"store_name": "Pawpilot Supply", "metrics": {"period": "last_30d", "revenue": "9.00"}}
    )

    assert many.startswith("Store summary, last_30d.")
    assert one.startswith("Pawpilot Supply, last_30d.")


def test_the_queue_is_told_as_a_verdict_and_its_first_rows() -> None:
    summary = mcp_apps._summarize_attention(
        {
            "summary": {
                "status": "at_risk",
                "attention": [
                    {"title": "eBay stopped accepting our access", "severity": "critical"},
                    {"title": "3 orders are late to ship", "severity": "critical"},
                    {"title": "Credits are running low", "severity": "attention"},
                    {"title": "A fourth thing", "severity": "attention"},
                ],
                "degraded_blocks": ["connections"],
            }
        }
    )

    assert summary.startswith("Something urgent needs the owner. 4 items, 2 urgent.")
    assert '"3 orders are late to ship"' in summary
    assert "A fourth thing" not in summary
    assert "Could not check: connections." in summary


def test_a_quiet_queue_is_not_called_all_clear_when_a_check_did_not_run() -> None:
    summary = mcp_apps._summarize_attention({"summary": {"status": "unknown", "attention": []}})

    assert summary.startswith("Nothing turned up, but not every check ran.")


def test_a_list_of_listings_is_summed_up_by_what_does_not_sell() -> None:
    summary = mcp_apps._summarize_listings(
        {
            "listings": {
                "items": [
                    {"sale_state": "selling"},
                    {"sale_state": "not_selling"},
                    {"sale_state": "out_of_stock"},
                ],
                "total": 42,
            }
        }
    )

    assert summary.startswith("Showing 3 of 42 listings. Among them, 1 not selling and 1 out of stock.")


def test_one_listing_is_named_with_its_store_and_what_is_wrong_with_it() -> None:
    summary = mcp_apps._summarize_listings(
        {
            "listing": {
                "title": "Slow-feeder puzzle bowl",
                "sales_channel_id": STORE_ID,
                "group_id": "g1",
                "sale_state": "not_selling",
                "price": "24.99",
                "currency": "USD",
                "quantity": 12,
            },
            "problems": {"items": [{"id": "p1"}]},
            "elsewhere": {"items": [{"listing_id": "g1"}, {"listing_id": "g2"}]},
            "stores": [{"id": STORE_ID, "platform": "ebay", "display_name": "Pawpilot Supply"}],
        }
    )

    assert summary.startswith(
        '"Slow-feeder puzzle bowl" on Pawpilot Supply: not selling. Price 24.99 USD, 12 in stock. '
        "1 marketplace problem on it. Also listed in 1 other store."
    )


def test_one_order_is_named_by_its_marketplace_number() -> None:
    summary = mcp_apps._summarize_order(
        {
            "order": {
                "remote_order_name": "#1001",
                "store_name": "Pawpilot Supply",
                "status": "purchased",
                "total_revenue": "94.00",
                "currency": "USD",
                "line_items": [{}, {}],
                "tracking_number": "CJ883012774US",
                "tracking_carrier": "YunExpress",
                "has_unresolved_items": True,
            }
        }
    )

    assert summary.startswith(
        "Order #1001 from Pawpilot Supply: purchased. Total 94.00 USD for 2 items. "
        "Tracking CJ883012774US (YunExpress). Some items are not matched to a supplier yet."
    )


def test_ad_totals_are_told_per_currency_and_never_added_together() -> None:
    summary = mcp_apps._summarize_ads(
        {
            "overview": {
                "window_days": 7,
                "totals": [
                    {"currency": "USD", "metrics": {"spend": 310.0, "conversion_value": 1302.0}},
                    {"currency": "EUR", "metrics": {"spend": 84.0, "conversion_value": 0}},
                ],
                "accounts": [
                    {"account": {"display_name": "Pawpilot — Google Ads", "status": "token_expired"}},
                ],
            },
            "campaigns": {"items": [{"status": "enabled"}, {"status": "paused"}]},
        }
    )

    assert summary.startswith(
        "Ads, last 7 days. Spent 310.00 USD, 1302.00 USD in sales from ads. Spent 84.00 EUR. "
        "1 campaign running. Needs reconnecting: Pawpilot — Google Ads."
    )


def test_an_account_without_ad_accounts_is_told_so() -> None:
    summary = mcp_apps._summarize_ads({"overview": {"accounts": []}, "campaigns": {"items": []}})

    assert summary.startswith("No ad accounts are connected.")


@pytest.mark.parametrize(
    ("integrations", "opening"),
    [
        pytest.param(
            [
                {
                    "display_name": "eBay",
                    "connections": [
                        {"name": "pawpilot", "custom_name": "Pawpilot Supply", "status": "credentials_invalid"},
                    ],
                },
                {
                    "display_name": "Shopify",
                    "connections": [
                        {"name": "shop", "status": "active"},
                        {"name": "shop2", "status": "provider_suspended"},
                    ],
                },
                {
                    "display_name": "eBay Promoted Listings",
                    "connections": [{"name": "Pawpilot", "status": "active", "setup_warning": {"message": "x"}}],
                },
            ],
            "3 connections need the owner: Pawpilot Supply (eBay) needs reconnecting; shop2 (Shopify) "
            "switched off by the platform; Pawpilot (eBay Promoted Listings) has setup unfinished. "
            "1 working. Fixing one happens on the SellerClaw website",
            id="broken",
        ),
        pytest.param(
            [
                {
                    "display_name": "eBay",
                    "connections": [{"name": "a", "status": "active"}, {"name": "b", "status": "active"}],
                }
            ],
            "All 2 connections are working.",
            id="healthy",
        ),
        pytest.param([], "Nothing is connected yet.", id="empty"),
    ],
)
def test_connections_are_told_by_what_needs_the_owner(integrations: list[Any], opening: str) -> None:
    assert mcp_apps._summarize_connections({"integrations": integrations}).startswith(opening)


@pytest.mark.parametrize(
    "summary",
    [
        pytest.param(
            mcp_apps._summarize_store_summary({"metrics": {"revenue": "1.00"}}), id="store-summary"
        ),
        pytest.param(mcp_apps._summarize_orders({"orders": {"items": []}}), id="orders"),
        pytest.param(mcp_apps._summarize_order({"order": {"status": "new"}}), id="order"),
        pytest.param(
            mcp_apps._summarize_attention({"summary": {"status": "all_clear"}}), id="attention"
        ),
        pytest.param(mcp_apps._summarize_listings({"listings": {"items": []}}), id="listings"),
        pytest.param(
            mcp_apps._summarize_ads({"overview": {"accounts": []}}), id="ads"
        ),
        pytest.param(mcp_apps._summarize_connections({"integrations": []}), id="connections"),
    ],
)
def test_a_client_without_cards_is_not_told_the_owner_is_looking_at_one(summary: str) -> None:
    """These tools answer any MCP client, and only some of them render our screens.

    A model told flatly "the owner is looking at this" in a terminal would talk about something
    nobody can see, and would stop reciting figures that are then shown nowhere.
    """
    assert "If this client shows SellerClaw cards" in summary
    assert "structured result" in summary
