"""What the ChatGPT surface hands over: only what a request needs (OpenAI's plugin rules)."""

from __future__ import annotations

import dataclasses
import json
from typing import Any

import pytest
import respx

import sellerclaw_cli.cli  # noqa: F401 — registers every command group
from sellerclaw_cli import mcp_apps
from sellerclaw_cli._errors import ApiError, UserInputError
from sellerclaw_cli.chatgpt import ACTIONS, _action, _answers, _cards, card_wording
from sellerclaw_cli.chatgpt._answers import (
    credits_only,
    hide_contacts,
    refusal_details,
    refusal_message,
    shape_answer,
)
from sellerclaw_cli.chatgpt._cards import shape_payload

pytestmark = pytest.mark.unit

BY_NAME = {a.name: a for a in ACTIONS}
BUYER_EMAIL = "jane.buyer@example.com"
BUYER_PHONE = "+1 512 555 0142"


def _order(**fields: Any) -> dict[str, Any]:
    """An order as ``GET /agent/orders/{id}`` answers it, buyer details and bookkeeping included."""
    return {
        "id": "o-1",
        "user_id": "u-1",
        "remote_order_id": "R-1",
        "remote_order_name": "#1001",
        "status": "new",
        "customer_name": "Jane Buyer",
        "customer_email": BUYER_EMAIL,
        "shipping_address": {
            "full_name": "Jane Buyer",
            "address1": "12 Elm St",
            "address2": "Apt 4",
            "city": "Austin",
            "province": "TX",
            "zip_code": "73301",
            "country_code": "US",
            "phone": BUYER_PHONE,
        },
        "line_items": [{"remote_line_item_id": "L1", "title": "Mug", "quantity": 1, "sell_price": "12.00"}],
        "attribution": {"source": "google", "click_id": "gclid-1"},
        "fx_rate_used": "1.0",
        "created_at": "2026-10-01T00:00:00Z",
        "updated_at": "2026-10-02T00:00:00Z",
        "remote_created_at": "2026-09-30T00:00:00Z",
        **fields,
    }


def _billing() -> dict[str, Any]:
    """``GET /agent/billing/overview`` with every price and offer it can carry."""
    return {
        "in_app_offers": False,
        "balance": {
            "subscription_state": "active",
            "intro_offer": {"tier_id": "pro", "price_usd": "1"},
            "scheduled_change": {"tier_id": "starter", "tier_name": "Starter", "price_usd": "29"},
            "assistant_trial": {
                "status": "active",
                "ends_at": "2026-11-05T00:00:00Z",
                "duration_days": 7,
                "plan": {"tier_id": "own-ai", "name": "Your Own AI", "price_usd": "10"},
            },
            "promo_offers": [{"offer_id": "x", "first_month_price_usd": "5", "full_price_usd": "40"}],
            "active_period": {
                "tier_id": "pro",
                "tier_name": "Pro — 20,000 credits / month",
                "tier_price_usd": "160",
                "credit_limit": "20000",
                "credits_used": "500",
                "balance": "19500",
                "period_end": "2026-11-15T00:00:00Z",
                "trial_ends_at": None,
                "is_exhausted": False,
                "agent_lock_reason": None,
                "entitlements": {"cj_from_tier_id": "pro"},
            },
        },
        "usage": {
            "total_credits": "500",
            "categories": [{"category": "media", "label": "Images", "credits": "500", "count": 3}],
        },
        "preferences": {"exhaustion_strategy": "auto_top_up", "auto_top_up_max_per_period": 3},
        "auto_top_up_pack": {"id": "p5k", "name": "5,000", "credits": "5000", "price_usd": "50"},
    }


_CREDITS = {
    "in_app_offers": False,
    "balance": {
        "subscription_state": "active",
        "active_period": {
            "credit_limit": "20000",
            "credits_used": "500",
            "balance": "19500",
            "period_end": "2026-11-15T00:00:00Z",
            "trial_ends_at": None,
            "is_exhausted": False,
            "agent_lock_reason": None,
        },
        "assistant_trial": {"status": "active", "ends_at": "2026-11-05T00:00:00Z", "duration_days": 7, "plan": {}},
    },
    "usage": {"total_credits": "500", "categories": [{"category": "media", "label": "Images", "credits": "500"}]},
}


# --------------------------------------------------------------------------- orders


