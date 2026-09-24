from __future__ import annotations

import asyncio
import base64
import json

import httpx
import pytest
import respx

from sellerclaw_cli import __version__, mcp_apps
from sellerclaw_cli._client import DEFAULT_TIMEOUT_SECONDS
from sellerclaw_cli._command_group import LONG_TIMEOUT_SECONDS, REGISTRY
from sellerclaw_cli._errors import UserInputError

# Importing the CLI app registers every command group into the shared REGISTRY that the MCP
# proxy tools read. Without this import the registry would be empty for direct-call tests.
from sellerclaw_cli.cli import app  # noqa: F401
from sellerclaw_cli.mcp_server import (
    _LIST_CACHE_TTL_MS,
    MCP_HIDDEN_COMMANDS,
    MCP_VISIBLE_GROUPS,
    SERVER_WEBSITE_URL,
    build_server,
    describe_command,
    list_groups,
    run_command,
)

pytestmark = pytest.mark.unit

ORDER_ID = "22222222-2222-4222-8222-222222222222"
STORE_ID = "11111111-1111-4111-8111-111111111111"
LISTING_ID = "33333333-3333-4333-8333-333333333333"


@pytest.fixture
def env_pointing_at_fake_api(
    monkeypatch: pytest.MonkeyPatch,
    fake_api_url: str,
    fake_token: str,
) -> None:
    monkeypatch.setenv("SELLERCLAW_API_URL", fake_api_url)
    monkeypatch.setenv("SELLERCLAW_TOKEN", fake_token)


def _url(fake_api_url: str, group: str, command: str, **positionals: str) -> str:
    """Concrete request URL for a command — resolved from the live schema, so it stays correct
    even if a path is reworked."""
    path = describe_command(group, command)["path"]
    for name, value in positionals.items():
        path = path.replace("{" + name + "}", value)
    return f"{fake_api_url}{path}"


# --------------------------------------------------------------------------- audience filter

# The only groups the MCP server hides, and the whole reason it hides them: they are the machinery
# of *our* agent (sellerclaw-agent) — its supervisor/subagent task tree, the goals that drive it,
# the roster it works with, the chats it holds with the owner, and the models it routes to. An MCP
# client is the owner themselves, and on the MCP-only plan that agent is switched off entirely.
# Everything else they run their business with is visible. All of these exist in the CLI registry;
# none may reach `sellerclaw_groups`.
_HIDDEN_FROM_MCP = {
    "chats",
    "goals",
    "team",
    "team-tasks",
    "subagent-tasks",
    "models",
}


#: Every storefront a seller can connect. The allowlist has to cover all of them: someone who
#: connected a shop expects to run it from Claude, and a channel left out is not "not exposed yet" —
#: it is a connected store the person cannot touch at all, with no error that explains why. Etsy sat
#: in exactly that hole, then TikTok Shop and Walmart: fully supported by the CLI, invisible to
#: every MCP client.
_SUPPORTED_STOREFRONTS = (
    "shopify",
    "ebay",
    "amazon",
    "etsy",
    "woocommerce",
    "wix",
    "bigcommerce",
    "walmart",
    "tiktok-shop",
)
#: The groups a channel carries whatever it is: raw passthrough, shop admin, listings, orders.
_CHANNEL_GROUP_SUFFIXES = ("", "-store", "-listings", "-orders")


def test_allowlist_names_all_exist_in_registry() -> None:
    """Guard against a typo in MCP_VISIBLE_GROUPS — every name must be a real CLI group."""
    unknown = MCP_VISIBLE_GROUPS - {g.name for g in REGISTRY}
    assert not unknown, f"MCP_VISIBLE_GROUPS names absent from the CLI registry: {sorted(unknown)}"


@pytest.mark.parametrize("channel", [pytest.param(c, id=c) for c in _SUPPORTED_STOREFRONTS])
def test_every_supported_storefront_channel_is_visible(channel: str) -> None:
    in_registry = {g.name for g in REGISTRY}
    channel_groups = {f"{channel}{suffix}" for suffix in _CHANNEL_GROUP_SUFFIXES} & in_registry

    assert channel_groups, f"no {channel} groups in the CLI registry — the naming must have changed"
    missing = sorted(channel_groups - MCP_VISIBLE_GROUPS)
    assert not missing, (
        f"a connected {channel} store cannot be managed over MCP: "
        f"{', '.join(missing)} exists in the CLI but is not in MCP_VISIBLE_GROUPS."
    )


