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


@respx.mock
def test_children_walks_by_the_marketplaces_own_parent_id(
    env_pointing_at_fake_api: None,  # noqa: ARG001
    fake_api_url: str,
) -> None:
    """`category_id` elsewhere on this surface is our mirror row's UUID; the parent here has always
    been the marketplace's own id, so the option says so."""
    route = respx.get(f"{fake_api_url}/agent/categories/children").mock(
        return_value=httpx.Response(200, json={"data": []})
    )

    result = runner.invoke(
        app,
        ["categories", "children", "--store-id", STORE_ID, "--parent-external-id", "2993"],
    )

    assert result.exit_code == 0, result.stderr
    assert route.calls.last.request.url.params["parent_external_id"] == "2993"


@respx.mock
def test_children_still_accepts_the_old_parent_id_spelling(
    env_pointing_at_fake_api: None,  # noqa: ARG001
    fake_api_url: str,
) -> None:
    """Callers written against the old name keep working while the skills move over."""
    route = respx.get(f"{fake_api_url}/agent/categories/children").mock(
        return_value=httpx.Response(200, json={"data": []})
    )

    result = runner.invoke(
        app, ["categories", "children", "--store-id", STORE_ID, "--parent-id", "2993"]
    )

    assert result.exit_code == 0, result.stderr
    assert route.calls.last.request.url.params["parent_external_id"] == "2993"


@respx.mock
def test_rename_sends_the_shops_own_id_under_its_new_name(
    env_pointing_at_fake_api: None,  # noqa: ARG001
    fake_api_url: str,
) -> None:
    """The rename never took our UUID — only the field name said otherwise."""
    route = respx.post(f"{fake_api_url}/agent/categories/rename").mock(
        return_value=httpx.Response(200, json={"data": {"external_id": "15"}})
    )

    result = runner.invoke(
        app,
        [
            "categories", "rename",
            "-b", '{"store_id": "' + STORE_ID + '", "external_id": "15", "name": "Dog Muzzles"}',
        ],
    )

    assert result.exit_code == 0, result.stderr
    assert route.calls.last.request.read().decode().count("external_id") == 1


@respx.mock
def test_rename_still_accepts_the_old_category_id_spelling(
    env_pointing_at_fake_api: None,  # noqa: ARG001
    fake_api_url: str,
) -> None:
    """Declared on both sides: the API takes either, and the CLI must not refuse one locally."""
    route = respx.post(f"{fake_api_url}/agent/categories/rename").mock(
        return_value=httpx.Response(200, json={"data": {"external_id": "15"}})
    )

    result = runner.invoke(
        app,
        [
            "categories", "rename",
            "-b", '{"store_id": "' + STORE_ID + '", "category_id": "15", "name": "Dog Muzzles"}',
        ],
    )

    assert result.exit_code == 0, result.stderr
    assert route.call_count == 1