@pytest.mark.parametrize(
    ("tool", "result", "expected"),
    [
        pytest.param(
            "list_orders",
            {"items": [_order()], "total": 1, "limit": 50, "offset": 0},
            {
                "items": [
                    {
                        "id": "o-1",
                        "remote_order_id": "R-1",
                        "remote_order_name": "#1001",
                        "status": "new",
                        "customer_name": "Jane Buyer",
                        "shipping_address": {"city": "Austin", "province": "TX", "country_code": "US"},
                        "line_items": [
                            {"remote_line_item_id": "L1", "title": "Mug", "quantity": 1, "sell_price": "12.00"}
                        ],
                        "remote_created_at": "2026-09-30T00:00:00Z",
                    }
                ],
                "total": 1,
                "limit": 50,
                "offset": 0,
            },
            id="a-list-names-the-buyer-and-their-town-only",
        ),
        pytest.param(
            "get_order",
            _order(),
            {
                "id": "o-1",
                "remote_order_id": "R-1",
                "remote_order_name": "#1001",
                "status": "new",
                "customer_name": "Jane Buyer",
                "shipping_address": {
                    "full_name": "Jane Buyer",
                    "address1": "12 Elm St",
                    "address2": "Apt 4",
                    "city": "Austin",
                    "province": "TX",
                    "zip_code": "73301",
                    "country_code": "US",
                    "phone": BUYER_PHONE,
                },
                "line_items": [{"remote_line_item_id": "L1", "title": "Mug", "quantity": 1, "sell_price": "12.00"}],
                "remote_created_at": "2026-09-30T00:00:00Z",
            },
            id="one-order-keeps-the-address-and-phone-shipping-and-the-supplier-need",
        ),
        pytest.param(
            "update_order",
            _order(),
            {
                "id": "o-1",
                "remote_order_id": "R-1",
                "remote_order_name": "#1001",
                "status": "new",
                "customer_name": "Jane Buyer",
                "shipping_address": {"city": "Austin", "province": "TX", "country_code": "US"},
                "line_items": [{"remote_line_item_id": "L1", "title": "Mug", "quantity": 1, "sell_price": "12.00"}],
                "remote_created_at": "2026-09-30T00:00:00Z",
            },
            id="a-write-answers-without-the-address-it-did-not-ask-for",
        ),
    ],
)
def test_orders_carry_the_buyer_only_as_far_as_the_request_needs(tool: str, result: Any, expected: Any) -> None:
    assert shape_answer(tool, result) == expected


@pytest.mark.parametrize(
    ("result", "expected"),
    [
        pytest.param(
            [
                {
                    "remote_id": "S-1",
                    "buyer_name": "Jane Buyer",
                    "buyer_email": BUYER_EMAIL,
                    "shipping_address": {
                        "address1": "12 Elm St",
                        "city": "Austin",
                        "country_code": "US",
                        "phone": BUYER_PHONE,
                    },
                    "extra": {"customer": {"id": "gid://shopify/Customer/1", "email": BUYER_EMAIL}},
                }
            ],
            [
                {
                    "remote_id": "S-1",
                    "buyer_name": "Jane Buyer",
                    "shipping_address": {"city": "Austin", "country_code": "US"},
                }
            ],
            id="shopify-without-its-raw-order",
        ),
        pytest.param(
            {
                "items": [
                    {
                        "remote_id": "E-1",
                        "buyer": "Jane Buyer",
                        "email": BUYER_EMAIL,
                        "phone": BUYER_PHONE,
                        "note": "Leave at the back door",
                        "address": {
                            "country": "US",
                            "region_or_state": "TX",
                            "city": "Austin",
                            "postal_code": "73301",
                            "address_line_1": "12 Elm St",
                            "reference_id": "ref-9",
                        },
                    }
                ]
            },
            {
                "items": [
                    {
                        "remote_id": "E-1",
                        "buyer": "Jane Buyer",
                        "address": {"country": "US", "region_or_state": "TX", "city": "Austin"},
                    }
                ]
            },
            id="ebay-without-contacts-or-the-buyer-s-note",
        ),
        pytest.param(
            {
                "items": [
                    {
                        "remote_id": "A-1",
                        "buyer": "Jane Buyer",
                        "email": "x@marketplace.amazon.com",
                        "shipping": {
                            "Name": "Jane",
                            "AddressLine1": "12 Elm St",
                            "City": "Austin",
                            "StateOrRegion": "TX",
                            "CountryCode": "US",
                            "Phone": BUYER_PHONE,
                        },
                    }
                ]
            },
            {
                "items": [
                    {
                        "remote_id": "A-1",
                        "buyer": "Jane Buyer",
                        "shipping": {"City": "Austin", "StateOrRegion": "TX", "CountryCode": "US"},
                    }
                ]
            },
            id="amazon-without-the-relay-email-or-the-street",
        ),
    ],
)
def test_store_orders_lose_the_buyer_s_contacts_and_street(result: Any, expected: Any) -> None:
    assert shape_answer("list_store_orders", result) == expected


