"""What a ChatGPT tool answers with: what the request needs, and nothing the owner did not ask for.

OpenAI's plugin rules hold every tool response to the data the user's request needs: no personal
identifiers it does not need, no internal ids, raw payloads or debug detail, and nothing the privacy
policy does not disclose. The Agent API answers our own agent and every other client too, so it
keeps returning everything; this module is where the ChatGPT surface cuts the answer down, at the
one place every action's result passes on its way out (:func:`shape_answer`). Reads an action makes
for itself — the marketplace id behind an order number — still see the full answer.

Two layers. Every answer loses :data:`_NEVER` at any depth. On top of that a tool can have its own
shape: an order list keeps the buyer's name and town but not their street, a social profile keeps
the account's figures but not the people around it.
"""

from __future__ import annotations

import re
from collections.abc import Callable, Mapping
from typing import Any

#: Keys no ChatGPT answer carries, at any depth: our own ids and bookkeeping, raw platform payloads,
#: what a data provider charged us, and buyer contact details no request here needs.
_NEVER: frozenset[str] = frozenset(
    {
        "user_id",
        "raw",
        "specifics",
        "attribution",
        "customer_email",
        "buyer_email",
        "fx_rate_used",
        "cost_usd",
        "available_providers",
        "error_details",
        "report_href",
        "budget_resource_name",
        "import_profile",
        "used_by",
        "account_user_name",
        "created_by",
        "team_task_id",
        "goal_id",
    }
)

#: The keys of an address that say where it is without saying who lives there, in every spelling
#: the platforms use.
_PLACE_KEYS: frozenset[str] = frozenset(
    {
        "city", "province", "region", "region_or_state", "state", "state_or_province", "country",
        "country_code", "countryCode", "City", "StateOrRegion", "CountryCode",
    }
)
_POSTCODE_KEYS: frozenset[str] = frozenset({"zip", "zip_code", "postal_code", "postcode", "PostalCode"})

#: Keys of a marketplace order row that reach the buyer — and ``extra``, the platform's raw order with
#: the buyer's details in it: the store's own order page has them, a list of orders does not need them.
_BUYER_CONTACT: frozenset[str] = frozenset({"email", "phone", "Phone", "BuyerEmail", "note", "extra"})
_ADDRESS_KEYS: frozenset[str] = frozenset({"shipping_address", "address", "shipping", "ShippingAddress"})

#: Store settings kept from the store record's ``specifics``; the rest of it is the connection's
#: own bookkeeping, seller account ids included.
_STORE_SETTINGS: frozenset[str] = frozenset(
    {
        "reorder_lead_time_days", "listing_quantity_cap", "default_policies", "target_market",
        "target_market_derived", "shipping_included_in_price", "cj_auto_purchase", "amazon_fulfils_orders",
        "stock_sync_threshold", "managed_stock", "currency", "marketplace", "marketplace_id", "region",
    }
)


def without(value: Any, keys: frozenset[str] = _NEVER) -> Any:
    """``value`` with every key in ``keys`` gone, at any depth."""
    if isinstance(value, Mapping):
        return {k: without(v, keys) for k, v in value.items() if k not in keys}
    if isinstance(value, list):
        return [without(item, keys) for item in value]
    return value


def _keep(value: Any, keys: frozenset[str]) -> Any:
    if not isinstance(value, Mapping):
        return value
    return {k: v for k, v in value.items() if k in keys}


def _place(address: Any, *, postcode: bool = False) -> Any:
    """Where an address is — town, region, country — without the street, the name or the phone."""
    if not isinstance(address, Mapping):
        return address
    kept = _keep(address, _PLACE_KEYS | _POSTCODE_KEYS if postcode else _PLACE_KEYS)
    return kept or None


def _items(result: Any, shape: Callable[[Any], Any]) -> Any:
    """Apply ``shape`` to each row of a page (``{"items": [...]}``) or a bare list."""
    if isinstance(result, list):
        return [shape(row) for row in result]
    if isinstance(result, Mapping) and isinstance(result.get("items"), list):
        return {**result, "items": [shape(row) for row in result["items"]]}
    return result


# ---------------------------------------------------------------------------------------------
# Orders
# ---------------------------------------------------------------------------------------------


