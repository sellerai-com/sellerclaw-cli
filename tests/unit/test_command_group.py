from __future__ import annotations

import json
from pathlib import Path

import httpx
import pytest
import respx
import typer
from typer.testing import CliRunner

from sellerclaw_cli._command_group import Cmd, body_field, build_group, flag, positionals_of

pytestmark = pytest.mark.unit

runner = CliRunner()


def _body_app() -> typer.Typer:
    """A bare root app whose group declares JSON body schemas (for body-validation tests)."""
    specs = (
        Cmd(
            "review",
            "POST",
            "/agent/things/{thing_id}/review",
            summary="Submit with an outcome.",
            body=(
                body_field("outcome", required=True, help="The result."),
                body_field("score", type=int, help="Optional score."),
                body_field("tags", type=str, repeatable=True, help="Optional labels."),
                body_field("status", choices=("ok", "blocked"), help="Optional status."),
            ),
        ),
        Cmd(
            "loose",
            "POST",
            "/agent/things/{thing_id}/loose",
            summary="Documented but extensible.",
            body=(body_field("title", required=True),),
            body_strict=False,
        ),
        Cmd(
            "raw",
            "POST",
            "/agent/things/{thing_id}/raw",
            summary="Free-form body, no schema.",
            body_freeform=True,
        ),
    )
    group = build_group("things", "Synthetic body-schema group.", specs)
    root = typer.Typer()
    root.add_typer(group, name="things")
    return root


def _app() -> typer.Typer:
    """A bare root app with one synthetic group covering every command shape."""
    specs = (
        Cmd("list", "GET", "/agent/widgets", summary="List widgets.", flags=(flag("status"),)),
        Cmd("get", "GET", "/agent/widgets/{widget_id}", summary="Get one widget."),
        Cmd("create", "POST", "/agent/widgets", summary="Create widgets.", has_body=True),
        Cmd("update", "PATCH", "/agent/widgets/{widget_id}", summary="Update.", has_body=True),
        Cmd("delete", "DELETE", "/agent/widgets/{widget_id}", summary="Delete."),
        Cmd(
            "get-part",
            "GET",
            "/agent/widgets/{widget_id}/parts/{part_id}",
            summary="Two positionals.",
        ),
        Cmd(
            "paged",
            "GET",
            "/agent/widgets",
            summary="Paged listing.",
            flags=(
                flag(
                    "limit",
                    type=int,
                    param="page_size",
                    aliases=("--page-size",),
                    minimum=1,
                    maximum=200,
                    default=200,
                    help="Max rows.",
                ),
                flag("state", choices=("active", "draft"), help="State."),
            ),
        ),
    )
    group = build_group("widgets", "Synthetic test group.", specs)
    root = typer.Typer()
    root.add_typer(group, name="widgets")
    return root


@pytest.fixture
def env_pointing_at_fake_api(
    monkeypatch: pytest.MonkeyPatch,
    fake_api_url: str,
    fake_token: str,
) -> None:
    monkeypatch.setenv("SELLERCLAW_API_URL", fake_api_url)
    monkeypatch.setenv("SELLERCLAW_TOKEN", fake_token)


def test_positionals_of_extracts_placeholders_in_order() -> None:
    assert positionals_of("/agent/widgets/{widget_id}/parts/{part_id}") == ["widget_id", "part_id"]
    assert positionals_of("/agent/widgets") == []


def test_group_help_lists_every_command() -> None:
    result = runner.invoke(_app(), ["widgets", "--help"])
    assert result.exit_code == 0
    for name in ("list", "get", "create", "update", "delete", "get-part"):
        assert name in result.stdout


@respx.mock
def test_list_forwards_set_flag_and_drops_unset(
    env_pointing_at_fake_api: None,  # noqa: ARG001
    fake_api_url: str,
) -> None:
    route = respx.get(f"{fake_api_url}/agent/widgets").mock(
        return_value=httpx.Response(200, json={"items": []})
    )
    result = runner.invoke(_app(), ["widgets", "list", "--status", "active"])
    assert result.exit_code == 0, result.stderr
    assert json.loads(result.stdout) == {"data": {"items": []}}
    assert route.calls.last.request.url.params["status"] == "active"


