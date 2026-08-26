from __future__ import annotations

import json

import httpx
import pytest
import respx
from typer.testing import CliRunner

from sellerclaw_cli.cli import app

pytestmark = pytest.mark.unit

runner = CliRunner()


@pytest.fixture
def env_pointing_at_fake_api(
    monkeypatch: pytest.MonkeyPatch,
    fake_api_url: str,
    fake_token: str,
) -> None:
    monkeypatch.setenv("SELLERCLAW_API_URL", fake_api_url)
    monkeypatch.setenv("SELLERCLAW_TOKEN", fake_token)


@pytest.mark.parametrize(
    ("command", "body"),
    [
        pytest.param("instagram-profile", {"handle": "rival"}, id="instagram-profile"),
        pytest.param("instagram-posts", {"handle": "rival", "next_max_id": "c1"}, id="instagram-posts"),
        pytest.param("instagram-reels", {"user_id": "42"}, id="instagram-reels"),
        pytest.param(
            "instagram-post-comments",
            {"url": "https://instagram.com/p/abc"},
            id="instagram-post-comments",
        ),
        pytest.param("tiktok-profile", {"handle": "rival"}, id="tiktok-profile"),
        pytest.param(
            "tiktok-profile-videos",
            {"handle": "rival", "sort_by": "popular"},
            id="tiktok-profile-videos",
        ),
        pytest.param(
            "tiktok-video-comments",
            {"url": "https://tiktok.com/@rival/video/1"},
            id="tiktok-video-comments",
        ),
        pytest.param("tiktok-audience-demographics", {"handle": "rival"}, id="tiktok-demographics"),
        pytest.param("tiktok-followers", {"handle": "rival"}, id="tiktok-followers"),
        pytest.param("tiktok-following", {"handle": "rival"}, id="tiktok-following"),
        pytest.param("youtube-channel", {"handle": "RivalTV"}, id="youtube-channel"),
        pytest.param(
            "youtube-channel-videos",
            {"channel_id": "UC123", "sort": "latest"},
            id="youtube-channel-videos",
        ),
        pytest.param(
            "youtube-video-comments",
            {"url": "https://youtu.be/abc", "order": "top"},
            id="youtube-video-comments",
        ),
        pytest.param("facebook-profile", {"url": "https://facebook.com/rival"}, id="facebook-profile"),
        pytest.param("facebook-profile-posts", {"page_id": "777"}, id="facebook-profile-posts"),
        pytest.param("twitter-profile", {"handle": "rival"}, id="twitter-profile"),
        pytest.param("twitter-user-tweets", {"handle": "rival"}, id="twitter-user-tweets"),
        pytest.param("threads-profile", {"handle": "rival"}, id="threads-profile"),
        pytest.param("threads-posts", {"handle": "rival"}, id="threads-posts"),
        pytest.param("pinterest-user-boards", {"handle": "rival"}, id="pinterest-user-boards"),
        pytest.param("linkedin-profile", {"url": "https://linkedin.com/in/rival"}, id="linkedin-profile"),
        pytest.param("linkedin-company", {"url": "https://linkedin.com/company/rival"}, id="linkedin-company"),
    ],
)
@respx.mock
def test_social_profile_commands_post_body_to_their_endpoint(
    env_pointing_at_fake_api: None,  # noqa: ARG001
    fake_api_url: str,
    command: str,
    body: dict[str, object],
) -> None:
    route = respx.post(f"{fake_api_url}/agent/research/social/{command}").mock(
        return_value=httpx.Response(200, json={"provider": "sociavault", "response": {}})
    )

    result = runner.invoke(app, ["research-social", command, "-b", json.dumps(body)])

    assert result.exit_code == 0, result.stderr
    assert route.call_count == 1
    assert json.loads(route.calls.last.request.content) == body


@respx.mock
def test_ad_library_search_accepts_tiktok_with_its_filters(
    env_pointing_at_fake_api: None,  # noqa: ARG001
    fake_api_url: str,
) -> None:
    route = respx.post(f"{fake_api_url}/agent/research/social/ad-library-search").mock(
        return_value=httpx.Response(200, json={"provider": "sociavault", "response": {}})
    )
    body = {"platform": "tiktok", "query": "dog toy", "region": "US", "period": 30, "limit": 20}

    result = runner.invoke(app, ["research-social", "ad-library-search", "-b", json.dumps(body)])

    assert result.exit_code == 0, result.stderr
    assert json.loads(route.calls.last.request.content) == body


@respx.mock
def test_ad_library_company_ads_rejects_tiktok_locally(
    env_pointing_at_fake_api: None,  # noqa: ARG001
    fake_api_url: str,
) -> None:
    route = respx.post(f"{fake_api_url}/agent/research/social/ad-library-company-ads").mock(
        return_value=httpx.Response(200, json={})
    )
    body = {"platform": "tiktok", "company_name": "Acme"}

    result = runner.invoke(app, ["research-social", "ad-library-company-ads", "-b", json.dumps(body)])

    assert result.exit_code != 0
    assert route.call_count == 0, "TikTok has no ads-by-company view — the call must not leave the CLI"


@respx.mock
def test_missing_required_field_never_reaches_the_api(
    env_pointing_at_fake_api: None,  # noqa: ARG001
    fake_api_url: str,
) -> None:
    route = respx.post(f"{fake_api_url}/agent/research/social/tiktok-profile").mock(
        return_value=httpx.Response(200, json={})
    )

    result = runner.invoke(app, ["research-social", "tiktok-profile", "-b", json.dumps({"user_id": "42"})])

    assert result.exit_code != 0
    assert route.call_count == 0


@respx.mock
def test_ebay_search_sends_sellers_and_sort(
    env_pointing_at_fake_api: None,  # noqa: ARG001
    fake_api_url: str,
) -> None:
    route = respx.post(f"{fake_api_url}/agent/research/catalog/ebay/search").mock(
        return_value=httpx.Response(200, json={"items": []})
    )
    body = {"sellers": ["rival_store", "other_store"], "sort": "price", "limit": 50}

    result = runner.invoke(app, ["research-catalog", "ebay-search", "-b", json.dumps(body)])

    assert result.exit_code == 0, result.stderr
    assert json.loads(route.calls.last.request.content) == body


@respx.mock
def test_ebay_search_rejects_an_unsupported_sort(
    env_pointing_at_fake_api: None,  # noqa: ARG001
    fake_api_url: str,
) -> None:
    route = respx.post(f"{fake_api_url}/agent/research/catalog/ebay/search").mock(
        return_value=httpx.Response(200, json={"items": []})
    )

    result = runner.invoke(
        app,
        ["research-catalog", "ebay-search", "-b", json.dumps({"query": "x", "sort": "bestSelling"})],
    )

    assert result.exit_code != 0
    assert route.call_count == 0
