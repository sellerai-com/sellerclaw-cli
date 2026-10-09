"""The ChatGPT surface: one tool per action, generalised across platforms, served at /chatgpt/mcp."""

from __future__ import annotations

import asyncio
import json
import re
from typing import Any

import httpx
import jsonschema
import pytest
import respx
from pydantic import BaseModel

import sellerclaw_cli.cli  # noqa: F401 — registers every command group
from sellerclaw_cli import chatgpt, mcp_apps, mcp_usage
from sellerclaw_cli._command_group import positionals_of
from sellerclaw_cli._errors import UserInputError
from sellerclaw_cli.chatgpt import ACTIONS, _action, research
from sellerclaw_cli.chatgpt._action import Action
from sellerclaw_cli.mcp_server import _reads, _resolve, build_chatgpt_http_server, create_http_app

pytestmark = pytest.mark.unit

ISSUER = "https://api.sellerclaw.test"
RESOURCE = "https://mcp.sellerclaw.test"
STORE_ID = "11111111-1111-4111-8111-111111111111"
ORDER_ID = "22222222-2222-4222-8222-222222222222"
BY_NAME = {a.name: a for a in ACTIONS}
#: What the platforms behind the shared order address take to ship an order.
_SHARED_SHAPE = {
    "tracking": {"number": "1Z9", "company": "UPS"},
    "line_items": [{"remote_line_item_id": "L1", "quantity": 1}],
}
CARD_TOOLS = frozenset(
    {
        "sellerclaw_attention", "sellerclaw_store_summary", "sellerclaw_orders", "sellerclaw_listings",
        "sellerclaw_products", "sellerclaw_ads", "sellerclaw_connections", "sellerclaw_billing",
        "sellerclaw_approval", "sellerclaw_media", "sellerclaw_media_studio",
    }
)
#: Words that only mean something to someone holding the CLI or the read/write runners.
_RUNNER_WORDS = re.compile(
    r"sellerclaw_(read|write|describe|groups|guide|run)|\bCLI\b|--[a-z]|Changes nothing|sellerclaw auth"
)
#: Platforms SellerClaw no longer lets an owner connect; research may still look at them.
_RETIRED = re.compile(r"Etsy|TikTok Shop|tiktok_shop|etsy", re.IGNORECASE)


def _texts(action: Action) -> list[str]:
    return [action.description, action.title, *(p.description for p in action.params)]


@pytest.fixture
def env_pointing_at_fake_api(monkeypatch: pytest.MonkeyPatch, fake_api_url: str, fake_token: str) -> None:
    monkeypatch.setenv("SELLERCLAW_API_URL", fake_api_url)
    monkeypatch.setenv("SELLERCLAW_TOKEN", fake_token)


def _store_is(fake_api_url: str, platform: str) -> None:
    respx.get(f"{fake_api_url}/agent/sales-channels/{STORE_ID}").mock(
        return_value=httpx.Response(200, json={"id": STORE_ID, "platform": platform})
    )


def _sent(route: respx.Route) -> Any:
    return json.loads(route.calls.last.request.content)


# --------------------------------------------------------------------------- the set of tools


def test_the_surface_has_one_tool_per_action_and_the_cards() -> None:
    server = build_chatgpt_http_server(issuer_url=ISSUER, resource_url=RESOURCE, api_url=ISSUER)
    tools = asyncio.run(server.list_tools())
    visible = {
        t.name for t in tools if "model" in ((t.meta or {}).get("ui") or {}).get("visibility", ["model"])
    }

    assert len(ACTIONS) == 119
    assert visible == {a.name for a in ACTIONS} | CARD_TOOLS
    assert asyncio.run(server.list_prompts()) == []


def test_action_names_are_unique_short_and_never_a_card_s() -> None:
    names = [a.name for a in ACTIONS]

    assert len(names) == len(set(names))
    assert all(re.fullmatch(r"[a-z][a-z_]{2,63}", n) and not n.startswith("sellerclaw_") for n in names)
    assert not set(names) & set(mcp_apps.tool_names())


@pytest.mark.parametrize("action", ACTIONS, ids=lambda a: a.name)
def test_every_text_the_model_reads_is_free_of_runner_and_cli_words(action: Action) -> None:
    for text in _texts(action):
        assert text.strip()
        assert not _RUNNER_WORDS.search(text), text


@pytest.mark.parametrize(
    "action", [a for a in ACTIONS if a not in research.ACTIONS], ids=lambda a: a.name
)
def test_platforms_no_longer_connectable_are_only_named_by_research(action: Action) -> None:
    for text in _texts(action):
        assert not _RETIRED.search(text), text