@respx.mock
def test_list_without_flag_sends_no_query(
    env_pointing_at_fake_api: None,  # noqa: ARG001
    fake_api_url: str,
) -> None:
    route = respx.get(f"{fake_api_url}/agent/widgets").mock(
        return_value=httpx.Response(200, json={"items": []})
    )
    result = runner.invoke(_app(), ["widgets", "list"])
    assert result.exit_code == 0, result.stderr
    assert "status" not in route.calls.last.request.url.params


@respx.mock
def test_positional_path_is_substituted(
    env_pointing_at_fake_api: None,  # noqa: ARG001
    fake_api_url: str,
) -> None:
    route = respx.get(f"{fake_api_url}/agent/widgets/w-42").mock(
        return_value=httpx.Response(200, json={"id": "w-42"})
    )
    result = runner.invoke(_app(), ["widgets", "get", "w-42"])
    assert result.exit_code == 0, result.stderr
    assert route.call_count == 1
    assert json.loads(result.stdout) == {"data": {"id": "w-42"}}


@respx.mock
def test_two_positionals_in_path_order(
    env_pointing_at_fake_api: None,  # noqa: ARG001
    fake_api_url: str,
) -> None:
    route = respx.get(f"{fake_api_url}/agent/widgets/w1/parts/p2").mock(
        return_value=httpx.Response(200, json={"ok": True})
    )
    result = runner.invoke(_app(), ["widgets", "get-part", "w1", "p2"])
    assert result.exit_code == 0, result.stderr
    assert route.call_count == 1


@pytest.mark.parametrize(
    "body_flag",
    [
        pytest.param("-b", id="short"),
        pytest.param("--body", id="canonical"),
        pytest.param("--json-body", id="deprecated"),
    ],
)
@respx.mock
def test_body_is_forwarded(
    env_pointing_at_fake_api: None,  # noqa: ARG001
    fake_api_url: str,
    body_flag: str,
) -> None:
    route = respx.patch(f"{fake_api_url}/agent/widgets/w1").mock(
        return_value=httpx.Response(200, json={"id": "w1"})
    )
    result = runner.invoke(
        _app(), ["widgets", "update", "w1", body_flag, '{"name": "x"}']
    )
    assert result.exit_code == 0, result.stderr
    assert json.loads(route.calls.last.request.content) == {"name": "x"}


@respx.mock
def test_delete_maps_to_delete_method(
    env_pointing_at_fake_api: None,  # noqa: ARG001
    fake_api_url: str,
) -> None:
    route = respx.delete(f"{fake_api_url}/agent/widgets/w1").mock(
        return_value=httpx.Response(200, json={"deleted": True})
    )
    result = runner.invoke(_app(), ["widgets", "delete", "w1"])
    assert result.exit_code == 0, result.stderr
    assert route.call_count == 1


@respx.mock
def test_flag_maps_to_aliased_query_param(
    env_pointing_at_fake_api: None,  # noqa: ARG001
    fake_api_url: str,
) -> None:
    """A flag with ``param=`` sends the API query key, not the CLI name."""
    route = respx.get(f"{fake_api_url}/agent/widgets").mock(
        return_value=httpx.Response(200, json={"items": []})
    )
    result = runner.invoke(_app(), ["widgets", "paged", "--limit", "50"])
    assert result.exit_code == 0, result.stderr
    params = route.calls.last.request.url.params
    assert params["page_size"] == "50"
    assert "limit" not in params


@respx.mock
def test_flag_alias_spelling_is_accepted(
    env_pointing_at_fake_api: None,  # noqa: ARG001
    fake_api_url: str,
) -> None:
    """The deprecated ``--page-size`` alias still works and maps to ``page_size``."""
    route = respx.get(f"{fake_api_url}/agent/widgets").mock(
        return_value=httpx.Response(200, json={"items": []})
    )
    result = runner.invoke(_app(), ["widgets", "paged", "--page-size", "75"])
    assert result.exit_code == 0, result.stderr
    assert route.calls.last.request.url.params["page_size"] == "75"


