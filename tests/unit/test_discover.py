from __future__ import annotations

import json
from typing import Any

import pytest
from typer.testing import CliRunner

from sellerclaw_cli._command_group import LONG_TIMEOUT_SECONDS, REGISTRY, positionals_of
from sellerclaw_cli.cli import app

pytestmark = pytest.mark.unit

runner = CliRunner()


def _data(result_stdout: str) -> Any:
    return json.loads(result_stdout)["data"]


def test_every_group_help_renders() -> None:
    """Smoke test: each group registered on the root app renders --help (synthetic sigs parse)."""
    registered = {ti.name for ti in app.registered_groups}
    real_groups = [g for g in REGISTRY if g.name in registered]
    assert real_groups, "no groups registered"
    for group in real_groups:
        result = runner.invoke(app, [group.name, "--help"])
        assert result.exit_code == 0, f"{group.name} --help failed: {result.output}"


def test_groups_lists_new_names_not_old() -> None:
    result = runner.invoke(app, ["groups"])
    assert result.exit_code == 0, result.output
    names = {row["group"] for row in _data(result.stdout)}
    assert {"orders", "catalog", "channels", "google-ads", "shopify-listings", "suppliers"} <= names
    assert not any(n.startswith("agent-") for n in names)
    assert "stores" not in names


def test_every_typer_group_is_discoverable() -> None:
    """Every group mounted on the root app must be in REGISTRY (no invisible groups).

    Guards against hand-written groups (like ``files``) that bypass ``build_group`` and
    silently vanish from ``guide`` / ``groups`` / ``commands`` / ``describe``.
    """
    typer_names = {ti.name for ti in app.registered_groups if ti.name is not None}
    registry_names = {g.name for g in REGISTRY}
    # ``auth`` manages local credentials, not Agent API operations — deliberately undiscoverable.
    missing = typer_names - registry_names - {"auth"}
    assert not missing, f"groups mounted on the CLI but invisible to discovery: {sorted(missing)}"


def test_files_group_discoverable() -> None:
    result = runner.invoke(app, ["commands", "--group", "files"])
    assert result.exit_code == 0, result.output
    cmds = {row["command"] for row in _data(result.stdout)}
    assert cmds == {"list", "from-url", "upload"}

    described = runner.invoke(app, ["describe", "files", "from-url"])
    assert described.exit_code == 0, described.output
    detail = _data(described.stdout)
    assert detail["method"] == "POST"
    flags = {f["flag"]: f for f in detail["flags"]}
    assert flags["--url"]["required"] is True


_LISTINGS_COMMANDS = [
    "get",
    "adopt-marketplace-version",
    "search",
    "history",
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
]


def test_listings_group_exposes_get_and_search() -> None:
    """The channel-agnostic 'listings' group resolves a listing by id, finds listings by any of
    the handles the caller may hold, and runs the bulk draft workflow (drafts → readiness → fix →
    publish)."""
    result = runner.invoke(app, ["commands", "--group", "listings"])
    assert result.exit_code == 0, result.output
    cmds = {row["command"] for row in _data(result.stdout)}
    assert cmds == set(_LISTINGS_COMMANDS)

    get_detail = _data(runner.invoke(app, ["describe", "listings", "get"]).stdout)
    assert get_detail["method"] == "GET"
    assert get_detail["positionals"] == ["listing_id"]

    search_detail = _data(runner.invoke(app, ["describe", "listings", "search"]).stdout)
    assert search_detail["method"] == "GET"
    flags = {f["flag"]: f for f in search_detail["flags"]}
    assert {"--q", "--product-id", "--store-id", "--sku", "--remote-id", "--platform", "--status"} <= set(flags)
    # The two that make updating live listings workable: which rows still owe the channel, and what
    # actually moved lately (as opposed to what the background sync re-saved).
    assert {"--has-unpublished-changes", "--changed-since", "--changed-by"} <= set(flags)

    history_detail = _data(runner.invoke(app, ["describe", "listings", "history"]).stdout)
    assert history_detail["method"] == "GET"
    history_flags = {f["flag"] for f in history_detail["flags"]}
    assert {"--listing-id", "--field", "--source", "--since", "--only-undelivered"} <= history_flags
    # No criterion is mandatory any more: each one is a separate route to the same listings, and
    # requiring free text blocked the product -> listings lookup entirely.
    assert all(not spec["required"] for spec in flags.values())
    assert flags["--q"]["aliases"] == ["--query", "--search", "--text", "--keyword", "--keywords"]