# --------------------------------------------------------------------------- the account


def test_connections_keep_store_settings_but_not_the_seller_s_account_ids() -> None:
    result = {
        "stores": [
            {
                "id": "s-1",
                "user_id": "u-1",
                "platform": "ebay",
                "status": "active",
                "name": "pawpilot_seller",
                "custom_name": None,
                "display_name": "Pawpilot",
                "domain": None,
                "markup_percent": 30.0,
                "specifics": {"ebay_username": "pawpilot_seller", "reorder_lead_time_days": 5, "target_market": "US"},
                "categories": [{"id": "1"}],
                "description": "",
            }
        ],
        "ad_accounts": [{"id": "a-1", "platform": "google", "display_name": "Ads", "strategy": {"goal": "roas"}}],
        "supplier_accounts": [{"id": "c-1", "provider": "cj", "contact": "rep@supplier.example", "import_profile": {}}],
        "integrations": [
            {
                "kind": "facebook",
                "used_by": ["ads"],
                "connections": [{"id": "f-1", "name": "Page", "account_user_name": "John Owner", "health_error": None}],
            }
        ],
    }

    assert shape_answer("list_connections", result) == {
        "stores": [
            {
                "id": "s-1",
                "platform": "ebay",
                "status": "active",
                "custom_name": None,
                "display_name": "Pawpilot",
                "domain": None,
                "markup_percent": 30.0,
                "settings": {"reorder_lead_time_days": 5, "target_market": "US"},
            }
        ],
        "ad_accounts": [{"id": "a-1", "platform": "google", "display_name": "Ads"}],
        "supplier_accounts": [{"id": "c-1", "provider": "cj"}],
        "integrations": [{"kind": "facebook", "connections": [{"id": "f-1", "name": "Page", "health_error": None}]}],
    }


def test_the_account_overview_tells_credits_and_never_a_plan_or_a_price() -> None:
    result = {
        "profile": {"id": "u-1", "name": "Kim Seller"},
        "business_profile": {"team_size": "1"},
        "billing": _billing(),
    }

    assert shape_answer("get_account_overview", result) == {
        "profile": {"name": "Kim Seller"},
        "business_profile": {"team_size": "1"},
        "billing": _CREDITS,
    }


def test_credits_only_adds_nothing_the_server_did_not_send() -> None:
    assert credits_only({"balance": {"subscription_state": "no_plan"}, "usage": {"categories": []}}) == {
        "in_app_offers": False,
        "balance": {"subscription_state": "no_plan"},
        "usage": {"categories": []},
    }


def test_approval_requests_in_a_list_carry_what_they_are_not_whom_they_reach() -> None:
    request = {
        "id": "r-1",
        "user_id": "u-1",
        "goal_id": "g-1",
        "team_task_id": "t-1",
        "title": "Send the follow-up email",
        "status": "pending",
        "details": [{"label": "To", "value": BUYER_EMAIL}],
        "created_by": {"kind": "agent", "user_id": "u-1"},
        "execution": {"handler": "email.send", "status": "waiting", "message": None, "result": {"raw": 1}},
        "resolved_client": "chatgpt",
    }

    assert shape_answer("list_action_requests", {"items": [request]}) == {
        "items": [
            {
                "id": "r-1",
                "title": "Send the follow-up email",
                "status": "pending",
                "execution": {"status": "waiting", "message": None},
            }
        ]
    }


# --------------------------------------------------------------------------- research


