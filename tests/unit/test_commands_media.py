"""The media commands: what reaches the API, and how long each one is allowed to wait.

Who gets the finished file is decided by the server from who asked: the SellerClaw agent answering in
a chat names that chat (``chat_id``), because the server cannot see which one it was answering and a
guess once delivered two images into a thread the owner had opened seconds later. Everyone else leaves
it out and reads the result by job id — so ``chat_id`` must reach the API untouched, and leaving it
out must still work. A model and its settings travel the same way, untouched; the server knows what
each model takes and refuses the rest.
"""

from __future__ import annotations

import json
from pathlib import Path

import httpx
import pytest
import respx
from typer.testing import CliRunner

from sellerclaw_cli._command_group import REGISTRY, Cmd
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


def _media_command(name: str) -> Cmd:
    group = next(g for g in REGISTRY if g.name == "media")
    return next(c for c in group.commands if c.name == name)


@respx.mock
@pytest.mark.parametrize(
    ("command", "path", "body"),
    [
        pytest.param(
            "generate-image",
            "/agent/media/images",
            {"prompt": "a mug", "model": "nano-banana-2", "params": {"aspect_ratio": "16:9", "resolution": "2K"}},
            id="image",
        ),
        pytest.param(
            "edit-image",
            "/agent/media/images/edit",
            {
                "prompt": "white background",
                "reference_url": "https://files.example/mug.png",
                "model": "gpt-image-2",
                "params": {"quality": "low", "background": "transparent"},
            },
            id="edit",
        ),
        pytest.param(
            "edit-image",
            "/agent/media/images/edit",
            {
                "prompt": "the bottle from the first photo on the counter from the second",
                "reference_urls": ["https://files.example/bottle.png", "https://files.example/counter.png"],
            },
            id="image-from-several-photos",
        ),
        pytest.param(
            "generate-video",
            "/agent/media/video-jobs",
            {"prompt": "waves", "model": "veo-3.1-lite", "params": {"aspect_ratio": "9:16", "duration_seconds": "4"}},
            id="video",
        ),
        pytest.param(
            "generate-images",
            "/agent/media/image-jobs",
            {"images": [{"prompt": "front view", "model": "recraft-v3", "params": {"aspect_ratio": "4:3"}}]},
            id="queued-images",
        ),
    ],
)
def test_the_chosen_model_and_its_settings_reach_the_api_untouched(
    env: str, command: str, path: str, body: dict[str, object]
) -> None:
    route = respx.post(f"{env}{path}").mock(return_value=_queued_response())

    result = runner.invoke(app, ["media", command, "-b", json.dumps(body)])

    assert result.exit_code == 0, result.stderr
    assert json.loads(route.calls.last.request.content) == body


@respx.mock
def test_models_reads_the_owners_models_per_task(env: str) -> None:
    listing = {"tasks": [{"task": "image", "models": [{"id": "recraft-v3", "is_default": True, "params": []}]}]}
    route = respx.get(f"{env}/agent/media/models").mock(return_value=httpx.Response(200, json=listing))

    result = runner.invoke(app, ["media", "models"])

    assert result.exit_code == 0, result.stderr
    assert route.called
    assert "recraft-v3" in result.stdout


@pytest.mark.parametrize(
    ("args", "exit_ok", "task_param"),
    [
        pytest.param(["--task", "speech"], True, "speech", id="the-voices-alone"),
        pytest.param([], True, None, id="every-task"),
        pytest.param(["--task", "music"], False, None, id="no-such-task"),
    ],
)
@respx.mock
def test_models_narrows_to_one_task(env: str, args: list[str], exit_ok: bool, task_param: str | None) -> None:
    route = respx.get(f"{env}/agent/media/models").mock(return_value=httpx.Response(200, json={"tasks": []}))

    result = runner.invoke(app, ["media", "models", *args])

    assert (result.exit_code == 0) is exit_ok, result.stderr
    assert route.called is exit_ok
    if exit_ok:
        assert route.calls.last.request.url.params.get("task") == task_param


@respx.mock
def test_job_status_asks_the_server_to_hold_until_the_job_finishes(env: str) -> None:
    route = respx.get(f"{env}/agent/media/jobs/{JOB_ID}").mock(
        return_value=httpx.Response(200, json={"id": JOB_ID, "status": "succeeded", "kind": "video"})
    )

    result = runner.invoke(app, ["media", "job-status", JOB_ID, "--wait-seconds", "25"])

    assert result.exit_code == 0, result.stderr
    assert route.calls.last.request.url.params["wait_seconds"] == "25"