def test_catalog_finds_a_product_by_sku_and_by_supplier_item() -> None:
    """`catalog list` carries the exact-SKU and supplier-item lookups — the latter is the
    'do I already have this product?' check that prevents sourcing a duplicate."""
    detail = _data(runner.invoke(app, ["describe", "catalog", "list"]).stdout)
    flags = {f["flag"] for f in detail["flags"]}
    assert {"--sku", "--supplier-product-id", "--supplier-provider", "--q"} <= flags


def test_orders_find_who_bought_a_product() -> None:
    """`orders list --product-id` answers 'who bought this' without scanning every order."""
    detail = _data(runner.invoke(app, ["describe", "orders", "list"]).stdout)
    flags = {f["flag"] for f in detail["flags"]}
    assert "--product-id" in flags


def test_describe_a_whole_group_in_one_call() -> None:
    """Omitting the command describes every command in the group — one call instead of N."""
    result = runner.invoke(app, ["describe", "catalog"])
    assert result.exit_code == 0, result.output
    payload = _data(result.stdout)
    assert payload["group"] == "catalog"
    described = {cmd["command"] for cmd in payload["commands"]}
    assert {"list", "get", "search", "create", "source-from-supplier"} <= described
    source = next(cmd for cmd in payload["commands"] if cmd["command"] == "source-from-supplier")
    assert [field["field"] for field in source["body_fields"]]  # body schema travels with it
    assert source["example"].startswith("sellerclaw catalog source-from-supplier")


def test_describe_an_unknown_group_suggests_a_real_one() -> None:
    """A wrong group name is a dead end unless the error names the closest real one."""
    result = runner.invoke(app, ["describe", "shopify-products"])
    assert result.exit_code != 0
    assert "shopify-" in result.stderr


def test_groups_carry_their_command_names() -> None:
    """`groups` lists the commands, not just a count — a count forces a second call to find out
    whether the verb you want even exists there."""
    payload = _data(runner.invoke(app, ["groups"]).stdout)
    listings = next(row for row in payload if row["group"] == "listings")
    assert listings["commands"] == _LISTINGS_COMMANDS


def test_suppliers_expose_per_product_stock() -> None:
    """``check-stock-by-product`` fetches stock for all variants of a product in one call."""
    result = runner.invoke(app, ["commands", "--group", "suppliers"])
    assert result.exit_code == 0, result.output
    cmds = {row["command"] for row in _data(result.stdout)}
    assert "check-stock-by-product" in cmds

    detail = _data(runner.invoke(app, ["describe", "suppliers", "check-stock-by-product"]).stdout)
    assert detail["method"] == "GET"
    assert detail["positionals"] == ["provider", "product_id"]
    assert detail["body"] is False
    assert detail["example"].startswith("sellerclaw suppliers check-stock-by-product <provider> <product_id>")


def test_catalog_and_orders_expose_search() -> None:
    """Products and orders are findable by name/number/SKU without dumping the whole list."""
    for group in ("catalog", "orders"):
        result = runner.invoke(app, ["commands", "--group", group])
        assert result.exit_code == 0, result.output
        cmds = {row["command"] for row in _data(result.stdout)}
        assert "search" in cmds, f"{group} is missing a 'search' command"
        detail = _data(runner.invoke(app, ["describe", group, "search"]).stdout)
        flags = {f["flag"]: f for f in detail["flags"]}
        assert flags["--q"]["required"] is True


def test_commands_filtered_by_group() -> None:
    result = runner.invoke(app, ["commands", "--group", "orders"])
    assert result.exit_code == 0, result.output
    cmds = {row["command"] for row in _data(result.stdout)}
    assert {"overview", "list", "get", "update"} <= cmds


