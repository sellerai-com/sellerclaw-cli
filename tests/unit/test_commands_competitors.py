from __future__ import annotations

import json

import httpx
import pytest
import respx
from typer.testing import CliRunner

from sellerclaw_cli.cli import app

pytestmark = pytest.mark.unit

runner = CliRunner()

STORE_ID = "11111111-1111-4111-8111-111111111111"
WATCH_ID = "22222222-2222-4222-8222-222222222222"


@pytest.fixture
def env_pointing_at_fake_api(
    monkeypatch: pytest.MonkeyPatch,
    fake_api_url: str,
    fake_token: str,
) -> None:
    monkeypatch.setenv("SELLERCLAW_API_URL", fake_api_url)
    monkeypatch.setenv("SELLERCLAW_TOKEN", fake_token)


@respx.mock
def test_add_watch_posts_body_and_substitutes_store_id(
    env_pointing_at_fake_api: None,  # noqa: ARG001
    fake_api_url: str,
) -> None:
    route = respx.post(f"{fake_api_url}/agent/competitors/stores/{STORE_ID}/watches").mock(
        return_value=httpx.Response(201, json={"id": WATCH_ID})
    )
    result = runner.invoke(
        app,
        [
            "competitors",
            "add-watch",
            STORE_ID,
            "-b",
            json.dumps({"competitor_item_id": "v1|123|0", "our_sku": "SKU-7"}),
        ],
    )
    assert result.exit_code == 0, result.stderr
    assert route.call_count == 1
    sent = json.loads(route.calls.last.request.content)
    assert sent == {"competitor_item_id": "v1|123|0", "our_sku": "SKU-7"}


@respx.mock
def test_add_watch_requires_competitor_item_id_locally(
    env_pointing_at_fake_api: None,  # noqa: ARG001
    fake_api_url: str,
) -> None:
    route = respx.post(f"{fake_api_url}/agent/competitors/stores/{STORE_ID}/watches").mock(
        return_value=httpx.Response(201, json={"id": WATCH_ID})
    )
    result = runner.invoke(app, ["competitors", "add-watch", STORE_ID, "-b", "{}"])
    assert result.exit_code != 0
    assert route.call_count == 0  # missing required field caught before the network call


@respx.mock
def test_list_watches_forwards_include_inactive(
    env_pointing_at_fake_api: None,  # noqa: ARG001
    fake_api_url: str,
) -> None:
    route = respx.get(f"{fake_api_url}/agent/competitors/stores/{STORE_ID}/watches").mock(
        return_value=httpx.Response(200, json={"store_id": STORE_ID, "watches": []})
    )
    result = runner.invoke(app, ["competitors", "list-watches", STORE_ID, "--include-inactive"])
    assert result.exit_code == 0, result.stderr
    assert route.calls.last.request.url.params["include_inactive"] == "true"


@respx.mock
def test_list_watches_default_omits_include_inactive(
    env_pointing_at_fake_api: None,  # noqa: ARG001
    fake_api_url: str,
) -> None:
    route = respx.get(f"{fake_api_url}/agent/competitors/stores/{STORE_ID}/watches").mock(
        return_value=httpx.Response(200, json={"store_id": STORE_ID, "watches": []})
    )
    result = runner.invoke(app, ["competitors", "list-watches", STORE_ID])
    assert result.exit_code == 0, result.stderr
    assert "include_inactive" not in route.calls.last.request.url.params


@respx.mock
def test_remove_watch_deletes_with_watch_id(
    env_pointing_at_fake_api: None,  # noqa: ARG001
    fake_api_url: str,
) -> None:
    route = respx.delete(
        f"{fake_api_url}/agent/competitors/stores/{STORE_ID}/watches/{WATCH_ID}"
    ).mock(return_value=httpx.Response(204))
    result = runner.invoke(app, ["competitors", "remove-watch", STORE_ID, WATCH_ID])
    assert result.exit_code == 0, result.stderr
    assert route.call_count == 1


@respx.mock
def test_poll_posts(
    env_pointing_at_fake_api: None,  # noqa: ARG001
    fake_api_url: str,
) -> None:
    route = respx.post(f"{fake_api_url}/agent/competitors/stores/{STORE_ID}/poll").mock(
        return_value=httpx.Response(200, json={"store_id": STORE_ID, "snapshots_written": 3})
    )
    result = runner.invoke(app, ["competitors", "poll", STORE_ID])
    assert result.exit_code == 0, result.stderr
    assert route.call_count == 1
    assert json.loads(result.stdout)["data"]["snapshots_written"] == 3


@respx.mock
def test_report_gets(
    env_pointing_at_fake_api: None,  # noqa: ARG001
    fake_api_url: str,
) -> None:
    route = respx.get(f"{fake_api_url}/agent/competitors/stores/{STORE_ID}/report").mock(
        return_value=httpx.Response(
            200, json={"store_id": STORE_ID, "watched_count": 0, "changes": []}
        )
    )
    result = runner.invoke(app, ["competitors", "report", STORE_ID])
    assert result.exit_code == 0, result.stderr
    assert route.call_count == 1
