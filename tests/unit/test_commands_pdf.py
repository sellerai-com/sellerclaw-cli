from __future__ import annotations

import json

import httpx
import pytest
import respx
from typer.testing import CliRunner

from sellerclaw_cli.cli import app

pytestmark = pytest.mark.unit

runner = CliRunner()

_CREATED = {
    "file_id": "pdf-1",
    "filename": "weekly-review.pdf",
    "content_type": "application/pdf",
    "size_bytes": 24576,
    "download_url": "http://testserver/files/pdf-1/weekly-review.pdf",
    "expires_at": "2026-12-31T00:00:00+00:00",
    "pages": 3,
}


@pytest.fixture
def env_pointing_at_fake_api(
    monkeypatch: pytest.MonkeyPatch,
    fake_api_url: str,
    fake_token: str,
) -> None:
    monkeypatch.setenv("SELLERCLAW_API_URL", fake_api_url)
    monkeypatch.setenv("SELLERCLAW_TOKEN", fake_token)


def test_pdf_help_lists_create() -> None:
    result = runner.invoke(app, ["pdf", "--help"])
    assert result.exit_code == 0
    assert "create" in result.stdout


@respx.mock
def test_pdf_create_posts_the_document_and_returns_the_link(
    env_pointing_at_fake_api: None,  # noqa: ARG001
    fake_api_url: str,
) -> None:
    route = respx.post(f"{fake_api_url}/agent/pdf").mock(return_value=httpx.Response(201, json=_CREATED))
    body = json.dumps(
        {
            "filename": "weekly-review.pdf",
            "title": "Weekly review",
            "blocks": [
                {"type": "cover", "title": "Weekly review", "date": "13 July 2026"},
                {"type": "heading", "text": "How the week went", "level": 1},
                {
                    "type": "chart",
                    "kind": "bar",
                    "labels": ["Mon", "Tue"],
                    "series": [{"name": "This week", "values": [1180, 1420]}],
                },
            ],
        }
    )

    result = runner.invoke(app, ["pdf", "create", "-b", body])

    assert result.exit_code == 0, result.stderr
    assert route.call_count == 1
    sent = json.loads(route.calls.last.request.content.decode("utf-8"))
    assert sent["title"] == "Weekly review"
    assert [b["type"] for b in sent["blocks"]] == ["cover", "heading", "chart"]
    payload = json.loads(result.stdout)
    assert payload["data"]["download_url"] == _CREATED["download_url"]
    assert payload["data"]["pages"] == 3


@respx.mock
@pytest.mark.parametrize(
    ("body", "reason"),
    [
        pytest.param(
            {"title": "No filename", "blocks": [{"type": "paragraph", "text": "hi"}]},
            "filename is required",
            id="missing-required-filename",
        ),
        pytest.param(
            {"filename": "x.pdf", "title": "No blocks"},
            "blocks is required",
            id="missing-required-blocks",
        ),
        pytest.param(
            {
                "filename": "x.pdf",
                "title": "Typo",
                "blocks": [{"type": "paragraph", "text": "hi"}],
                "stlye": "fancy",
            },
            "unknown key is rejected before the call",
            id="unknown-top-level-key",
        ),
    ],
)
def test_pdf_create_rejects_a_bad_body_without_calling_the_api(
    env_pointing_at_fake_api: None,  # noqa: ARG001
    fake_api_url: str,
    body: dict[str, object],
    reason: str,
) -> None:
    """The declared schema fails locally, so a malformed document never costs a round-trip."""
    route = respx.post(f"{fake_api_url}/agent/pdf").mock(return_value=httpx.Response(201, json=_CREATED))

    result = runner.invoke(app, ["pdf", "create", "-b", json.dumps(body)])

    assert result.exit_code != 0, reason
    assert route.call_count == 0
