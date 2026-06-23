from __future__ import annotations

import json

import pytest

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
    code, _out, err = _run(monkeypatch, capsys, ["research-trends", "interest-over-time", "--keyword", "x"])
    assert code == 1
    msg = _err(err)
    assert "No such option: --keyword" in msg
    assert "--keywords" in msg  # Click's own suggestion
    assert "describe research-trends interest-over-time" in msg


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
    code, _out, err = _run(monkeypatch, capsys, ["subagent-tasks", "progress", "X"])
    assert code == 1
    msg = _err(err)
    assert "No such command 'progress'" in msg
    assert "commands --group subagent-tasks" in msg


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
