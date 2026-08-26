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


# --- The shop itself -------------------------------------------------------------------------


@respx.mock
def test_update_patches_name_and_markup(
    env_pointing_at_fake_api: None,  # noqa: ARG001
    fake_api_url: str,
) -> None:
    route = respx.patch(f"{fake_api_url}/agent/sellercart").mock(
        return_value=httpx.Response(200, json={"name": "Acme Gear", "markup_percent": 45})
    )

    result = runner.invoke(
        app,
        ["sellercart", "update", "-b", json.dumps({"name": "Acme Gear", "markup_percent": 45})],
    )

    assert result.exit_code == 0, result.stderr
    assert json.loads(route.calls.last.request.content) == {
        "name": "Acme Gear",
        "markup_percent": 45,
    }


@respx.mock
def test_create_sets_the_language_the_shop_speaks(
    env_pointing_at_fake_api: None,  # noqa: ARG001
    fake_api_url: str,
) -> None:
    """A shop born without a language is born English, whatever its seller writes in."""
    route = respx.post(f"{fake_api_url}/agent/sellercart").mock(
        return_value=httpx.Response(200, json={"slug": "komok", "language": "ru"})
    )

    result = runner.invoke(
        app,
        [
            "sellercart",
            "create",
            "-b",
            json.dumps({"name": "Комокъ", "slug": "komok", "currency": "RUB", "language": "ru"}),
        ],
    )

    assert result.exit_code == 0, result.stderr
    assert json.loads(route.calls.last.request.content) == {
        "name": "Комокъ",
        "slug": "komok",
        "currency": "RUB",
        "language": "ru",
    }


@respx.mock
def test_update_switches_the_language_the_shop_speaks(
    env_pointing_at_fake_api: None,  # noqa: ARG001
    fake_api_url: str,
) -> None:
    """The one field that fixes a Russian shop greeting its buyers in English."""
    route = respx.patch(f"{fake_api_url}/agent/sellercart").mock(
        return_value=httpx.Response(200, json={"language": "ru"})
    )

    result = runner.invoke(app, ["sellercart", "update", "-b", json.dumps({"language": "ru"})])

    assert result.exit_code == 0, result.stderr
    assert json.loads(route.calls.last.request.content) == {"language": "ru"}


@pytest.mark.parametrize(
    "command",
    [
        pytest.param("create", id="create"),
        pytest.param("update", id="update"),
    ],
)
def test_the_shop_language_is_offered_on_both_paths(command: str) -> None:
    """A field the API takes but this surface omits is a field the agent cannot reach at all."""
    detail = _data(runner.invoke(app, ["describe", "sellercart", command]).stdout)

    assert "language" in {f["field"] for f in detail["body_fields"]}


@respx.mock
def test_update_turns_the_shop_into_a_catalog(
    env_pointing_at_fake_api: None,  # noqa: ARG001
    fake_api_url: str,
) -> None:
    """A shop with no checkout is a shape the seller chooses, so the agent can set it."""
    route = respx.patch(f"{fake_api_url}/agent/sellercart").mock(
        return_value=httpx.Response(200, json={"sells_online": False})
    )
    body = {
        "sells_online": False,
        "product_cta_label": "Ask about this",
        "product_cta_href": "/contacts",
    }

    result = runner.invoke(app, ["sellercart", "update", "-b", json.dumps(body)])

    assert result.exit_code == 0, result.stderr
    assert json.loads(route.calls.last.request.content) == body


@respx.mock
def test_the_product_button_can_be_cleared(
    env_pointing_at_fake_api: None,  # noqa: ARG001
    fake_api_url: str,
) -> None:
    """Empty strings must survive the trip — dropping them would mean "leave the button alone"."""
    route = respx.patch(f"{fake_api_url}/agent/sellercart").mock(
        return_value=httpx.Response(200, json={"product_cta_label": None})
    )

    result = runner.invoke(
        app,
        [
            "sellercart",
            "update",
            "-b",
            json.dumps({"product_cta_label": "", "product_cta_href": ""}),
        ],
    )

    assert result.exit_code == 0, result.stderr
    assert json.loads(route.calls.last.request.content) == {
        "product_cta_label": "",
        "product_cta_href": "",
    }


