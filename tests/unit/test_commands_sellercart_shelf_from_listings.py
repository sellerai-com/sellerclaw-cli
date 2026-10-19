"""`sellercart-products add` carries listing entries to the server as they are."""

from __future__ import annotations

import json

import httpx
import pytest
import respx
from typer.testing import CliRunner

from sellerclaw_cli.cli import app

pytestmark = pytest.mark.unit

runner = CliRunner()


@respx.mock
def test_a_listing_entry_reaches_the_server_untouched(
    monkeypatch: pytest.MonkeyPatch, fake_api_url: str, fake_token: str
) -> None:
    monkeypatch.setenv("SELLERCLAW_API_URL", fake_api_url)
    monkeypatch.setenv("SELLERCLAW_TOKEN", fake_token)
    route = respx.post(f"{fake_api_url}/agent/sellercart/products").mock(
        return_value=httpx.Response(200, json={"items": [], "total": 0, "from_listings": []})
    )
    body = {
        "products": [
            {"listing_id": "0b1c2d3e-4f50-6172-8394-a5b6c7d8e9f0"},
            {"listing_id": "1b1c2d3e-4f50-6172-8394-a5b6c7d8e9f0", "title": "Cotton romper"},
        ],
        "prices": {"1400-53-68": 19.99},
    }

    result = runner.invoke(app, ["sellercart-products", "add", "-b", json.dumps(body)])

    assert result.exit_code == 0, result.stderr or result.stdout
    assert json.loads(route.calls.last.request.content) == body


def test_the_command_says_it_takes_listings() -> None:
    described = json.loads(runner.invoke(app, ["describe", "sellercart-products", "add"]).stdout)["data"]
    products = {f["field"]: f for f in described["body_fields"]}["products"]

    assert "{listing_id, title?, description?, images?}" in products["help"]
    assert "'listings search' hands back, up to 100 per call" in described["summary"]
