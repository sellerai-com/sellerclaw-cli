"""The catalog-file group: building a catalog from a spreadsheet.

These pin the two things the group exists for. A file in the owner's own wording is only readable
because the agent supplies a column mapping, so ``columns`` has to reach the server intact — and,
unlike a price list, it is not remembered anywhere, so it has to travel with every call. And the
group has no delete command: an upload adds and changes, never removes.
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

BASE = "/agent/products/catalog-file"


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
    route = respx.get(f"{fake_api_url}{BASE}/template").mock(
        return_value=httpx.Response(200, json={"file_id": "f-1", "instructions": "..."})
    )

    result = runner.invoke(app, ["catalog-file", "template", "--fmt", "csv"])

    assert result.exit_code == 0, result.output
    assert route.calls.last.request.url.params["fmt"] == "csv"


@respx.mock
def test_check_sends_the_column_mapping_through(
    env_pointing_at_fake_api: None,  # noqa: ARG001
    fake_api_url: str,
) -> None:
    """The mapping is the only way a foreign heading is ever read; mangling it loses the file."""
    route = respx.post(f"{fake_api_url}{BASE}/check").mock(
        return_value=httpx.Response(200, json={"accepted": True})
    )
    body = {"file_id": "f-1", "columns": {"Артикул": "SKU", "Наименование": "Name"}}

    result = runner.invoke(app, ["catalog-file", "check", "-b", json.dumps(body)])

    assert result.exit_code == 0, result.output
    assert json.loads(route.calls.last.request.content) == body


@respx.mock
def test_preview_writes_nothing_and_reports_the_plan(
    env_pointing_at_fake_api: None,  # noqa: ARG001
    fake_api_url: str,
) -> None:
    respx.post(f"{fake_api_url}{BASE}/preview").mock(
        return_value=httpx.Response(
            200, json={"accepted": True, "plan": {"rows_read": 3, "new_products": 2}}
        )
    )

    result = runner.invoke(
        app, ["catalog-file", "preview", "-b", json.dumps({"file_id": "f-1"})]
    )

    assert result.exit_code == 0, result.output
    assert "new_products" in result.output


@respx.mock
def test_apply_posts_to_apply_not_preview(
    env_pointing_at_fake_api: None,  # noqa: ARG001
    fake_api_url: str,
) -> None:
    route = respx.post(f"{fake_api_url}{BASE}/apply").mock(
        return_value=httpx.Response(200, json={"products_created": 2})
    )

    result = runner.invoke(app, ["catalog-file", "apply", "-b", json.dumps({"file_id": "f-1"})])

    assert result.exit_code == 0, result.output
    assert route.called


@respx.mock
def test_the_mapping_travels_with_apply_too(
    env_pointing_at_fake_api: None,  # noqa: ARG001
    fake_api_url: str,
) -> None:
    """Nothing remembers it, so an apply without it would read a file the check accepted."""
    route = respx.post(f"{fake_api_url}{BASE}/apply").mock(
        return_value=httpx.Response(200, json={"products_created": 1})
    )
    body = {"file_id": "f-1", "columns": {"Артикул": "SKU"}}

    result = runner.invoke(app, ["catalog-file", "apply", "-b", json.dumps(body)])

    assert result.exit_code == 0, result.output
    assert json.loads(route.calls.last.request.content)["columns"] == {"Артикул": "SKU"}


def test_a_missing_file_id_is_caught_before_the_request(
    env_pointing_at_fake_api: None,  # noqa: ARG001
) -> None:
    """Locally, so a half-written body does not cost a round trip and a server-side error."""
    result = runner.invoke(app, ["catalog-file", "apply", "-b", json.dumps({"columns": {}})])

    assert result.exit_code != 0
    assert "file_id" in result.output


def test_the_group_is_exactly_the_four_steps_of_the_flow() -> None:
    """An upload adds and changes; taking goods off sale stays a separate, explicit request, so
    there is deliberately no fifth command here to delete anything."""
    from sellerclaw_cli.commands.catalog_file import SPECS

    assert [spec.name for spec in SPECS] == ["template", "check", "preview", "apply"]


@respx.mock
def test_catalog_update_accepts_the_brand_the_api_accepts(
    env_pointing_at_fake_api: None,  # noqa: ARG001
    fake_api_url: str,
) -> None:
    """It used to be rejected locally, so a documented field never reached a working endpoint."""
    route = respx.patch(f"{fake_api_url}/agent/products/p-1").mock(
        return_value=httpx.Response(200, json={"id": "p-1"})
    )
    body = {"brand": "Acme", "country_of_origin": "PT"}

    result = runner.invoke(app, ["catalog", "update", "p-1", "-b", json.dumps(body)])

    assert result.exit_code == 0, result.output
    assert json.loads(route.calls.last.request.content) == body
