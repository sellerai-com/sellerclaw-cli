from __future__ import annotations

import json
from pathlib import Path

import pytest

from sellerclaw_cli._errors import UserInputError
from sellerclaw_cli._runtime import parse_json_body

pytestmark = pytest.mark.unit


def test_parse_json_body_literal_object() -> None:
    assert parse_json_body('{"k": 1}') == {"k": 1}


def test_parse_json_body_literal_array() -> None:
    assert parse_json_body("[1, 2]") == [1, 2]


def test_parse_json_body_none() -> None:
    assert parse_json_body(None) is None


def test_parse_json_body_at_prefix_reads_file(tmp_path: Path) -> None:
    target = tmp_path / "body.json"
    target.write_text(json.dumps({"items": [1, 2, 3]}))
    assert parse_json_body(f"@{target}") == {"items": [1, 2, 3]}


def test_parse_json_body_bare_path_reads_file(tmp_path: Path) -> None:
    """A bare path to an existing file is auto-read, no '@' prefix required.

    Why: agents (and humans) routinely build a request body in a temp file and
    pass it as ``-b /tmp/quote.json``. The old behavior rejected this with a
    "looks like a file path; prefix it with '@'" error, costing an extra retry.
    """
    target = tmp_path / "shipping_quote.json"
    payload = {"items": [{"variant_id": "v1", "quantity": 1}]}
    target.write_text(json.dumps(payload))
    assert parse_json_body(str(target)) == payload


def test_parse_json_body_bare_path_to_missing_file_raises_json_error(
    tmp_path: Path,
) -> None:
    """A bare argument that is not literal JSON and not a real file ends up in
    the JSON decoder — surface a clear "invalid JSON" error rather than the
    confusing "file not found" wording."""
    missing = tmp_path / "does-not-exist.json"
    with pytest.raises(UserInputError, match="invalid JSON"):
        parse_json_body(str(missing))


def test_parse_json_body_at_missing_path_raises_file_not_found(
    tmp_path: Path,
) -> None:
    missing = tmp_path / "nope.json"
    with pytest.raises(UserInputError, match="--body file not found"):
        parse_json_body(f"@{missing}")


def test_parse_json_body_stdin_dash(monkeypatch: pytest.MonkeyPatch) -> None:
    import io
    import sys as _sys

    monkeypatch.setattr(_sys, "stdin", io.StringIO('{"from_stdin": true}'))
    assert parse_json_body("@-") == {"from_stdin": True}


def test_parse_json_body_literal_wins_over_coincidental_path(tmp_path: Path) -> None:
    """A literal JSON value (object/array/string) is never re-interpreted as a path,
    even when a file at the same string happens to exist."""
    odd = tmp_path / '{"shadow": 1}'
    odd.write_text(json.dumps({"shadow": 99}))
    # The argument starts with ``{`` -> literal JSON wins, file is ignored.
    assert parse_json_body('{"shadow": 1}') == {"shadow": 1}