def _order(order: Any, *, address: bool) -> Any:
    """One order: the full address only where the request is about shipping this one order."""
    if not isinstance(order, Mapping):
        return order
    shaped = {k: v for k, v in order.items() if k not in ("created_at", "updated_at")}
    if not address and "shipping_address" in shaped:
        shaped["shipping_address"] = _place(shaped["shipping_address"])
    return shaped


def _order_row(order: Any) -> Any:
    return _order(order, address=False)


def _store_order(order: Any) -> Any:
    """A marketplace's own order row: who and where, without the buyer's contact details."""
    if not isinstance(order, Mapping):
        return order
    shaped = {k: v for k, v in order.items() if k not in _BUYER_CONTACT}
    for key in _ADDRESS_KEYS & shaped.keys():
        shaped[key] = _place(shaped[key])
    return shaped


def _store_orders(result: Any) -> Any:
    return _items(result, _store_order)


# ---------------------------------------------------------------------------------------------
# The account and its connections
# ---------------------------------------------------------------------------------------------


def _store(store: Any) -> Any:
    """A store as its settings describe it, without the connection's account ids.

    ``name`` is the platform's own name for the store — an eBay login; ``display_name`` says what
    to call it.
    """
    if not isinstance(store, Mapping) or "platform" not in store:
        return store
    settings = _keep(store.get("specifics"), _STORE_SETTINGS)
    shaped = {
        k: v
        for k, v in store.items()
        if k not in ("name", "specifics", "categories", "description", "created_at", "updated_at")
    }
    if settings:
        shaped["settings"] = settings
    return shaped


def _connections(result: Any) -> Any:
    if not isinstance(result, Mapping):
        return result
    shaped = dict(result)
    shaped["stores"] = _items(result.get("stores"), _store)
    shaped["ad_accounts"] = _items(
        result.get("ad_accounts"), lambda row: _drop(row, ("strategy", "created_at", "updated_at"))
    )
    shaped["supplier_accounts"] = _items(result.get("supplier_accounts"), _supplier_account)
    return shaped


def _supplier_account(account: Any) -> Any:
    return _drop(account, ("contact", "created_at", "updated_at"))


def _drop(value: Any, keys: tuple[str, ...]) -> Any:
    if not isinstance(value, Mapping):
        return value
    return {k: v for k, v in value.items() if k not in keys}


def _mapping(value: Any) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


#: What the credits of a billing period are: how many, how many used, when they reset.
_CREDIT_FIELDS: frozenset[str] = frozenset(
    {"credit_limit", "credits_used", "balance", "period_end", "trial_ends_at", "is_exhausted", "agent_lock_reason"}
)


def credits_only(billing: Any) -> Any:
    """The owner's credits — left, used, when they reset — and nothing about plans or prices.

    OpenAI's rules forbid a plugin to show plans, prices or a way to buy, so ChatGPT is told what
    the account has, never what it could buy. ``assistant_trial.plan`` stays as an empty object:
    the billing card reads it before deciding not to draw it.
    """
    if not isinstance(billing, Mapping):
        return billing
    balance = _mapping(billing.get("balance"))
    shaped_balance: dict[str, Any] = _keep(balance, frozenset({"subscription_state", "subscription_ends_at"}))
    if "active_period" in balance:
        period = balance["active_period"]
        shaped_balance["active_period"] = _keep(period, _CREDIT_FIELDS) if isinstance(period, Mapping) else None
    trial = balance.get("assistant_trial")
    if isinstance(trial, Mapping):
        trial_state = _keep(trial, frozenset({"status", "ends_at", "duration_days"}))
        shaped_balance["assistant_trial"] = {**trial_state, "plan": {}}
    usage = _mapping(billing.get("usage"))
    categories = usage.get("categories")
    shaped_usage: dict[str, Any] = _keep(usage, frozenset({"total_credits"}))
    rows = categories if isinstance(categories, list) else []
    shaped_usage["categories"] = [_keep(row, frozenset({"category", "label", "credits"})) for row in rows]
    return {"in_app_offers": False, "balance": shaped_balance, "usage": shaped_usage}


def _account_overview(result: Any) -> Any:
    if not isinstance(result, Mapping):
        return result
    profile = result.get("profile")
    return {
        **result,
        "profile": _drop(profile, ("id",)),
        "billing": credits_only(result.get("billing")),
    }


