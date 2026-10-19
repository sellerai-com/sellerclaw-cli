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


@pytest.mark.parametrize(
    "extra",
    [
        pytest.param({"sells_online": False}, id="a-catalog-the-owner-asked-for"),
        pytest.param(
            {"source_store_id": "3f1c2a9e-5b7d-4c8e-9a10-6d2b4e8f7c31"},
            id="started-from-an-amazon-store",
        ),
    ],
)
@respx.mock
def test_create_sends_how_the_shop_starts(
    env_pointing_at_fake_api: None,  # noqa: ARG001
    fake_api_url: str,
    extra: dict[str, Any],
) -> None:
    """Both were refused before they reached the API: the body is checked against its fields."""
    route = respx.post(f"{fake_api_url}/agent/sellercart").mock(
        return_value=httpx.Response(200, json={"slug": "mossmere"})
    )
    body = {"name": "Mossmere", "slug": "mossmere", "currency": "USD", **extra}

    result = runner.invoke(app, ["sellercart", "create", "-b", json.dumps(body)])

    assert result.exit_code == 0, result.stderr
    assert json.loads(route.calls.last.request.content) == body


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


@pytest.mark.parametrize(
    "command",
    [
        pytest.param("create", id="create"),
        pytest.param("update", id="update"),
    ],
)
def test_extra_display_currencies_are_offered_on_both_paths(command: str) -> None:
    """The strict body check refuses a key it does not know, so an unlisted field is one the agent
    is told to send and then cannot."""
    detail = _data(runner.invoke(app, ["describe", "sellercart", command]).stdout)

    fields = {f["field"]: f for f in detail["body_fields"]}
    assert fields["display_currencies"]["repeatable"] is True


@respx.mock
def test_update_sends_the_whole_list_of_extra_currencies(
    env_pointing_at_fake_api: None,  # noqa: ARG001
    fake_api_url: str,
) -> None:
    """The list replaces what the shop has, so it travels as the list — including an empty one."""
    route = respx.patch(f"{fake_api_url}/agent/sellercart").mock(
        return_value=httpx.Response(200, json={"display_currencies": ["EUR", "GBP"]})
    )

    for body in ({"display_currencies": ["EUR", "GBP"]}, {"display_currencies": []}):
        result = runner.invoke(app, ["sellercart", "update", "-b", json.dumps(body)])

        assert result.exit_code == 0, result.stderr
        assert json.loads(route.calls.last.request.content) == body


def test_update_offers_adding_and_removing_one_currency() -> None:
    """The whole-list field replaces; these change the list the shop has, so asking to add one
    currency cannot cost the owner the others."""
    detail = _data(runner.invoke(app, ["describe", "sellercart", "update"]).stdout)

    fields = {f["field"]: f for f in detail["body_fields"]}
    assert fields["add_display_currencies"]["repeatable"] is True
    assert fields["remove_display_currencies"]["repeatable"] is True


@respx.mock
def test_update_sends_currency_additions_and_removals_as_given(
    env_pointing_at_fake_api: None,  # noqa: ARG001
    fake_api_url: str,
) -> None:
    route = respx.patch(f"{fake_api_url}/agent/sellercart").mock(
        return_value=httpx.Response(200, json={"display_currencies": ["EUR", "JPY"]})
    )
    body = {"add_display_currencies": ["JPY"], "remove_display_currencies": ["GBP"]}

    result = runner.invoke(app, ["sellercart", "update", "-b", json.dumps(body)])

    assert result.exit_code == 0, result.stderr
    assert json.loads(route.calls.last.request.content) == body


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
def test_update_shows_sold_out_products(
    env_pointing_at_fake_api: None,  # noqa: ARG001
    fake_api_url: str,
) -> None:
    """Hiding sold-out products is how every shop starts; showing them is the owner's call."""
    route = respx.patch(f"{fake_api_url}/agent/sellercart").mock(
        return_value=httpx.Response(200, json={"show_sold_out": True})
    )
    body = {"show_sold_out": True}

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


@respx.mock
def test_theme_moves_the_currency_switcher(
    env_pointing_at_fake_api: None,  # noqa: ARG001
    fake_api_url: str,
) -> None:
    route = respx.patch(f"{fake_api_url}/agent/sellercart/theme").mock(
        return_value=httpx.Response(200, json={"theme": {"currency_switcher": "product"}})
    )

    result = runner.invoke(
        app, ["sellercart", "theme", "-b", json.dumps({"currency_switcher": "product"})]
    )

    assert result.exit_code == 0, result.stderr
    assert json.loads(route.calls.last.request.content) == {"currency_switcher": "product"}


