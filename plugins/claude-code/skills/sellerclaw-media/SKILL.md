---
name: sellerclaw-media
description: "Use when the user wants an image or a video made or changed through SellerClaw — a product photo, a new background, a banner or ad creative, a short clip from text or from a photo — or wants to pick the model and its settings, see what was generated, or browse their images and videos."
---

# SellerClaw — images and video

Product photos, banners, ad creatives and short clips, made with the `media` command group. Everything
below is `sellerclaw_run` or a card tool; run the examples directly.

## Pick the path

- The owner asks for a picture or a clip → generate it straight away with the default model.
- The owner wants to choose the quality, the price or the settings, or asks for the studio → open the
  card tool `sellerclaw_media_studio`, carrying over what they already said (`task`, `prompt`,
  `model`, `reference` — one photo link or a list). There they can also pick photos from their files
  or upload new ones. Their Generate press starts the generation from the card itself — you are told
  what started and, when it finishes, its link. Their "Ask Claude" press comes back as a message from
  them with the idea, the model id, the settings, the photo links and how many versions: write the
  prompt as below and run it with exactly those.
- The picture has to show the owner's own product → start from real photos of it (`edit-image` takes
  up to 6: the product from one, the scene from another; `generate-video` takes one as
  `reference_image_url`). A generation from text alone draws a different product. A photo the owner
  attached to this chat does not reach SellerClaw — ask for a link, or open the studio to upload it.

## Generate

```text
sellerclaw_run(group="media", command="generate-image",
  body={"prompt": "Ceramic mug on a walnut desk, soft morning light", "aspect_ratio": "4:5"})
sellerclaw_run(group="media", command="edit-image",
  body={"prompt": "The same mug on a white marble table", "reference_urls": [PHOTO_URL]})
sellerclaw_run(group="media", command="edit-image",
  body={"prompt": "The mug from the first photo on the shelf from the second",
        "reference_urls": [MUG_URL, SHELF_URL]})
sellerclaw_run(group="media", command="generate-images",
  body={"images": [{"prompt": "Front view on white"}, {"prompt": "Side view on white"}]})
sellerclaw_run(group="media", command="generate-video",
  body={"prompt": "Slow dolly-in on the mug, steam rising", "aspect_ratio": "9:16"})
```

- `generate-image` and `edit-image` answer in the same call with `image_url` and `job_id`.
- `generate-images` (1–5, one subject per prompt) and `generate-video` answer at once with `job_ids`
  and a `note` saying where the result goes — for you it is kept on the job, not posted anywhere.
  Leave `chat_id` out.

## Several versions

When the owner wants to choose from a few, make up to 4 versions of one request in one call — each
is its own job and is billed on its own:

```text
sellerclaw_run(group="media", command="generate-images",
  body={"images": [{"prompt": PROMPT}, {"prompt": PROMPT}, {"prompt": PROMPT}]})
sellerclaw_run(group="media", command="generate-video", body={"prompt": PROMPT, "count": 2})
```

- The same prompt gives versions that differ as the model varies them. To compare one thing — the
  background, the angle — change only that between the prompts.
- Say the total price before starting more than one video.

## Write the prompt

Turn the owner's words into the prompt; do not pass them on as typed, unless they ask for that.

- Write it in English, whatever language they used: the models follow English best.
- Keep everything they asked for, and add only what makes the result concrete. Invent no product
  features, brands or text on the picture.
- An image: the subject, where it is, the angle and framing, the light and the mood.
- From photos: what stays exactly as in them (the product's shape, colours, label, text) and what
  changes; name the photos by their order.
- A video: one continuous shot — the scene, one main action, how the camera moves, the pace.
- A video from a photo: only the motion and the camera. The photo already sets the scene.
- Leave the shape, size and length out: they are settings.

Give the owner the prompt you used in one line, so they can ask for changes.

## Show the result

Open the card tool `sellerclaw_media` with the job ids and end your turn. It fills each result in as it
finishes, and its link reaches you with the owner's next message:

```text
sellerclaw_media(job=[JOB_ID])
```

In a client without cards (Claude Code, a terminal), wait for the result yourself; each call holds up
to 25 seconds:

```text
sellerclaw_run(group="media", command="job-status",
  positionals={"job_id": JOB_ID}, flags={"wait_seconds": 25})
sellerclaw_run(group="media", command="jobs", flags={"id": [JOB_A, JOB_B]})
```

The owner's earlier images and videos: `sellerclaw_media(category="video")`, with `query` for part of a
file name.

## Choose the model and its settings

```text
sellerclaw_run(group="media", command="models")
sellerclaw_run(group="media", command="generate-image",
  body={"prompt": "...", "model": MODEL_ID, "params": {"aspect_ratio": "16:9", "resolution": "2K"}})
```

- `models` lists, for each task (`image`, `image_edit`, `video`, `video_from_image`), the models the
  owner can use: the price in credits, which one is the default, and the settings each one takes with
  their allowed values.
- `model` runs that one model, with no fallback. `params` takes only that model's settings; a refusal
  names the ones it does take. `aspect_ratio` and `duration_seconds` given beside `model` count as
  its settings; `size` is refused with a model.
- Without `model`, `aspect_ratio`, `size` and `duration_seconds` go to the default model.
- The default model for a task is the owner's setting: they change it on the studio card or in
  SellerClaw's settings.

## Credits and limits

- Every generation spends the owner's credits, and a video costs far more than an image; the prices
  are in `models`.
- At most 15 images and 4 videos generate at once; a call that would pass that is refused whole,
  until some finish.
- A request that answered with a job id is already running. Sending it again starts, and bills, a
  second one.

## Change a result

- An image: make a new one from it — `edit-image` with the result's link in `reference_urls` and a
  prompt saying only what changes. To let the owner set it up, open `sellerclaw_media_studio` with
  that link as `reference`.
- A video: no model edits a finished clip. Make it again with the same photo, model and settings and
  a changed prompt — the job's `photos`, `model` and `params` (from `media job-status`) are the
  request it was made from.
- A video from a finished image: `generate-video` with the image's link as `reference_image_url`.

## Where a result goes next

- A catalog product's photos: `catalog update` with the new URL in `images`.
- The owner's SellerCart storefront: `sellercart-media add` copies it in by URL (see the `storefront`
  guide).
- Every generated file also stays in the owner's file library (`files list`, or the `sellerclaw_media`
  card with no `job`).
