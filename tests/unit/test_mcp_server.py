from __future__ import annotations

import asyncio
import base64
import json

import httpx
import pytest
import respx

from sellerclaw_cli import __version__
from sellerclaw_cli._command_group import REGISTRY
from sellerclaw_cli._errors import UserInputError

# Importing the CLI app registers every command group into the shared REGISTRY that the MCP
# proxy tools read. Without this import the registry would be empty for direct-call tests.
from sellerclaw_cli.cli import app  # noqa: F401
from sellerclaw_cli.mcp_server import (
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

# Groups the CLI keeps for the OpenClaw agent (sellerclaw-agent) but the MCP server must hide
# from human MCP clients: the agent's own task/goal orchestration, owner escalation & chat reads,
# in-chat media/files, plus the Shopify content + spreadsheet/web utilities left out of the
# allowlist. All exist in the CLI registry; none may reach `sellerclaw_groups`.
_HIDDEN_FROM_MCP = {
    "chats",
    "goals",
    "team-tasks",
    "subagent-tasks",
    "action-requests",
    "media",
    "files",
    "spreadsheet",
    "web",
    "shopify-collections",
    "shopify-pages",
    "shopify-menus",
    "shopify-themes",
}


def test_allowlist_names_all_exist_in_registry() -> None:
    """Guard against a typo in MCP_VISIBLE_GROUPS — every name must be a real CLI group."""
    unknown = MCP_VISIBLE_GROUPS - {g.name for g in REGISTRY}
    assert not unknown, f"MCP_VISIBLE_GROUPS names absent from the CLI registry: {sorted(unknown)}"


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
    with pytest.raises(UserInputError, match="unknown group 'action-requests'"):
        run_command("action-requests", "list")


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
    assert flags["limit"]["maximum"] == 500


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
    route = respx.get(_url(fake_api_url, "ebay-listings", "list", store_id=STORE_ID)).mock(
        return_value=httpx.Response(200, json=[])
    )
    # `--page-size` is the deprecated alias of the `limit` flag (query key `limit`).
    run_command(
        "ebay-listings",
        "list",
        positionals={"store_id": STORE_ID},
        flags={"page-size": 5},
    )
    assert route.calls.last.request.url.params["limit"] == "5"


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


# --------------------------------------------------------------------------- wiring


def test_build_server_registers_exactly_the_four_proxy_tools() -> None:
    server = build_server()
    tools = asyncio.run(server.list_tools())
    by_name = {t.name: t for t in tools}
    assert set(by_name) == {
        "sellerclaw_guide",
        "sellerclaw_groups",
        "sellerclaw_describe",
        "sellerclaw_run",
    }
    run_props = set(by_name["sellerclaw_run"].inputSchema["properties"])
    assert {"group", "command", "positionals", "flags", "body"} <= run_props
    describe_props = set(by_name["sellerclaw_describe"].inputSchema["properties"])
    assert {"group", "command"} <= describe_props
    assert "topic" in by_name["sellerclaw_guide"].inputSchema["properties"]


def test_every_tool_carries_a_human_title() -> None:
    """A permission dialog shows the title, and "Sellerclaw run" tells nobody what it does."""
    tools = asyncio.run(build_server().list_tools())

    assert {t.name: t.title for t in tools} == {
        "sellerclaw_guide": "Read a SellerClaw guide",
        "sellerclaw_groups": "List SellerClaw commands",
        "sellerclaw_describe": "Describe a SellerClaw command",
        "sellerclaw_run": "Run a SellerClaw command",
    }


def test_only_run_is_advertised_as_writing_and_reaching_the_outside_world() -> None:
    """An unannotated tool is treated as destructive, which made reading a guide look dangerous.

    A client renders these hints in the dialog where someone decides whether to allow the call, so
    a warning on all four is a warning on none. Discovery reads this process's own registry; only
    ``sellerclaw_run`` touches the account.
    """
    by_name = {t.name: t.annotations for t in asyncio.run(build_server().list_tools())}

    for name in ("sellerclaw_guide", "sellerclaw_groups", "sellerclaw_describe"):
        annotations = by_name[name]
        assert annotations is not None, name
        assert annotations.readOnlyHint is True, name
        assert annotations.destructiveHint is False, name
        assert annotations.idempotentHint is True, name
        assert annotations.openWorldHint is False, name

    run = by_name["sellerclaw_run"]
    assert run is not None
    assert run.readOnlyHint is False
    assert run.destructiveHint is True
    assert run.idempotentHint is False
    assert run.openWorldHint is True


def test_the_handshake_carries_our_branding_and_our_version() -> None:
    """Clients that render server metadata should get SellerClaw's logo, site and version.

    The icon travels inline so a permission dialog never has to reach our web host, and the version
    must be ours: FastMCP otherwise reports the ``mcp`` SDK's, which would be quoted back at anyone
    asked "which version are you running?".
    """
    options = build_server()._mcp_server.create_initialization_options()

    assert options.website_url == SERVER_WEBSITE_URL
    assert options.server_version == __version__
    icon = (options.icons or [])[0]
    assert icon.mimeType == "image/png"
    assert icon.src.startswith("data:image/png;base64,")
    # A real image, not an empty placeholder: the PNG magic number survives the round trip.
    assert base64.b64decode(icon.src.split(",", 1)[1])[:8] == b"\x89PNG\r\n\x1a\n"


def test_a_build_without_the_logo_still_serves(monkeypatch: pytest.MonkeyPatch) -> None:
    """Losing a decoration must not take the server down.

    The hosted server is installed from a wheel; if one ever shipped without the asset, it has to
    keep answering tool calls with a blank tile rather than refuse to start.
    """
    import importlib.resources

    def _missing(_package: str) -> object:
        raise FileNotFoundError("this build has no assets")

    monkeypatch.setattr(importlib.resources, "files", _missing)

    options = build_server()._mcp_server.create_initialization_options()

    assert not options.icons
    assert options.website_url == SERVER_WEBSITE_URL
