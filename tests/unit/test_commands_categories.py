from __future__ import annotations

import httpx
import pytest
import respx
from typer.testing import CliRunner

from sellerclaw_cli.cli import app

pytestmark = pytest.mark.unit

runner = CliRunner()

STORE_ID = "11111111-1111-4111-8111-111111111111"


@pytest.fixture
def env_pointing_at_fake_api(
    monkeypatch: pytest.MonkeyPatch,
    fake_api_url: str,
    fake_token: str,
) -> None:
    monkeypatch.setenv("SELLERCLAW_API_URL", fake_api_url)
    monkeypatch.setenv("SELLERCLAW_TOKEN", fake_token)


@respx.mock
def test_refresh_posts_the_store(
    env_pointing_at_fake_api: None,  # noqa: ARG001
    fake_api_url: str,
) -> None:
    route = respx.post(f"{fake_api_url}/agent/categories/refresh").mock(
        return_value=httpx.Response(
            200,
            json=[
                {
                    "tree_id": "33333333-3333-4333-8333-333333333333",
                    "platform": "woocommerce",
                    "region_code": "",
                    "external_tree_id": "",
                    "is_default": True,
                    "node_count": 7,
                    "sync_status": "ok",
                    "synced_at": "2026-07-17T04:00:00Z",
                }
            ],
        )
    )

    result = runner.invoke(app, ["categories", "refresh", "--store-id", STORE_ID])

    assert result.exit_code == 0, result.stderr
    assert route.call_count == 1
    assert route.calls.last.request.url.params["store_id"] == STORE_ID
    assert route.calls.last.request.content in (b"", None)
    # node_count is why the caller ran this at all: it says whether the new category arrived.
    assert "7" in result.stdout


@respx.mock
def test_refresh_without_a_store_never_reaches_the_server(
    env_pointing_at_fake_api: None,  # noqa: ARG001
    fake_api_url: str,
) -> None:
    route = respx.post(f"{fake_api_url}/agent/categories/refresh").mock(
        return_value=httpx.Response(200, json=[])
    )

    result = runner.invoke(app, ["categories", "refresh"])

    assert result.exit_code != 0
    assert route.call_count == 0
