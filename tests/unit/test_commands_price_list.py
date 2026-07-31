"""The price-list group: files from suppliers who have no API.

These pin the two things the group exists for. A file in the supplier's own wording is only readable
because the agent supplies a column mapping, so ``--columns`` has to reach the server intact. And
nothing here takes goods off sale by itself: ``out-of-sale`` is its own command, with the positions
named.
"""

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


@respx.mock
def test_template_asks_for_the_requested_format(
    env_pointing_at_fake_api: None,  # noqa: ARG001
    fake_api_url: str,
) -> None:
    route = respx.get(f"{fake_api_url}/agent/suppliers/price-list/template").mock(
        return_value=httpx.Response(200, json={"file_id": "f-1", "instructions": "..."})
    )

    result = runner.invoke(app, ["price-list", "template", "--fmt", "csv"])

    assert result.exit_code == 0, result.output
    assert route.calls.last.request.url.params["fmt"] == "csv"


@respx.mock
def test_check_sends_the_column_mapping_through(
    env_pointing_at_fake_api: None,  # noqa: ARG001
    fake_api_url: str,
) -> None:
    """The mapping is the only way a foreign heading is ever read; mangling it loses the file."""
    route = respx.post(f"{fake_api_url}/agent/suppliers/price-list/check").mock(
        return_value=httpx.Response(200, json={"accepted": True})
    )
    body = {
        "supplier_id": "11111111-1111-1111-1111-111111111111",
        "file_id": "f-1",
        "columns": {"Артикул": "SKU", "Цена": "Cost"},
    }

    result = runner.invoke(app, ["price-list", "check", "-b", json.dumps(body)])

    assert result.exit_code == 0, result.output
    assert json.loads(route.calls.last.request.content) == body


@respx.mock
def test_preview_writes_nothing_and_reports_the_plan(
    env_pointing_at_fake_api: None,  # noqa: ARG001
    fake_api_url: str,
) -> None:
    respx.post(f"{fake_api_url}/agent/suppliers/price-list/preview").mock(
        return_value=httpx.Response(
            200, json={"accepted": True, "plan": {"rows_read": 2, "changes": 1}}
        )
    )
    body = {"supplier_id": "11111111-1111-1111-1111-111111111111", "file_id": "f-1"}

    result = runner.invoke(app, ["price-list", "preview", "-b", json.dumps(body)])

    assert result.exit_code == 0, result.output
    assert "rows_read" in result.output


@respx.mock
def test_apply_posts_to_apply_not_preview(
    env_pointing_at_fake_api: None,  # noqa: ARG001
    fake_api_url: str,
) -> None:
    route = respx.post(f"{fake_api_url}/agent/suppliers/price-list/apply").mock(
        return_value=httpx.Response(200, json={"products_updated": 1})
    )
    body = {"supplier_id": "11111111-1111-1111-1111-111111111111", "file_id": "f-1"}

    result = runner.invoke(app, ["price-list", "apply", "-b", json.dumps(body)])

    assert result.exit_code == 0, result.output
    assert route.called


@respx.mock
def test_out_of_sale_names_the_positions(
    env_pointing_at_fake_api: None,  # noqa: ARG001
    fake_api_url: str,
) -> None:
    """Taking goods off sale is always by name — there is no "everything not in the file" switch."""
    route = respx.post(f"{fake_api_url}/agent/suppliers/price-list/out-of-sale").mock(
        return_value=httpx.Response(200, json={"withdrawn": []})
    )
    body = {
        "supplier_id": "11111111-1111-1111-1111-111111111111",
        "codes": ["TEE-M", "SOCKS-41"],
    }

    result = runner.invoke(app, ["price-list", "out-of-sale", "-b", json.dumps(body)])

    assert result.exit_code == 0, result.output
    assert json.loads(route.calls.last.request.content)["codes"] == ["TEE-M", "SOCKS-41"]


@respx.mock
def test_create_products_passes_the_batch_cap(
    env_pointing_at_fake_api: None,  # noqa: ARG001
    fake_api_url: str,
) -> None:
    route = respx.post(f"{fake_api_url}/agent/suppliers/price-list/create-products").mock(
        return_value=httpx.Response(200, json={"created": [], "remaining": 0})
    )
    body = {"supplier_id": "11111111-1111-1111-1111-111111111111", "limit": 50}

    result = runner.invoke(app, ["price-list", "create-products", "-b", json.dumps(body)])

    assert result.exit_code == 0, result.output
    assert json.loads(route.calls.last.request.content)["limit"] == 50


def test_a_missing_supplier_id_is_caught_before_the_request(
    env_pointing_at_fake_api: None,  # noqa: ARG001
) -> None:
    """Locally, so a half-written body does not cost a round trip and a server-side error."""
    result = runner.invoke(app, ["price-list", "apply", "-b", json.dumps({"file_id": "f-1"})])

    assert result.exit_code != 0
    assert "supplier_id" in result.output