@pytest.mark.parametrize("action", ACTIONS, ids=lambda a: a.name)
def test_every_schema_is_valid_and_flat(action: Action) -> None:
    schema = action.input_schema()

    jsonschema.Draft202012Validator.check_schema(schema)
    assert set(schema["properties"]) == {p.name for p in action.params}
    assert set(schema["required"]) <= set(schema["properties"])
    for param in action.params:
        assert not param.name.startswith("_")
        assert not callable(getattr(BaseModel, param.name, None)), param.name


def test_every_tool_says_all_three_hints_explicitly() -> None:
    server = build_chatgpt_http_server(issuer_url=ISSUER, resource_url=RESOURCE, api_url=ISSUER)
    for tool in asyncio.run(server.list_tools()):
        if tool.name in BY_NAME:
            hints = tool.annotations
            assert hints is not None
            assert isinstance(hints.read_only_hint, bool)
            assert isinstance(hints.destructive_hint, bool)
            assert isinstance(hints.open_world_hint, bool)
            assert tool.input_schema == BY_NAME[tool.name].input_schema()


@pytest.mark.parametrize("action", [a for a in ACTIONS if a.target], ids=lambda a: a.name)
def test_a_single_command_action_fits_its_command(action: Action) -> None:
    """Every parameter lands on a real path argument, flag or body field, and the hints match."""
    assert action.target is not None
    _, cmd = _resolve(*action.target)
    path = [p.command_key for p in action.params if p.to == "path"]
    flags = {p.command_key for p in action.params if p.to == "flag"}
    body = {p.command_key for p in action.params if p.to == "body"}

    assert sorted(path) == sorted(positionals_of(cmd.path))
    assert flags <= {f.name for f in cmd.flags}
    if cmd.body and not cmd.body_freeform:
        assert body <= {b.name for b in cmd.body}
    assert action.read_only == _reads(cmd)


@pytest.mark.parametrize(
    "name",
    [
        "delete_listings", "withdraw_listings", "cancel_order", "ship_order", "pay_supplier_order",
        "reply_to_review", "update_listings", "update_store_settings", "set_product_cost",
    ],
)
def test_deleting_cancelling_paying_and_overwriting_are_destructive(name: str) -> None:
    assert BY_NAME[name].destructive


@pytest.mark.parametrize("name", ["publish_listings", "reply_to_review", "launch_google_ads_campaign", "keyword_ideas"])
def test_what_reaches_the_public_is_open_world(name: str) -> None:
    assert BY_NAME[name].open_world


@pytest.mark.parametrize("name", ["list_orders", "update_products", "get_store_metrics"])
def test_the_owner_s_own_data_is_not_open_world(name: str) -> None:
    assert not BY_NAME[name].open_world


def test_cards_name_this_surface_s_tools_instead_of_commands() -> None:
    wording = chatgpt.card_wording()

    assert set(wording.descriptions) >= {"sellerclaw_listings", "sellerclaw_orders", "sellerclaw_ads"}
    for text in [*wording.descriptions.values(), wording.close_in_words, wording.read_media_job]:
        assert "command" not in text
    assert "answer_action_request" in mcp_apps._summarize_approval({"request": {"title": "x"}}, wording)


# --------------------------------------------------------------------------- running them


@respx.mock
@pytest.mark.parametrize(
    ("platform", "path", "body"),
    [
        pytest.param(
            "shopify",
            f"/agent/stores/{STORE_ID}/orders/1001/fulfillments",
            _SHARED_SHAPE,
            id="shopify-shared-address-and-tracking-object",
        ),
        pytest.param(
            "woocommerce",
            f"/agent/stores/{STORE_ID}/orders/1001/fulfillments",
            _SHARED_SHAPE,
            id="woocommerce-shared-address",
        ),
        pytest.param(
            "ebay",
            f"/agent/ebay/stores/{STORE_ID}/orders/1001/fulfillments",
            {"carrier": "UPS", "tracking_number": "1Z9", "line_items": [{"lineItemId": "L1", "quantity": 1}]},
            id="ebay-own-address-and-fields",
        ),
        pytest.param(
            "amazon",
            f"/agent/amazon/stores/{STORE_ID}/orders/1001/fulfillments",
            {"carrier": "UPS", "tracking_number": "1Z9", "line_items": [{"orderItemId": "L1", "quantity": 1}]},
            id="amazon-own-address-and-fields",
        ),
    ],
)
@pytest.mark.usefixtures("env_pointing_at_fake_api")
def test_ship_order_speaks_each_platform_s_own_shape(
    fake_api_url: str, platform: str, path: str, body: dict[str, Any]
) -> None:
    _store_is(fake_api_url, platform)
    route = respx.post(f"{fake_api_url}{path}").mock(return_value=httpx.Response(200, json={"ok": True}))

    BY_NAME["ship_order"].run(
        {
            "store_id": STORE_ID, "order_id": "1001", "tracking_number": "1Z9", "carrier": "UPS",
            "line_items": [{"line_item_id": "L1", "quantity": 1}],
        }
    )

    assert _sent(route) == body


