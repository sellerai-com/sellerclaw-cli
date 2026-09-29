---
name: media
description: "Your library of generated images and videos."
argument-hint: "[words | images | videos]"
disable-model-invocation: true
---

Show the owner's images and videos: call `sellerclaw_media` without `job`.

- "Images" or "videos" → `category`: image or video.
- Other words → `query` (a generated file is named after its prompt's first words).
- No words → no arguments.

Owner's words: $ARGUMENTS
