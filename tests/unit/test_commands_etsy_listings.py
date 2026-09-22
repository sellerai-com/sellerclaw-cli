from __future__ import annotations

import json

import httpx
import pytest
import respx
from typer.testing import CliRunner

from sellerclaw_cli._command_group import REGISTRY
from sellerclaw_cli.cli import app

pytestmark = pytest.mark.unit

runner = CliRunner()

STORE_ID = "11111111-1111-4111-8111-111111111111"
LISTING_ID = "22222222-2222-4222-8222-222222222222"
OTHER_LISTING_ID = "44444444-4444-4444-8444-444444444444"
PRODUCT_ID = "33333333-3333-4333-8333-333333333333"
READINESS_STATE_ID = "77777777-7777-4777-8777-777777777777"

_SET_POLICIES_JSON = {
    "results": [{"id": LISTING_ID, "sku": "SKU-1", "readiness": {"ready": True, "issues": []}}],
    "errors": [],
}
_BATCH_JSON = {"results": [], "errors": []}


def _summary(command: str) -> str:
    """The command's own help text, as `describe` and `--help` both serve it."""
    group = next(g for g in REGISTRY if g.name == "etsy-listings")
    return next(c for c in group.commands if c.name == command).summary


@pytest.fixture
def env_pointing_at_fake_api(
    monkeypatch: pytest.MonkeyPatch,
    fake_api_url: str,
    fake_token: str,
) -> None:
    monkeypatch.setenv("SELLERCLAW_API_URL", fake_api_url)
    monkeypatch.setenv("SELLERCLAW_TOKEN", fake_token)


@respx.mock
def test_set_policies_posts_one_policy_set_for_every_listing(
    env_pointing_at_fake_api: None,  # noqa: ARG001
    fake_api_url: str,
) -> None:
    """The whole point of the command: one shipping profile, many drafts, one call."""
    route = respx.post(f"{fake_api_url}/agent/etsy/stores/{STORE_ID}/listings/set-policies").mock(
        return_value=httpx.Response(200, json=_SET_POLICIES_JSON)
    )

    result = runner.invoke(
        app,
        [
            "etsy-listings",
            "set-policies",
            STORE_ID,
            "-b",
            json.dumps(
                {
                    "listing_ids": [LISTING_ID, OTHER_LISTING_ID],
                    "shipping_profile_id": "123456789",
                }
            ),
        ],
    )

    assert result.exit_code == 0, result.stderr
    assert route.call_count == 1
    sent = json.loads(route.calls.last.request.content)
    assert sent == {
        "listing_ids": [LISTING_ID, OTHER_LISTING_ID],
        "shipping_profile_id": "123456789",
    }
    # The response carries fresh readiness, so the caller learns whether the drafts can publish now.
    assert json.loads(result.stdout)["data"]["results"][0]["readiness"]["ready"] is True


@respx.mock
def test_set_policies_leaves_an_unnamed_policy_out_of_the_body(
    env_pointing_at_fake_api: None,  # noqa: ARG001
    fake_api_url: str,
) -> None:
    """An omitted policy must stay omitted — sending it empty would blank it on the server."""
    route = respx.post(f"{fake_api_url}/agent/etsy/stores/{STORE_ID}/listings/set-policies").mock(
        return_value=httpx.Response(200, json=_SET_POLICIES_JSON)
    )

    result = runner.invoke(
        app,
        [
            "etsy-listings",
            "set-policies",
            STORE_ID,
            "-b",
            json.dumps({"listing_ids": [LISTING_ID], "return_policy_id": "999"}),
        ],
    )

    assert result.exit_code == 0, result.stderr
    sent = json.loads(route.calls.last.request.content)
    assert "shipping_profile_id" not in sent