@respx.mock
@pytest.mark.usefixtures("env_pointing_at_fake_api")
def test_ship_order_on_ebay_turns_our_order_id_into_ebay_s(fake_api_url: str) -> None:
    _store_is(fake_api_url, "ebay")
    respx.get(f"{fake_api_url}/agent/orders/{ORDER_ID}").mock(
        return_value=httpx.Response(200, json={"id": ORDER_ID, "remote_order_id": "14-15000-75039"})
    )
    route = respx.post(f"{fake_api_url}/agent/ebay/stores/{STORE_ID}/orders/14-15000-75039/fulfillments").mock(
        return_value=httpx.Response(200, json={"ok": True})
    )

    BY_NAME["ship_order"].run(
        {"store_id": STORE_ID, "order_id": ORDER_ID, "tracking_number": "1Z9", "carrier": "UPS"}
    )

    assert route.called


@respx.mock
@pytest.mark.usefixtures("env_pointing_at_fake_api")
def test_ship_order_on_ebay_without_a_carrier_is_refused_before_anything_is_sent(fake_api_url: str) -> None:
    _store_is(fake_api_url, "ebay")
    route = respx.post(url__regex=r".*/fulfillments$")

    with pytest.raises(UserInputError, match="carrier"):
        BY_NAME["ship_order"].run({"store_id": STORE_ID, "order_id": "1001", "tracking_number": "1Z9"})
    assert not route.called


@respx.mock
@pytest.mark.parametrize(
    ("action", "platform", "values"),
    [
        pytest.param("cancel_order", "ebay", {"order_id": "1001"}, id="cancel-on-ebay"),
        pytest.param("list_store_policies", "shopify", {}, id="policies-on-shopify"),
        pytest.param("list_store_locations", "sellercart", {}, id="locations-on-sellercart"),
        pytest.param("ship_order", "sellercart", {"order_id": "1", "tracking_number": "1"}, id="ship-on-sellercart"),
    ],
)
@pytest.mark.usefixtures("env_pointing_at_fake_api")
def test_a_platform_without_the_action_is_refused_naming_the_ones_with_it(
    fake_api_url: str, action: str, platform: str, values: dict[str, Any]
) -> None:
    _store_is(fake_api_url, platform)

    with pytest.raises(UserInputError, match="is not available for") as refused:
        BY_NAME[action].run({"store_id": STORE_ID, **values})
    assert not _RETIRED.search(refused.value.message)
    assert len(respx.calls) == 1  # only the platform lookup


@respx.mock
@pytest.mark.parametrize(("action", "kind"), [("publish_listings", "publish"), ("withdraw_listings", "withdraw")])
@pytest.mark.usefixtures("env_pointing_at_fake_api")
def test_publish_and_withdraw_are_one_bulk_job_of_their_kind(fake_api_url: str, action: str, kind: str) -> None:
    route = respx.post(f"{fake_api_url}/agent/stores/{STORE_ID}/bulk-listing-jobs").mock(
        return_value=httpx.Response(202, json={"id": "job-1", "status": "queued"})
    )

    answer = BY_NAME[action].run({"store_id": STORE_ID, "listing_ids": ["L1"]})

    assert _sent(route) == {"listing_ids": ["L1"], "kind": kind}
    assert f'get_listing_job(store_id="{STORE_ID}", job_id="job-1")' in answer["note"]
    assert "sellerclaw_" not in answer["note"]


@respx.mock
@pytest.mark.usefixtures("env_pointing_at_fake_api")
def test_a_change_waiting_on_the_owner_points_at_the_card_and_this_surface_s_answer_tool(
    fake_api_url: str,
) -> None:
    respx.patch(f"{fake_api_url}/agent/sales-channels/{STORE_ID}").mock(
        return_value=httpx.Response(202, json={"status": "pending_approval", "action_request_id": "R1"})
    )

    answer = BY_NAME["propose_store_markup"].run({"store_id": STORE_ID, "markup_percent": 30})

    assert 'sellerclaw_approval(request="R1")' in answer["note"]
    assert 'answer_action_request(request_id="R1"' in answer["note"]
    assert "sellerclaw_write" not in answer["note"]