@pytest.mark.parametrize(
    ("args", "needle"),
    [
        pytest.param(["widgets", "paged", "--limit", "1000"], "<= 200", id="above-max"),
        pytest.param(["widgets", "paged", "--limit", "0"], ">= 1", id="below-min"),
        pytest.param(["widgets", "paged", "--state", "archived"], "one of", id="bad-choice"),
    ],
)
@respx.mock
def test_out_of_range_or_choice_fails_locally_without_request(
    env_pointing_at_fake_api: None,  # noqa: ARG001
    fake_api_url: str,
    args: list[str],
    needle: str,
) -> None:
    """Bad values fail fast with a clear local error and never hit the API."""
    route = respx.get(f"{fake_api_url}/agent/widgets").mock(
        return_value=httpx.Response(200, json={"items": []})
    )
    result = runner.invoke(_app(), args)
    assert result.exit_code == 1
    assert needle in json.loads(result.stderr)["error"]["message"]
    assert route.call_count == 0


@respx.mock
def test_valid_choice_is_forwarded(
    env_pointing_at_fake_api: None,  # noqa: ARG001
    fake_api_url: str,
) -> None:
    route = respx.get(f"{fake_api_url}/agent/widgets").mock(
        return_value=httpx.Response(200, json={"items": []})
    )
    result = runner.invoke(_app(), ["widgets", "paged", "--state", "active"])
    assert result.exit_code == 0, result.stderr
    assert route.calls.last.request.url.params["state"] == "active"


@pytest.mark.parametrize(
    ("body_value", "needle"),
    [
        pytest.param('{"name": ', "invalid JSON", id="malformed-literal"),
        pytest.param("@/nope/does-not-exist.json", "file not found", id="missing-at-file"),
    ],
)
@respx.mock
def test_bad_body_emits_structured_error_not_traceback(
    env_pointing_at_fake_api: None,  # noqa: ARG001
    fake_api_url: str,
    body_value: str,
    needle: str,
) -> None:
    """A malformed -b value surfaces as the structured stderr contract, never a raw traceback."""
    route = respx.patch(f"{fake_api_url}/agent/widgets/w1").mock(
        return_value=httpx.Response(200, json={"id": "w1"})
    )
    result = runner.invoke(_app(), ["widgets", "update", "w1", "-b", body_value])
    assert result.exit_code == 1
    assert "Traceback" not in (result.stdout + result.stderr)
    assert needle in json.loads(result.stderr)["error"]["message"]
    assert route.call_count == 0


@respx.mock
def test_bare_file_path_body_is_auto_read(
    env_pointing_at_fake_api: None,  # noqa: ARG001
    fake_api_url: str,
    tmp_path: Path,
) -> None:
    """A bare file path passed to ``-b`` (no ``@`` prefix) is read and forwarded as JSON.

    Why: agents (and humans) routinely build a body in a temp file and pass
    ``-b /tmp/body.json``; forcing the ``@`` prefix wasted a retry per call.
    """
    body_file = tmp_path / "body.json"
    body_file.write_text('{"name": "x"}')
    route = respx.patch(f"{fake_api_url}/agent/widgets/w1").mock(
        return_value=httpx.Response(200, json={"id": "w1"})
    )
    result = runner.invoke(_app(), ["widgets", "update", "w1", "-b", str(body_file)])
    assert result.exit_code == 0, result.stderr
    assert json.loads(route.calls.last.request.content) == {"name": "x"}


def test_registry_records_group() -> None:
    from sellerclaw_cli import _command_group

    build_group("regtest", "help", (Cmd("list", "GET", "/agent/regtest"),))
    group = next(g for g in _command_group.REGISTRY if g.name == "regtest")
    assert [c.name for c in group.commands] == ["list"]


# --- body-schema validation (local, before any network call) -------------------------------


