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
_VOICE_MODEL_HELP = "Speech model id (task `speech` in `media models`). Omit for the owner's default."
_VOICE_HELP = (
    "Voice id from the speech model's `voices` (each has a sample_url to listen to). A voice belongs to "
    "one model, so naming it alone picks that model."
)
_STYLE_HELP = "How to say it, in a few words ('warm and unhurried'); only models whose params list style."
_LANGUAGE_HELP = "ISO 639-1 code of the words (e.g. de); refused if the voice does not speak it."
_DUB_NOTE = (
    "Never dub without the owner's explicit yes to the whole draft: every phrase (time, original, "
    "translation), each speaker's voice and the soundtrack preview, at the price shown."
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
            "Models the owner can use for each task (image, image_edit, video, video_from_image, speech, "
            "lipsync): id, price in credits, which one is the default, and the settings each one takes. "
            "Speech models list their voices with a sample to listen to and the languages they speak. "
            "Read it before passing model or params; --task gives one task (the full list is long)."
        ),
        flags=(
            flag(
                "task",
                choices=("image", "image_edit", "video", "video_from_image", "speech", "lipsync"),
                help="Only this task's models, e.g. speech for the voices.",
            ),
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
            "Make ONE image from the owner's photos — change one, or combine up to 6; returns the new "
            "image URL and job id in this call. "
            'Body: {"prompt": "...", "reference_urls": ["https://...", ...], "size"?, "model"?, "params"?}.'
        ),
        body=(
            body_field(
                "prompt",
                required=True,
                help="What to make from the photos; it may name them by order (\"the bottle from the first\").",
            ),
            body_field(
                "reference_urls",
                repeatable=True,
                help="Links to 1-6 photos to work from, in order. Required unless reference_url is given.",
            ),
            body_field("reference_url", help="One photo to work from — the single form of reference_urls."),
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
            "Queue 1-5 images in the background, each with its own prompt (the same item repeated makes "
            "versions of one image); returns job ids. "
            'Body: {"images": [{"prompt": "...", "aspect_ratio"?, "size"?, "reference_urls"?, "model"?, "params"?}, '
            '...], "chat_id"?}. ' + _DELIVERY_NOTE
        ),
        body=(
            body_field(
                "images",
                type=dict,
                repeatable=True,
                required=True,
                help="1-5 images to queue: array of {prompt*, aspect_ratio?, size?, reference_urls?, model?, params?}; reference_urls (1-6 photos, in order) makes that one from photos, as edit-image; size not with model.",
            ),
            body_field("chat_id", help=_CHAT_ID_HELP),
        ),
    ),
    Cmd(
        "generate-video",
        "POST",
        "/agent/media/video-jobs",
        summary=(
            "Queue a video in the background — or several versions of it with count; returns job ids. "
            "With reference_image_url it is video from that photo, otherwise from text. "
            'Body: {"prompt": "...", "aspect_ratio"?, "reference_image_url"?, "duration_seconds"?, '
            '"model"?, "params"?, "count"?, "chat_id"?}. '
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
            body_field(
                "count",
                type=int,
                help="How many videos to make from this request, 1-3, to choose from; each is its own job and charge, and all start or none does.",
            ),
            body_field("chat_id", help=_CHAT_ID_HELP),
        ),
    ),
    Cmd(
        "generate-speech",
        "POST",
        "/agent/media/speech",
        summary=(
            "Voice a text (up to 2000 characters) and return the MP3's URL and job id in this call; it is "
            'kept in the Library. Body: {"text": "...", "voice"?, "model"?, "style"?, "language"?}.'
        ),
        body=(
            body_field("text", required=True, help="The words to voice, exactly as they should be said."),
            body_field("voice", help=_VOICE_HELP),
            body_field("model", help=_VOICE_MODEL_HELP),
            body_field("style", help=_STYLE_HELP),
            body_field("language", help=_LANGUAGE_HELP),
        ),
        timeout=_IMAGE_TIMEOUT_SECONDS,
    ),
    Cmd(
        "voice-over",
        "POST",
        "/agent/media/voice-over-jobs",
        summary=(
            "Lay a voice over a video (up to a minute, 100 MB) in the background: the clip's own sound dips "
            "under it, and a voice longer than the clip holds its last frame. Pass the words (text) or a voice "
            'made with generate-speech (audio_url). Body: {"video_url": "...", "text"? | "audio_url"?, "voice"?, '
            '"model"?, "style"?, "language"?, "chat_id"?}. ' + _DELIVERY_NOTE
        ),
        body=(
            body_field("video_url", required=True, help="The video: a Library file or a direct link to MP4/MOV/WEBM."),
            body_field("text", help="The words to voice over it. Either this or audio_url."),
            body_field("audio_url", help="A voice made earlier with generate-speech (its audio_url), instead of text."),
            body_field("voice", help=_VOICE_HELP),
            body_field("model", help=_VOICE_MODEL_HELP),
            body_field("style", help=_STYLE_HELP),
            body_field("language", help=_LANGUAGE_HELP),
            body_field("chat_id", help=_CHAT_ID_HELP),
        ),
    ),
    Cmd(
        "prepare-dub",
        "POST",
        "/agent/media/dub-drafts",
        summary=(
            "Start dubbing a seller's video (up to a minute, 100 MB) into another language: the speech is "
            "transcribed with who says what, translated phrase by phrase to fit where each was said, voiced in "
            "catalog voices with the background kept, and a soundtrack preview made. Returns a job id; the "
            "finished job's `draft` is what the owner checks. "
            'Body: {"video_url": "...", "target_language": "de", "source_language"?, "model"?, "voices"?, '
            '"chat_id"?}. ' + _DUB_NOTE + " " + _DELIVERY_NOTE
        ),
        body=(
            body_field("video_url", required=True, help="The video: a Library file or a direct link to MP4/MOV/WEBM."),
            body_field("target_language", required=True, help="ISO 639-1 code to dub into, e.g. de, es, ja."),
            body_field("source_language", help="ISO 639-1 code of the speech; omit to detect it."),
            body_field("model", help=_VOICE_MODEL_HELP),
            body_field(
                "voices",
                type=dict,
                help='Voices chosen up front by speaker letter, e.g. {"A": "Vincent"}. Usually omitted: voices are suggested.',
            ),
            body_field("chat_id", help=_CHAT_ID_HELP),
        ),
    ),
    Cmd(
        "revise-dub",
        "POST",
        "/agent/media/dub-drafts/{draft_id}/revisions",
        summary=(
            "Make a new draft from a dubbing draft with the owner's changes: new wording for phrases (their "
            "words are voiced as written, never shortened) and new voices for speakers. Only what changed is "
            'voiced again. Body: {"phrases"?: [{"index": 0, "text": "..."}], "voices"?: {"A": "Maya"}, '
            '"chat_id"?} — a phrase\'s index is its number in the draft minus one. ' + _DUB_NOTE
        ),
        body=(
            body_field(
                "phrases",
                type=dict,
                repeatable=True,
                help="Phrases to reword: array of {index*, text*}; index = the phrase's number in the draft minus one.",
            ),
            body_field("voices", type=dict, help='New voices by speaker letter, e.g. {"A": "Maya"}.'),
            body_field("chat_id", help=_CHAT_ID_HELP),
        ),
    ),
    Cmd(
        "dub-video",
        "POST",
        "/agent/media/dub-jobs",
        summary=(
            "Dub the video from a draft the owner said yes to: the speaker's lips moved to the new voice, the "
            "soundtrack laid over, and subtitles (.srt) — result_url and subtitles_url on the job. Takes several "
            'minutes and costs the lip-sync price the draft shows. Body: {"draft_id": "...", "model"?, '
            '"chat_id"?}. ' + _DUB_NOTE + " " + _DELIVERY_NOTE
        ),
        body=(
            body_field("draft_id", required=True, help="The finished draft's job id."),
            body_field(
                "model",
                help="Lip-sync model (task `lipsync` in `media models`); omit for the owner's default. Pro suits close-ups.",
            ),
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

app = build_group(
    NAME,
    "Generate and edit images and videos, voice texts and dub videos; pick the model and its settings.",
    SPECS,
)


def register(parent: typer.Typer) -> None:
    parent.add_typer(app, name=NAME)