@respx.mock
@pytest.mark.parametrize(
    ("values", "body"),
    [
        pytest.param(
            {"reorder_lead_time_days": 9, "target_market": "US"},
            {"reorder_lead_time_days": 9, "target_market": "US"},
            id="several-settings-one-change",
        ),
        pytest.param(
            {"remove_listing_quantity_cap": True}, {"listing_quantity_cap": None}, id="removing-the-cap-sends-null"
        ),
        pytest.param({"shipping_included_in_price": False}, {"shipping_included_in_price": False}, id="false-is-sent"),
    ],
)
@pytest.mark.usefixtures("env_pointing_at_fake_api")
def test_update_store_settings_sends_only_what_was_asked(
    fake_api_url: str, values: dict[str, Any], body: dict[str, Any]
) -> None:
    route = respx.patch(f"{fake_api_url}/agent/sales-channels/{STORE_ID}").mock(
        return_value=httpx.Response(200, json={"id": STORE_ID})
    )

    BY_NAME["update_store_settings"].run({"store_id": STORE_ID, **values})

    assert _sent(route) == body


def test_update_store_settings_with_nothing_to_change_is_refused() -> None:
    with pytest.raises(UserInputError, match="at least one setting"):
        BY_NAME["update_store_settings"].run({"store_id": STORE_ID})


@respx.mock
@pytest.mark.usefixtures("env_pointing_at_fake_api")
def test_a_platform_s_command_gets_only_the_fields_it_takes(fake_api_url: str) -> None:
    _store_is(fake_api_url, "woocommerce")
    route = respx.get(f"{fake_api_url}/agent/stores/{STORE_ID}/reviews").mock(
        return_value=httpx.Response(200, json={"items": []})
    )

    BY_NAME["list_reviews"].run({"store_id": STORE_ID, "days": 7, "limit": 5})

    assert dict(route.calls.last.request.url.params) == {"limit": "5"}


@respx.mock
@pytest.mark.usefixtures("env_pointing_at_fake_api")
def test_queued_media_points_at_the_card_not_at_a_command(fake_api_url: str) -> None:
    respx.post(f"{fake_api_url}/agent/media/image-jobs").mock(
        return_value=httpx.Response(
            202, json={"jobs": [{"id": "j1"}], "note": "read it with `job-status <job_id> --wait-seconds 25`"}
        )
    )

    answer = BY_NAME["generate_images"].run({"images": [{"prompt": "a mug"}]})

    assert "sellerclaw_media" in answer["note"]
    assert "job-status" not in answer["note"]


@respx.mock
@pytest.mark.parametrize(
    ("action", "platform", "values", "command"),
    [
        pytest.param("cancel_order", "shopify", {"order_id": "1001"}, "shopify-orders cancel", id="one-command"),
        pytest.param(
            "ship_order",
            "ebay",
            {"order_id": ORDER_ID, "tracking_number": "1Z9", "carrier": "UPS"},
            "ebay-orders create-fulfillment",
            id="the-change-not-the-order-lookup-before-it",
        ),
        pytest.param("list_connections", "ebay", {}, "channels list", id="several-reads-named-by-the-first"),
    ],
)
@pytest.mark.usefixtures("env_pointing_at_fake_api")
def test_the_command_an_action_ran_reaches_its_usage_report(
    fake_api_url: str, action: str, platform: str, values: dict[str, Any], command: str
) -> None:
    _store_is(fake_api_url, platform)
    respx.route(host="api.test.sellerclaw.ai").mock(return_value=httpx.Response(200, json={"ok": True}))
    holder: dict[str, str] = {}
    reset = mcp_usage._executed.set(holder)
    try:
        BY_NAME[action].run({"store_id": STORE_ID, **values})
    finally:
        mcp_usage._executed.reset(reset)

    assert holder["command"] == command


