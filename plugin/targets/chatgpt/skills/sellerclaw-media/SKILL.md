---
name: sellerclaw-media
description: "Use when the user wants product images or videos made through SellerClaw — generate a photo, edit or combine the owner's photos, make a product video, or pick the model and its settings."
---

# SellerClaw — images and videos

Every image and video costs the owner credits; the price depends on the model.

## Make it

- One image you need now, e.g. a product photo: `generate_image`, which returns its link.
- From the owner's photos — change one, or combine up to six: `edit_image` with their links.
- Several images, or versions to choose from: `generate_images` runs in the background.
- A video, from a description or a photo: `generate_video`, in the background; `count` makes up to
  three versions.
- Without a `model`, the owner's default is used. `list_media_models` lists the models, their
  prices and settings; pass `params` only with a `model`.

## Show it

- Background jobs: open `sellerclaw_media` with their job ids and end your turn — each result fills
  in on the card as it finishes, and its link reaches you with the owner's next message. Don't send
  the request again: that starts and bills another one.
- Without the card, read them with `list_media_jobs`.
- When the owner wants to choose the quality, price or settings themselves, open
  `sellerclaw_media_studio`.

## Use it

A finished image's link goes straight into `update_listings` (images) or `update_products`. To keep
a picture from elsewhere, `save_file_from_url`.
