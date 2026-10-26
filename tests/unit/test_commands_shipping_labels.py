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


ADDRESS_ID = "5d5d5d5d-0000-4000-8000-000000000002"


@respx.mock
def test_quote_ships_from_the_sender_address_named(
    env_pointing_at_fake_api: None,  # noqa: ARG001
    fake_api_url: str,
) -> None:
    route = respx.post(f"{fake_api_url}/agent/orders/{ORDER_PATH}/shipping-label/quote").mock(
        return_value=httpx.Response(200, json={"rates": []})
    )

    result = runner.invoke(
        app, ["shipping-labels", "quote", ORDER, "-b", json.dumps({"sender_address_id": ADDRESS_ID})]
    )

    assert result.exit_code == 0, result.stderr
    assert json.loads(route.calls.last.request.content) == {"sender_address_id": ADDRESS_ID}


@respx.mock
def test_sender_addresses_are_listed_added_finished_made_default_and_removed(
    env_pointing_at_fake_api: None,  # noqa: ARG001
    fake_api_url: str,
) -> None:
    base = f"{fake_api_url}/agent/shipping/sender-addresses"
    listed = respx.get(base).mock(
        return_value=httpx.Response(200, json={"addresses": [{"id": ADDRESS_ID, "missing": ["phone"]}], "ready": False})
    )
    added = respx.post(base).mock(return_value=httpx.Response(201, json={"id": "new"}))
    finished = respx.patch(f"{base}/{ADDRESS_ID}").mock(return_value=httpx.Response(200, json={"missing": []}))
    made_default = respx.post(f"{base}/{ADDRESS_ID}/default").mock(
        return_value=httpx.Response(200, json={"is_default": True})
    )
    removed = respx.delete(f"{base}/{ADDRESS_ID}").mock(return_value=httpx.Response(204))
    warehouse = {"warehouse_id": "7e7e7e7e-0000-4000-8000-000000000003", "phone": "+1 718 555 0100"}

    results = [
        runner.invoke(app, ["shipping-labels", "list-addresses"]),
        runner.invoke(app, ["shipping-labels", "add-address", "-b", json.dumps({**warehouse, "make_default": True})]),
        runner.invoke(app, ["shipping-labels", "update-address", ADDRESS_ID, "-b", json.dumps({"phone": "555"})]),
        runner.invoke(app, ["shipping-labels", "set-default-address", ADDRESS_ID]),
        runner.invoke(app, ["shipping-labels", "remove-address", ADDRESS_ID]),
    ]

    assert [result.exit_code for result in results] == [0] * 5, [result.stderr for result in results]
    assert json.loads(results[0].stdout)["data"]["ready"] is False
    assert json.loads(added.calls.last.request.content) == {**warehouse, "make_default": True}
    assert json.loads(finished.calls.last.request.content) == {"phone": "555"}
    assert (listed.call_count, made_default.call_count, removed.call_count) == (1, 1, 1)


def test_an_address_field_the_api_does_not_take_is_refused_before_sending(
    env_pointing_at_fake_api: None,  # noqa: ARG001
) -> None:
    result = runner.invoke(
        app, ["shipping-labels", "update-address", ADDRESS_ID, "-b", json.dumps({"postcode": "11201"})]
    )

    assert result.exit_code != 0
    assert "postcode" in (result.stderr or result.stdout)


@respx.mock
def test_the_carriers_the_owner_named_are_saved_without_the_profile(
    env_pointing_at_fake_api: None,  # noqa: ARG001
    fake_api_url: str,
) -> None:
    saved = respx.put(f"{fake_api_url}/agent/shipping/sender").mock(
        return_value=httpx.Response(200, json={"couriers": [{"id": "ups-1", "name": "UPS", "enabled": True}]})
    )

    result = runner.invoke(
        app, ["shipping-labels", "update-sender", "-b", json.dumps({"enabled_couriers": ["ups-1"]})]
    )

    assert result.exit_code == 0, result.stderr
    assert json.loads(saved.calls.last.request.content) == {"enabled_couriers": ["ups-1"]}


@respx.mock
def test_the_label_format_is_saved_without_a_name(
    env_pointing_at_fake_api: None,  # noqa: ARG001
    fake_api_url: str,
) -> None:
    saved = respx.put(f"{fake_api_url}/agent/shipping/sender").mock(
        return_value=httpx.Response(200, json={"label_file_type": "ZPLII"})
    )

    result = runner.invoke(app, ["shipping-labels", "update-sender", "-b", json.dumps({"label_file_type": "ZPLII"})])

    assert result.exit_code == 0, result.stderr
    assert json.loads(saved.calls.last.request.content) == {"label_file_type": "ZPLII"}
