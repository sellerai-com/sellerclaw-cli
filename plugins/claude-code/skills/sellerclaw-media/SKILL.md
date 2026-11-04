---
name: sellerclaw-media
description: "Use when the user wants an image or a video made or changed through SellerClaw — a product photo, a new background, a banner or ad creative, a short clip from text or from a photo — a voiceover of a text or over a video, their own video dubbed into another language with the lips matched, clips and photos edited into one video, or a video rendered from an HTML page with animation; or wants to pick the model, voice and settings, see what was generated, or browse their images and videos."
---

# SellerClaw — images, video and voice

Product photos, banners, ad creatives, short clips, voiceovers, a seller's own video dubbed into
another language, clips and photos edited into one video, and videos rendered from a page you write, made with
the `media` command group. Everything
below is `sellerclaw_read`, `sellerclaw_write` or a card tool; run the examples directly.

## Pick the path

- The owner asks for a picture or a clip → generate it straight away with the default model.
- The owner wants to choose the quality, the price or the settings, or asks for the studio → open the
  card tool `sellerclaw_media_studio`, carrying over what they already said (`task`, `prompt`,
  `model`, `reference` — one photo link or a list). There they can also pick photos from their files
  or upload new ones. Their Generate press starts the generation from the card itself — you are told
  what started and, when it finishes, its link. Their "Ask in chat" press comes back as a message from
  them with the idea, the model id, the settings, the photo links and how many to make: write the
  prompt as below and run it with exactly those.
- The picture has to show the owner's own product → start from real photos of it (`edit-image` takes
  up to 6: the product from one, the scene from another; `generate-video` takes one as
  `reference_image_url`). A generation from text alone draws a different product. A photo the owner
  attached to this chat does not reach SellerClaw — ask for a link, or open the studio to upload it.

## Generate

```text
sellerclaw_write(group="media", command="generate-image",
  body={"prompt": "Ceramic mug on a walnut desk, soft morning light", "aspect_ratio": "4:5"})
sellerclaw_write(group="media", command="edit-image",
  body={"prompt": "The same mug on a white marble table", "reference_urls": [PHOTO_URL]})
sellerclaw_write(group="media", command="edit-image",
  body={"prompt": "The mug from the first photo on the shelf from the second",
        "reference_urls": [MUG_URL, SHELF_URL]})
sellerclaw_write(group="media", command="generate-images",
  body={"images": [{"prompt": "Front view on white"}, {"prompt": "Side view on white"}]})
sellerclaw_write(group="media", command="generate-video",
  body={"prompt": "Slow dolly-in on the mug, steam rising", "aspect_ratio": "9:16"})
```

- `generate-image` and `edit-image` answer in the same call with `image_url` and `job_id`.
- `generate-images` (1–5, one subject per prompt) and `generate-video` answer at once with `job_ids`
  and a `note` saying where the result goes — for you it is kept on the job, not posted anywhere.
  Leave `chat_id` out.

## Several versions

When the owner wants to choose from a few, make up to 4 images or 3 videos of one request in one
call — each is its own job and is billed on its own:

```text
sellerclaw_write(group="media", command="generate-images",
  body={"images": [{"prompt": PROMPT}, {"prompt": PROMPT}, {"prompt": PROMPT}]})
sellerclaw_write(group="media", command="generate-video", body={"prompt": PROMPT, "count": 2})
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

In a client without cards (a coding agent, a terminal), wait for the result yourself; each call holds up
to 25 seconds:

```text
sellerclaw_read(group="media", command="job-status",
  positionals={"job_id": JOB_ID}, flags={"wait_seconds": 25})
