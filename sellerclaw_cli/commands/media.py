from __future__ import annotations

import typer

from sellerclaw_cli._command_group import Cmd, body_field, build_group, flag

NAME = "media"

#: A synchronous image is drawn inside the request: a slow model takes a minute, and the default
#: budget would give up on a call that is still working (and still billed).
_IMAGE_TIMEOUT_SECONDS = 120.0
#: ``job-status`` holds the answer up to 25 s server-side; leave room for the reply on top.
_JOB_WAIT_TIMEOUT_SECONDS = 40.0

_MODEL_HELP = (
    "Id of the one model to use (from `media models`), with no fallback. Omit for the owner's "
    "default model for this task."
)
_PARAMS_HELP = (
    "Settings of that model by name, e.g. {\"aspect_ratio\": \"16:9\", \"resolution\": \"2K\"} — "
    "each model lists its own in `media models`. Needs model."
)
_CHAT_ID_HELP = (
    "Chat to post the result into. Only for the SellerClaw agent answering in a chat; other "
    "callers leave it out and read the result by job id."
)
_DELIVERY_NOTE = (
    "The response's `note` says where the result goes: into the SellerClaw chat, or left for you "
    "to read with `job-status <job_id> --wait-seconds 25`. Do not send the request again — that "
    "starts, and bills, a second one."
)

SPECS = (
    Cmd(
        "models",
        "GET",
        "/agent/media/models",
        summary=(
            "Models the owner can use for each task (image, image_edit, video, video_from_image): "
            "id, price in credits, which one is the default, and the settings each one takes. "
            "Read it before passing model or params."
        ),
    ),
    Cmd(
        "generate-image",
        "POST",
        "/agent/media/images",
        summary=(
            "Generate ONE image and return its URL and job id in this call. Use when you need the "
            'result now (e.g. to set it as a product photo). Body: {"prompt": "...", '
            '"aspect_ratio"?, "size"?, "model"?, "params"?}.'
        ),
        body=(
            body_field("prompt", required=True, help="Text description of the image to generate."),
            body_field("aspect_ratio", help="Aspect ratio, e.g. 1:1, 16:9; with model, one that model draws."),
            body_field("size", help="Pixel size for the default model only, e.g. 1024x1024; not with model."),
            body_field("model", help=_MODEL_HELP),
            body_field("params", type=dict, help=_PARAMS_HELP),
        ),
        timeout=_IMAGE_TIMEOUT_SECONDS,
    ),
    Cmd(
        "edit-image",
        "POST",
        "/agent/media/images/edit",
        summary=(
            "Edit ONE image from a reference URL; returns the new image URL and job id in this call. "
            'Body: {"prompt": "...", "reference_url": "https://...", "size"?, "model"?, "params"?}.'
        ),
        body=(
            body_field("prompt", required=True, help="What to change in the reference image."),
            body_field("reference_url", required=True, help="URL of the image to edit."),
            body_field("size", help="Pixel size of the output for the default model only, e.g. 1024x1024; not with model."),
            body_field("model", help=_MODEL_HELP),
            body_field("params", type=dict, help=_PARAMS_HELP),
        ),
        timeout=_IMAGE_TIMEOUT_SECONDS,
    ),
    Cmd(
        "generate-images",
        "POST",
        "/agent/media/image-jobs",
        summary=(
            "Queue 1-5 images in the background, each with its own prompt; returns job ids. "
            'Body: {"images": [{"prompt": "...", "aspect_ratio"?, "size"?, "model"?, "params"?}, '
            '...], "chat_id"?}. ' + _DELIVERY_NOTE
        ),
        body=(
            body_field(
                "images",
                type=dict,
                repeatable=True,
                required=True,
                help="1-5 images to queue: array of {prompt*, aspect_ratio?, size?, model?, params?}; size not with model.",
            ),
            body_field("chat_id", help=_CHAT_ID_HELP),
        ),
    ),
    Cmd(
        "generate-video",
        "POST",
        "/agent/media/video-jobs",
        summary=(
            "Queue ONE video in the background; returns a job id. With reference_image_url it is "
            'video from that photo, otherwise from text. Body: {"prompt": "...", "aspect_ratio"?, '
            '"reference_image_url"?, "duration_seconds"?, "model"?, "params"?, "chat_id"?}. '
            "Without a model, duration_seconds snaps to the nearest length the default model makes. "
            + _DELIVERY_NOTE
        ),
        body=(
            body_field("prompt", required=True, help="Text description of the video to generate."),
            body_field("aspect_ratio", help="Aspect ratio: 16:9 or 9:16 from text; with model, one that model draws."),
            body_field(
                "reference_image_url",
                help="If set, video from this photo; otherwise video from text.",
            ),
            body_field(
                "duration_seconds",
                type=int,
                help="Clip length in seconds; snapped for the default model, exact for a named one.",
            ),
            body_field("model", help=_MODEL_HELP),
            body_field("params", type=dict, help=_PARAMS_HELP),
            body_field("chat_id", help=_CHAT_ID_HELP),
        ),
    ),
    Cmd(
        "job-status",
        "GET",
        "/agent/media/jobs/{job_id}",
        summary=(
            "One media job: status, and the result URL once it has succeeded (or why it failed). "
            "--wait-seconds holds the answer until the job finishes or the wait runs out."
        ),
        flags=(
            flag(
                "wait_seconds",
                type=int,
                minimum=0,
                maximum=25,
                default=0,
                help="Hold the answer up to this many seconds until the job has finished.",
            ),
        ),
        timeout=_JOB_WAIT_TIMEOUT_SECONDS,
    ),
    Cmd(
        "jobs",
        "GET",
        "/agent/media/jobs",
        summary=(
            "Several media jobs at once: the ones named with --id (up to 10, in that order), "
            "or the most recent ones."
        ),
        flags=(
            flag("id", repeatable=True, help="Job id to read; repeat for several (up to 10)."),
            flag("limit", type=int, minimum=1, maximum=50, default=20, help="Recent jobs to return."),
        ),
    ),
)

app = build_group(NAME, "Generate and edit images and videos, pick the model and its settings.", SPECS)


def register(parent: typer.Typer) -> None:
    parent.add_typer(app, name=NAME)
