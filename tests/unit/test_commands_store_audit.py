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


@respx.mock
def test_pagespeed_posts_body(
    env_pointing_at_fake_api: None,  # noqa: ARG001
    fake_api_url: str,
) -> None:
    route = respx.post(f"{fake_api_url}/agent/store-audit/pagespeed").mock(
        return_value=httpx.Response(200, json={"url": "https://shop.example", "scores": []})
    )
    result = runner.invoke(
        app,
        ["store-audit", "pagespeed", "-b", json.dumps({"url": "https://shop.example", "strategy": "mobile"})],
    )
    assert result.exit_code == 0, result.stderr
    assert route.call_count == 1
    assert json.loads(route.calls.last.request.content) == {"url": "https://shop.example", "strategy": "mobile"}


@respx.mock
def test_onpage_posts_body(
    env_pointing_at_fake_api: None,  # noqa: ARG001
    fake_api_url: str,
) -> None:
    route = respx.post(f"{fake_api_url}/agent/store-audit/onpage").mock(
        return_value=httpx.Response(200, json={"url": "https://shop.example"})
    )
    result = runner.invoke(
        app,
        ["store-audit", "onpage", "-b", json.dumps({"url": "https://shop.example", "enable_javascript": True})],
    )
    assert result.exit_code == 0, result.stderr
    assert route.call_count == 1
    body = json.loads(route.calls.last.request.content)
    assert body["url"] == "https://shop.example"
    assert body["enable_javascript"] is True


@respx.mock
def test_ai_answers_posts_body(
    env_pointing_at_fake_api: None,  # noqa: ARG001
    fake_api_url: str,
) -> None:
    route = respx.post(f"{fake_api_url}/agent/store-audit/ai-answers").mock(
        return_value=httpx.Response(200, json={"items": []})
    )
    result = runner.invoke(
        app,
        [
            "store-audit",
            "ai-answers",
            "-b",
            json.dumps({"prompts": ["best dog leash stores"], "engines": ["chatgpt", "perplexity"]}),
        ],
    )
    assert result.exit_code == 0, result.stderr
    assert route.call_count == 1
    body = json.loads(route.calls.last.request.content)
    assert body["prompts"] == ["best dog leash stores"]
    assert body["engines"] == ["chatgpt", "perplexity"]


@respx.mock
def test_ai_mentions_posts_body(
    env_pointing_at_fake_api: None,  # noqa: ARG001
    fake_api_url: str,
) -> None:
    route = respx.post(f"{fake_api_url}/agent/store-audit/ai-mentions").mock(
        return_value=httpx.Response(200, json={"target": "dog leash", "items": []})
    )
    result = runner.invoke(app, ["store-audit", "ai-mentions", "-b", json.dumps({"target": "dog leash"})])
    assert result.exit_code == 0, result.stderr
    assert route.call_count == 1
    assert json.loads(route.calls.last.request.content) == {"target": "dog leash"}


@respx.mock
def test_ai_answers_rejects_unknown_engine_before_calling_api(
    env_pointing_at_fake_api: None,  # noqa: ARG001
    fake_api_url: str,
) -> None:
    route = respx.post(f"{fake_api_url}/agent/store-audit/ai-answers").mock(
        return_value=httpx.Response(200, json={})
    )
    result = runner.invoke(
        app,
        ["store-audit", "ai-answers", "-b", json.dumps({"prompts": ["x"], "engines": ["bard"]})],
    )
    # Local body-schema validation rejects the bad choice; the API is never called.
    assert result.exit_code != 0
    assert route.call_count == 0


@respx.mock
def test_pagespeed_missing_required_url_is_rejected_locally(
    env_pointing_at_fake_api: None,  # noqa: ARG001
    fake_api_url: str,
) -> None:
    route = respx.post(f"{fake_api_url}/agent/store-audit/pagespeed").mock(
        return_value=httpx.Response(200, json={})
    )
    result = runner.invoke(app, ["store-audit", "pagespeed", "-b", json.dumps({"strategy": "mobile"})])
    assert result.exit_code != 0
    assert route.call_count == 0
