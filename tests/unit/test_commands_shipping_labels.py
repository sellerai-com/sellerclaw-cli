from __future__ import annotations

import json

import httpx
import pytest
import respx
from typer.testing import CliRunner

from sellerclaw_cli.cli import app

pytestmark = pytest.mark.unit

runner = CliRunner()

ORDER = "#1042"
ORDER_PATH = "%231042"


@pytest.fixture
def env_pointing_at_fake_api(
    monkeypatch: pytest.MonkeyPatch,
    fake_api_url: str,
    fake_token: str,
) -> None:
    monkeypatch.setenv("SELLERCLAW_API_URL", fake_api_url)
    monkeypatch.setenv("SELLERCLAW_TOKEN", fake_token)


@respx.mock
def test_quote_with_no_body_asks_for_the_label_as_drafted(
    env_pointing_at_fake_api: None,  # noqa: ARG001
    fake_api_url: str,
) -> None:
    route = respx.post(f"{fake_api_url}/agent/orders/{ORDER_PATH}/shipping-label/quote").mock(
        return_value=httpx.Response(200, json={"rates": [{"rate_id": "r1", "title": "UPS Ground"}]})
    )

    result = runner.invoke(app, ["shipping-labels", "quote", ORDER])

    assert result.exit_code == 0, result.stderr
    assert route.call_count == 1
    assert json.loads(result.stdout)["data"]["rates"][0]["rate_id"] == "r1"


@respx.mock
def test_quote_sends_only_what_to_change(
    env_pointing_at_fake_api: None,  # noqa: ARG001
    fake_api_url: str,
) -> None:
    route = respx.post(f"{fake_api_url}/agent/orders/{ORDER_PATH}/shipping-label/quote").mock(
        return_value=httpx.Response(200, json={"rates": []})
    )
    change = {"parcel": {"weight_grams": 1250}, "signature": "ADULT"}

    result = runner.invoke(app, ["shipping-labels", "quote", ORDER, "-b", json.dumps(change)])

    assert result.exit_code == 0, result.stderr
    assert json.loads(route.calls.last.request.content) == change


def test_quote_refuses_a_signature_carriers_do_not_offer(
    env_pointing_at_fake_api: None,  # noqa: ARG001
) -> None:
    result = runner.invoke(
        app, ["shipping-labels", "quote", ORDER, "-b", json.dumps({"signature": "NOTARY"})]
    )

    assert result.exit_code != 0
    assert "signature" in (result.stderr or result.stdout)


@respx.mock
def test_buy_asks_the_owner_by_the_rate(
    env_pointing_at_fake_api: None,  # noqa: ARG001
    fake_api_url: str,
) -> None:
    route = respx.post(f"{fake_api_url}/agent/orders/{ORDER_PATH}/shipping-label").mock(
        return_value=httpx.Response(
            202,
            json={
                "status": "pending_approval",
                "action_request_id": "1b1b1b1b-0000-4000-8000-000000000001",
                "change": {"order": "#1042", "label": "UPS Ground", "price": "12.40 USD"},
                "message": "Sent to the owner for approval.",
            },
        )
    )

    result = runner.invoke(
        app,
        ["shipping-labels", "buy", ORDER, "-b", json.dumps({"rate_id": "r1", "label_file_type": "ZPLII"})],
    )

    assert result.exit_code == 0, result.stderr
    assert json.loads(route.calls.last.request.content) == {"rate_id": "r1", "label_file_type": "ZPLII"}
    assert json.loads(result.stdout)["data"]["status"] == "pending_approval"


def test_buy_needs_a_rate(
    env_pointing_at_fake_api: None,  # noqa: ARG001
) -> None:
    result = runner.invoke(app, ["shipping-labels", "buy", ORDER, "-b", "{}"])

    assert result.exit_code != 0
    assert "rate_id" in (result.stderr or result.stdout)


@respx.mock
def test_the_sender_is_read_and_saved(
    env_pointing_at_fake_api: None,  # noqa: ARG001
    fake_api_url: str,
) -> None:
    read = respx.get(f"{fake_api_url}/agent/shipping/sender").mock(
        return_value=httpx.Response(200, json={"profile": None, "suggestion": {"name": "Kim"}})
    )
    saved = respx.put(f"{fake_api_url}/agent/shipping/sender").mock(
        return_value=httpx.Response(200, json={"name": "Nest Supply Co."})
    )

    got = runner.invoke(app, ["shipping-labels", "get-sender"])
    put = runner.invoke(
        app,
        ["shipping-labels", "update-sender", "-b", json.dumps({"name": "Nest Supply Co.", "email": "a@b.co"})],
    )

    assert got.exit_code == 0, got.stderr
    assert put.exit_code == 0, put.stderr
    assert read.call_count == 1
    assert json.loads(saved.calls.last.request.content) == {"name": "Nest Supply Co.", "email": "a@b.co"}