def test_commands_unknown_group_is_user_error() -> None:
    result = runner.invoke(app, ["commands", "--group", "does-not-exist"])
    assert result.exit_code == 1
    assert json.loads(result.stderr)["error"]["code"] == "user_error"


def test_describe_returns_full_detail() -> None:
    result = runner.invoke(app, ["describe", "orders", "update"])
    assert result.exit_code == 0, result.output
    detail = _data(result.stdout)
    assert detail["method"] == "PATCH"
    assert detail["body"] is True
    assert detail["positionals"] == ["order_id"]
    assert detail["example"].startswith("sellerclaw orders update <order_id>")


def test_describe_surfaces_flag_constraints_for_ebay_list() -> None:
    """The eBay list flag advertises its range/default and the deprecated alias."""
    result = runner.invoke(app, ["describe", "ebay-listings", "list"])
    assert result.exit_code == 0, result.output
    flags = {f["flag"]: f for f in _data(result.stdout)["flags"]}
    assert "--limit" in flags
    limit = flags["--limit"]
    assert limit["minimum"] == 1
    assert limit["maximum"] == 500
    assert limit["default"] == 100
    # Flag name now matches the query param ("limit"), so no separate mapping is surfaced.
    assert "query_param" not in limit
    assert limit["aliases"] == ["--page-size"]


def test_describe_surfaces_status_choices_for_shopify_list() -> None:
    result = runner.invoke(app, ["describe", "shopify-listings", "list"])
    assert result.exit_code == 0, result.output
    flags = {f["flag"]: f for f in _data(result.stdout)["flags"]}
    assert flags["--status"]["choices"] == ["active", "published", "draft", "withdrawn"]
    assert flags["--limit"]["maximum"] == 500


def test_describe_analytics_report() -> None:
    result = runner.invoke(app, ["describe", "analytics", "report"])
    assert result.exit_code == 0, result.output
    payload = _data(result.stdout)
    assert payload["method"] == "POST"
    assert payload["positionals"] == ["store_id"]
    flags = {f["flag"]: f for f in payload["flags"]}
    assert flags["--period"]["choices"] == [
        "last_7d",
        "last_30d",
        "last_90d",
        "this_month",
        "last_month",
        "this_year",
    ]


@pytest.mark.parametrize(
    "command",
    ["metrics", "timeseries", "inventory", "geography"],
)
def test_analytics_reads_share_one_window_contract(command: str) -> None:
    """Every windowed read in the group offers the same four ways to name a period.

    The point of the group is that a caller learns the contract once; a command that drifted to
    its own dialect would send them back to reading each one.
    """
    payload = _data(runner.invoke(app, ["describe", "analytics", command]).stdout)
    flags = {f["flag"] for f in payload["flags"]}
    assert {"--period", "--week", "--month", "--date-from", "--date-to"} <= flags


@pytest.mark.parametrize(
    "command",
    ["metrics", "timeseries", "inventory", "geography", "capital"],
)
def test_analytics_reads_accept_several_stores(command: str) -> None:
    """Every read can be aggregated over more than one store."""
    payload = _data(runner.invoke(app, ["describe", "analytics", command]).stdout)
    store = next(f for f in payload["flags"] if f["flag"] == "--store")
    assert store["repeatable"] is True


def test_analytics_capital_takes_no_period() -> None:
    """Stock is always "as of now", so offering a period would promise history we do not keep."""
    payload = _data(runner.invoke(app, ["describe", "analytics", "capital"]).stdout)
    flags = {f["flag"] for f in payload["flags"]}
    assert "--period" not in flags
    assert "--dead-after" in flags


def test_analytics_metrics_offers_fees_and_warns_it_is_slow() -> None:
    payload = _data(runner.invoke(app, ["describe", "analytics", "metrics"]).stdout)
    flags = {f["flag"]: f for f in payload["flags"]}
    assert "--with-fees" in flags
    # A live finance call per store needs a budget the caller can size against.
    assert payload["timeout_seconds"] == LONG_TIMEOUT_SECONDS