@pytest.mark.parametrize(
    ("body", "needles"),
    [
        pytest.param('{"score": 5}', ["missing required", "outcome"], id="missing-required"),
        pytest.param('{"outcome": "x", "note": "y"}', ["unknown field", "note"], id="unknown-field"),
        pytest.param('{"outcome": "x", "score": "high"}', ["score", "integer"], id="wrong-type"),
        pytest.param('{"outcome": "x", "status": "nope"}', ["status", "one of", "ok"], id="bad-choice"),
        pytest.param('["outcome"]', ["must be a JSON object"], id="not-an-object"),
    ],
)
@respx.mock
def test_body_schema_rejects_bad_body_locally(
    env_pointing_at_fake_api: None,  # noqa: ARG001
    fake_api_url: str,
    body: str,
    needles: list[str],
) -> None:
    """A body that breaks the declared schema fails locally with an actionable message — no request."""
    route = respx.post(f"{fake_api_url}/agent/things/t1/review").mock(
        return_value=httpx.Response(200, json={"ok": True})
    )
    result = runner.invoke(_body_app(), ["things", "review", "t1", "-b", body])
    assert result.exit_code == 1, result.stdout
    message = json.loads(result.stderr)["error"]["message"]
    for needle in needles:
        assert needle in message, f"{needle!r} not in {message!r}"
    assert route.call_count == 0


@respx.mock
def test_body_schema_suggests_closest_field(
    env_pointing_at_fake_api: None,  # noqa: ARG001
    fake_api_url: str,
) -> None:
    """An unknown key close to a real field gets a 'did you mean' pointer (e.g. outcom -> outcome)."""
    route = respx.post(f"{fake_api_url}/agent/things/t1/review").mock(
        return_value=httpx.Response(200, json={"ok": True})
    )
    result = runner.invoke(_body_app(), ["things", "review", "t1", "-b", '{"outcom": "x"}'])
    assert result.exit_code == 1, result.stdout
    message = json.loads(result.stderr)["error"]["message"]
    assert "did you mean 'outcome'" in message
    assert route.call_count == 0


@respx.mock
def test_body_schema_missing_body_when_required(
    env_pointing_at_fake_api: None,  # noqa: ARG001
    fake_api_url: str,
) -> None:
    """Omitting -b entirely on a command with required fields is rejected locally with the field list."""
    route = respx.post(f"{fake_api_url}/agent/things/t1/review").mock(
        return_value=httpx.Response(200, json={"ok": True})
    )
    result = runner.invoke(_body_app(), ["things", "review", "t1"])
    assert result.exit_code == 1, result.stdout
    message = json.loads(result.stderr)["error"]["message"]
    assert "needs a JSON body" in message
    assert "outcome" in message
    assert route.call_count == 0


@respx.mock
def test_body_schema_valid_body_is_forwarded(
    env_pointing_at_fake_api: None,  # noqa: ARG001
    fake_api_url: str,
) -> None:
    route = respx.post(f"{fake_api_url}/agent/things/t1/review").mock(
        return_value=httpx.Response(200, json={"ok": True})
    )
    result = runner.invoke(
        _body_app(),
        ["things", "review", "t1", "-b", '{"outcome": "done", "score": 9, "tags": ["a"], "status": "ok"}'],
    )
    assert result.exit_code == 0, result.stderr
    assert json.loads(route.calls.last.request.content) == {
        "outcome": "done",
        "score": 9,
        "tags": ["a"],
        "status": "ok",
    }


@respx.mock
def test_body_strict_off_allows_extra_fields(
    env_pointing_at_fake_api: None,  # noqa: ARG001
    fake_api_url: str,
) -> None:
    """With body_strict=False, undeclared keys pass through (required fields still enforced)."""
    route = respx.post(f"{fake_api_url}/agent/things/t1/loose").mock(
        return_value=httpx.Response(200, json={"ok": True})
    )
    result = runner.invoke(_body_app(), ["things", "loose", "t1", "-b", '{"title": "x", "extra": 1}'])
    assert result.exit_code == 0, result.stderr
    assert json.loads(route.calls.last.request.content) == {"title": "x", "extra": 1}


@respx.mock
def test_freeform_body_skips_validation(
    env_pointing_at_fake_api: None,  # noqa: ARG001
    fake_api_url: str,
) -> None:
    """A body_freeform command forwards any JSON shape without local schema checks."""
    route = respx.post(f"{fake_api_url}/agent/things/t1/raw").mock(
        return_value=httpx.Response(200, json={"ok": True})
    )
    result = runner.invoke(_body_app(), ["things", "raw", "t1", "-b", '{"anything": [1, 2, 3]}'])
    assert result.exit_code == 0, result.stderr
    assert json.loads(route.calls.last.request.content) == {"anything": [1, 2, 3]}
