from __future__ import annotations

import json

import httpx
import pytest
import respx
from typer.testing import CliRunner

from sellerclaw_cli.cli import app

pytestmark = pytest.mark.unit

runner = CliRunner()

PAGE_URL = "https://claude.site/artifacts/abc"


@pytest.fixture
def env_pointing_at_fake_api(
    monkeypatch: pytest.MonkeyPatch,
    fake_api_url: str,
    fake_token: str,
) -> None:
    monkeypatch.setenv("SELLERCLAW_API_URL", fake_api_url)
    monkeypatch.setenv("SELLERCLAW_TOKEN", fake_token)


@respx.mock
def test_scrape_defaults_to_markdown_and_asks_for_nothing_extra(
    env_pointing_at_fake_api: None,  # noqa: ARG001
    fake_api_url: str,
) -> None:
    route = respx.get(f"{fake_api_url}/agent/web/scrape").mock(
        return_value=httpx.Response(
            200,
            json={
                "url": PAGE_URL,
                "content": "# Komok",
                "content_format": "markdown",
                "content_chars": 7,
                "truncated": False,
            },
        )
    )

    result = runner.invoke(app, ["web", "scrape", "--url", PAGE_URL])

    assert result.exit_code == 0, result.output
    # A screenshot costs extra, so it is never implied — the request carries only the URL.
    assert dict(route.calls.last.request.url.params) == {"url": PAGE_URL}
    assert json.loads(result.output)["data"]["content_format"] == "markdown"


@respx.mock
def test_scrape_can_ask_for_the_source_and_a_picture(
    env_pointing_at_fake_api: None,  # noqa: ARG001
    fake_api_url: str,
) -> None:
    """Reproducing a design needs the page's markup and how it looks, not its prose."""
    route = respx.get(f"{fake_api_url}/agent/web/scrape").mock(
        return_value=httpx.Response(
            200,
            json={
                "url": PAGE_URL,
                "content": "<html><body style='background:#faf6ee'></body></html>",
                "content_format": "html",
                "content_chars": 52,
                "truncated": False,
                "screenshot_url": "https://files.test/page-abc.png",
                "screenshot_file_id": "file-abc",
            },
        )
    )

    result = runner.invoke(
        app, ["web", "scrape", "--url", PAGE_URL, "--format", "html", "--screenshot"]
    )

    assert result.exit_code == 0, result.output
    assert dict(route.calls.last.request.url.params) == {
        "url": PAGE_URL,
        "format": "html",
        "screenshot": "true",
    }
    body = json.loads(result.output)["data"]
    assert body["content_format"] == "html"
    assert body["screenshot_url"] == "https://files.test/page-abc.png"


def test_scrape_refuses_a_format_the_api_does_not_have(
    env_pointing_at_fake_api: None,  # noqa: ARG001
) -> None:
    """Caught here rather than as a 422 three seconds later."""
    result = runner.invoke(app, ["web", "scrape", "--url", PAGE_URL, "--format", "pdf"])

    assert result.exit_code != 0
    assert "pdf" in result.output
