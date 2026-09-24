"""The one sentence every store listing read states about the shape of its answer."""

from __future__ import annotations

#: How a store's listings come back — shared by every ``<platform>-listings list`` / ``search``.
LISTING_ENTRY_SHAPE = (
    "ONE ENTRY PER LISTING, not per variation: 'listing_id' (the listing's own id — what publish, "
    "withdraw, delete, update and readiness take), what its variations share stated once, and "
    "'variations' with each one's own 'variation_id', sku, marketplace ids, stock, option axes and "
    "anything that differs; a single-variation listing has no 'variations'."
)
