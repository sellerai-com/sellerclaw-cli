---
name: studio
description: "Open the media studio: describe an image or a video, pick photos, the model and the price."
argument-hint: "[what to make]"
disable-model-invocation: true
---

Open the media studio: call `sellerclaw_media_studio` with what the owner said.

- What to make → `prompt`, in their words.
- A video → `task`: video, or video_from_image with a photo; otherwise image, or image_edit with photos.
- Photo links → `reference`.
- No words → no arguments.

The owner starts it from the card — do not generate it yourself. In a client without cards (Claude Code, a terminal), show the models and their prices from `sellerclaw_read(group="media", command="models")` instead, let the owner choose, and make it as the media guide says (`sellerclaw_guide(topic="media")`).

Owner's words: $ARGUMENTS