def test_an_etsy_shop_is_reachable_from_an_mcp_client() -> None:
    """The regression this guards: Etsy was missing from the allowlist entirely, finances included,
    so a connected Etsy shop could not be managed from Claude at all."""
    groups = {g["group"]: g for g in list_groups()}

    assert {"etsy", "etsy-store", "etsy-listings", "etsy-orders", "etsy-finances"} <= set(groups)
    listing_commands = {c["name"] for c in groups["etsy-listings"]["commands"]}
    assert {"draft", "publish", "withdraw", "delete"} <= listing_commands


def test_list_groups_exposes_exactly_the_allowlist() -> None:
    assert {g["group"] for g in list_groups()} == set(MCP_VISIBLE_GROUPS)


def test_list_groups_hides_agent_internal_groups() -> None:
    # The hidden groups really do exist in the CLI (so this stays meaningful), but none surface.
    assert _HIDDEN_FROM_MCP <= {g.name for g in REGISTRY}
    assert not (_HIDDEN_FROM_MCP & {g["group"] for g in list_groups()})


def test_describe_hidden_group_reads_as_unknown() -> None:
    with pytest.raises(UserInputError, match="unknown group 'team-tasks'"):
        describe_command("team-tasks", "overview")


def test_run_hidden_group_reads_as_unknown() -> None:
    with pytest.raises(UserInputError, match="unknown group 'subagent-tasks'"):
        run_command("subagent-tasks", "list")


def test_the_owner_can_answer_a_pending_approval_without_leaving_the_conversation() -> None:
    """The point of exposing `action-requests`: a gated action must not end in "go to the website".

    Listing what is waiting and closing one with the owner's own words are the two calls that make
    an approval answerable from inside Claude, so both are pinned here.
    """
    commands = {c["command"] for c in describe_command("action-requests")["commands"]}
    assert {"list", "get", "confirm", "cancel"} <= commands

    confirm = describe_command("action-requests", "confirm")
    assert "quote" in {field["name"] for field in confirm["body_fields"]}


def test_a_command_written_for_our_agent_is_hidden_inside_a_visible_group() -> None:
    """`action-requests create` asks the owner to go and do something — which an assistant sitting
    in front of that same owner never needs, and which must read as absent rather than as refused."""
    listed = {g["group"]: g for g in list_groups()}["action-requests"]
    assert "create" not in {c["name"] for c in listed["commands"]}
    assert "create" not in {c["command"] for c in describe_command("action-requests")["commands"]}

    with pytest.raises(UserInputError, match="unknown command 'create'"):
        describe_command("action-requests", "create")
    with pytest.raises(UserInputError, match="unknown command 'create'"):
        run_command("action-requests", "create", body={"title": "x"})


def test_hidden_commands_all_name_a_real_command_of_a_visible_group() -> None:
    """A typo here would hide nothing and nobody would notice."""
    by_name = {g.name: g for g in REGISTRY}
    for group, command in MCP_HIDDEN_COMMANDS:
        assert group in MCP_VISIBLE_GROUPS, f"{group} is hidden wholesale; the pair is dead weight"
        assert command in {c.name for c in by_name[group].commands}, (
            f"{group} {command} is not a command of that group"
        )


# --------------------------------------------------------------------------- discovery


def test_list_groups_includes_known_groups_with_their_commands() -> None:
    groups = {g["group"]: g for g in list_groups()}
    assert {"orders", "listings", "ebay-listings", "shopify-orders"} <= set(groups)
    orders_commands = {c["name"] for c in groups["orders"]["commands"]}
    assert {"list", "get", "update", "search"} <= orders_commands
    # Each command carries its HTTP method and summary, not just a name.
    update = next(c for c in groups["orders"]["commands"] if c["name"] == "update")
    assert update["method"] == "PATCH"