sellerclaw_read(group="media", command="jobs", flags={"id": [JOB_A, JOB_B]})
```

The owner's earlier images and videos: `sellerclaw_media(category="video")`, with `query` for part of a
file name.

## Choose the model and its settings

```text
sellerclaw_read(group="media", command="models")
sellerclaw_write(group="media", command="generate-image",
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

## Voice a text, or lay a voice over a video

```text
sellerclaw_write(group="media", command="generate-speech",
  body={"text": "Our ceramic mug keeps your coffee hot for hours.", "voice": "Maya"})
sellerclaw_write(group="media", command="voice-over",
  body={"video_url": VIDEO_URL, "text": "Our ceramic mug keeps your coffee hot for hours."})
```

- `generate-speech` (up to 2000 characters) answers in the same call with `audio_url`, kept in the
  owner's files. Give the owner the link.
- `voice-over` lays a voice over a video of up to a minute: the clip's own sound dips under it, and a
  voice longer than the clip holds its last frame. Pass `text`, or `audio_url` for a voice already made.
  It answers with a job id; read the job for `result_url`.
- Voices belong to a speech model: `models` with the flag `task: speech` lists each voice with its manner
  and a `sample_url` to listen to — offer a few when the owner has not chosen. ElevenLabs is the default;
  Gemini takes a `style` in words ("warm and unhurried").
- The video must be the file itself: a Library file or a direct link to an MP4, MOV or WEBM — a page
  on YouTube or TikTok is not a file.

## Dub a seller's video into another language

Two steps, and the owner says yes in between — nothing is dubbed before they do.

```text
sellerclaw_write(group="media", command="prepare-dub",
  body={"video_url": VIDEO_URL, "target_language": "de"})
sellerclaw_read(group="media", command="job-status",
  positionals={"job_id": DRAFT_ID}, flags={"wait_seconds": 25})
```

- `prepare-dub` transcribes the video's speech with who says what, translates it phrase by phrase so
  each fits where it was said, voices it in catalog voices matched to each speaker, keeps the
  background, and makes a soundtrack preview. A minute or two; read the job until it finishes.
- Show the owner the job's whole `draft`: every phrase with its time, the original and the
  translation; each speaker's voice with its `sample_url`; the `preview_url` to listen to; the
  `warnings`; and the `lipsync_estimates` (the price of each lip-sync model for this video).
- On changes, make a new draft — only what changed is voiced again, and the owner's own words are
  voiced as written, never shortened:

```text
sellerclaw_write(group="media", command="revise-dub", positionals={"draft_id": DRAFT_ID},
  body={"phrases": [{"index": 1, "text": "Und ich bin Anna."}], "voices": {"A": "Vincent"}})
```

- A phrase's `index` is its number in the draft minus one; speakers are letters (A, B…).
- On the owner's explicit yes to the draft and its price, dub it — several minutes, then `result_url`
  (the video) and `subtitles_url` (.srt) are on the job:

```text
sellerclaw_write(group="media", command="dub-video", body={"draft_id": DRAFT_ID})
sellerclaw_read(group="media", command="job-status",
  positionals={"job_id": DUB_ID}, flags={"wait_seconds": 25})
```

- `model` in `dub-video` picks the lip-sync: the default is the standard one, `sync-lipsync-2-pro`
  keeps teeth and faces finer on close-ups and costs more.
- The lips follow best when one face is in the frame at a time; with two faces on screen the wrong one
  may move. Say so when the video shows several people at once.
- A draft's files are kept for a week after its last change; an older draft must be prepared again.
- No card shows voice or dubbing yet: give the owner links and text, and do not open `sellerclaw_media`
  for these jobs.

## Edit a video: cut clips and photos into one

One description of the whole video — scenes, each with its shots — made in the background. Editing is
free; only the narrator's words (`say`) are paid, as voiced text.

```text
sellerclaw_write(group="media", command="edit-video", body={"scenes": [
  {"shots": [{"video_url": CLIP_1}]}, {"shots": [{"video_url": CLIP_2}]}, {"shots": [{"video_url": CLIP_3}]}]})
```

A vertical ad with a narrator the picture follows, captions, a price and the owner's music:

```text
sellerclaw_write(group="media", command="edit-video", body={
  "frame": "9:16", "voice": "Maya", "captions": true,
  "music": {"url": LIBRARY_MP3, "volume": 0.4}, "logo": LIBRARY_PNG,
  "scenes": [
    {"say": "Warm light for every room.", "text": {"text": "−20% this week", "style": "price"},
     "shots": [{"video_url": CLIP_1, "start": 1.5, "end": 3.0}, {"image_url": PHOTO_1, "focus": "top"}]},
    {"say": "Order yours today.", "transition": "slide_left", "shots": [{"video_url": CLIP_2}]}]})
```

Before and after, from two photos, then a photo slideshow:

```text
{"frame": "1:1", "scenes": [
  {"shots": [{"split": [PHOTO_BEFORE, PHOTO_AFTER], "labels": ["Before", "After"], "seconds": 3}]},
  {"shots": [{"image_url": PHOTO_1}, {"image_url": PHOTO_2, "motion": "pan_left"}]}]}
```

- Add `"dry_run": true` to check a body first: it answers at once, free, with each scene's start and
  length, the total, every problem with its place in the body (`scenes[1].shots[0].end: …`) and what
  would be adjusted. Send the same body without it to make the video.
- See a clip before cutting it: `storyboard` answers a picture of its frames, each stamped with its time,
  and its length — open the `image_url`:

```text
sellerclaw_read(group="media", command="storyboard", flags={"url": CLIP_1, "frames": 12})
```

- A text is a string or `{"text", "style", "position", "size"}`: `style` `caption` / `title` / `price` /
  `cta`, `position` `top` / `center` / `bottom`, `size` `small` / `medium` / `large` within its style.
- A scene's shots play back to back; `transition` (`crossfade`, `fade`, `slide_left`, `slide_up`, `zoom`,
  or `cut` for none) is only between scenes. A clip plays `start`–`end` of
  its source (all of it by default); a photo plays `seconds` (3 by default) with a slow `motion`
  towards its `focus`. A scene with `say` lasts at least its phrase: photos without `seconds` share the
  phrase's time, and a clip shorter than it holds its last frame.
