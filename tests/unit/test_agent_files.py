from __future__ import annotations

import json
from pathlib import Path

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


def test_agent_files_help_lists_three_subcommands() -> None:
    result = runner.invoke(app, ["files", "--help"])

    assert result.exit_code == 0
    for cmd in ("list", "from-url", "upload"):
        assert cmd in result.stdout, f"missing {cmd!r} in agent-files help output"


@respx.mock
def test_agent_files_list_calls_get_with_pagination(
    env_pointing_at_fake_api: None,  # noqa: ARG001
    fake_api_url: str,
) -> None:
    route = respx.get(f"{fake_api_url}/agent/files/").mock(
        return_value=httpx.Response(200, json={"files": [{"file_id": "f-1"}], "total": 1})
    )

    result = runner.invoke(app, ["files", "list", "--offset", "5", "--limit", "10"])

    assert result.exit_code == 0, result.stderr
    assert route.call_count == 1
    sent = route.calls.last.request.url
    assert sent.params["offset"] == "5"
    assert sent.params["limit"] == "10"
    payload = json.loads(result.stdout)
    assert payload == {"data": {"files": [{"file_id": "f-1"}], "total": 1}}


@respx.mock
def test_agent_files_from_url_posts_json_body(
    env_pointing_at_fake_api: None,  # noqa: ARG001
    fake_api_url: str,
) -> None:
    route = respx.post(f"{fake_api_url}/agent/files/from-url").mock(
        return_value=httpx.Response(
            201,
            json={
                "file_id": "f-1",
                "filename": "report.csv",
                "content_type": "text/csv",
                "size_bytes": 12,
                "download_url": "http://x/files/f-1/report.csv",
                "expires_at": "2030-01-01T00:00:00+00:00",
            },
        )
    )

    result = runner.invoke(
        app,
        [
            "files",
            "from-url",
            "--url",
            "https://example.com/r.csv",
            "--filename",
            "report.csv",
        ],
    )

    assert result.exit_code == 0, result.stderr
    assert route.call_count == 1
    body = json.loads(route.calls.last.request.content.decode())
    assert body == {"url": "https://example.com/r.csv", "filename": "report.csv"}


@respx.mock
def test_agent_files_from_url_omits_filename_when_not_provided(
    env_pointing_at_fake_api: None,  # noqa: ARG001
    fake_api_url: str,
) -> None:
    route = respx.post(f"{fake_api_url}/agent/files/from-url").mock(
        return_value=httpx.Response(201, json={})
    )

    result = runner.invoke(
        app, ["files", "from-url", "--url", "https://example.com/r.csv"]
    )

    assert result.exit_code == 0, result.stderr
    body = json.loads(route.calls.last.request.content.decode())
    assert body == {"url": "https://example.com/r.csv"}


@respx.mock
def test_agent_files_upload_sends_multipart_payload(
    env_pointing_at_fake_api: None,  # noqa: ARG001
    fake_api_url: str,
    tmp_path: Path,
) -> None:
    route = respx.post(f"{fake_api_url}/agent/files/upload-for-user").mock(
        return_value=httpx.Response(
            201,
            json={"file_id": "f-1", "filename": "creative.png"},
        )
    )
    file_path = tmp_path / "creative.png"
    file_path.write_bytes(b"fake-image")

    result = runner.invoke(app, ["files", "upload", str(file_path)])

    assert result.exit_code == 0, result.stderr
    assert route.call_count == 1
    sent = route.calls.last.request
    content_type = sent.headers.get("content-type", "")
    assert content_type.startswith("multipart/form-data")
    body = sent.content
    assert b"fake-image" in body
    assert b'name="file"' in body
    assert b'filename="creative.png"' in body


@respx.mock
def test_agent_files_upload_supports_filename_override(
    env_pointing_at_fake_api: None,  # noqa: ARG001
    fake_api_url: str,
    tmp_path: Path,
) -> None:
    route = respx.post(f"{fake_api_url}/agent/files/upload-for-user").mock(
        return_value=httpx.Response(201, json={})
    )
    file_path = tmp_path / "creative.png"
    file_path.write_bytes(b"fake-image")

    result = runner.invoke(
        app,
        ["files", "upload", str(file_path), "--filename", "renamed.png"],
    )

    assert result.exit_code == 0, result.stderr
    body = route.calls.last.request.content
    assert b'filename="renamed.png"' in body


def test_agent_files_upload_rejects_missing_file(
    env_pointing_at_fake_api: None,  # noqa: ARG001
    tmp_path: Path,
) -> None:
    missing = tmp_path / "does-not-exist.png"

    result = runner.invoke(app, ["files", "upload", str(missing)])

    assert result.exit_code != 0
