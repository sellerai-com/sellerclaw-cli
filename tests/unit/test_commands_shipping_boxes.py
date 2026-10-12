"""The seller's shipping boxes: the size and own weight of every parcel, named by products and listings."""

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

BOX_ID = "55555555-5555-4555-8555-555555555555"

_BOX_JSON = {
    "id": BOX_ID,
    "name": "Small mailer",
    "length_mm": 300,
    "width_mm": 200,
    "height_mm": 100,
    "weight_grams": 120,
    "is_default": True,
    "created_at": "2026-10-12T00:00:00Z",
    "updated_at": "2026-10-12T00:00:00Z",
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
def test_a_box_is_created_with_its_sides_and_own_weight(
    env_pointing_at_fake_api: None,  # noqa: ARG001
    fake_api_url: str,
) -> None:
    body = {"name": "Small mailer", "length_mm": 300, "width_mm": 200, "height_mm": 100, "weight_grams": 120}
    route = respx.post(f"{fake_api_url}/agent/shipping-boxes").mock(
        return_value=httpx.Response(201, json=_BOX_JSON)
    )

    result = runner.invoke(app, ["shipping-boxes", "create", "-b", json.dumps(body)])

    assert result.exit_code == 0, result.stderr
    assert json.loads(route.calls.last.request.content) == body
    assert json.loads(result.stdout)["data"]["id"] == BOX_ID


@pytest.mark.parametrize(
    ("body", "named"),
    [
        pytest.param(
            {"name": "Small mailer", "length_mm": 300, "width_mm": 200},
            "height_mm",
            id="a-side-missing",
        ),
        pytest.param(
            {"name": "Small mailer", "length_mm": 300, "width_mm": 200, "height_mm": "10cm"},
            "height_mm: expected integer",
            id="a-side-not-a-number",
        ),
        pytest.param(
            {"name": "Small mailer", "length_mm": 300, "width_mm": 200, "height_mm": 100, "depth_mm": 5},
            "depth_mm",
            id="an-unknown-field",
        ),
    ],
)
def test_a_box_the_api_would_refuse_is_refused_before_the_request(
    env_pointing_at_fake_api: None,  # noqa: ARG001
    body: dict[str, object],
    named: str,
) -> None:
    result = runner.invoke(app, ["shipping-boxes", "create", "-b", json.dumps(body)])

    assert result.exit_code != 0
    assert named in result.stderr


@respx.mock
def test_a_box_own_weight_is_cleared_with_null(
    env_pointing_at_fake_api: None,  # noqa: ARG001
    fake_api_url: str,
) -> None:
    """``null`` is the one way to say "the box's weight is unknown" — it must reach the API as sent."""
    route = respx.patch(f"{fake_api_url}/agent/shipping-boxes/{BOX_ID}").mock(
        return_value=httpx.Response(200, json={**_BOX_JSON, "weight_grams": None})
    )

    result = runner.invoke(
        app, ["shipping-boxes", "update", BOX_ID, "-b", '{"weight_grams": null, "is_default": false}']
    )

    assert result.exit_code == 0, result.stderr
    assert json.loads(route.calls.last.request.content) == {"weight_grams": None, "is_default": False}


@respx.mock
def test_boxes_are_listed_and_deleted_by_id(
    env_pointing_at_fake_api: None,  # noqa: ARG001
    fake_api_url: str,
) -> None:
    listed = respx.get(f"{fake_api_url}/agent/shipping-boxes").mock(
        return_value=httpx.Response(200, json={"items": [_BOX_JSON]})
    )
    deleted = respx.delete(f"{fake_api_url}/agent/shipping-boxes/{BOX_ID}").mock(
        return_value=httpx.Response(204)
    )

    listing = runner.invoke(app, ["shipping-boxes", "list"])
    deletion = runner.invoke(app, ["shipping-boxes", "delete", BOX_ID])

    assert listing.exit_code == 0, listing.stderr
    assert json.loads(listing.stdout)["data"]["items"][0]["id"] == BOX_ID
    assert deletion.exit_code == 0, deletion.stderr
    assert listed.call_count == 1
    assert deleted.call_count == 1


@respx.mock
def test_a_box_still_in_use_reaches_the_caller_with_its_counts(
    env_pointing_at_fake_api: None,  # noqa: ARG001
    fake_api_url: str,
) -> None:
    respx.delete(f"{fake_api_url}/agent/shipping-boxes/{BOX_ID}").mock(
        return_value=httpx.Response(
            409,
            json={
                "detail": {
                    "code": "shipping_box_in_use",
                    "message": "This box is used by 3 product(s) and 5 listing(s). Move them to another box first.",
                    "products": 3,
                    "listings": 5,
                }
            },
        )
    )

    result = runner.invoke(app, ["shipping-boxes", "delete", BOX_ID])

    assert result.exit_code != 0
    assert "shipping_box_in_use" in result.stderr
    assert "3 product(s) and 5 listing(s)" in result.stderr


def test_an_owner_on_mcp_can_manage_their_boxes() -> None:
    """Boxes are part of running the business, so the MCP face shows them like the catalog."""
    assert "shipping-boxes" in MCP_VISIBLE_GROUPS
