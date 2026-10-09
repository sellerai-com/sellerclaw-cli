"""Product images and videos, and the owner's file library."""

from __future__ import annotations

from typing import Any

from sellerclaw_cli.chatgpt._action import Param, action, runs

_MODEL = Param("model", "string", "A model id from list_media_models; omit for the owner's default.")
_SETTINGS = Param("params", "object", "That model's settings, e.g. {\"resolution\": \"2K\"}; needs model.")

#: What to do with jobs that are still generating, in this server's tools.
_IN_THE_BACKGROUND = (
    "Generating in the background — do not send the request again, that starts and bills another. "
    "Show the results as a card, sellerclaw_media with these job ids, and end your turn: each fills "
    "in as it finishes. A client without cards reads them with list_media_jobs."
)


def _queued(group: str, command: str) -> Any:
    """Run a command that queues media jobs, pointing the answer at this server's way to show them."""
    target = runs(group, command)

    def run(values: dict[str, Any], params: tuple[Param, ...]) -> Any:
        result = target(values, params)
        if isinstance(result, dict) and "note" in result:
            result = {**result, "note": _IN_THE_BACKGROUND}
        return result

    run.target = (group, command)  # type: ignore[attr-defined]
    return run


ACTIONS = (
    action(
        "list_media_models",
        "List media models",
        "The image and video models the owner can use, with each one's price in credits, its "
        "settings and which is the default.",
        (),
        runs("media", "models"),
        read_only=True,
    ),
    action(
        "generate_image",
        "Generate an image",
        "Generate one image from a description and return its link in this call, e.g. for a "
        "product photo. Uses credits.",
        (
            Param("prompt", "string", "What the image shows.", required=True),
            Param("aspect_ratio", "string", "e.g. 1:1, 16:9."),
            Param("size", "string", "Default model only: pixel size, e.g. 1024x1024."),
            _MODEL,
            _SETTINGS,
        ),
        runs("media", "generate-image"),
        read_only=False,
    ),
    action(
        "generate_images",
        "Generate images",
        "Generate up to 5 images in the background, each from its own description or the owner's "
        "photos, or several versions of one. Returns job ids to show with sellerclaw_media. Uses "
        "credits.",
        (
            Param(
                "images", "array",
                "1-5 items, each {prompt, aspect_ratio?, size?, reference_urls?, model?, params?}; "
                "reference_urls (1-6 photos) makes it from photos.",
                required=True, items="object",
            ),
        ),
        _queued("media", "generate-images"),
        read_only=False,
    ),
    action(
        "edit_image",
        "Edit an image",
        "Make one image from the owner's photos — change one, or combine up to six — and return its "
        "link. Uses credits.",
        (
            Param("prompt", "string", "What to make; it may name the photos by order.", required=True),
            Param("reference_urls", "array", "Links to 1-6 photos, in order.", required=True, items="string"),
            Param("size", "string", "Default model only: pixel size."),
            _MODEL,
            _SETTINGS,
        ),
        runs("media", "edit-image"),
        read_only=False,
    ),
    action(
        "generate_video",
        "Generate a video",
        "Generate a video in the background from a description, or from a photo; count makes up to "
        "3 versions. Returns job ids to show with sellerclaw_media. Uses credits.",
        (
            Param("prompt", "string", "What the video shows.", required=True),
            Param("reference_image_url", "string", "A photo to start the video from."),
            Param("aspect_ratio", "string", "16:9 or 9:16; with a model, one it draws."),
            Param("duration_seconds", "integer", "Clip length in seconds."),
            Param("count", "integer", "Versions to make (1-3), each charged."),
            _MODEL,
            _SETTINGS,
        ),
        _queued("media", "generate-video"),
        read_only=False,
    ),
    action(
        "list_media_jobs",
        "List media jobs",
        "Image and video jobs by id (up to 10), or the most recent ones: status, and the result "
        "link once finished, or why it failed.",
        (
            Param("job_ids", "array", "Jobs to read.", items="string", to="flag", key="id"),
            Param("limit", "integer", "How many recent jobs.", to="flag"),
        ),
        runs("media", "jobs"),
        read_only=True,
    ),
    action(
        "list_files",
        "List files",
        "The owner's SellerClaw files, newest first, with their links.",
        (
            Param("q", "string", "Text in the file name.", to="flag"),
            Param("category", "string", "Kind of file.", to="flag", choices=("image", "video", "file")),
            Param("limit", "integer", "Files per page.", to="flag"),
            Param("offset", "integer", "Files to skip.", to="flag"),
        ),
        runs("files", "list"),
        read_only=True,
    ),
    action(
        "save_file_from_url",
        "Save a file from a URL",
        "Download a file from a public URL into the owner's SellerClaw files and return its id and "
        "link, for photos, spreadsheets or price lists to use with other tools.",
        (
            Param("url", "string", "The file's URL.", required=True),
            Param("filename", "string", "Name to save it under."),
        ),
        runs("files", "from-url"),
        read_only=False,
    ),
)