@pytest.mark.parametrize(
    ("result", "expected"),
    [
        pytest.param(
            {
                "provider": "sociavault",
                "available_providers": ["sociavault"],
                "credits_used": 1,
                "cost_usd": "0.002",
                "response": {
                    "success": True,
                    "data": {
                        "user": {
                            "pk": "123",
                            "username": "jane.makes",
                            "full_name": "Jane Maker",
                            "biography": "Handmade mugs. Orders: jane@example.com",
                            "profile_pic_url": "https://cdn/x.jpg",
                            "business_email": "jane@example.com",
                            "edge_followed_by": {"count": 1200},
                            "edge_related_profiles": {"edges": [{"node": {"username": "someone"}}]},
                        }
                    },
                },
            },
            {
                "response": {
                    "data": {
                        "user": {
                            "username": "jane.makes",
                            "biography": "Handmade mugs. Orders: [hidden]",
                            "edge_followed_by": {"count": 1200},
                        }
                    }
                }
            },
            id="a-private-person-keeps-figures-not-name-contacts-or-the-people-around",
        ),
        pytest.param(
            {
                "provider": "sociavault",
                "response": {
                    "data": {
                        "user": {
                            "username": "acme",
                            "full_name": "Acme Mugs",
                            "is_business_account": True,
                            "edge_followed_by": {"count": 90000},
                            "business_phone_number": "+1 512 555 0100",
                        }
                    }
                },
            },
            {
                "response": {
                    "data": {
                        "user": {
                            "username": "acme",
                            "full_name": "Acme Mugs",
                            "is_business_account": True,
                            "edge_followed_by": {"count": 90000},
                        }
                    }
                }
            },
            id="a-business-keeps-its-name",
        ),
    ],
)
def test_a_social_profile_is_the_account_s_figures_not_a_person(result: Any, expected: Any) -> None:
    assert shape_answer("get_social_profile", result) == expected


def test_social_posts_keep_content_and_engagement_without_the_people() -> None:
    result = {
        "credits_used": 1,
        "response": {
            "data": {
                "items": {
                    "0": {
                        "code": "Cx1",
                        "taken_at": 1730000000,
                        "like_count": 50,
                        "caption": {"text": "New mug drop! Call 512-555-0199", "user": {"username": "jane"}},
                        "user": {"username": "jane", "full_name": "Jane"},
                        "usertags": {"in": [{"user": {"username": "friend"}}]},
                        "location": {"name": "Austin"},
                    }
                }
            }
        },
    }

    assert shape_answer("get_social_posts", result) == {
        "response": {
            "data": {
                "items": {
                    "0": {
                        "code": "Cx1",
                        "taken_at": 1730000000,
                        "like_count": 50,
                        "caption": {"text": "New mug drop! Call [hidden]"},
                    }
                }
            }
        }
    }


def test_ad_library_keeps_the_creative_and_the_brand_not_who_paid() -> None:
    result = {
        "provider": "sociavault",
        "cost_usd": "0.01",
        "response": {
            "results": [
                {
                    "page_id": "99",
                    "page_name": "Acme Mugs",
                    "snapshot": {
                        "body": {"text": "20% off mugs"},
                        "byline": "Paid for by John Smith",
                        "page_profile_uri": "https://fb/acme",
                    },
                    "start_date": "2026-10-01",
                    "is_active": True,
                }
            ]
        },
    }

    assert shape_answer("search_ad_library", result) == {
        "response": {
            "results": [
                {
                    "page_name": "Acme Mugs",
                    "snapshot": {"body": {"text": "20% off mugs"}},
                    "start_date": "2026-10-01",
                    "is_active": True,
                }
            ]
        }
    }


@pytest.mark.parametrize(
    ("tool", "result", "expected"),
    [
        pytest.param(
            "keyword_ideas",
            {
                "provider": "dataforseo",
                "available_providers": ["dataforseo"],
                "cost_usd": "0.05",
                "items": [{"keyword": "mug"}],
            },
            {"items": [{"keyword": "mug"}]},
            id="seo-without-who-answered-or-what-it-cost-us",
        ),
        pytest.param(
            "scrape_web_page",
            {
                "url": "https://a.example",
                "content": "Hi",
                "status_code": 200,
                "content_chars": 2,
                "screenshot_error": "x",
                "screenshot_file_id": "f",
            },
            {"url": "https://a.example", "content": "Hi"},
            id="a-page-without-the-fetch-s-debug-fields",
        ),
        pytest.param(
            "list_media_jobs",
            {
                "jobs": [
                    {"id": "j1", "status": "failed", "error": "Media provider returned HTTP 500. litellm group img-pro"}
                ]
            },
            {
                "jobs": [
                    {"id": "j1", "status": "failed", "error": "The generation failed; try again or pick another model."}
                ]
            },
            id="a-failed-job-without-the-provider-s-internals",
        ),
    ],
)
def test_research_and_media_lose_provider_bookkeeping(tool: str, result: Any, expected: Any) -> None:
    assert shape_answer(tool, result) == expected