@respx.mock
def test_a_switcher_place_the_shop_cannot_draw_is_refused_before_the_call(
    env_pointing_at_fake_api: None,  # noqa: ARG001
    fake_api_url: str,
) -> None:
    route = respx.patch(f"{fake_api_url}/agent/sellercart/theme")

    result = runner.invoke(
        app, ["sellercart", "theme", "-b", json.dumps({"currency_switcher": "footer"})]
    )

    assert result.exit_code != 0
    assert "both" in (result.stderr or result.stdout)
    assert route.call_count == 0


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


@respx.mock
def test_layouts_lists_the_ready_made_layouts(
    env_pointing_at_fake_api: None,  # noqa: ARG001
    fake_api_url: str,
) -> None:
    route = respx.get(f"{fake_api_url}/agent/sellercart/layouts").mock(
        return_value=httpx.Response(200, json={"items": [{"id": "gallery", "header": "centered"}]})
    )

    result = runner.invoke(app, ["sellercart", "layouts"])

    assert result.exit_code == 0, result.stderr
    assert route.called
    assert _data(result.stdout)["items"][0]["id"] == "gallery"


@respx.mock
def test_apply_layout_posts_the_layout_id_and_the_note(
    env_pointing_at_fake_api: None,  # noqa: ARG001
    fake_api_url: str,
) -> None:
    route = respx.post(f"{fake_api_url}/agent/sellercart/layouts/apply").mock(
        return_value=httpx.Response(200, json={"theme": {"template": "gallery"}})
    )

    result = runner.invoke(
        app,
        [
            "sellercart",
            "apply-layout",
            "-b",
            json.dumps({"layout": "gallery", "note": "Bigger photos"}),
        ],
    )

    assert result.exit_code == 0, result.stderr
    assert json.loads(route.calls.last.request.content) == {
        "layout": "gallery",
        "note": "Bigger photos",
    }


@respx.mock
def test_apply_layout_without_a_layout_is_refused_before_the_call(
    env_pointing_at_fake_api: None,  # noqa: ARG001
    fake_api_url: str,
) -> None:
    route = respx.post(f"{fake_api_url}/agent/sellercart/layouts/apply")

    result = runner.invoke(app, ["sellercart", "apply-layout", "-b", json.dumps({"note": "x"})])

    assert result.exit_code != 0
    assert "layout" in (result.stderr or result.stdout)
    assert route.call_count == 0


@respx.mock
def test_theme_mixes_one_part_of_a_layout(
    env_pointing_at_fake_api: None,  # noqa: ARG001
    fake_api_url: str,
) -> None:
    route = respx.patch(f"{fake_api_url}/agent/sellercart/theme").mock(
        return_value=httpx.Response(200, json={"theme": {"product_card": "portrait"}})
    )

    result = runner.invoke(
        app, ["sellercart", "theme", "-b", json.dumps({"product_card": "portrait"})]
    )

    assert result.exit_code == 0, result.stderr
    assert json.loads(route.calls.last.request.content) == {"product_card": "portrait"}


@respx.mock
@pytest.mark.parametrize(
    ("field", "value", "a_choice"),
    [
        pytest.param("header", "floating", "centered", id="header"),
        pytest.param("product_card", "huge", "portrait", id="product-card"),
        pytest.param("product_page", "wide", "editorial", id="product-page"),
    ],
)
def test_theme_refuses_a_layout_part_the_shop_cannot_draw(
    env_pointing_at_fake_api: None,  # noqa: ARG001
    fake_api_url: str,
    field: str,
    value: str,
    a_choice: str,
) -> None:
    route = respx.patch(f"{fake_api_url}/agent/sellercart/theme")

    result = runner.invoke(app, ["sellercart", "theme", "-b", json.dumps({field: value})])

    assert result.exit_code != 0
    assert a_choice in (result.stderr or result.stdout)
    assert route.call_count == 0


# --- Payments --------------------------------------------------------------------------------