@respx.mock
def test_unpublish_takes_the_shop_off_the_air(
    env_pointing_at_fake_api: None,  # noqa: ARG001
    fake_api_url: str,
) -> None:
    route = respx.post(f"{fake_api_url}/agent/sellercart/unpublish").mock(
        return_value=httpx.Response(200, json={"status": "draft"})
    )

    result = runner.invoke(app, ["sellercart", "unpublish"])

    assert result.exit_code == 0, result.stderr
    assert route.call_count == 1


@respx.mock
def test_check_slug_sends_the_address_as_a_query(
    env_pointing_at_fake_api: None,  # noqa: ARG001
    fake_api_url: str,
) -> None:
    route = respx.get(f"{fake_api_url}/agent/sellercart/slug-check").mock(
        return_value=httpx.Response(
            200, json={"slug": "acme-gear", "available": True, "host": "acme-gear.sellercart.shop"}
        )
    )

    result = runner.invoke(app, ["sellercart", "check-slug", "--slug", "acme-gear"])

    assert result.exit_code == 0, result.stderr
    assert route.calls.last.request.url.params["slug"] == "acme-gear"


def test_check_slug_without_an_address_is_refused_locally(
    env_pointing_at_fake_api: None,  # noqa: ARG001
) -> None:
    """A required flag is caught here rather than as a 422 the agent has to interpret."""
    result = runner.invoke(app, ["sellercart", "check-slug"])

    assert result.exit_code != 0


@respx.mock
def test_preview_mints_the_secret_link(
    env_pointing_at_fake_api: None,  # noqa: ARG001
    fake_api_url: str,
) -> None:
    route = respx.post(f"{fake_api_url}/agent/sellercart/preview").mock(
        return_value=httpx.Response(
            200, json={"origin": "https://acme.sellercart.shop", "token": "s3cr3t"}
        )
    )

    result = runner.invoke(app, ["sellercart", "preview"])

    assert result.exit_code == 0, result.stderr
    assert route.call_count == 1
    assert "s3cr3t" in result.stdout


# --- Theme -----------------------------------------------------------------------------------


@respx.mock
def test_theme_accepts_the_full_token_set(
    env_pointing_at_fake_api: None,  # noqa: ARG001
    fake_api_url: str,
) -> None:
    """The tokens that make a shop look designed — headings, surface, ink, accent, its own CSS."""
    route = respx.patch(f"{fake_api_url}/agent/sellercart/theme").mock(
        return_value=httpx.Response(200, json={"theme": {}})
    )
    body = {
        "primary": "#1f4d3a",
        "accent": "#b08d57",
        "background": "#faf6ee",
        "ink": "#231f1c",
        "font": "Manrope",
        "heading_font": "Cormorant Garamond",
        "custom_css": ".sc-hero { letter-spacing: -0.02em; }",
    }

    result = runner.invoke(app, ["sellercart", "theme", "-b", json.dumps(body)])

    assert result.exit_code == 0, result.stderr
    assert json.loads(route.calls.last.request.content) == body


@respx.mock
def test_theme_clears_a_token_with_an_empty_string(
    env_pointing_at_fake_api: None,  # noqa: ARG001
    fake_api_url: str,
) -> None:
    """Clearing has to reach the API as an empty string — dropping it would mean "leave as is"."""
    route = respx.patch(f"{fake_api_url}/agent/sellercart/theme").mock(
        return_value=httpx.Response(200, json={"theme": {}})
    )

    result = runner.invoke(
        app, ["sellercart", "theme", "-b", json.dumps({"heading_font": "", "custom_css": ""})]
    )

    assert result.exit_code == 0, result.stderr
    assert json.loads(route.calls.last.request.content) == {"heading_font": "", "custom_css": ""}