@respx.mock
def test_set_policies_requires_listing_ids_locally(
    env_pointing_at_fake_api: None,  # noqa: ARG001
    fake_api_url: str,
) -> None:
    route = respx.post(f"{fake_api_url}/agent/etsy/stores/{STORE_ID}/listings/set-policies").mock(
        return_value=httpx.Response(200, json=_SET_POLICIES_JSON)
    )

    result = runner.invoke(
        app,
        ["etsy-listings", "set-policies", STORE_ID, "-b", json.dumps({"shipping_profile_id": "1"})],
    )

    assert result.exit_code != 0
    assert route.call_count == 0  # caught before the network call
    assert "listing_ids" in result.stderr


@respx.mock
def test_set_policies_rejects_an_ebay_policy_name_locally(
    env_pointing_at_fake_api: None,  # noqa: ARG001
    fake_api_url: str,
) -> None:
    """Etsy has no fulfillment policy — the neighbouring group's name must not silently no-op."""
    route = respx.post(f"{fake_api_url}/agent/etsy/stores/{STORE_ID}/listings/set-policies").mock(
        return_value=httpx.Response(200, json=_SET_POLICIES_JSON)
    )

    result = runner.invoke(
        app,
        [
            "etsy-listings",
            "set-policies",
            STORE_ID,
            "-b",
            json.dumps({"listing_ids": [LISTING_ID], "fulfillment_policy_id": "1"}),
        ],
    )

    assert result.exit_code != 0
    assert route.call_count == 0
    assert "fulfillment_policy_id" in result.stderr


@respx.mock
def test_update_sends_the_shipping_profile_to_a_draft(
    env_pointing_at_fake_api: None,  # noqa: ARG001
    fake_api_url: str,
) -> None:
    """A draft missing its profile has to be fixable one listing at a time, not only in bulk."""
    route = respx.patch(
        f"{fake_api_url}/agent/etsy/stores/{STORE_ID}/listings/{LISTING_ID}"
    ).mock(return_value=httpx.Response(200, json={"id": LISTING_ID}))

    result = runner.invoke(
        app,
        [
            "etsy-listings",
            "update",
            STORE_ID,
            LISTING_ID,
            "-b",
            json.dumps({"shipping_profile_id": "123456789"}),
        ],
    )

    assert result.exit_code == 0, result.stderr
    assert json.loads(route.calls.last.request.content) == {"shipping_profile_id": "123456789"}


# --------------------------------------------------------------------------- delete


@respx.mock
def test_delete_posts_the_listing_ids_to_the_etsy_delete_endpoint(
    env_pointing_at_fake_api: None,  # noqa: ARG001
    fake_api_url: str,
) -> None:
    """Deleting is irreversible, so the call must land on `delete` and not on `withdraw`."""
    route = respx.post(f"{fake_api_url}/agent/etsy/stores/{STORE_ID}/listings/delete").mock(
        return_value=httpx.Response(200, json=_BATCH_JSON)
    )

    result = runner.invoke(
        app,
        [
            "etsy-listings",
            "delete",
            STORE_ID,
            "-b",
            json.dumps({"listing_ids": [LISTING_ID, OTHER_LISTING_ID]}),
        ],
    )

    assert result.exit_code == 0, result.stderr
    assert route.call_count == 1
    assert json.loads(route.calls.last.request.content) == {
        "listing_ids": [LISTING_ID, OTHER_LISTING_ID]
    }


def test_delete_without_listing_ids_is_refused_before_the_request(
    env_pointing_at_fake_api: None,  # noqa: ARG001
) -> None:
    """An empty delete would be a no-op round trip at best; a missing required field is caught here."""
    result = runner.invoke(app, ["etsy-listings", "delete", STORE_ID, "-b", json.dumps({})])

    assert result.exit_code != 0
    assert "listing_ids" in result.stderr


