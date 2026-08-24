from __future__ import annotations

import json

import httpx
import pytest
import respx
from typer.testing import CliRunner

from sellerclaw_cli.cli import app

pytestmark = pytest.mark.unit

runner = CliRunner()

LISTING_ID = "22222222-2222-4222-8222-222222222222"

_LISTING_JSON = {"id": LISTING_ID, "status": "published", "title": "Widget"}


@pytest.fixture
def env_pointing_at_fake_api(
    monkeypatch: pytest.MonkeyPatch,
    fake_api_url: str,
    fake_token: str,
) -> None:
    monkeypatch.setenv("SELLERCLAW_API_URL", fake_api_url)
    monkeypatch.setenv("SELLERCLAW_TOKEN", fake_token)


@respx.mock
def test_adopt_marketplace_version_posts_to_listing_path(
    env_pointing_at_fake_api: None,  # noqa: ARG001
    fake_api_url: str,
) -> None:
    """The command POSTs to the per-listing adopt endpoint with the id substituted, no body."""
    route = respx.post(
        f"{fake_api_url}/agent/listings/{LISTING_ID}/adopt-marketplace-version"
    ).mock(return_value=httpx.Response(200, json=_LISTING_JSON))

    result = runner.invoke(app, ["listings", "adopt-marketplace-version", LISTING_ID])

    assert result.exit_code == 0, result.stderr
    assert route.call_count == 1
    # It carries no request body — the action takes only the listing id.
    assert route.calls.last.request.content in (b"", b"null")
    assert json.loads(result.stdout)["data"]["id"] == LISTING_ID


def test_adopt_marketplace_version_requires_listing_id(
    env_pointing_at_fake_api: None,  # noqa: ARG001
) -> None:
    """Omitting the listing id fails locally (missing positional) without a network call."""
    result = runner.invoke(app, ["listings", "adopt-marketplace-version"])

    assert result.exit_code != 0


@respx.mock
def test_search_filters_by_the_variation_group(
    env_pointing_at_fake_api: None,  # noqa: ARG001
    fake_api_url: str,
) -> None:
    """The group id is what drafting and publishing hand back, so it has to be searchable."""
    group_id = "33333333-3333-4333-8333-333333333333"
    route = respx.get(f"{fake_api_url}/agent/listings/search").mock(
        return_value=httpx.Response(200, json={"data": {"items": [], "total": 0}})
    )

    result = runner.invoke(app, ["listings", "search", "--group-id", group_id])

    assert result.exit_code == 0, result.stderr
    assert route.calls.last.request.url.params["group_id"] == group_id