def test_analytics_range_flags_map_to_from_and_to() -> None:
    """``--from``/``--to`` are the natural spelling; the API keys are the bare words."""
    payload = _data(runner.invoke(app, ["describe", "analytics", "metrics"]).stdout)
    by_flag = {f["flag"]: f for f in payload["flags"]}
    assert "--from" in by_flag["--date-from"]["aliases"]
    assert "--to" in by_flag["--date-to"]["aliases"]


def test_kb_group_exposes_search() -> None:
    """The knowledge-base group offers a single read-only 'search' with a required query."""
    result = runner.invoke(app, ["commands", "--group", "kb"])
    assert result.exit_code == 0, result.output
    cmds = {row["command"] for row in _data(result.stdout)}
    assert cmds == {"search"}

    detail = _data(runner.invoke(app, ["describe", "kb", "search"]).stdout)
    assert detail["method"] == "GET"
    flags = {f["flag"]: f for f in detail["flags"]}
    assert flags["--query"]["required"] is True
    assert flags["--filter"]["required"] is False


def test_describe_surfaces_body_fields_and_example() -> None:
    """A command with a declared body schema exposes its fields and a concrete -b example."""
    result = runner.invoke(app, ["describe", "subagent-tasks", "request-review"])
    assert result.exit_code == 0, result.output
    detail = _data(result.stdout)
    assert detail["body"] is True
    fields = {f["field"]: f for f in detail["body_fields"]}
    assert fields["outcome"]["required"] is True
    assert detail["body_strict"] is True
    assert detail["body_freeform"] is False
    # The example is runnable: it carries the required field, not a placeholder file.
    assert '"outcome"' in detail["example"]
    assert "@body.json" not in detail["example"]


def test_describe_marks_freeform_body() -> None:
    """A command that takes a body but declares no schema is flagged free-form (no field list)."""
    result = runner.invoke(app, ["describe", "shopify-collections", "update"])
    assert result.exit_code == 0, result.output
    detail = _data(result.stdout)
    assert detail["body"] is True
    assert detail["body_fields"] == []
    assert detail["body_freeform"] is True


def test_describe_marks_graphql_as_query_body() -> None:
    """The raw GraphQL command exposes -q/--query (query_body), not a free-form -b body."""
    result = runner.invoke(app, ["describe", "shopify", "graphql"])
    assert result.exit_code == 0, result.output
    detail = _data(result.stdout)
    assert detail["body"] is True
    assert detail["query_body"] is True
    assert detail["body_freeform"] is False
    assert "-q" in detail["example"]


def test_ebay_raw_passthrough_group_exposes_request_and_trading() -> None:
    """The raw eBay group offers a REST `request` and a Trading-API `trading` fallback."""
    result = runner.invoke(app, ["commands", "--group", "ebay"])
    assert result.exit_code == 0, result.output
    cmds = {row["command"] for row in _data(result.stdout)}
    assert cmds == {"request", "trading"}

    rest = _data(runner.invoke(app, ["describe", "ebay", "request"]).stdout)
    assert rest["method"] == "POST"
    assert rest["positionals"] == ["store_id"]
    rest_fields = {f["field"]: f for f in rest["body_fields"]}
    assert rest_fields["path"]["required"] is True
    assert rest_fields["method"]["choices"] == ["GET", "POST", "PUT", "PATCH", "DELETE"]

    trading = _data(runner.invoke(app, ["describe", "ebay", "trading"]).stdout)
    trading_fields = {f["field"]: f for f in trading["body_fields"]}
    assert trading_fields["verb"]["required"] is True


def test_amazon_raw_passthrough_group_exposes_request() -> None:
    """The raw Amazon group offers a single SP-API `request` fallback with a required path."""
    result = runner.invoke(app, ["commands", "--group", "amazon"])
    assert result.exit_code == 0, result.output
    cmds = {row["command"] for row in _data(result.stdout)}
    assert cmds == {"request"}

    detail = _data(runner.invoke(app, ["describe", "amazon", "request"]).stdout)
    assert detail["method"] == "POST"
    assert detail["positionals"] == ["store_id"]
    fields = {f["field"]: f for f in detail["body_fields"]}
    assert fields["path"]["required"] is True