def _locations(result: Any) -> Any:
    def location(row: Any) -> Any:
        if not isinstance(row, Mapping) or "address" not in row:
            return row
        return {**row, "address": _place(row["address"], postcode=True)}

    return _items(result, location)


# ---------------------------------------------------------------------------------------------
# Approvals
# ---------------------------------------------------------------------------------------------

_REQUEST_FIELDS: frozenset[str] = frozenset(
    {
        "id", "kind", "title", "summary", "description", "status", "mode", "options", "cta_label",
        "created_at", "deadline", "blocking", "execution",
    }
)


def _request(request: Any) -> Any:
    """An approval request as a list or an answer needs it: what it is and where it stands.

    Its ``details`` — the recipients and text of an email, the buyer a reply goes to — are for the
    owner deciding on the approval card, not for a list of requests.
    """
    if not isinstance(request, Mapping):
        return request
    shaped = _keep(request, _REQUEST_FIELDS)
    if isinstance(shaped.get("execution"), Mapping):
        shaped["execution"] = _keep(shaped["execution"], frozenset({"status", "message"}))
    return shaped


def _requests(result: Any) -> Any:
    return _items(result, _request)


def _answered_request(result: Any) -> Any:
    if isinstance(result, Mapping) and isinstance(result.get("request"), Mapping):
        return {**result, "request": _request(result["request"])}
    return _request(result)


# ---------------------------------------------------------------------------------------------
# Research and the web
# ---------------------------------------------------------------------------------------------

#: Who answered a research call and what it was billed: the provider's business, not the owner's.
_VENDOR: frozenset[str] = frozenset(
    {"provider", "available_providers", "credits_used", "credits_charged", "cost_usd"}
)
#: The social-data provider's own envelope around its answer, on top of :data:`_VENDOR`.
_SOCIAL_ENVELOPE: frozenset[str] = _VENDOR | {"endpoint", "note", "success"}

#: Social-media keys that point at a person: authors, tagged and mentioned users, commenters, the
#: people around a profile, contact details, platform user ids and pictures of faces. Dropped with
#: everything under them, wherever they appear.
_PEOPLE: frozenset[str] = frozenset(
    {
        # authors and the accounts around a post
        "author", "author_fullname", "authors", "owner", "user", "users", "user_results", "core",
        "caption_user", "coauthor_producers", "usertags", "tagged_users", "edge_media_to_tagged_user",
        "mentions", "user_mentions", "mention_fragment", "user_unique_id", "reply_to_author",
        "root_post_author", "quoted_status_result", "quoted_status", "retweeted_status_result", "awarders",
        "approved_by", "banned_by", "topComments", "comments", "comment_preview", "preview_comments",
        "edge_media_to_comment", "edge_media_preview_comment", "owner_nickname", "owner_handle", "owner_id",
        "clips_metadata",
        # the people around a profile
        "edge_mutual_followed_by", "edge_related_profiles", "related_profiles", "profile_context_facepile_users",
        "similarProfiles", "similar_profiles", "employees", "recommendations", "contributors", "investors",
        "connections", "experience", "education", "activity", "ai_agent_owner_username",
        # contact details and places
        "email", "emails", "phone", "phones", "business_email", "business_phone_number", "public_email",
        "public_phone_number", "contact_phone_number", "business_address_json", "address", "location",
        "latitude", "longitude", "tipjar_settings", "pronouns", "gender", "birthday",
        # platform ids of people and pictures of them
        "pk", "uid", "sec_uid", "short_id", "secUid", "shortId", "fbid", "eimu_id", "rest_id",
        "user_id_str", "guardian_id", "profile_pic_url", "profile_pic_url_hd", "hd_profile_pic_versions",
        "hd_profile_pic_url_info", "profilePhoto", "profilePic", "profilePicture", "avatar",
        "avatar_thumb", "avatar_medium", "avatar_larger", "avatarThumb", "avatarMedium", "avatarLarger",
        "coverPhoto",
        # who paid for an ad, and the person posting it
        "byline", "disclaimer_label", "branded_content", "page_id", "page_profile_uri",
        "page_profile_picture_url", "brazil_tax_id", "payer", "beneficiary", "poster", "promotedBy",
        "promoted_by",
    }
)

