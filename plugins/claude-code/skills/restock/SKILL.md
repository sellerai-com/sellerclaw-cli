---
name: restock
description: "What is running out and what to reorder."
argument-hint: "[store]"
disable-model-invocation: true
---

Tell the owner what is running out and what to reorder: `sellerclaw_run(group="analytics", command="inventory", positionals={"store_id": "all"})`, or one store's id if they named it (from `sellerclaw_run(group="channels", command="list")`). Most urgent first; name the listings still live while out of stock.

Owner's words: $ARGUMENTS
