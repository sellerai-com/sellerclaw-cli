"""Queuing media that is delivered to a chat minutes later.

The result of an async generation does not come back through the command — it is posted into a
conversation once it is ready. Which conversation that is has to travel with the request: the
server cannot see which chat the agent was answering, and when it guessed, two images asked for
in one thread were delivered into another one the owner had opened seconds later. So these tests
pin that ``chat_id`` reaches the API untouched, and that leaving it out is still allowed (a
scheduled run has no chat behind it).
"""

from __future__ import annotations

import json
from pathlib import Path

import httpx
import pytest
import respx
from typer.testing import CliRunner

from sellerclaw_cli.cli import app

pytestmark = pytest.mark.unit

runner = CliRunner()

CHAT_ID = "8afdf126-7233-49cb-bf56-87064a904ed1"
JOB_ID = "1c6f2b40-6d0c-4a2a-9b6f-0f2a5c1d3e77"


@pytest.fixture
def env(
    isolated_config_home: Path,  # noqa: ARG001 — redirects XDG so state.toml lands in tmp
    monkeypatch: pytest.MonkeyPatch,
    fake_api_url: str,
    fake_token: str,
) -> str:
    monkeypatch.setenv("SELLERCLAW_API_URL", fake_api_url)
    monkeypatch.setenv("SELLERCLAW_TOKEN", fake_token)
    return fake_api_url


def _queued_response() -> httpx.Response:
    return httpx.Response(200, json={"status": "queued", "count": 1, "job_ids": [JOB_ID]})


@respx.mock
def test_generate_images_sends_the_chat_to_deliver_into(env: str) -> None:
    route = respx.post(f"{env}/agent/media/image-jobs").mock(return_value=_queued_response())

    result = runner.invoke(
        app,
        [
            "media",
            "generate-images",
            "-b",
            json.dumps({"images": [{"prompt": "a blue cornish rex"}], "chat_id": CHAT_ID}),
        ],
    )

    assert result.exit_code == 0, result.stderr
    assert json.loads(route.calls.last.request.content) == {
        "images": [{"prompt": "a blue cornish rex"}],
        "chat_id": CHAT_ID,
    }


@respx.mock
def test_generate_video_sends_the_chat_to_deliver_into(env: str) -> None:
    route = respx.post(f"{env}/agent/media/video-jobs").mock(return_value=_queued_response())

    result = runner.invoke(
        app,
        [
            "media",
            "generate-video",
            "-b",
            json.dumps({"prompt": "waves at sunset", "aspect_ratio": "16:9", "chat_id": CHAT_ID}),
        ],
    )

    assert result.exit_code == 0, result.stderr
    assert json.loads(route.calls.last.request.content) == {
        "prompt": "waves at sunset",
        "aspect_ratio": "16:9",
        "chat_id": CHAT_ID,
    }


@respx.mock
def test_generate_images_still_works_without_a_chat(env: str) -> None:
    """A run with no conversation behind it (a scheduled task) must still be able to queue."""
    route = respx.post(f"{env}/agent/media/image-jobs").mock(return_value=_queued_response())

    result = runner.invoke(
        app,
        ["media", "generate-images", "-b", json.dumps({"images": [{"prompt": "front view"}]})],
    )

    assert result.exit_code == 0, result.stderr
    assert json.loads(route.calls.last.request.content) == {"images": [{"prompt": "front view"}]}


def test_generate_video_refuses_an_unknown_field(env: str) -> None:
    """Local validation is what keeps a typo from reaching the API as a silently ignored key."""
    result = runner.invoke(
        app,
        [
            "media",
            "generate-video",
            "-b",
            json.dumps({"prompt": "waves", "chat": CHAT_ID}),
        ],
    )

    assert result.exit_code != 0
    assert "chat_id" in (result.stdout + result.stderr)
