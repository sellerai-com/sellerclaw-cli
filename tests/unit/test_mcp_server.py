from __future__ import annotations

import asyncio
import json

import httpx
import pytest
import respx

from sellerclaw_cli._command_group import REGISTRY
from sellerclaw_cli._errors import UserInputError

# Importing the CLI app registers every command group into the shared REGISTRY that the MCP
# proxy tools read. Without this import the registry would be empty for direct-call tests.
from sellerclaw_cli.cli import app  # noqa: F401
from sellerclaw_cli.mcp_server import (
    MCP_VISIBLE_GROUPS,
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
    assert flags["limit"]["maximum"] == 200


def test_describe_command_unknown_group_raises() -> None:
    with pytest.raises(UserInputError, match="unknown group 'does-not-exist'"):
        describe_command("does-not-exist", "list")


def test_describe_command_unknown_command_raises() -> None:
    with pytest.raises(UserInputError, match="unknown command 'nope' in group 'orders'"):
        describe_command("orders", "nope")


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


def test_build_server_registers_exactly_the_three_proxy_tools() -> None:
    server = build_server()
    tools = asyncio.run(server.list_tools())
    by_name = {t.name: t for t in tools}
    assert set(by_name) == {"sellerclaw_groups", "sellerclaw_describe", "sellerclaw_run"}
    run_props = set(by_name["sellerclaw_run"].inputSchema["properties"])
    assert {"group", "command", "positionals", "flags", "body"} <= run_props
    describe_props = set(by_name["sellerclaw_describe"].inputSchema["properties"])
    assert {"group", "command"} <= describe_props