def test_an_unavailable_typeface_is_refused_before_the_call(
    env_pointing_at_fake_api: None,  # noqa: ARG001
) -> None:
    """Every typeface becomes a font request from the buyer's browser, so the list is closed."""
    result = runner.invoke(
        app, ["sellercart", "theme", "-b", json.dumps({"font": "Comic Sans MS"})]
    )

    assert result.exit_code != 0
    assert "Manrope" in (result.stderr or result.stdout)


def test_describe_says_which_theme_tokens_can_be_cleared() -> None:
    """A caller that cannot see the way back assumes there is none, and leaves the token set."""
    detail = _data(runner.invoke(app, ["describe", "sellercart", "theme"]).stdout)

    fields = {f["field"]: f for f in detail["body_fields"]}
    assert fields["heading_font"]["clearable"] is True
    assert fields["custom_css"]["clearable"] is True
    assert "clearable" not in fields["primary"]  # not clearable: a shop always has a brand colour


@respx.mock
def test_apply_preset_posts_the_preset_id(
    env_pointing_at_fake_api: None,  # noqa: ARG001
    fake_api_url: str,
) -> None:
    route = respx.post(f"{fake_api_url}/agent/sellercart/presets/apply").mock(
        return_value=httpx.Response(200, json={"theme": {"preset": "boutique"}})
    )

    result = runner.invoke(
        app, ["sellercart", "apply-preset", "-b", json.dumps({"preset": "boutique"})]
    )

    assert result.exit_code == 0, result.stderr
    assert json.loads(route.calls.last.request.content) == {"preset": "boutique"}


# --- Payments --------------------------------------------------------------------------------


@respx.mock
def test_payouts_status_reads_whether_the_shop_can_sell(
    env_pointing_at_fake_api: None,  # noqa: ARG001
    fake_api_url: str,
) -> None:
    route = respx.get(f"{fake_api_url}/agent/sellercart/payouts").mock(
        return_value=httpx.Response(
            200, json={"connected": False, "can_accept_orders": False, "shipping_amount": None}
        )
    )

    result = runner.invoke(app, ["sellercart-payouts", "status"])

    assert result.exit_code == 0, result.stderr
    assert route.call_count == 1


def test_connecting_stripe_without_a_country_is_refused_locally() -> None:
    """The API defaults to US. A German seller handed a US account starts over, so the agent asks."""
    result = runner.invoke(app, ["sellercart-payouts", "connect", "-b", json.dumps({})])

    assert result.exit_code != 0
    assert "country" in (result.stderr or result.stdout)


def test_money_is_a_number_across_the_shop_commands() -> None:
    """One shape for money everywhere, so an agent that learned one command can write the next.

    Prices on the shelf sit inside an object and are never type-checked locally, so the two commands
    can only agree by saying the same thing — hence the assertion on what the caller is told.
    """
    delivery = _data(runner.invoke(app, ["describe", "sellercart-payouts", "delivery"]).stdout)
    shipping = {f["field"]: f for f in delivery["body_fields"]}["shipping_amount"]
    assert shipping["type"] == "float"

    products = _data(runner.invoke(app, ["describe", "sellercart-products", "add"]).stdout)
    prices = {f["field"]: f for f in products["body_fields"]}["prices"]
    assert "Plain numbers" in prices["help"]


def test_a_quoted_price_is_refused_with_the_shape_to_use(
    env_pointing_at_fake_api: None,  # noqa: ARG001
) -> None:
    """The wrong guess costs one turn, not a silent 422 the agent has to decode."""
    result = runner.invoke(
        app,
        [
            "sellercart-payouts",
            "delivery",
            "-b",
            json.dumps({"shipping_amount": "5.99", "shipping_countries": ["US"]}),
        ],
    )

    assert result.exit_code != 0
    message = result.stderr or result.stdout
    assert "shipping_amount" in message
    assert "number" in message


