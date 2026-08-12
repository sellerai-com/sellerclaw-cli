"""The sheets group: reading and writing a Google Sheet the seller shared with SellerClaw.

These pin what makes this group different from ``spreadsheet``. The spreadsheet is addressed by a
pasted URL, so the link has to travel as a parameter and reach the API byte-for-byte instead of
being spliced into the path. And a write is destructive in ``replace`` mode, so the mode and the
rows have to arrive exactly as the caller wrote them.
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

BASE = "/agent/sheets"
SHEET_LINK = "https://docs.google.com/spreadsheets/d/1AbCdEfGhIjKlMnOpQrStUvWxYz0123456789/edit?usp=sharing"


@pytest.fixture
def env_pointing_at_fake_api(
    monkeypatch: pytest.MonkeyPatch,
    fake_api_url: str,
    fake_token: str,
) -> None:
    monkeypatch.setenv("SELLERCLAW_API_URL", fake_api_url)
    monkeypatch.setenv("SELLERCLAW_TOKEN", fake_token)


@respx.mock
def test_info_sends_the_link_untouched(
    env_pointing_at_fake_api: None,  # noqa: ARG001
    fake_api_url: str,
) -> None:
    """A mangled link is indistinguishable from a sheet that does not exist, so it must survive."""
    route = respx.get(f"{fake_api_url}{BASE}/info").mock(
        return_value=httpx.Response(
            200,
            json={
                "spreadsheet_id": "1AbCdEfGhIjKlMnOpQrStUvWxYz0123456789",
                "title": "Weekly reports",
                "url": SHEET_LINK,
                "tabs": [],
                "service_account_email": "sheets@sellerclaw.iam.gserviceaccount.com",
            },
        )
    )

    result = runner.invoke(app, ["sheets", "info", "--link", SHEET_LINK])

    assert result.exit_code == 0, result.output
    assert route.calls.last.request.url.params["link"] == SHEET_LINK


@respx.mock
def test_read_passes_paging_and_column_choice_through(
    env_pointing_at_fake_api: None,  # noqa: ARG001
    fake_api_url: str,
) -> None:
    route = respx.get(f"{fake_api_url}{BASE}/values").mock(
        return_value=httpx.Response(
            200,
            json={
                "spreadsheet_id": "1AbCdEfGhIjKlMnOpQrStUvWxYz0123456789",
                "title": "Weekly reports",
                "tab": "Data",
                "offset": 100,
                "limit": 50,
                "returned_rows": 0,
                "has_more": False,
                "columns": [],
                "rows": [],
            },
        )
    )

    result = runner.invoke(
        app,
        [
            "sheets", "read",
            "--link", SHEET_LINK,
            "--tab", "Data",
            "--offset", "100",
            "--limit", "50",
            "--columns", "sku,qty",
        ],
    )

    assert result.exit_code == 0, result.output
    params = route.calls.last.request.url.params
    assert params["tab"] == "Data"
    assert params["offset"] == "100"
    assert params["limit"] == "50"
    assert params["columns"] == "sku,qty"


@respx.mock
def test_write_sends_the_body_as_written(
    env_pointing_at_fake_api: None,  # noqa: ARG001
    fake_api_url: str,
) -> None:
    route = respx.post(f"{fake_api_url}{BASE}/values").mock(
        return_value=httpx.Response(
            200,
            json={
                "spreadsheet_id": "1AbCdEfGhIjKlMnOpQrStUvWxYz0123456789",
                "title": "Weekly reports",
                "tab": "July",
                "mode": "append",
                "rows_written": 2,
                "headers_written": True,
                "created_tab": True,
                "url": SHEET_LINK,
            },
        )
    )
    body = {
        "link": SHEET_LINK,
        "tab": "July",
        "mode": "append",
        "headers": ["sku", "qty"],
        "rows": [["A1", 5], ["B2", 7]],
        "create_tab": True,
    }

    result = runner.invoke(app, ["sheets", "write", "-b", json.dumps(body)])

    assert result.exit_code == 0, result.output
    assert json.loads(route.calls.last.request.content) == body


def test_write_refuses_an_unknown_mode_before_calling_the_api() -> None:
    """``replace`` wipes a tab, so a typo'd mode must fail locally, not be guessed at server-side."""
    body = {"link": SHEET_LINK, "mode": "overwrite", "rows": [["A1"]]}

    result = runner.invoke(app, ["sheets", "write", "-b", json.dumps(body)])

    assert result.exit_code != 0
    assert "overwrite" in result.output


@pytest.mark.parametrize(
    "argv",
    [
        pytest.param(["sheets", "info"], id="info-without-link"),
        pytest.param(["sheets", "read"], id="read-without-link"),
    ],
)
def test_link_is_required(argv: list[str]) -> None:
    result = runner.invoke(app, argv)

    assert result.exit_code != 0