def test_describe_unknown_command_is_user_error() -> None:
    result = runner.invoke(app, ["describe", "orders", "nope"])
    assert result.exit_code == 1
    assert json.loads(result.stderr)["error"]["code"] == "user_error"


def test_guide_has_conventions_and_groups() -> None:
    result = runner.invoke(app, ["guide"])
    assert result.exit_code == 0, result.output
    payload = _data(result.stdout)
    assert payload["conventions"]
    assert payload["groups"]


def test_no_http_verb_or_agent_prefix_leaks_in_command_names() -> None:
    for group in REGISTRY:
        assert not group.name.startswith("agent-"), group.name
        for cmd in group.commands:
            assert not cmd.name.startswith("post-"), f"{group.name} {cmd.name}"
            assert cmd.name == cmd.name.lower(), f"{group.name} {cmd.name}"
            # positionals are derived from the path; ensure they are real placeholders
            for pos in positionals_of(cmd.path):
                assert "{" + pos + "}" in cmd.path


def test_every_body_command_documents_its_schema() -> None:
    """Every command that takes a -b body must declare its fields (`body=`), be marked
    `body_freeform=True`, or be a `query_body=True` GraphQL command. A bare `has_body=True` leaves
    `describe` blind and the body unvalidated — exactly the gap that let an agent guess wrong field
    names. This guard keeps the sweep complete: a new body command without a schema fails here.
    """
    # Only real shipped groups (synthetic groups built by other tests also land in the global REGISTRY).
    registered = {ti.name for ti in app.registered_groups}
    offenders = [
        f"{g.name} {c.name}"
        for g in REGISTRY
        if g.name in registered
        for c in g.commands
        if c.takes_body and not c.body and not c.body_freeform and not c.query_body
    ]
    assert not offenders, f"body commands missing a schema, `body_freeform`, or `query_body`: {offenders}"


def test_ads_groups_mirror_each_other() -> None:
    google = {c.name for g in REGISTRY if g.name == "google-ads" for c in g.commands}
    facebook = {c.name for g in REGISTRY if g.name == "facebook-ads" for c in g.commands}
    shared = {"list-campaigns", "get-campaign", "create-campaign", "update-campaign", "metrics", "action-log"}
    assert shared <= google
    assert shared <= facebook


def test_channels_set_markup_patches_markup_percent() -> None:
    """`channels set-markup` PATCHes a store with a required numeric `markup_percent` body field."""
    set_markup = next(
        c for g in REGISTRY if g.name == "channels" for c in g.commands if c.name == "set-markup"
    )
    assert set_markup.method == "PATCH"
    assert set_markup.path == "/agent/sales-channels/{sales_channel_id}"
    markup_field = next(f for f in set_markup.body if f.name == "markup_percent")
    assert markup_field.required is True
    assert markup_field.type is float


def test_google_ads_reads_what_the_money_was_spent_on() -> None:
    """`search-terms` answers what keywords cannot: which queries actually took the budget.

    It is a read, so it must stay a GET with plain flags — a body here would make it unusable
    from `describe` and from the MCP surface.
    """
    search_terms = next(
        c for g in REGISTRY if g.name == "google-ads" for c in g.commands if c.name == "search-terms"
    )
    assert search_terms.method == "GET"
    assert search_terms.path == "/agent/ads/google/search-terms"
    assert not search_terms.takes_body
    names = {f.name for f in search_terms.flags}
    assert {"campaign_id", "adgroup_id", "date_from", "date_to", "order", "limit"} <= names


def test_google_ads_targeting_takes_either_level() -> None:
    """Campaign and ad group carry different criteria, so both ids are offered; the server
    refuses a call that names neither or both."""
    targeting = next(
        c for g in REGISTRY if g.name == "google-ads" for c in g.commands if c.name == "targeting"
    )
    assert targeting.method == "GET"
    assert targeting.path == "/agent/ads/google/targeting"
    assert {f.name for f in targeting.flags} == {"campaign_id", "adgroup_id"}