@respx.mock
@pytest.mark.usefixtures("env_pointing_at_fake_api")
def test_deleting_ebay_listings_reports_each_one_even_when_one_is_refused(fake_api_url: str) -> None:
    _store_is(fake_api_url, "ebay")
    respx.delete(f"{fake_api_url}/agent/stores/{STORE_ID}/ebay-listings/L1").mock(return_value=httpx.Response(204))
    respx.delete(f"{fake_api_url}/agent/stores/{STORE_ID}/ebay-listings/L2").mock(
        return_value=httpx.Response(404, json={"detail": "Listing L2 not found"})
    )
    respx.delete(f"{fake_api_url}/agent/stores/{STORE_ID}/ebay-listings/L3").mock(return_value=httpx.Response(204))

    answer = BY_NAME["delete_listings"].run({"store_id": STORE_ID, "listing_ids": ["L1", "L2", "L3"]})

    assert [(r["listing_id"], r["deleted"]) for r in answer["results"]] == [("L1", True), ("L2", False), ("L3", True)]
    assert "L2 not found" in answer["results"][1]["error"]


@respx.mock
@pytest.mark.parametrize(
    ("tracking", "key", "shown"),
    [
        pytest.param(httpx.Response(200, json={"number": "YT1"}), "tracking", "YT1", id="shipped"),
        pytest.param(
            httpx.Response(502, json={"detail": "CJ: tracking not available yet"}),
            "tracking_error",
            "CJ: tracking not available yet",
            id="unreadable-tracking-is-said-not-hidden",
        ),
    ],
)
@pytest.mark.usefixtures("env_pointing_at_fake_api")
def test_a_supplier_order_comes_with_its_tracking_or_why_there_is_none(
    fake_api_url: str, tracking: httpx.Response, key: str, shown: str
) -> None:
    order_path = f"{fake_api_url}/agent/suppliers/cj/orders/CJ1"
    respx.get(order_path).mock(return_value=httpx.Response(200, json={"status": "paid"}))
    respx.get(f"{order_path}/tracking").mock(return_value=tracking)

    answer = BY_NAME["get_supplier_order"].run({"provider": "cj", "supplier_order_id": "CJ1"})

    assert set(answer) == {"order", key}
    assert answer["order"] == {"status": "paid"}
    assert shown in json.dumps(answer[key])


def test_a_job_no_tool_here_reads_answers_as_it_is_instead_of_failing_the_write() -> None:
    _, reader = _resolve("listings", "bulk-job")

    assert _action._poll_call("listings", reader, {"store_id": "s", "job_id": "j"}) == (
        'get_listing_job(store_id="s", job_id="j")'
    )
    assert _action._poll_call("media", reader, {"job_id": "j"}) is None


# --------------------------------------------------------------------------- every action, run


#: The store's platform an action is run against, where the default (eBay) has no such action.
_PLATFORM_FOR = {"cancel_order": "shopify", "get_publish_status": "amazon", "list_fba_stock": "amazon"}
#: Arguments beyond the required ones, for actions that need one of several optional inputs.
_EXTRA = {
    "update_store_settings": {"reorder_lead_time_days": 5},
    "ship_order": {"carrier": "UPS"},
    "reply_to_review": {"review_id": "f1", "buyer": "b1", "text": "Thanks"},
    "search_supplier_products": {"queries": ["mug"]},
    "check_supplier_stock": {"product_id": "p1"},
    "quote_supplier_shipping": {"destination": {"country_code": "US", "zip_code": "10001"}},
    "check_ai_visibility": {"target": "mugs"},
    "update_ebay_campaign_listings": {"remove_listing_ids": ["1"]},
    "list_ad_campaigns": {"store_id": STORE_ID},
    "get_ad_metrics": {"store_id": STORE_ID},
    "pause_ad_campaign": {"store_id": STORE_ID},
    "resume_ad_campaign": {"store_id": STORE_ID},
    "get_social_profile": {"handle": "brand"},
    "get_social_posts": {"handle": "brand"},
    "preview_import": {"file_id": "f1"},
    "delete_draft_listings": {"listing_ids": ["L1"]},
}
_SAMPLE = {"string": "x", "integer": 1, "number": 1.5, "boolean": True, "object": {"a": "b"}}


def _arguments(action: Action) -> dict[str, Any]:
    values: dict[str, Any] = {}
    for param in action.params:
        if not param.required:
            continue
        if param.name == "store_id":
            values[param.name] = STORE_ID
        elif param.choices:
            values[param.name] = [param.choices[0]] if param.type == "array" else param.choices[0]
        elif param.type == "array":
            values[param.name] = [{"a": "b"}] if param.items == "object" else ["x"]
        else:
            values[param.name] = _SAMPLE[param.type]
    return {**values, **_EXTRA.get(action.name, {})}