def test_describe_command_returns_full_schema_for_a_write_command() -> None:
    detail = describe_command("orders", "update")
    assert detail["method"] == "PATCH"
    assert detail["positionals"] == ["order_id"]
    assert detail["takes_body"] is True
    assert detail["body_fields"], "a write command should advertise its body fields"
    # The call_example is a ready-made sellerclaw_run argument object.
    example = detail["call_example"]
    assert example["group"] == "orders"
    assert example["command"] == "update"
    assert example["positionals"] == {"order_id": "<order_id>"}


def test_describe_command_surfaces_flag_choices_and_ranges() -> None:
    detail = describe_command("ebay-listings", "list")
    flags = {f["name"]: f for f in detail["flags"]}
    assert "limit" in flags
    assert flags["limit"]["minimum"] == 1
    assert flags["limit"]["maximum"] == 100


_LISTINGS_COMMANDS = {
    "get",
    "adopt-marketplace-version",
    "search",
    "variable",
    "sync",
    "drafts",
    "readiness",
    "check",
    "bulk-update",
    "delete-drafts",
    "create-drafts",
    "bulk-publish",
    "bulk-jobs",
    "bulk-job",
    "history",
}


def test_describe_a_whole_group_without_naming_a_command() -> None:
    """Omitting the command describes every command in the group at once — one call, not N."""
    detail = describe_command("listings")
    assert detail["group"] == "listings"
    described = {cmd["command"] for cmd in detail["commands"]}
    assert described == _LISTINGS_COMMANDS
    search = next(cmd for cmd in detail["commands"] if cmd["command"] == "search")
    assert {f["name"] for f in search["flags"]} >= {"q", "product_id", "store_id", "sku"}


def test_describe_surfaces_the_alternative_spellings_of_the_search_flag() -> None:
    """The caller's first guess at the search flag must be accepted, so the schema advertises the
    other spellings — the API names it --q here and --search there."""
    detail = describe_command("listings", "search")
    q_flag = next(f for f in detail["flags"] if f["name"] == "q")
    assert "query" in q_flag["also_accepted_as"]
    assert "search" in q_flag["also_accepted_as"]


def test_describe_command_unknown_group_raises() -> None:
    with pytest.raises(UserInputError, match="unknown group 'does-not-exist'"):
        describe_command("does-not-exist", "list")


def test_describe_command_unknown_command_raises() -> None:
    with pytest.raises(UserInputError, match="unknown command 'nope' in group 'orders'"):
        describe_command("orders", "nope")


def test_reading_a_listing_by_id_redirects_to_the_channel_agnostic_group() -> None:
    """`shopify-listings get` is the natural guess but a SellerClaw id is not channel-scoped, so
    the verb only exists in the cross-channel group — the error has to say where it went."""
    with pytest.raises(UserInputError, match="group='listings'"):
        describe_command("shopify-listings", "get")


# --------------------------------------------------------------------------- run


@respx.mock
def test_run_command_substitutes_positional_and_returns_response(
    env_pointing_at_fake_api: None,  # noqa: ARG001
    fake_api_url: str,
) -> None:
    payload = {"id": LISTING_ID, "title": "Widget"}
    route = respx.get(_url(fake_api_url, "listings", "get", listing_id=LISTING_ID)).mock(
        return_value=httpx.Response(200, json=payload)
    )
    result = run_command("listings", "get", positionals={"listing_id": LISTING_ID})
    assert route.call_count == 1
    assert result == payload


@respx.mock
def test_run_command_maps_flags_to_query_params_and_drops_unset(
    env_pointing_at_fake_api: None,  # noqa: ARG001
    fake_api_url: str,
) -> None:
    route = respx.get(_url(fake_api_url, "ebay-listings", "list", store_id=STORE_ID)).mock(
        return_value=httpx.Response(200, json=[])
    )
    # A set flag becomes a query param...
    run_command("ebay-listings", "list", positionals={"store_id": STORE_ID}, flags={"limit": 10})
    assert route.calls[0].request.url.params["limit"] == "10"
    # ...while an explicitly-None flag is dropped rather than sent as `?limit=`.
    run_command("ebay-listings", "list", positionals={"store_id": STORE_ID}, flags={"limit": None})
    assert "limit" not in route.calls[1].request.url.params


