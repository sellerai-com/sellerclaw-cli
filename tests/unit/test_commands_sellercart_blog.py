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


@respx.mock
def test_the_list_can_be_narrowed_to_the_plan(
    env_pointing_at_fake_api: None,  # noqa: ARG001
    fake_api_url: str,
) -> None:
    route = respx.get(f"{fake_api_url}/agent/sellercart/blog/posts").mock(
        return_value=httpx.Response(200, json=[])
    )

    result = runner.invoke(app, ["sellercart-blog", "list", "--stage", "planned"])

    assert result.exit_code == 0, result.stderr or result.stdout
    assert route.calls.last.request.url.params["stage"] == "planned"


def test_a_stage_the_blog_does_not_have_is_refused_locally() -> None:
    result = runner.invoke(app, ["sellercart-blog", "list", "--stage", "published"])

    assert result.exit_code != 0


@pytest.mark.parametrize(
    "body",
    [
        pytest.param(
            {"slug": "season-a-pan", "title": "Season a pan", "stage": "planned", "brief": "Query: x"},
            id="a-planned-topic",
        ),
        pytest.param(
            {
                "slug": "season-a-pan",
                "title": "Season a pan",
                "category": "Care",
                "excerpt": "Three coats.",
                "cover_url": "https://cdn.example/c.webp",
                "cover_alt": "A pan",
                "layout": [{"type": "richText", "content": "## Why\n\nBecause."}],
                "seo": {"title": "Season a pan", "description": "Three coats."},
                "publish_at": "2026-11-02T09:00:00-05:00",
            },
            id="a-whole-draft",
        ),
    ],
)
@respx.mock
def test_an_article_is_sent_as_given(
    env_pointing_at_fake_api: None,  # noqa: ARG001
    fake_api_url: str,
    body: dict[str, Any],
) -> None:
    route = respx.post(f"{fake_api_url}/agent/sellercart/blog/posts").mock(
        return_value=httpx.Response(201, json={"slug": body["slug"]})
    )

    result = runner.invoke(app, ["sellercart-blog", "create", "-b", json.dumps(body)])

    assert result.exit_code == 0, result.stderr or result.stdout
    assert json.loads(route.calls.last.request.content) == body


def test_a_new_article_needs_an_address_and_a_title() -> None:
    result = runner.invoke(app, ["sellercart-blog", "create", "-b", json.dumps({"title": "Pans"})])

    assert result.exit_code != 0
    assert "slug" in (result.stderr or result.stdout)


@respx.mock
def test_an_edit_can_empty_a_field_with_null(
    env_pointing_at_fake_api: None,  # noqa: ARG001
    fake_api_url: str,
) -> None:
    route = respx.put(f"{fake_api_url}/agent/sellercart/blog/posts/season-a-pan").mock(
        return_value=httpx.Response(200, json={"slug": "season-a-pan"})
    )
    body = {"excerpt": None, "publish_at": None, "mark_updated": True}

    result = runner.invoke(
        app, ["sellercart-blog", "update", "season-a-pan", "-b", json.dumps(body)]
    )

    assert result.exit_code == 0, result.stderr or result.stdout
    assert json.loads(route.calls.last.request.content) == body


@respx.mock
def test_publishing_names_the_articles_with_options_rather_than_json(
    env_pointing_at_fake_api: None,  # noqa: ARG001
    fake_api_url: str,
) -> None:
    route = respx.post(f"{fake_api_url}/agent/sellercart/blog/publish").mock(
        return_value=httpx.Response(202, json={"status": "pending_approval", "posts": ["a", "b"]})
    )

    result = runner.invoke(
        app,
        [
            "sellercart-blog",
            "publish",
            "--slug",
            "a",
            "--slug",
            "b",
            "--summary",
            "Pan care, part 1",
        ],
    )

    assert result.exit_code == 0, result.stderr or result.stdout
    assert json.loads(route.calls.last.request.content) == {
        "slugs": ["a", "b"],
        "summary": "Pan care, part 1",
    }


@pytest.mark.parametrize(
    ("command", "method", "path"),
    [
        pytest.param("get", "GET", "/agent/sellercart/blog/posts/a", id="get"),
        pytest.param("delete", "DELETE", "/agent/sellercart/blog/posts/a", id="delete"),
        pytest.param("discard", "POST", "/agent/sellercart/blog/posts/a/discard", id="discard"),
        pytest.param("unpublish", "POST", "/agent/sellercart/blog/posts/a/unpublish", id="unpublish"),
    ],
)
@respx.mock
def test_one_article_is_named_in_the_path(
    env_pointing_at_fake_api: None,  # noqa: ARG001
    fake_api_url: str,
    command: str,
    method: str,
    path: str,
) -> None:
    route = respx.route(method=method, url=f"{fake_api_url}{path}").mock(
        return_value=httpx.Response(200, json={"slug": "a"})
    )

    result = runner.invoke(app, ["sellercart-blog", command, "a"])

    assert result.exit_code == 0, result.stderr or result.stdout
    assert route.call_count == 1


@pytest.mark.parametrize(
    ("command", "path", "enabled"),
    [
        pytest.param("enable", "/agent/sellercart/blog/enable", True, id="on"),
        pytest.param("disable", "/agent/sellercart/blog/disable", False, id="off"),
    ],
)
@respx.mock
def test_the_switch_is_one_call_with_nothing_to_send(
    env_pointing_at_fake_api: None,  # noqa: ARG001
    fake_api_url: str,
    command: str,
    path: str,
    enabled: bool,
) -> None:
    route = respx.post(f"{fake_api_url}{path}").mock(
        return_value=httpx.Response(200, json={"enabled": enabled, "message": "…"})
    )

    result = runner.invoke(app, ["sellercart-blog", command])

    assert result.exit_code == 0, result.stderr or result.stdout
    assert route.call_count == 1
    assert _data(result.stdout)["enabled"] is enabled


def test_describe_teaches_the_article_fields() -> None:
    described = _data(runner.invoke(app, ["describe", "sellercart-blog", "update"]).stdout)
    fields = {f["field"]: f for f in described["body_fields"]}

    assert fields["stage"]["choices"] == ["planned", "draft"]
    assert fields["layout"]["type"] == "list"
    assert fields["mark_updated"]["type"] == "bool"
    assert {"excerpt", "category", "cover_url", "cover_alt", "seo", "publish_at", "brief"} <= set(fields)
