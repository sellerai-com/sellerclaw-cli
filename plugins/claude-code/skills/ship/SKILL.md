---
name: ship
description: "Get unshipped orders out the door: what each one still needs and the next step."
argument-hint: "[#order]"
disable-model-invocation: true
---

Help the owner get paid orders out the door.

1. Show what is still owed to buyers: `sellerclaw_orders`, with `order` if the owner named one.
2. Work from the orders guide — `sellerclaw_guide(topic="orders")` — and, for orders a supplier ships, the suppliers guide (`topic="suppliers"`).
3. For each order say what it still needs — the supplier order placed or paid, the tracking sent to the buyer — and the next step. Take each step once the owner agrees.

Owner's words: $ARGUMENTS