@respx.mock
def test_run_command_accepts_kebab_and_alias_flag_spellings(
    env_pointing_at_fake_api: None,  # noqa: ARG001
    fake_api_url: str,
) -> None:
    """A flag is reachable by its snake name, its --kebab spelling, or a documented alias."""
    route = respx.get(_url(fake_api_url, "orders", "list")).mock(
        return_value=httpx.Response(200, json=[])
    )
    # `--store-id` is the alias of the `sales_channel_id` flag (query key `sales_channel_id`).
    run_command("orders", "list", flags={"store-id": STORE_ID})
    assert route.calls.last.request.url.params["sales_channel_id"] == STORE_ID


@respx.mock
def test_run_command_sends_json_body_for_write_commands(
    env_pointing_at_fake_api: None,  # noqa: ARG001
    fake_api_url: str,
) -> None:
    body = {"status": "cancelled"}
    route = respx.patch(_url(fake_api_url, "orders", "update", order_id=ORDER_ID)).mock(
        return_value=httpx.Response(200, json={"ok": True})
    )
    run_command("orders", "update", positionals={"order_id": ORDER_ID}, body=body)
    assert json.loads(route.calls.last.request.content) == body


def test_run_command_missing_positional_raises() -> None:
    with pytest.raises(UserInputError, match="missing positional argument"):
        run_command("ebay-listings", "list", positionals={})


def test_run_command_unknown_flag_raises(
    env_pointing_at_fake_api: None,  # noqa: ARG001
) -> None:
    with pytest.raises(UserInputError, match="unknown flag 'bogus'"):
        run_command(
            "ebay-listings",
            "list",
            positionals={"store_id": STORE_ID},
            flags={"bogus": 1},
        )


def test_run_command_rejects_body_on_command_without_one() -> None:
    with pytest.raises(UserInputError, match="does not take a body"):
        run_command("listings", "get", positionals={"listing_id": LISTING_ID}, body={"x": 1})


# --------------------------------------------------------------------------- background jobs

JOB_ID = "job-42"


@respx.mock
def test_a_queued_job_comes_back_with_the_call_that_reads_it(
    env_pointing_at_fake_api: None,  # noqa: ARG001
    fake_api_url: str,
) -> None:
    """A job id and no way to read it is the dead end that makes a caller re-send the write.

    The CLI can offer `--wait`; there is no such flag here, so the note has to carry the whole answer:
    which call reads the job, with both ids already in it.
    """
    job = {"id": JOB_ID, "status": "queued", "kind": "publish", "total_count": 2}
    route = respx.post(_url(fake_api_url, "listings", "bulk-publish", store_id=STORE_ID)).mock(
        return_value=httpx.Response(202, json=job)
    )

    result = run_command(
        "listings",
        "bulk-publish",
        positionals={"store_id": STORE_ID},
        body={"kind": "publish", "listing_ids": [LISTING_ID]},
    )

    assert route.call_count == 1
    # The job itself survives intact — the note is added, nothing is replaced.
    assert {k: result[k] for k in job} == job
    note = result["note"]
    assert 'sellerclaw_run(group="listings", command="bulk-job"' in note
    assert f'"store_id": "{STORE_ID}"' in note
    assert f'"job_id": "{JOB_ID}"' in note
    # Advice a caller here cannot take, and the one thing it must not do instead.
    assert "--wait" not in note
    assert "second job" in note