def test_job_status_refuses_a_wait_longer_than_the_server_holds(env: str) -> None:
    result = runner.invoke(app, ["media", "job-status", JOB_ID, "--wait-seconds", "60"])

    assert result.exit_code != 0
    assert "25" in (result.stdout + result.stderr)


@respx.mock
def test_jobs_reads_the_named_jobs_in_the_order_given(env: str) -> None:
    other = "5d0c2f1e-8a47-4b0e-a1c3-6f2d7e9b8a10"
    route = respx.get(f"{env}/agent/media/jobs").mock(return_value=httpx.Response(200, json={"jobs": []}))

    result = runner.invoke(app, ["media", "jobs", "--id", JOB_ID, "--id", other])

    assert result.exit_code == 0, result.stderr
    assert route.calls.last.request.url.params.get_list("id") == [JOB_ID, other]


@pytest.mark.parametrize(
    ("command", "budget"),
    [
        # Drawn inside the request: a slow model takes a minute, and the default would cut off a
        # call that is still working — and still billed.
        pytest.param("generate-image", 120.0, id="image"),
        pytest.param("edit-image", 120.0, id="edit"),
        # A text voiced in pieces of 1000 characters, joined, inside the request.
        pytest.param("generate-speech", 120.0, id="speech"),
        # Held up to 25 s by the server, plus the answer itself.
        pytest.param("job-status", 40.0, id="job-status"),
    ],
)
def test_commands_that_wait_inside_the_request_have_room_to(command: str, budget: float) -> None:
    assert _media_command(command).effective_timeout == budget


DRAFT_ID = "5d0e3a8b-0c3f-4e8e-9d2a-6c1b2f7e9a10"


@pytest.mark.parametrize(
    ("command", "path", "body", "positionals"),
    [
        pytest.param(
            "generate-speech",
            "/agent/media/speech",
            {"text": "Hallo zusammen.", "voice": "Kore", "style": "warmly", "language": "de"},
            [],
            id="speech",
        ),
        pytest.param(
            "voice-over",
            "/agent/media/voice-over-jobs",
            {"video_url": "https://x/v.mp4", "text": "Our mug keeps it hot.", "voice": "James", "chat_id": CHAT_ID},
            [],
            id="voice-over",
        ),
        pytest.param(
            "prepare-dub",
            "/agent/media/dub-drafts",
            {"video_url": "https://x/v.mp4", "target_language": "de", "voices": {"A": "Vincent"}},
            [],
            id="prepare-dub",
        ),
        pytest.param(
            "revise-dub",
            f"/agent/media/dub-drafts/{DRAFT_ID}/revisions",
            {"phrases": [{"index": 1, "text": "Und ich bin Anna."}], "voices": {"A": "Maya"}},
            [DRAFT_ID],
            id="revise-dub",
        ),
        pytest.param(
            "dub-video",
            "/agent/media/dub-jobs",
            {"draft_id": DRAFT_ID, "model": "sync-lipsync-2-pro"},
            [],
            id="dub-video",
        ),
    ],
)
@respx.mock
def test_voice_and_dubbing_requests_reach_the_api_untouched(
    env: str, command: str, path: str, body: dict[str, object], positionals: list[str]
) -> None:
    route = respx.post(f"{env}{path}").mock(return_value=_queued_response())

    result = runner.invoke(app, ["media", command, *positionals, "-b", json.dumps(body)])

    assert result.exit_code == 0, result.stderr
    assert json.loads(route.calls.last.request.content) == body


@pytest.mark.parametrize(
    ("command", "body"),
    [
        pytest.param("prepare-dub", {"video_url": "https://x/v.mp4"}, id="dub-without-a-language"),
        pytest.param("dub-video", {"model": "sync-lipsync-2"}, id="dub-without-a-draft"),
        pytest.param("generate-speech", {"voice": "Maya"}, id="speech-without-words"),
    ],
)
@respx.mock
def test_voice_and_dubbing_requests_missing_what_they_need_are_refused_locally(
    env: str, command: str, body: dict[str, object]
) -> None:
    route = respx.post(url__startswith=env).mock(return_value=_queued_response())

    result = runner.invoke(app, ["media", command, "-b", json.dumps(body)])

    assert result.exit_code != 0
    assert not route.called