def _command_of(request: httpx.Request) -> Any:
    """The registry command a request was made by: its method and the path template it fills."""
    from sellerclaw_cli._command_group import REGISTRY

    path = request.url.path
    for group in REGISTRY:
        for cmd in group.commands:
            pattern = "^" + re.sub(r"\{[^}]+\}", "[^/]+", cmd.path) + "$"
            if cmd.method == request.method and re.match(pattern, path):
                return cmd
    raise AssertionError(f"no command makes {request.method} {path}")


@respx.mock
@pytest.mark.parametrize("action", ACTIONS, ids=lambda a: a.name)
@pytest.mark.usefixtures("env_pointing_at_fake_api")
def test_every_action_runs_and_its_read_only_hint_tells_the_truth(fake_api_url: str, action: Action) -> None:
    """Run each action against a fake API: it must get through, and say truly whether it changes things.

    A read-only hint lets ChatGPT run the tool without asking the owner, so one that wrote anything
    would act behind their back; a write marked as one would ask for nothing.
    """
    platform = _PLATFORM_FOR.get(action.name, "ebay")
    respx.get(f"{fake_api_url}/agent/sales-channels/{STORE_ID}").mock(
        return_value=httpx.Response(200, json={"id": STORE_ID, "platform": platform})
    )
    respx.route(host="api.test.sellerclaw.ai").mock(return_value=httpx.Response(200, json={"ok": True}))

    action.run(_arguments(action))

    made = [
        _command_of(call.request)
        for call in respx.calls
        if (call.request.method, call.request.url.path) != ("GET", f"/agent/sales-channels/{STORE_ID}")
    ]
    assert made, "the action reached no command"
    if action.read_only:
        assert all(_reads(cmd) for cmd in made), [c.name for c in made]
    else:
        assert any(not _reads(cmd) for cmd in made), [c.name for c in made]


# --------------------------------------------------------------------------- over HTTP


def _app(monkeypatch: pytest.MonkeyPatch) -> Any:
    monkeypatch.setenv("SELLERCLAW_MCP_ISSUER_URL", ISSUER)
    monkeypatch.setenv("SELLERCLAW_MCP_RESOURCE_URL", RESOURCE)
    monkeypatch.setenv("SELLERCLAW_API_URL", ISSUER)
    monkeypatch.setenv("HOST", "0.0.0.0")  # noqa: S104
    return create_http_app()


def _list_tools(app: Any, path: str, token: str | None) -> httpx.Response:
    async def call() -> httpx.Response:
        async with app.router.lifespan_context(app):
            transport = httpx.ASGITransport(app=app)
            async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
                headers = {
                    "Accept": "application/json, text/event-stream",
                    "Content-Type": "application/json",
                    "MCP-Protocol-Version": "2025-06-18",
                }
                if token:
                    headers["Authorization"] = f"Bearer {token}"
                return await client.post(
                    path, json={"jsonrpc": "2.0", "id": 1, "method": "tools/list", "params": {}}, headers=headers
                )

    return asyncio.run(call())


def _tool_names(resp: httpx.Response) -> set[str]:
    text = resp.text
    if resp.headers.get("content-type", "").startswith("text/event-stream"):
        text = next(line[5:] for line in text.splitlines() if line.startswith("data:"))
    return {t["name"] for t in json.loads(text)["result"]["tools"]}


def test_the_chatgpt_path_asks_for_sign_in_like_the_other(monkeypatch: pytest.MonkeyPatch) -> None:
    resp = _list_tools(_app(monkeypatch), "/chatgpt/mcp", token=None)

    assert resp.status_code == 401
    assert "www-authenticate" in {k.lower() for k in resp.headers}


@respx.mock
@pytest.mark.parametrize(
    ("path", "has", "lacks"),
    [
        pytest.param("/chatgpt/mcp", "ship_order", "sellerclaw_write", id="chatgpt-gets-actions"),
        pytest.param("/mcp", "sellerclaw_write", "ship_order", id="everyone-else-keeps-the-runners"),
    ],
)
def test_each_path_serves_its_own_tools(monkeypatch: pytest.MonkeyPatch, path: str, has: str, lacks: str) -> None:
    respx.get(f"{ISSUER}/agent/me").mock(return_value=httpx.Response(200, json={"id": "user-1"}))

    resp = _list_tools(_app(monkeypatch), path, token="sca_good")

    assert resp.status_code == 200, resp.text
    names = _tool_names(resp)
    assert has in names
    assert lacks not in names
    assert "sellerclaw_orders" in names