#: The account a profile answer is about sits under these keys, which elsewhere hold a post's author.
_PROFILE_HOLDERS: frozenset[str] = frozenset({"user", "users", "core"})

#: The name of the account a profile belongs to. Kept only for a business, verified or organisation
#: account: for a private person the handle the owner typed already says whose profile it is.
_DISPLAY_NAMES: frozenset[str] = frozenset({"full_name", "fullName", "nickname", "name"})
_BRAND_FLAGS: frozenset[str] = frozenset(
    {
        "is_business_account", "is_professional_account", "isOrganization", "is_verified", "verified",
        "isVerified", "is_blue_verified", "category_name", "business_category_name", "commerceUserInfo",
        "ttSeller",
    }
)

_EMAIL = re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+")
#: Digit groups joined by spaces, dots, dashes or brackets — a phone number's shape, and a date's.
_DIGIT_RUN = re.compile(r"(?<![\w.])(?:\+\d{1,3}[\s.-]?)?(?:\(\d{2,4}\)[\s.-]?)?\d{2,4}(?:[\s.-]\d{2,4}){1,4}(?![\w.])")
#: Fewer digits than any phone number with its area code: a date (2026-10-01), a size, a price.
_PHONE_DIGITS = 9
_HIDDEN = "[hidden]"


def _phone_or_not(match: re.Match[str]) -> str:
    run = match.group(0)
    return _HIDDEN if sum(ch.isdigit() for ch in run) >= _PHONE_DIGITS else run


def hide_contacts(text: str) -> str:
    """``text`` with email addresses and phone numbers replaced: free text can hold anyone's."""
    return _DIGIT_RUN.sub(_phone_or_not, _EMAIL.sub(_HIDDEN, text))


def _no_people(value: Any, people: frozenset[str] = _PEOPLE) -> Any:
    if isinstance(value, Mapping):
        return {
            k: _no_people(v, people) for k, v in value.items() if k not in people and k not in _SOCIAL_ENVELOPE
        }
    if isinstance(value, list):
        return [_no_people(item, people) for item in value]
    if isinstance(value, str):
        return hide_contacts(value)
    return value


def _is_brand(value: Any) -> bool:
    """Does the profile say anywhere that it is a business, verified or an organisation?"""
    if isinstance(value, Mapping):
        for key, item in value.items():
            if key in _BRAND_FLAGS and item not in (None, False, "", 0, {}, []):
                return True
            if _is_brand(item):
                return True
    elif isinstance(value, list):
        return any(_is_brand(item) for item in value)
    return False


def _social(result: Any) -> Any:
    return _no_people(result)


def _social_profile(result: Any) -> Any:
    shaped = _no_people(result, _PEOPLE - _PROFILE_HOLDERS)
    return shaped if _is_brand(shaped) else without(shaped, _DISPLAY_NAMES)


def _research(result: Any) -> Any:
    return without(result, _VENDOR)


def _web_page(result: Any) -> Any:
    return _drop(result, ("status_code", "content_chars", "screenshot_error", "screenshot_file_id"))


# ---------------------------------------------------------------------------------------------
# Media, listings, ads
# ---------------------------------------------------------------------------------------------


def _media_jobs(result: Any) -> Any:
    """A failed job says that it failed — not the provider's HTTP status or its model names."""

    def job(row: Any) -> Any:
        if not isinstance(row, Mapping) or not row.get("error"):
            return row
        return {**row, "error": "The generation failed; try again or pick another model."}

    if isinstance(result, Mapping) and isinstance(result.get("jobs"), list):
        return {**result, "jobs": [job(row) for row in result["jobs"]]}
    return _items(result, job)


def _publish_status(result: Any) -> Any:
    return _drop(result, ("submission_id", "feed_id"))


def _quoted_refusals(result: Any) -> Any:
    """An answer that quotes a marketplace's or a supplier's refusal: their words, no one's contacts."""
    if isinstance(result, Mapping):
        return {
            k: hide_contacts(v) if k in ("error", "tracking_error") and isinstance(v, str) else _quoted_refusals(v)
            for k, v in result.items()
        }
    if isinstance(result, list):
        return [_quoted_refusals(item) for item in result]
    return result


