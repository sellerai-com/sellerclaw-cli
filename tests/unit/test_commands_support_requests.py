"""Requests to the SellerClaw team: what the owner's assistant passes on for them, and where it stands."""

from __future__ import annotations

import json

import httpx
import pytest
import respx
from typer.testing import CliRunner

from sellerclaw_cli.cli import app
from sellerclaw_cli.mcp_server import MCP_VISIBLE_GROUPS

pytestmark = pytest.mark.unit

runner = CliRunner()

REQUEST_ID = "66666666-6666-4666-8666-666666666666"

_REQUEST_JSON = {
    "id": REQUEST_ID,
    "kind": "bug",
    "raised_by": "owner",
    "title": "eBay sync keeps failing",
    "details": "Stock sync to the eBay store fails every night.",
    "owner_quote": "Please tell your team the eBay sync keeps failing.",
    "technical_details": None,
    "status": "open",
    "created_at": "2026-10-13T12:00:00Z",
    "updated_at": "2026-10-13T12:00:00Z",
    "resolved_at": None,
    "team_comment": None,
    "note": "Passed to the SellerClaw team.",
}


@pytest.fixture
def env_pointing_at_fake_api(
    monkeypatch: pytest.MonkeyPatch,
    fake_api_url: str,
    fake_token: str,
) -> None:
    monkeypatch.setenv("SELLERCLAW_API_URL", fake_api_url)
    monkeypatch.setenv("SELLERCLAW_TOKEN", fake_token)


@respx.mock
def test_a_request_is_filed_as_written(
    env_pointing_at_fake_api: None,  # noqa: ARG001
    fake_api_url: str,
) -> None:
    body = {
        "kind": "bug",
        "raised_by": "owner",
        "title": "eBay sync keeps failing",
        "details": "Stock sync to the eBay store fails every night.",
        "owner_quote": "Please tell your team the eBay sync keeps failing.",
        "technical_details": "ebay-listings sync -> 502",
    }
    route = respx.post(f"{fake_api_url}/agent/support-requests").mock(
        return_value=httpx.Response(201, json=_REQUEST_JSON)
    )

    result = runner.invoke(app, ["support-requests", "create", "-b", json.dumps(body)])

    assert result.exit_code == 0, result.stderr
    assert json.loads(route.calls.last.request.content) == body
    assert json.loads(result.stdout)["data"]["id"] == REQUEST_ID


@pytest.mark.parametrize(
    ("body", "named"),
    [
        pytest.param(
            {"kind": "complaint", "raised_by": "owner", "title": "t", "details": "d", "owner_quote": "q"},
            "kind",
            id="kind-outside-the-five",
        ),
        pytest.param(
            {"kind": "bug", "raised_by": "support", "title": "t", "details": "d"},
            "raised_by",
            id="raised-by-outside-the-two",
        ),
        pytest.param({"kind": "bug", "raised_by": "agent", "title": "t"}, "details", id="details-missing"),
    ],
)
def test_a_request_the_api_would_refuse_is_refused_before_the_request(
    env_pointing_at_fake_api: None,  # noqa: ARG001
    body: dict[str, object],
    named: str,
) -> None:
    result = runner.invoke(app, ["support-requests", "create", "-b", json.dumps(body)])

    assert result.exit_code != 0
    assert named in result.stderr


@respx.mock
def test_requests_are_listed_by_status_and_read_one_by_one(
    env_pointing_at_fake_api: None,  # noqa: ARG001
    fake_api_url: str,
) -> None:
    listed = respx.get(f"{fake_api_url}/agent/support-requests").mock(
        return_value=httpx.Response(200, json={"requests": [_REQUEST_JSON]})
    )
    one = respx.get(f"{fake_api_url}/agent/support-requests/{REQUEST_ID}").mock(
        return_value=httpx.Response(200, json=_REQUEST_JSON)
    )

    listing = runner.invoke(app, ["support-requests", "list", "--status", "resolved", "--limit", "5"])
    reading = runner.invoke(app, ["support-requests", "get", REQUEST_ID])

    assert listing.exit_code == 0, listing.stderr
    assert dict(listed.calls.last.request.url.params) == {"status": "resolved", "limit": "5"}
    assert json.loads(listing.stdout)["data"]["requests"][0]["id"] == REQUEST_ID
    assert reading.exit_code == 0, reading.stderr
    assert one.call_count == 1


@respx.mock
def test_the_daily_limit_reaches_the_caller_with_its_code(
    env_pointing_at_fake_api: None,  # noqa: ARG001
    fake_api_url: str,
) -> None:
    respx.post(f"{fake_api_url}/agent/support-requests").mock(
        return_value=httpx.Response(
            429,
            json={
                "detail": {
                    "code": "support_request_daily_limit",
                    "message": "This account has sent the daily maximum of requests to the SellerClaw team.",
                }
            },
        )
    )
    body = {"kind": "other", "raised_by": "agent", "title": "t", "details": "d"}

    result = runner.invoke(app, ["support-requests", "create", "-b", json.dumps(body)])

    assert result.exit_code != 0
    assert "support_request_daily_limit" in result.stderr


def test_connectors_do_not_see_support_requests_yet() -> None:
    """Owner's decision: for now only our own agent passes requests to the team."""
    assert "support-requests" not in MCP_VISIBLE_GROUPS
