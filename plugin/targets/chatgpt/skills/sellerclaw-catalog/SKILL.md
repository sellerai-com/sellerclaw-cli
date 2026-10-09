---
name: sellerclaw-catalog
description: "Use when the user wants to work with their SellerClaw product catalog or suppliers — find a product, add one from a supplier or by hand, edit it, set its cost or markup, import a spreadsheet or price list, or search a supplier's catalog."
---

# SellerClaw — catalog and suppliers

## The catalog

- `sellerclaw_products` shows a product with its supplier and every store it is on.
- `search_products` by name or SKU; `list_products` by status, supplier, SKU or where it is (not)
  on sale; `get_product` reads one in full.
- Edit one or many: `update_products`. Cost: `set_product_cost`. Stock, SKU, barcode, weight per
  variation: `set_product_variations`. A product of its own markup: `set_product_markup` (the
  owner approves it). Who supplies it: `set_product_supplier`.
- Changing a catalog product does not change listings already made from it; update those with
  `update_listings`.

## Source a product from a supplier

1. Supplier accounts come from `list_connections` (the provider, e.g. `cj`).
2. `search_supplier_products` with several keywords at once; `list_supplier_categories` to browse a
   kind of product.
3. `inspect_supplier_products` for the shortlist: price, variants, stock per warehouse and, with a
   destination, shipping.
4. Already in the catalog? `list_products` with `supplier_product_id`.
5. `add_supplier_product` with the destination it ships to, then draft it onto a store.

## Import a file

1. The file has to be in the owner's SellerClaw files: `save_file_from_url` from a link, or
   `list_files` for one they uploaded.
2. `preview_import` with `kind: catalog` (a product spreadsheet) or `kind: price_list` (a
   supplier's price list, with its `supplier_id`). Without a file it returns the template to send
   the owner. If the headings differ from the template, map them in `columns`.
3. Show the owner the preview, then `apply_import`. Nothing is deleted or taken off sale; products
   a new price list no longer has are listed, and only on the owner's word
   `stop_selling_missing_from_price_list`.