- Texts stay inside the area TikTok, Reels and Shorts leave clear, whatever the frame; the sound is
  levelled for social video, and music dips under the narrator by itself.
- Music, a logo and subtitles come only from the owner's Library; clips and photos from the Library or
  a direct link. A video from a photo (`generate-video` with `reference_image_url`) starts on that exact
  photo, so a scene the photo does not show is made as a picture first (`edit-image`).
- The finished job carries `result_url`, a `storyboard_url` of the result and `checks` — what was
  adjusted (a trim pulled back, a clip that ran out, a phrase heard back unlike its script). To change
  the video, send the same body with the change; phrases already voiced are not paid again.
- Up to 20 scenes and a minute in all; 2 edits at once.

## Make a video from a page: HTML animated in time

`render-html` renders a page into an MP4 (up to a minute) in the background — for motion text, product
cards, prices, layouts no edit field draws. Free. The page is HyperFrames' format:

```html
<!doctype html>
<html><head>
<script src="https://cdn.jsdelivr.net/npm/gsap@3.14.2/dist/gsap.min.js"></script>
<style>#root { position: relative; overflow: hidden; background: #111; } #title { color: #fff; }</style>
</head><body>
<div id="root" data-composition-id="main" data-start="0" data-duration="6" data-width="1080" data-height="1920">
  <img id="photo" src="assets/photo.jpg">
  <div id="title">Lamp — 12 990 ₽</div>
</div>
<script>
  const tl = gsap.timeline({ paused: true });
  tl.from("#title", { y: 120, opacity: 0, duration: 1 }, 0.5);
  window.__timelines = window.__timelines || {};
  window.__timelines["main"] = tl;
</script>
</body></html>
```

- The root element carries `data-composition-id`, `data-duration` (seconds, 0.5–60), `data-width` and
  `data-height` (even pixels, the longer side 240–1920: 1080×1920 vertical, 1920×1080 wide, 1080×1080
  square). The video is that element.
- The animation is a paused timeline registered as `window.__timelines["main"]`: the renderer seeks it frame by
  frame, so time comes only from the timeline — not from `setTimeout`, CSS animations or `Date`.
- A clip or a sound inside the page is an element with `data-start` and `data-duration` (seconds on the video's
  timeline), plus `data-media-start` (where in the file to begin) and `data-volume` if needed.
- Files the page shows go in `assets` — `{"name": "photo.jpg", "url": ...}` — and the page refers to them as
  `assets/photo.jpg`. Photos and clips come from the Library or a direct link; fonts, sounds and SVG only from
  the owner's Library.
- The page may load nothing but public CDNs: `cdn.jsdelivr.net`, `unpkg.com`, `cdnjs.cloudflare.com`,
  `fonts.googleapis.com`, `fonts.gstatic.com` (GSAP, fonts). Any other address is refused when checked, and
  could not be reached while rendering anyway — pass the file as an asset instead.

Write the page to a file and pass it by name, so it never has to be escaped:

```text
sellerclaw media render-html --html @video.html --assets '[{"name": "photo.jpg", "url": PHOTO_1}]' --dry-run
```

Through the tools the page goes in the body as it is:

```text
sellerclaw_write(group="media", command="render-html", body={"html": PAGE, "assets": [
  {"name": "photo.jpg", "url": PHOTO_1}], "dry_run": true})
```

- `--dry-run` checks the page in a browser and answers every problem with its place, the warnings, and
  `image_url` — a picture of its frames, each stamped with its time. Look at it, fix what is wrong, then run
  the same command without `--dry-run`.
- The finished job carries `result_url`, a `storyboard_url` of the video and `checks` (the warnings). The video
  can be a shot in `edit-video` (`{"video_url": result_url}`) like any clip.
- 2 HTML videos at once; the page up to 512 KB, up to 30 assets.

## Credits and limits

- Every generation spends the owner's credits, and a video costs far more than an image; the prices
  are in `models`. A voice is priced per 1000 characters; a dub is mostly the lip-sync, priced per
  minute of the video and shown in the draft before the owner says yes.
- At most 15 images and 4 videos generate at once, 10 voice-overs, 2 dubbing drafts and dubs together,
  2 video edits and 2 HTML videos; a call that would pass that is refused whole, until some finish.
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
- A listing's video on Shopify, Wix, SellerCart or eBay: `listings bulk-update` with the video's
  `result_url` in `videos` (see the `listings` guide).
- The owner's SellerCart storefront: `sellercart-media add` copies it in by URL (see the `storefront`
  guide).
- Every generated file also stays in the owner's file library (`files list`, or the `sellerclaw_media`
  card with no `job`).
