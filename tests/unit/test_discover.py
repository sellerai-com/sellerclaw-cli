from __future__ import annotations

import json
from typing import Any

import pytest
from typer.testing import CliRunner

from sellerclaw_cli._command_group import REGISTRY, positionals_of
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


def test_listings_group_exposes_get_and_search() -> None:
    """The channel-agnostic 'listings' group resolves a listing by id and searches by name."""
    result = runner.invoke(app, ["commands", "--group", "listings"])
    assert result.exit_code == 0, result.output
    cmds = {row["command"] for row in _data(result.stdout)}
    assert cmds == {"get", "search"}

    get_detail = _data(runner.invoke(app, ["describe", "listings", "get"]).stdout)
    assert get_detail["method"] == "GET"
    assert get_detail["positionals"] == ["listing_id"]

    search_detail = _data(runner.invoke(app, ["describe", "listings", "search"]).stdout)
    assert search_detail["method"] == "GET"
    flags = {f["flag"]: f for f in search_detail["flags"]}
    assert flags["--q"]["required"] is True


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
    assert limit["maximum"] == 200
    assert limit["default"] == 200
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
        "this_year",
    ]


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
    result = runner.invoke(app, ["describe", "shopify", "graphql"])
    assert result.exit_code == 0, result.output
    detail = _data(result.stdout)
    assert detail["body"] is True
    assert detail["body_fields"] == []
    assert detail["body_freeform"] is True


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
    """Every command that takes a -b body must declare its fields (`body=`) or be marked
    `body_freeform=True`. A bare `has_body=True` leaves `describe` blind and the body
    unvalidated — exactly the gap that let an agent guess wrong field names. This guard keeps
    the sweep complete: a new body command without a schema fails here.
    """
    # Only real shipped groups (synthetic groups built by other tests also land in the global REGISTRY).
    registered = {ti.name for ti in app.registered_groups}
    offenders = [
        f"{g.name} {c.name}"
        for g in REGISTRY
        if g.name in registered
        for c in g.commands
        if c.takes_body and not c.body and not c.body_freeform
    ]
    assert not offenders, f"body commands missing a `body=` schema or `body_freeform=True`: {offenders}"


def test_ads_groups_mirror_each_other() -> None:
    google = {c.name for g in REGISTRY if g.name == "google-ads" for c in g.commands}
    facebook = {c.name for g in REGISTRY if g.name == "facebook-ads" for c in g.commands}
    shared = {"list-campaigns", "get-campaign", "create-campaign", "update-campaign", "metrics", "action-log"}
    assert shared <= google
    assert shared <= facebook