@respx.mock
@pytest.mark.parametrize(
    "url",
    [
        pytest.param("https://www.linkedin.com/in/jane-maker", id="a-person"),
        pytest.param("https://lnkd.in/abc", id="a-short-link"),
    ],
)
def test_linkedin_reads_company_pages_only(url: str) -> None:
    with pytest.raises(UserInputError, match="LinkedIn here reads company pages only"):
        BY_NAME["get_social_profile"].run({"network": "linkedin", "url": url})

    assert not respx.calls


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        pytest.param("Write to jane@example.com today", "Write to [hidden] today", id="email"),
        pytest.param("Call +1 (512) 555-0142 now", "Call [hidden] now", id="phone"),
        pytest.param("Call 512-555-0199", "Call [hidden]", id="dashed-phone"),
        pytest.param("Sold 1,200 mugs in 2026", "Sold 1,200 mugs in 2026", id="figures-stay"),
        pytest.param("Launched 2026-10-01, 12.5 x 8 cm", "Launched 2026-10-01, 12.5 x 8 cm", id="dates-and-sizes-stay"),
    ],
)
def test_free_text_hides_contacts_but_not_figures(text: str, expected: str) -> None:
    assert hide_contacts(text) == expected


# --------------------------------------------------------------------------- refusals


@pytest.mark.parametrize(
    ("details", "expected"),
    [
        pytest.param(
            {
                "detail": [
                    {
                        "loc": ["body", "address1"],
                        "msg": "too long",
                        "type": "string_too_long",
                        "input": "12 Elm St",
                        "ctx": {"max_length": 5},
                    }
                ]
            },
            {"detail": [{"loc": ["body", "address1"], "msg": "too long", "type": "string_too_long"}]},
            id="a-422-without-the-value-sent",
        ),
        pytest.param(
            {
                "detail": {
                    "code": "listing_is_a_variation",
                    "message": "Use the group",
                    "use_instead": "L-9",
                    "user_id": "u-1",
                }
            },
            {"detail": {"code": "listing_is_a_variation", "message": "Use the group", "use_instead": "L-9"}},
            id="a-refusal-keeps-its-fix",
        ),
        pytest.param({"body": "<html>502</html>"}, None, id="a-proxy-page-is-dropped"),
        pytest.param(None, None, id="nothing"),
    ],
)
def test_refusal_details_keep_the_fix_and_drop_echoes(details: Any, expected: Any) -> None:
    assert refusal_details(details) == expected


def test_a_refused_action_reaches_chatgpt_without_the_echoed_input() -> None:
    def refuse(values: dict[str, Any]) -> Any:
        raise ApiError(
            "address1: too long (got '12 Elm St')",
            status=422,
            details={"detail": [{"loc": ["body", "address1"], "msg": "too long", "input": "12 Elm St"}]},
        )

    tool = _action._tool_function(dataclasses.replace(BY_NAME["get_order"], run=refuse))

    with pytest.raises(ApiError) as refused:
        tool(order_id="#1001")

    assert refused.value.message == "address1: too long"
    assert refused.value.details == {"detail": [{"loc": ["body", "address1"], "msg": "too long"}]}
    assert "12 Elm St" not in json.dumps(refused.value.details)


# --------------------------------------------------------------------------- cards


def test_the_order_board_card_carries_what_the_board_draws() -> None:
    payload = {
        "orders": {
            "items": [_order(store_name="Pawpilot", platform="ebay", total_revenue="12.00")],
            "total": 1,
            "offset": 0,
            "limit": 25,
        },
        "overview": {"total": 1, "by_status": {"new": 1}, "unresolved": 0},
        "stores": [{"id": "s-1", "platform": "ebay", "display_name": "Pawpilot", "domain": None}],
        "filters": {"status": "open"},
    }

    assert shape_payload("sellerclaw_orders", payload) == {
        "orders": {
            "items": [
                {
                    "id": "o-1",
                    "remote_order_id": "R-1",
                    "remote_order_name": "#1001",
                    "status": "new",
                    "customer_name": "Jane Buyer",
                    "shipping_address": {"city": "Austin", "country_code": "US"},
                    "remote_created_at": "2026-09-30T00:00:00Z",
                    "store_name": "Pawpilot",
                    "platform": "ebay",
                    "total_revenue": "12.00",
                }
            ],
            "total": 1,
            "offset": 0,
        },
        "overview": {"total": 1, "by_status": {"new": 1}, "unresolved": 0},
        "stores": [{"id": "s-1", "platform": "ebay", "display_name": "Pawpilot"}],
        "filters": {"status": "open"},
    }


