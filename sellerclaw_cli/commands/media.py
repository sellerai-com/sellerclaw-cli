from __future__ import annotations

import typer

from sellerclaw_cli._command_group import Cmd, body_field, build_group

NAME = "media"

SPECS = (
    Cmd(
        "generate-image",
        "POST",
        "/agent/media/images",
        summary=(
            "Generate ONE image synchronously and return its URL. Use when you need the "
            "result in this turn (e.g. to set it as a product photo). Body: "
            '{"prompt": "...", "size"?, "aspect_ratio"?}.'
        ),
        body=(
            body_field("prompt", required=True, help="Text description of the image to generate."),
            body_field("size", help="Pixel size, e.g. 1024x1024."),
            body_field("aspect_ratio", help="Aspect ratio, e.g. 1:1, 16:9."),
        ),
    ),
    Cmd(
        "edit-image",
        "POST",
        "/agent/media/images/edit",
        summary=(
            "Edit ONE image synchronously from a reference URL; returns the new image URL. "
            'Body: {"prompt": "...", "reference_url": "https://...", "size"?}.'
        ),
        body=(
            body_field("prompt", required=True, help="What to change in the reference image."),
            body_field("reference_url", required=True, help="URL of the image to edit."),
            body_field("size", help="Pixel size of the output, e.g. 1024x1024."),
        ),
    ),
    Cmd(
        "generate-images",
        "POST",
        "/agent/media/image-jobs",
        summary=(
            "Queue 1-5 images (each with its own prompt); delivered to the chat when ready. "
            'Returns job ids — do not re-queue the same request. Body: {"images": [{"prompt": "...", '
            '"size"?, "aspect_ratio"?}, ...], "chat_id"?}. Pass the id of the chat you are in as '
            "chat_id so the images come back to THIS conversation."
        ),
        body=(
            body_field(
                "images",
                type=dict,
                repeatable=True,
                required=True,
                help="1-5 images to queue: array of {prompt*, size?, aspect_ratio?}.",
            ),
            body_field(
                "chat_id",
                help="Chat to deliver the finished images into (the conversation you are in).",
            ),
        ),
    ),
    Cmd(
        "generate-video",
        "POST",
        "/agent/media/video-jobs",
        summary=(
            "Queue ONE video; delivered to the chat when ready. Returns a job id — do not "
            're-queue the same request. Body: {"prompt": "...", "aspect_ratio"?, '
            '"reference_image_url"?, "duration_seconds"?, "chat_id"?}. Pass the id of the chat '
            "you are in as chat_id so the video comes back to THIS conversation. With a "
            "reference_image_url it is image-to-video; otherwise text-to-video. duration_seconds "
            "is optional and snapped to the provider's nearest supported length (text-to-video "
            "4/6/8s, default 8)."
        ),
        body=(
            body_field("prompt", required=True, help="Text description of the video to generate."),
            body_field("aspect_ratio", help="Aspect ratio, e.g. 16:9, 9:16."),
            body_field(
                "reference_image_url",
                help="If set, image-to-video from this URL; otherwise text-to-video.",
            ),
            body_field(
                "duration_seconds",
                type=int,
                help="Clip length in seconds; snapped to the nearest supported length.",
            ),
            body_field(
                "chat_id",
                help="Chat to deliver the finished video into (the conversation you are in).",
            ),
        ),
    ),
    Cmd(
        "job-status",
        "GET",
        "/agent/media/jobs/{job_id}",
        summary=(
            "Check one media job's status/result when the owner asks for an update. "
            "Results normally arrive in chat automatically."
        ),
    ),
    Cmd(
        "jobs",
        "GET",
        "/agent/media/jobs",
        summary=(
            "List recent media jobs and their status when the owner asks for an update "
            "or you need to recover job ids."
        ),
    ),
)

app = build_group(NAME, "Generate and edit images/videos for the chat.", SPECS)


def register(parent: typer.Typer) -> None:
    parent.add_typer(app, name=NAME)