def test_delete_help_warns_that_nothing_comes_back_and_names_the_reversible_verb() -> None:
    """Whoever reads this is one call away from destroying a listing's whole history on Etsy — the
    summary has to say what is lost and that `withdraw` is what a vague instruction means."""
    summary = _summary("delete")

    assert "irreversible" in summary
    assert "listing fee" in summary
    assert "withdraw" in summary
    # ...and the recoverable verb must not have grown the same warning by copy-paste.
    assert "irreversible" not in _summary("withdraw")


# --------------------------------------------------------------------------- processing profile

#: Every command that can name the shop's processing profile, with the request it makes. Etsy
#: refuses a physical listing without one, so all three paths that settle a draft's attributes have
#: to be able to carry it — a draft created without it is otherwise unfixable from the CLI.
_READINESS_TARGETS = [
    pytest.param(
        ["etsy-listings", "draft", STORE_ID],
        {"product_ids": [PRODUCT_ID]},
        "POST",
        "/listings/draft",
        id="draft",
    ),
    pytest.param(
        ["etsy-listings", "set-policies", STORE_ID],
        {"listing_ids": [LISTING_ID]},
        "POST",
        "/listings/set-policies",
        id="set-policies",
    ),
    pytest.param(
        ["etsy-listings", "update", STORE_ID, LISTING_ID],
        {"title": "Renamed"},
        "PATCH",
        f"/listings/{LISTING_ID}",
        id="update",
    ),
]


@respx.mock
@pytest.mark.parametrize(("argv", "base_body", "method", "suffix"), _READINESS_TARGETS)
def test_the_processing_profile_reaches_the_api_as_readiness_state_id(
    env_pointing_at_fake_api: None,  # noqa: ARG001
    fake_api_url: str,
    argv: list[str],
    base_body: dict[str, object],
    method: str,
    suffix: str,
) -> None:
    url = f"{fake_api_url}/agent/etsy/stores/{STORE_ID}{suffix}"
    route = respx.route(method=method, url=url).mock(
        return_value=httpx.Response(200, json=_SET_POLICIES_JSON)
    )

    result = runner.invoke(
        app,
        [*argv, "-b", json.dumps({**base_body, "readiness_state_id": READINESS_STATE_ID})],
    )

    assert result.exit_code == 0, result.stderr
    sent = json.loads(route.calls.last.request.content)
    assert sent["readiness_state_id"] == READINESS_STATE_ID


@respx.mock
@pytest.mark.parametrize(("argv", "base_body", "method", "suffix"), _READINESS_TARGETS)
def test_an_unnamed_processing_profile_stays_out_of_the_body(
    env_pointing_at_fake_api: None,  # noqa: ARG001
    fake_api_url: str,
    argv: list[str],
    base_body: dict[str, object],
    method: str,
    suffix: str,
) -> None:
    """Omitting it means "the shop settles it" — sending it empty would blank a profile instead."""
    url = f"{fake_api_url}/agent/etsy/stores/{STORE_ID}{suffix}"
    route = respx.route(method=method, url=url).mock(
        return_value=httpx.Response(200, json=_SET_POLICIES_JSON)
    )

    result = runner.invoke(app, [*argv, "-b", json.dumps(base_body)])

    assert result.exit_code == 0, result.stderr
    assert "readiness_state_id" not in json.loads(route.calls.last.request.content)


@pytest.mark.parametrize(("argv", "base_body", "method", "suffix"), _READINESS_TARGETS)
def test_a_misspelled_processing_profile_is_refused_before_the_request(
    env_pointing_at_fake_api: None,  # noqa: ARG001
    argv: list[str],
    base_body: dict[str, object],
    method: str,  # noqa: ARG001
    suffix: str,  # noqa: ARG001
) -> None:
    """Etsy's own name for it is `processing_profile_id`; guessing it must fail loudly here rather
    than be dropped on the way to a server that would then refuse the publish."""
    result = runner.invoke(
        app,
        [*argv, "-b", json.dumps({**base_body, "processing_profile_id": READINESS_STATE_ID})],
    )

    assert result.exit_code != 0
    assert "processing_profile_id" in result.stderr