def test_one_order_card_prints_the_address_but_not_the_phone_or_email() -> None:
    shaped = shape_payload("sellerclaw_orders", {"order": _order(), "item_images": {}})

    assert shaped["order"]["shipping_address"] == {
        "full_name": "Jane Buyer",
        "address1": "12 Elm St",
        "address2": "Apt 4",
        "city": "Austin",
        "province": "TX",
        "zip_code": "73301",
        "country_code": "US",
    }
    assert BUYER_EMAIL not in json.dumps(shaped)
    assert BUYER_PHONE not in json.dumps(shaped)


@pytest.mark.parametrize(
    ("tool", "payload", "expected"),
    [
        pytest.param(
            "sellerclaw_billing", {"billing": _billing()}, {"billing": _CREDITS}, id="billing-is-credits-only"
        ),
        pytest.param(
            "sellerclaw_billing",
            {
                "paywall": {
                    "code": "assistant_trial_ended",
                    "message": "Paused.",
                    "label": "Open SellerClaw",
                    "url": "https://app",
                }
            },
            {
                "paywall": {
                    "code": "assistant_trial_ended",
                    "message": "Paused.",
                    "label": "Open SellerClaw",
                    "url": "https://app",
                }
            },
            id="a-paused-account-keeps-its-paywall",
        ),
        pytest.param(
            "sellerclaw_connections",
            {
                "integrations": [
                    {
                        "kind": "facebook",
                        "display_name": "Meta",
                        "used_by": ["ads"],
                        "connections": [
                            {"id": "f-1", "name": "Page", "account_user_name": "John Owner", "status": "active"}
                        ],
                    }
                ]
            },
            {
                "integrations": [
                    {
                        "kind": "facebook",
                        "display_name": "Meta",
                        "connections": [{"id": "f-1", "name": "Page", "status": "active"}],
                    }
                ]
            },
            id="connections-without-whose-account-it-is",
        ),
    ],
)
def test_cards_hand_chatgpt_what_they_draw(tool: str, payload: dict[str, Any], expected: dict[str, Any]) -> None:
    assert shape_payload(tool, payload) == expected


def test_only_chatgpt_cuts_card_payloads() -> None:
    assert card_wording().shape_payload is shape_payload
    assert mcp_apps.RUNNER_WORDING.shape_payload is None


def _spec_keys(spec: Any) -> set[str]:
    if not isinstance(spec, dict):
        return set()
    return set(spec) | {key for inner in spec.values() for key in _spec_keys(inner)}


@pytest.mark.parametrize("tool", sorted(_cards._SPECS), ids=str)
def test_no_card_hands_chatgpt_our_ids_raw_payloads_or_buyer_contacts(tool: str) -> None:
    assert not _spec_keys(_cards._SPECS[tool]) & _answers._NEVER


def test_a_listing_keeps_the_context_of_why_it_cannot_be_bought() -> None:
    listing = {
        "listing_id": "L1",
        "sale_blockers": [{"code": "zero_stock", "message": "Out of stock", "extra": {"quantity": 0}}],
    }

    assert shape_answer("get_listing", listing) == listing


def test_a_shipment_answers_with_its_tracking_not_the_platform_s_raw_reply() -> None:
    fulfilment = {
        "remote_id": "F1",
        "status": "success",
        "tracking_number": "1Z9",
        "tracking_url": None,
        "extra": {"raw": {"receipt": 1}},
    }

    assert shape_answer("ship_order", fulfilment) == {
        "remote_id": "F1",
        "status": "success",
        "tracking_number": "1Z9",
        "tracking_url": None,
    }


@pytest.mark.parametrize(
    ("message", "details", "expected"),
    [
        pytest.param(
            "zip_code: too short (got '7'); phone: invalid (got '+1 512')",
            {
                "detail": [
                    {"loc": ["body", "zip_code"], "msg": "too short", "input": "7"},
                    {"loc": ["body", "phone"], "msg": "invalid", "input": "+1 512"},
                ]
            },
            "zip_code: too short; phone: invalid",
            id="a-422-names-the-fields-not-the-values",
        ),
        pytest.param(
            "Use the group",
            {"detail": {"code": "listing_is_a_variation", "message": "Use the group"}},
            "Use the group",
            id="a-domain-refusal-keeps-its-words",
        ),
        pytest.param("HTTP 502", None, "HTTP 502", id="no-details"),
    ],
)
def test_refusal_messages_name_the_field_but_never_repeat_the_value(message: str, details: Any, expected: str) -> None:
    assert refusal_message(message, details) == expected