@respx.mock
def test_delivery_sends_price_and_countries(
    env_pointing_at_fake_api: None,  # noqa: ARG001
    fake_api_url: str,
) -> None:
    route = respx.put(f"{fake_api_url}/agent/sellercart/payouts/delivery").mock(
        return_value=httpx.Response(200, json={"can_accept_orders": True})
    )

    result = runner.invoke(
        app,
        [
            "sellercart-payouts",
            "delivery",
            "-b",
            json.dumps({"shipping_amount": 5.99, "shipping_countries": ["US", "CA"]}),
        ],
    )

    assert result.exit_code == 0, result.stderr
    assert json.loads(route.calls.last.request.content) == {
        "shipping_amount": 5.99,
        "shipping_countries": ["US", "CA"],
    }


def test_delivery_without_a_price_is_refused_locally(
    env_pointing_at_fake_api: None,  # noqa: ARG001
) -> None:
    """"Free" and "unanswered" are different states, so the price cannot simply be left out."""
    result = runner.invoke(
        app,
        ["sellercart-payouts", "delivery", "-b", json.dumps({"shipping_countries": ["US"]})],
    )

    assert result.exit_code != 0
    assert "shipping_amount" in (result.stderr or result.stdout)


@respx.mock
def test_tax_switch_sends_a_boolean(
    env_pointing_at_fake_api: None,  # noqa: ARG001
    fake_api_url: str,
) -> None:
    route = respx.put(f"{fake_api_url}/agent/sellercart/payouts/tax").mock(
        return_value=httpx.Response(200, json={"tax_enabled": True})
    )

    result = runner.invoke(
        app, ["sellercart-payouts", "tax", "-b", json.dumps({"enabled": True})]
    )

    assert result.exit_code == 0, result.stderr
    assert json.loads(route.calls.last.request.content) == {"enabled": True}


# --- Custom domain ---------------------------------------------------------------------------


@respx.mock
def test_domain_connect_returns_the_dns_record_to_read_out(
    env_pointing_at_fake_api: None,  # noqa: ARG001
    fake_api_url: str,
) -> None:
    route = respx.post(f"{fake_api_url}/agent/sellercart/domain").mock(
        return_value=httpx.Response(
            201,
            json={
                "available": True,
                "domain": {
                    "hostname": "shop.example.com",
                    "status": "pending_dns",
                    "dns_records": [
                        {"name": "shop.example.com", "type": "CNAME", "value": "edge.sellercart.shop"}
                    ],
                },
            },
        )
    )

    result = runner.invoke(
        app,
        ["sellercart-domain", "connect", "-b", json.dumps({"hostname": "shop.example.com"})],
    )

    assert result.exit_code == 0, result.stderr
    assert json.loads(route.calls.last.request.content) == {"hostname": "shop.example.com"}
    assert "edge.sellercart.shop" in result.stdout


@respx.mock
def test_domain_check_forces_a_recheck(
    env_pointing_at_fake_api: None,  # noqa: ARG001
    fake_api_url: str,
) -> None:
    route = respx.post(f"{fake_api_url}/agent/sellercart/domain/check").mock(
        return_value=httpx.Response(200, json={"available": True, "domain": {"status": "active"}})
    )

    result = runner.invoke(app, ["sellercart-domain", "check"])

    assert result.exit_code == 0, result.stderr
    assert route.call_count == 1


@respx.mock
def test_domain_disconnect_deletes_it(
    env_pointing_at_fake_api: None,  # noqa: ARG001
    fake_api_url: str,
) -> None:
    route = respx.delete(f"{fake_api_url}/agent/sellercart/domain").mock(
        return_value=httpx.Response(204)
    )

    result = runner.invoke(app, ["sellercart-domain", "disconnect"])

    assert result.exit_code == 0, result.stderr
    assert route.call_count == 1


# --- Images ----------------------------------------------------------------------------------


@respx.mock
def test_media_delete_takes_the_image_id_as_a_positional(
    env_pointing_at_fake_api: None,  # noqa: ARG001
    fake_api_url: str,
) -> None:
    media_id = "1b8f0a4e-0000-4000-8000-000000000001"
    route = respx.delete(f"{fake_api_url}/agent/sellercart/media/{media_id}").mock(
        return_value=httpx.Response(204)
    )

    result = runner.invoke(app, ["sellercart-media", "delete", media_id])

    assert result.exit_code == 0, result.stderr
    assert route.call_count == 1