@respx.mock
def test_payouts_status_reads_whether_the_shop_can_sell(
    env_pointing_at_fake_api: None,  # noqa: ARG001
    fake_api_url: str,
) -> None:
    route = respx.get(f"{fake_api_url}/agent/sellercart/payouts").mock(
        return_value=httpx.Response(
            200, json={"connected": False, "can_accept_orders": False, "delivers": False}
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


@respx.mock
def test_the_shelf_can_be_read_in_its_draft_state(
    env_pointing_at_fake_api: None,  # noqa: ARG001
    fake_api_url: str,
) -> None:
    """Products staged while the shop was a draft are invisible to the default listing.

    Without a way to ask for them the only other answer the caller gets is 'listing already exists'
    from `add` — a contradiction that reads as data loss and invites deleting the rows.
    """
    route = respx.get(f"{fake_api_url}/agent/sellercart/products").mock(
        return_value=httpx.Response(200, json={"items": [], "total": 0})
    )

    result = runner.invoke(app, ["sellercart-products", "list", "--status", "draft"])

    assert result.exit_code == 0, result.stderr or result.stdout
    assert route.calls.last.request.url.params["status"] == "draft"


def test_the_shelf_status_offers_the_states_the_api_knows() -> None:
    """Every other channel's listing command already filters by status; the shop is not special."""
    listing = _data(runner.invoke(app, ["describe", "sellercart-products", "list"]).stdout)
    status_flag = {f["flag"]: f for f in listing["flags"]}["--status"]
    assert set(status_flag["choices"]) == {"published", "draft", "withdrawn", "all"}


@respx.mock
def test_adding_to_the_shelf_carries_the_shops_own_copy(
    env_pointing_at_fake_api: None,  # noqa: ARG001
    fake_api_url: str,
) -> None:
    """The shop's copy travels with the add, so it lands on the listing and not on the catalog."""
    route = respx.post(f"{fake_api_url}/agent/sellercart/products").mock(
        return_value=httpx.Response(200, json={"items": [], "total": 0})
    )
    body = {"products": [{"product_id": "0b1c2d3e-4f50-6172-8394-a5b6c7d8e9f0", "description": "Shop copy"}]}

    result = runner.invoke(app, ["sellercart-products", "add", "-b", json.dumps(body)])

    assert result.exit_code == 0, result.stderr or result.stdout
    assert json.loads(route.calls.last.request.content) == body


def test_money_is_a_number_across_the_shop_commands() -> None:
    """One shape for money everywhere, so an agent that learned one command can write the next.

    Prices on the shelf sit inside an object and are never type-checked locally, so the two commands
    can only agree by saying the same thing — hence the assertion on what the caller is told.
    """
    method = _data(runner.invoke(app, ["describe", "sellercart-delivery", "set-method"]).stdout)
    fields = {f["field"]: f for f in method["body_fields"]}
    assert {fields[name]["type"] for name in ("price", "extra_amount", "extra_percent")} == {"float"}

    products = _data(runner.invoke(app, ["describe", "sellercart-products", "add"]).stdout)
    prices = {f["field"]: f for f in products["body_fields"]}["prices"]
    assert "Plain numbers" in prices["help"]


def test_a_quoted_price_is_refused_with_the_shape_to_use(
    env_pointing_at_fake_api: None,  # noqa: ARG001
) -> None:
    """The wrong guess costs one turn, not a silent 422 the agent has to decode."""
    result = runner.invoke(
        app,
        ["sellercart-delivery", "set-method", "US", "Standard", "-b", json.dumps({"price": "5.99"})],
    )

    assert result.exit_code != 0
    message = result.stderr or result.stdout
    assert "price" in message
    assert "number" in message


@respx.mock
def test_delivery_zones_are_read_whole(
    env_pointing_at_fake_api: None,  # noqa: ARG001
    fake_api_url: str,
) -> None:
    route = respx.get(f"{fake_api_url}/agent/sellercart/delivery").mock(
        return_value=httpx.Response(200, json={"zones": [], "warnings": [], "delivers": False})
    )

    result = runner.invoke(app, ["sellercart-delivery", "list"])

    assert result.exit_code == 0, result.stderr
    assert route.call_count == 1


@respx.mock
def test_a_zone_is_named_in_the_path_and_its_countries_sent_as_they_are(
    env_pointing_at_fake_api: None,  # noqa: ARG001
    fake_api_url: str,
) -> None:
    """A name with a space is a zone name like any other — it reaches the API as one path segment."""
    route = respx.put(f"{fake_api_url}/agent/sellercart/delivery/zones/North%20America").mock(
        return_value=httpx.Response(200, json={"zones": []})
    )

    result = runner.invoke(
        app,
        [
            "sellercart-delivery",
            "set-zone",
            "North America",
            "-b",
            json.dumps({"countries": ["US", "CA"], "free_over": 75}),
        ],
    )

    assert result.exit_code == 0, result.stderr or result.stdout
    assert json.loads(route.calls.last.request.content) == {
        "countries": ["US", "CA"],
        "free_over": 75,
    }


@respx.mock
def test_a_free_delivery_offer_is_withdrawn_with_null(
    env_pointing_at_fake_api: None,  # noqa: ARG001
    fake_api_url: str,
) -> None:
    """null is the request, not an omission — leaving the field out keeps the offer."""
    route = respx.put(f"{fake_api_url}/agent/sellercart/delivery/zones/Europe").mock(
        return_value=httpx.Response(200, json={"zones": []})
    )

    result = runner.invoke(
        app, ["sellercart-delivery", "set-zone", "Europe", "-b", json.dumps({"free_over": None})]
    )

    assert result.exit_code == 0, result.stderr or result.stdout
    assert json.loads(route.calls.last.request.content) == {"free_over": None}


@respx.mock
def test_a_method_is_sent_to_its_zone_with_its_terms(
    env_pointing_at_fake_api: None,  # noqa: ARG001
    fake_api_url: str,
) -> None:
    route = respx.put(f"{fake_api_url}/agent/sellercart/delivery/zones/US/methods/Express").mock(
        return_value=httpx.Response(200, json={"zones": []})
    )
    body = {
        "price": 20,
        "calculated": True,
        "extra_percent": 10,
        "pick": "fastest",
        "days_min": 2,
        "days_max": 4,
    }

    result = runner.invoke(
        app, ["sellercart-delivery", "set-method", "US", "Express", "-b", json.dumps(body)]
    )

    assert result.exit_code == 0, result.stderr or result.stdout
    assert json.loads(route.calls.last.request.content) == body


def test_a_pick_the_api_does_not_know_is_refused_locally(
    env_pointing_at_fake_api: None,  # noqa: ARG001
) -> None:
    result = runner.invoke(
        app,
        ["sellercart-delivery", "set-method", "US", "Express", "-b", json.dumps({"pick": "slowest"})],
    )

    assert result.exit_code != 0
    assert "pick" in (result.stderr or result.stdout)


@pytest.mark.parametrize(
    ("args", "path"),
    [
        pytest.param(["delete-zone", "Europe"], "/zones/Europe", id="a-zone"),
        pytest.param(["delete-method", "Europe", "Express"], "/zones/Europe/methods/Express", id="a-method"),
    ],
)
@respx.mock
def test_zones_and_methods_are_removed_by_name(
    env_pointing_at_fake_api: None,  # noqa: ARG001
    fake_api_url: str,
    args: list[str],
    path: str,
) -> None:
    route = respx.delete(f"{fake_api_url}/agent/sellercart/delivery{path}").mock(
        return_value=httpx.Response(200, json={"zones": []})
    )

    result = runner.invoke(app, ["sellercart-delivery", *args])

    assert result.exit_code == 0, result.stderr or result.stdout
    assert route.call_count == 1


def test_the_one_price_delivery_command_is_gone() -> None:
    """Zones replaced it; an agent reaching for it is pointed at `sellercart-delivery` instead."""
    result = runner.invoke(app, ["sellercart-payouts", "delivery", "-b", "{}"])

    assert result.exit_code != 0


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


# --- The draft of a live shop -------------------------------------------------------------------


@respx.mock
def test_publish_asks_the_owner_with_an_optional_version_name(
    env_pointing_at_fake_api: None,  # noqa: ARG001
    fake_api_url: str,
) -> None:
    """Publishing raises an approval; the name travels as a short option, no JSON quoting."""
    route = respx.post(f"{fake_api_url}/agent/sellercart/publish").mock(
        return_value=httpx.Response(202, json={"status": "pending_approval"})
    )

    result = runner.invoke(app, ["sellercart", "publish", "--summary", "Owner's summer look"])

    assert result.exit_code == 0, result.stderr
    assert json.loads(route.calls.last.request.content) == {"summary": "Owner's summer look"}
    assert _data(result.stdout) == {"status": "pending_approval"}


@pytest.mark.parametrize(
    ("command", "method", "path"),
    [
        pytest.param("changes", "GET", "/agent/sellercart/changes", id="changes"),
        pytest.param("discard", "POST", "/agent/sellercart/discard", id="discard"),
        pytest.param("versions", "GET", "/agent/sellercart/versions", id="versions"),
    ],
)
@respx.mock
def test_the_draft_commands_reach_their_routes(
    env_pointing_at_fake_api: None,  # noqa: ARG001
    fake_api_url: str,
    command: str,
    method: str,
    path: str,
) -> None:
    route = respx.route(method=method, url=f"{fake_api_url}{path}").mock(
        return_value=httpx.Response(200, json={"ok": True})
    )

    result = runner.invoke(app, ["sellercart", command])

    assert result.exit_code == 0, result.stderr
    assert route.called


@respx.mock
def test_versions_takes_a_limit(
    env_pointing_at_fake_api: None,  # noqa: ARG001
    fake_api_url: str,
) -> None:
    route = respx.get(f"{fake_api_url}/agent/sellercart/versions").mock(
        return_value=httpx.Response(200, json=[])
    )

    result = runner.invoke(app, ["sellercart", "versions", "--limit", "3"])

    assert result.exit_code == 0, result.stderr
    assert route.calls.last.request.url.params["limit"] == "3"


@pytest.mark.parametrize(
    ("argv", "method", "path"),
    [
        pytest.param(
            ["sellercart", "update", "-b", '{"name": "Acme Home", "note": "New name"}'],
            "PATCH",
            "/agent/sellercart",
            id="settings",
        ),
        pytest.param(
            ["sellercart", "theme", "-b", '{"primary": "#000000", "note": "New name"}'],
            "PATCH",
            "/agent/sellercart/theme",
            id="theme",
        ),
        pytest.param(
            ["sellercart", "apply-preset", "-b", '{"preset": "minimal", "note": "New name"}'],
            "POST",
            "/agent/sellercart/presets/apply",
            id="preset",
        ),
        pytest.param(
            ["sellercart-pages", "update", "about", "-b", '{"title": "About", "note": "New name"}'],
            "PUT",
            "/agent/sellercart/pages/about",
            id="page",
        ),
        pytest.param(
            ["sellercart-menus", "update", "header", "-b", '{"items": [], "note": "New name"}'],
            "PUT",
            "/agent/sellercart/menus/header",
            id="menu",
        ),
    ],
)
@respx.mock
def test_writes_carry_the_agents_note_in_the_body(
    env_pointing_at_fake_api: None,  # noqa: ARG001
    fake_api_url: str,
    argv: list[str],
    method: str,
    path: str,
) -> None:
    """The owner reads the note beside the change it explains — it has to arrive with the write."""
    route = respx.route(method=method, url=f"{fake_api_url}{path}").mock(
        return_value=httpx.Response(200, json={})
    )

    result = runner.invoke(app, argv)

    assert result.exit_code == 0, result.stderr
    assert json.loads(route.calls.last.request.content)["note"] == "New name"


@respx.mock
def test_product_search_text_takes_the_note_as_an_option(
    env_pointing_at_fake_api: None,  # noqa: ARG001
    fake_api_url: str,
) -> None:
    """Every field of this one is an option already, so the note is one too — no JSON to quote."""
    product_id = "0b1c2d3e-4f50-6172-8394-a5b6c7d8e9f0"
    route = respx.put(f"{fake_api_url}/agent/sellercart/products/{product_id}/seo").mock(
        return_value=httpx.Response(200, json={})
    )

    result = runner.invoke(
        app,
        [
            "sellercart-products",
            "seo",
            product_id,
            "--title",
            "Linen apron",
            "--note",
            "The owner's own wording",
        ],
    )

    assert result.exit_code == 0, result.stderr
    assert json.loads(route.calls.last.request.content) == {
        "title": "Linen apron",
        "note": "The owner's own wording",
    }


@respx.mock
def test_deleting_a_page_carries_the_note_as_a_query(
    env_pointing_at_fake_api: None,  # noqa: ARG001
    fake_api_url: str,
) -> None:
    route = respx.delete(f"{fake_api_url}/agent/sellercart/pages/blog").mock(
        return_value=httpx.Response(204)
    )

    result = runner.invoke(
        app, ["sellercart-pages", "delete", "blog", "--note", "The owner asked to drop it"]
    )

    assert result.exit_code == 0, result.stderr
    assert route.calls.last.request.url.params["note"] == "The owner asked to drop it"
