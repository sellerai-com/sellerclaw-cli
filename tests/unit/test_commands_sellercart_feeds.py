from __future__ import annotations

import json
from typing import Any

import httpx
import pytest
import respx
from typer.testing import CliRunner

from sellerclaw_cli.cli import app

pytestmark = pytest.mark.unit

runner = CliRunner()

PRODUCT_ID = "7c9e6679-7425-40de-944b-e07fc1f90ae7"


def _data(stdout: str) -> Any:
    return json.loads(stdout)["data"]


@pytest.fixture
def env_pointing_at_fake_api(
    monkeypatch: pytest.MonkeyPatch,
    fake_api_url: str,
    fake_token: str,
) -> None:
    monkeypatch.setenv("SELLERCLAW_API_URL", fake_api_url)
    monkeypatch.setenv("SELLERCLAW_TOKEN", fake_token)


@respx.mock
@pytest.mark.parametrize(
    ("args", "limit"),
    [
        # The default is the server's: nothing is sent for it.
        pytest.param([], None, id="default"),
        pytest.param(["--limit", "20"], "20", id="narrowed"),
    ],
)
def test_status_reads_the_feeds(
    env_pointing_at_fake_api: None,  # noqa: ARG001
    fake_api_url: str,
    args: list[str],
    limit: str | None,
) -> None:
    feeds = {"unavailable": None, "products_total": 2, "feeds": []}
    route = respx.get(f"{fake_api_url}/agent/sellercart/feeds").mock(
        return_value=httpx.Response(200, json=feeds)
    )

    result = runner.invoke(app, ["sellercart-feeds", "status", *args])

    assert result.exit_code == 0, result.stderr or result.stdout
    assert route.calls.last.request.url.params.get("limit") == limit
    assert _data(result.stdout) == feeds


def test_a_limit_past_the_ceiling_is_refused_locally() -> None:
    result = runner.invoke(app, ["sellercart-feeds", "status", "--limit", "501"])

    assert result.exit_code != 0


@respx.mock
@pytest.mark.parametrize(
    ("command", "path", "status"),
    [
        pytest.param("keep-out", "keep-out", "kept_out", id="keep-out"),
        pytest.param("put-back", "put-back", "put_back", id="put-back"),
    ],
)
def test_keep_out_and_put_back_send_the_products(
    env_pointing_at_fake_api: None,  # noqa: ARG001
    fake_api_url: str,
    command: str,
    path: str,
    status: str,
) -> None:
    answer = {
        "results": [
            {"product": PRODUCT_ID, "card_id": PRODUCT_ID, "title": "Mug", "status": status, "error": None}
        ]
    }
    route = respx.post(f"{fake_api_url}/agent/sellercart/feeds/{path}").mock(
        return_value=httpx.Response(200, json=answer)
    )

    result = runner.invoke(
        app, ["sellercart-feeds", command, "-b", json.dumps({"products": [PRODUCT_ID]})]
    )

    assert result.exit_code == 0, result.stderr or result.stdout
    assert json.loads(route.calls.last.request.content) == {"products": [PRODUCT_ID]}
    assert _data(result.stdout) == answer


def test_keep_out_without_products_is_refused_locally() -> None:
    result = runner.invoke(app, ["sellercart-feeds", "keep-out", "-b", json.dumps({})])

    assert result.exit_code != 0