@respx.mock
@pytest.mark.parametrize(
    "status",
    [
        pytest.param("succeeded", id="done-already"),
        pytest.param("failed", id="refused-already"),
        pytest.param("partial", id="partly-done-already"),
    ],
)
def test_a_job_that_is_already_over_is_handed_back_as_the_result(
    env_pointing_at_fake_api: None,  # noqa: ARG001
    fake_api_url: str,
    status: str,
) -> None:
    """A small batch can be done — or refused — before the call returns.

    Then the payload in hand is the outcome. Telling the caller "running in the background, read it
    later" would spend a turn on a job that has nothing left to say, and on a failure it would hide
    the refusal behind a promise.
    """
    job = {"id": JOB_ID, "status": status, "error": "nothing was publishable"}
    respx.post(_url(fake_api_url, "listings", "bulk-publish", store_id=STORE_ID)).mock(
        return_value=httpx.Response(200, json=job)
    )

    result = run_command(
        "listings",
        "bulk-publish",
        positionals={"store_id": STORE_ID},
        body={"kind": "publish", "listing_ids": [LISTING_ID]},
    )

    assert result == job


@respx.mock
def test_an_ordinary_response_is_not_dressed_up_as_a_queued_job(
    env_pointing_at_fake_api: None,  # noqa: ARG001
    fake_api_url: str,
) -> None:
    """Plenty of responses carry an id and a status; only a command that queues work gets a note."""
    payload = {"id": LISTING_ID, "status": "active", "title": "Widget"}
    respx.get(_url(fake_api_url, "listings", "get", listing_id=LISTING_ID)).mock(
        return_value=httpx.Response(200, json=payload)
    )

    result = run_command("listings", "get", positionals={"listing_id": LISTING_ID})

    assert result == payload


def test_describe_says_which_commands_queue_work_and_how_long_a_call_may_take() -> None:
    """A caller with a deadline of its own, and one holding a job id, both read it here.

    ``amazon-listings draft`` is the sharp case: it declares the long budget for the work, but over
    MCP the call only queues the job, so the number advertised here is the one the call actually
    spends — the same one :func:`run_command` puts on the wire.
    """
    starter = describe_command("amazon-listings", "draft")

    assert starter["starts_background_job"] is True
    assert starter["poll_with"] == {
        "group": "listings",
        "command": "bulk-job",
        "positionals": ["store_id", "job_id"],
    }
    assert starter["timeout_seconds"] == DEFAULT_TIMEOUT_SECONDS

    # One that does the work inside the request advertises the long budget it genuinely needs, and
    # says nothing about a job, because there is none to read.
    synchronous = describe_command("ebay-listings", "publish")

    assert synchronous["timeout_seconds"] == LONG_TIMEOUT_SECONDS
    assert "starts_background_job" not in synchronous
    assert "poll_with" not in synchronous


# --------------------------------------------------------------------------- wiring


def test_build_server_registers_the_proxy_tools_and_the_screens() -> None:
    """The whole surface, pinned: four discovery/proxy tools plus one per screen action.

    An exact set rather than a containment check, because every addition here is a line item in
    every client's tool list — it should not be possible to add one without saying so.
    """
    server = build_server()
    tools = asyncio.run(server.list_tools())
    by_name = {t.name: t for t in tools}
    assert set(by_name) == {
        "sellerclaw_guide",
        "sellerclaw_groups",
        "sellerclaw_describe",
        "sellerclaw_run",
        "sellerclaw_store_summary",
        "sellerclaw_orders",
        "sellerclaw_order_mark_shipped",
        "sellerclaw_approval",
        "sellerclaw_approval_decide",
        "sellerclaw_attention",
        "sellerclaw_listings",
        "sellerclaw_ads",
        "sellerclaw_connections",
    }
    run_props = set(by_name["sellerclaw_run"].input_schema["properties"])
    assert {"group", "command", "positionals", "flags", "body"} <= run_props
    describe_props = set(by_name["sellerclaw_describe"].input_schema["properties"])
    assert {"group", "command"} <= describe_props
    assert "topic" in by_name["sellerclaw_guide"].input_schema["properties"]


def test_every_tool_carries_a_human_title() -> None:
    """A permission dialog shows the title, and "Sellerclaw run" tells nobody what it does."""
    tools = asyncio.run(build_server().list_tools())

    assert {t.name: t.title for t in tools} == {
        "sellerclaw_guide": "Read a SellerClaw guide",
        "sellerclaw_groups": "List SellerClaw commands",
        "sellerclaw_describe": "Describe a SellerClaw command",
        "sellerclaw_run": "Run a SellerClaw command",
        "sellerclaw_store_summary": "Show the store summary",
        "sellerclaw_orders": "Show the order board",
        "sellerclaw_order_mark_shipped": "Mark an order shipped",
        "sellerclaw_approval": "Show a request waiting on the owner",
        "sellerclaw_approval_decide": "Record the owner's answer",
        "sellerclaw_attention": "Show what needs the owner",
        "sellerclaw_listings": "Show listings",
        "sellerclaw_ads": "Show the ads",
        "sellerclaw_connections": "Show the connections",
    }


