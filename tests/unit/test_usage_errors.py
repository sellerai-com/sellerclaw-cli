from __future__ import annotations

import json

import click
import httpx
import pytest
import respx
import typer

from sellerclaw_cli import cli

pytestmark = pytest.mark.unit


def _run(monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str], argv: list[str]) -> tuple[int, str, str]:
    """Invoke the real console entry point (`main`, standalone_mode=False) and capture exit + streams."""
    monkeypatch.setattr("sys.argv", ["sellerclaw", *argv])
    code = 0
    with pytest.raises(SystemExit) as exc_info:
        cli.main()
    raw = exc_info.value.code
    code = raw if isinstance(raw, int) else (0 if raw is None else 1)
    captured = capsys.readouterr()
    return code, captured.out, captured.err


def _err(stderr: str) -> str:
    return json.loads(stderr)["error"]["message"]


def test_unknown_option_suggests_closest(monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    """A near-miss flag name surfaces Click's 'did you mean' plus a describe pointer — structured."""
    code, _out, err = _run(monkeypatch, capsys, ["research-trends", "interest-over-time", "--timeframes", "x"])
    assert code == 1
    msg = _err(err)
    assert "No such option: --timeframes" in msg
    assert "--timeframe" in msg  # Click's own suggestion
    assert "describe research-trends interest-over-time" in msg


def test_unknown_option_lists_the_accepted_ones(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """When nothing is close enough to guess, the error still names every option the command takes."""
    code, _out, err = _run(monkeypatch, capsys, ["listings", "search", "--name", "apron"])
    assert code == 1
    msg = _err(err)
    assert "Accepted options:" in msg
    assert "--product-id" in msg


@respx.mock
@pytest.mark.parametrize(
    "spelling",
    [
        pytest.param("--q", id="canonical"),
        pytest.param("--query", id="query"),
        pytest.param("--search", id="search"),
        pytest.param("--text", id="text"),
    ],
)
def test_every_spelling_of_the_search_flag_is_accepted(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    fake_api_url: str,
    spelling: str,
) -> None:
    """Free-text search is spelled --q here and --search there across the API's groups. Whichever
    one the caller reaches for, the command must accept it — a rejected guess costs a whole turn."""
    monkeypatch.setenv("SELLERCLAW_API_URL", fake_api_url)
    monkeypatch.delenv("SELLERCLAW_TOKEN", raising=False)
    respx.get(f"{fake_api_url}/agent/listings/search").mock(
        return_value=httpx.Response(401, json={"detail": "Missing bearer token"})
    )
    code, _out, err = _run(monkeypatch, capsys, ["listings", "search", spelling, "apron"])
    # Past option parsing (exit 1 = "No such option"); auth stops the call before any real network.
    assert code == 3, _err(err)


def test_flag_on_body_command_points_to_body(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """Passing --options to a command that takes a JSON body tells the agent to use -b with the fields."""
    code, _out, err = _run(monkeypatch, capsys, ["research-seo", "keyword-ideas", "--keywords", "x"])
    assert code == 1
    msg = _err(err)
    assert "takes a JSON body via -b" in msg
    assert "keyword" in msg  # a real body field is listed


def test_positional_passed_as_flag_is_explained(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    code, _out, err = _run(monkeypatch, capsys, ["suppliers", "search-products", "--provider", "cj"])
    assert code == 1
    msg = _err(err)
    assert "positional argument" in msg
    assert "provider" in msg


def test_unknown_command_lists_group(monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    """An unknown command names the group's real commands — a fuzzy guess alone is a coin flip."""
    code, _out, err = _run(monkeypatch, capsys, ["subagent-tasks", "progress", "X"])
    assert code == 1
    msg = _err(err)
    assert "No such command 'progress'" in msg
    assert "Commands in `subagent-tasks`:" in msg
    assert "add-note" in msg


@pytest.mark.parametrize(
    ("group", "sibling"),
    [
        pytest.param("shopify-listings", "listings", id="shopify-listings"),
        pytest.param("walmart-orders", "orders", id="walmart-orders"),
        pytest.param("ebay-listings", "listings", id="ebay-listings"),
    ],
)
def test_reading_by_id_redirects_to_the_channel_agnostic_group(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    group: str,
    sibling: str,
) -> None:
    """A SellerClaw id is not channel-scoped, so `get` lives only in the cross-channel group. The
    error must say so for every channel — the natural guess is `<channel>-listings get`."""
    code, _out, err = _run(monkeypatch, capsys, [group, "get", "some-id"])
    assert code == 1
    msg = _err(err)
    assert f"`sellerclaw {sibling} get ...`" in msg


def test_a_redundant_noun_before_the_command_is_named(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """`catalog products get <id>` — the entity noun is already the group; say exactly that."""
    code, _out, err = _run(monkeypatch, capsys, ["catalog", "products", "get", "some-id"])
    assert code == 1
    msg = _err(err)
    assert "drop it: `sellerclaw catalog get ...`" in msg


def test_unknown_group_suggests_close_group(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """A wrong GROUP name (e.g. `shopify-products`) suggests the closest real group."""
    code, _out, err = _run(monkeypatch, capsys, ["shopify-products", "list"])
    assert code == 1
    msg = _err(err)
    assert "Did you mean group:" in msg
    # The suggestion is drawn from real group names (closest matches, e.g. other shopify-* groups).
    suggestion = msg.split("Did you mean group:", 1)[1]
    assert "shopify-" in suggestion


def test_success_exits_zero_with_json(monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    code, out, _err = _run(monkeypatch, capsys, ["describe", "subagent-tasks", "request-review"])
    assert code == 0
    assert json.loads(out)["data"]["command"] == "request-review"


def test_body_validation_error_still_structured_via_main(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """Our own local body validation keeps its structured error + non-zero exit through main()."""
    code, _out, err = _run(
        monkeypatch, capsys, ["subagent-tasks", "request-review", "T", "-b", '{"summary": "x"}']
    )
    assert code == 1
    msg = _err(err)
    assert "missing required field(s): outcome" in msg


@pytest.mark.parametrize(
    "abort_class",
    [
        pytest.param(click.exceptions.Abort, id="public-click"),
        pytest.param(typer.Abort, id="installed-typer"),
    ],
)
def test_abort_is_structured_whichever_module_defines_it(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str], abort_class: type[BaseException]
) -> None:
    """Ctrl-C style aborts keep our contract no matter where typer currently keeps ``Abort``.

    typer 0.27.2 moved ``Abort`` out of the vendored ``typer._click.exceptions`` and back into
    ``typer.exceptions``; a hard reference to one location broke the *import* of the CLI entirely.
    """

    def _abort(*_args: object, **_kwargs: object) -> int:
        raise abort_class()

    monkeypatch.setattr(cli, "app", _abort)
    code, _out, err = _run(monkeypatch, capsys, ["listings", "search"])
    assert code == 1
    assert _err(err) == "aborted"