def _ad_recommendations(result: Any) -> Any:
    return without(result, frozenset({"resource_name"}))


def _product(result: Any) -> Any:
    """A product: where its supplier ships from by country, not by a warehouse's street."""

    def product(row: Any) -> Any:
        if isinstance(row, Mapping) and isinstance(row.get("supplier_warehouse"), Mapping):
            warehouse = _keep(row["supplier_warehouse"], frozenset({"id", "name", "country_code"}))
            return {**row, "supplier_warehouse": warehouse}
        return row

    if isinstance(result, Mapping) and "supplier_warehouse" in result:
        return product(result)
    return _items(result, product)


def _cancelled(result: Any) -> Any:
    return _drop(result, ("job",))


def _fulfilled(result: Any) -> Any:
    """A shipment the marketplace took: its status and tracking, not the platform's raw reply."""
    return _drop(result, ("extra",))


#: Tool name -> its own shape, applied before :data:`_NEVER`.
_SHAPES: Mapping[str, Callable[[Any], Any]] = {
    "list_orders": lambda result: _items(result, _order_row),
    "search_orders": lambda result: _items(result, _order_row),
    "get_order": lambda result: _order(result, address=True),
    "mark_order_shipped": _order_row,
    "update_order": _order_row,
    "list_store_orders": _store_orders,
    "cancel_order": _cancelled,
    "ship_order": _fulfilled,
    "list_connections": _connections,
    "update_store_settings": _store,
    "propose_store_markup": _store,
    "get_account_overview": _account_overview,
    "list_store_locations": _locations,
    "get_fba_status": _supplier_account,
    "list_action_requests": _requests,
    "answer_action_request": _answered_request,
    "cancel_action_request": _answered_request,
    "get_product": _product,
    "list_products": _product,
    "search_products": _product,
    "get_publish_status": _publish_status,
    "delete_listings": _quoted_refusals,
    "get_supplier_order": _quoted_refusals,
    "get_google_ads_recommendations": _ad_recommendations,
    "search_marketplace": _research,
    "get_marketplace_listing": _research,
    "get_marketplace_prices": _research,
    "keyword_ideas": _research,
    "keyword_volume": _research,
    "serp_competitors": _research,
    "google_trends": _research,
    "audit_store_site": _research,
    "check_ai_visibility": _research,
    "get_social_profile": _social_profile,
    "get_social_posts": _social,
    "search_social": _social,
    "search_ad_library": _social,
    "scrape_web_page": _web_page,
    "list_media_jobs": _media_jobs,
}


def shape_answer(tool: str, result: Any) -> Any:
    """What ``tool`` hands ChatGPT of ``result``: its own shape, then never any of :data:`_NEVER`."""
    shape = _SHAPES.get(tool)
    return without(shape(result) if shape is not None else result)


# ---------------------------------------------------------------------------------------------
# Refusals
# ---------------------------------------------------------------------------------------------

#: What a refusal's details keep of each 422 entry: where and what is wrong, not the value sent.
_VALIDATION_KEYS: frozenset[str] = frozenset({"loc", "msg", "type"})


def refusal_details(details: Any) -> Any:
    """A refusal's details as ChatGPT reads them: the code, the fix and the choices, nothing echoed.

    A 422 repeats the value that was sent (``input``), which can be a buyer's address; a body that
    was not JSON is a proxy's page, not something to act on. What a refusal offers to correct with —
    the id to use instead, the categories to pick from — stays.
    """
    if not isinstance(details, Mapping):
        return None
    if set(details) == {"body"}:
        return None
    detail = details.get("detail")
    if isinstance(detail, list):
        return {**details, "detail": [_keep(item, _VALIDATION_KEYS) for item in detail]}
    return without(details)


def refusal_message(message: str, details: Any) -> str:
    """A refusal's sentence without the values a 422 repeats back ("address1: too long (got '…')")."""
    from sellerclaw_cli._client import _format_validation_detail

    detail = details.get("detail") if isinstance(details, Mapping) else None
    if not isinstance(detail, list):
        return message
    return _format_validation_detail([_keep(item, _VALIDATION_KEYS) for item in detail]) or message