def test_discovery_is_advertised_as_reading_and_the_acting_tools_as_writing() -> None:
    """An unannotated tool is treated as destructive, which made reading a guide look dangerous.

    A client renders these hints in the dialog where someone decides whether to allow the call, so
    a warning on everything is a warning on nothing. Discovery reads this process's own registry
    and never leaves it; the screens and ``sellerclaw_run`` touch the account.
    """
    by_name = {t.name: t.annotations for t in asyncio.run(build_server().list_tools())}

    for name in ("sellerclaw_guide", "sellerclaw_groups", "sellerclaw_describe"):
        annotations = by_name[name]
        assert annotations is not None, name
        assert annotations.read_only_hint is True, name
        assert annotations.destructive_hint is False, name
        assert annotations.idempotent_hint is True, name
        assert annotations.open_world_hint is False, name

    run = by_name["sellerclaw_run"]
    assert run is not None
    assert run.read_only_hint is False
    assert run.destructive_hint is True
    assert run.idempotent_hint is False
    assert run.open_world_hint is True


def test_the_handshake_carries_our_branding_and_our_version() -> None:
    """Clients that render server metadata should get SellerClaw's logo, site and version.

    The icon travels inline so a permission dialog never has to reach our web host, and the version
    must be ours: an unversioned server reports an empty one, and the SDK's own number would be
    quoted back at anyone asked "which version are you running?".
    """
    server = build_server()

    assert server.website_url == SERVER_WEBSITE_URL
    assert server.version == __version__
    icon = (server.icons or [])[0]
    assert icon.mime_type == "image/png"
    assert icon.src.startswith("data:image/png;base64,")
    # A real image, not an empty placeholder: the PNG magic number survives the round trip.
    assert base64.b64decode(icon.src.split(",", 1)[1])[:8] == b"\x89PNG\r\n\x1a\n"


def test_the_static_lists_are_advertised_as_cacheable() -> None:
    """Four fixed tools re-listed every turn is a round trip and a prompt cache spent for nothing.

    The protocol's freshness hint defaults to "already stale", so the gain only arrives if we say
    otherwise. ``public`` is honest here: the list is byte-identical for every account, built from a
    registry frozen at import — there is no per-user answer to leak into a shared cache.
    """
    hints = build_server()._lowlevel_server.cache_hints

    assert set(hints) == {
        "server/discover",
        "tools/list",
        "prompts/list",
        "resources/list",
        "resources/read",
    }
    for method in ("server/discover", "tools/list", "prompts/list", "resources/list"):
        assert hints[method].ttl_ms == _LIST_CACHE_TTL_MS, method
    # A screen's document is just as public, and rebuilt far more often: an hour of a client
    # holding the previous one is an hour of a card whose scripts were deleted by the last deploy.
    assert hints["resources/read"].ttl_ms == mcp_apps.DOCUMENT_CACHE_TTL_MS
    assert hints["resources/read"].ttl_ms < _LIST_CACHE_TTL_MS
    for method, hint in hints.items():
        assert hint.scope == "public", method


def test_a_build_without_the_logo_still_serves(monkeypatch: pytest.MonkeyPatch) -> None:
    """Losing a decoration must not take the server down.

    The hosted server is installed from a wheel; if one ever shipped without the asset, it has to
    keep answering tool calls with a blank tile rather than refuse to start.
    """
    import importlib.resources

    def _missing(_package: str) -> object:
        raise FileNotFoundError("this build has no assets")

    monkeypatch.setattr(importlib.resources, "files", _missing)

    server = build_server()

    assert not server.icons
    assert server.website_url == SERVER_WEBSITE_URL
