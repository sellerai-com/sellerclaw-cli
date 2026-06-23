from __future__ import annotations

import json

import httpx
import pytest
import respx
from typer.testing import CliRunner

from sellerclaw_cli.cli import app

pytestmark = pytest.mark.unit

runner = CliRunner()


@pytest.fixture
def env_pointing_at_fake_api(
    monkeypatch: pytest.MonkeyPatch,
    fake_api_url: str,
    fake_token: str,
) -> None:
    monkeypatch.setenv("SELLERCLAW_API_URL", fake_api_url)
    monkeypatch.setenv("SELLERCLAW_TOKEN", fake_token)


def test_spreadsheet_help_lists_four_subcommands() -> None:
    result = runner.invoke(app, ["spreadsheet", "--help"])
    assert result.exit_code == 0
    for cmd in ("info", "read", "create", "edit"):
        assert cmd in result.stdout, f"missing {cmd!r} in spreadsheet help output"


@respx.mock
def test_spreadsheet_info_calls_get_with_file_id(
    env_pointing_at_fake_api: None,  # noqa: ARG001
    fake_api_url: str,
) -> None:
    route = respx.get(f"{fake_api_url}/agent/spreadsheet/abc-123").mock(
        return_value=httpx.Response(
            200,
            json={
                "filename": "x.xlsx",
                "size_bytes": 1024,
                "file_type": "xlsx",
                "csv": None,
                "sheets": [{"name": "Sheet1", "rows": 5, "columns": 2, "headers": ["a", "b"]}],
            },
        )
    )
    result = runner.invoke(app, ["spreadsheet", "info", "abc-123"])
    assert result.exit_code == 0, result.stderr
    assert route.call_count == 1
    payload = json.loads(result.stdout)
    assert payload["data"]["sheets"][0]["name"] == "Sheet1"


@respx.mock
def test_spreadsheet_read_passes_pagination_flags_as_query(
    env_pointing_at_fake_api: None,  # noqa: ARG001
    fake_api_url: str,
) -> None:
    route = respx.get(f"{fake_api_url}/agent/spreadsheet/abc-123/rows").mock(
        return_value=httpx.Response(
            200,
            json={
                "filename": "x.xlsx",
                "sheet": "Sheet1",
                "total_rows": 100,
                "offset": 10,
                "limit": 5,
                "returned_rows": 5,
                "has_more": True,
                "columns": ["a", "b"],
                "rows": [],
            },
        )
    )
    result = runner.invoke(
        app,
        ["spreadsheet", "read", "abc-123", "--offset", "10", "--limit", "5", "--sheet", "Inventory"],
    )
    assert result.exit_code == 0, result.stderr
    assert route.call_count == 1
    sent = route.calls.last.request.url
    assert sent.params["offset"] == "10"
    assert sent.params["limit"] == "5"
    assert sent.params["sheet"] == "Inventory"


@respx.mock
def test_spreadsheet_read_limit_above_max_fails_locally(
    env_pointing_at_fake_api: None,  # noqa: ARG001
    fake_api_url: str,
) -> None:
    # The maximum=1000 declared in the flag rejects locally; no HTTP call should fire.
    route = respx.get(f"{fake_api_url}/agent/spreadsheet/abc-123/rows").mock(
        return_value=httpx.Response(200, json={})
    )
    result = runner.invoke(app, ["spreadsheet", "read", "abc-123", "--limit", "10000"])
    assert result.exit_code != 0
    assert route.call_count == 0


@respx.mock
def test_spreadsheet_create_posts_body(
    env_pointing_at_fake_api: None,  # noqa: ARG001
    fake_api_url: str,
) -> None:
    route = respx.post(f"{fake_api_url}/agent/spreadsheet").mock(
        return_value=httpx.Response(
            201,
            json={
                "file_id": "new-1",
                "filename": "out.xlsx",
                "content_type": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                "size_bytes": 1024,
                "download_url": "http://testserver/files/new-1/out.xlsx",
                "expires_at": "2026-12-31T00:00:00+00:00",
                "rows_written": 2,
            },
        )
    )
    body = json.dumps({"filename": "out.xlsx", "rows": [["a", 1], ["b", 2]], "headers": ["x", "y"]})
    result = runner.invoke(app, ["spreadsheet", "create", "-b", body])
    assert result.exit_code == 0, result.stderr
    assert route.call_count == 1
    sent_body = json.loads(route.calls.last.request.content.decode("utf-8"))
    assert sent_body["filename"] == "out.xlsx"
    assert sent_body["rows"] == [["a", 1], ["b", 2]]


@respx.mock
def test_spreadsheet_edit_posts_op_body(
    env_pointing_at_fake_api: None,  # noqa: ARG001
    fake_api_url: str,
) -> None:
    route = respx.post(f"{fake_api_url}/agent/spreadsheet/abc-123/edits").mock(
        return_value=httpx.Response(
            200,
            json={
                "file_id": "new-2",
                "filename": "x.xlsx",
                "content_type": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                "size_bytes": 1100,
                "download_url": "http://testserver/files/new-2/x.xlsx",
                "expires_at": "2026-12-31T00:00:00+00:00",
                "operation": "append-rows",
                "sheet": "Sheet1",
                "rows_changed": 1,
            },
        )
    )
    body = json.dumps({"op": "append-rows", "rows": [["new", 42]]})
    result = runner.invoke(app, ["spreadsheet", "edit", "abc-123", "-b", body])
    assert result.exit_code == 0, result.stderr
    assert route.call_count == 1
    sent_body = json.loads(route.calls.last.request.content.decode("utf-8"))
    assert sent_body["op"] == "append-rows"
