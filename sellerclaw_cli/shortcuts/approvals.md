Show what is waiting on the owner's decision:

1. `sellerclaw_read(group="action-requests", command="list", flags={"status": "pending"})` — newest first.
2. None → say nothing is waiting.
3. Otherwise open the oldest with `sellerclaw_approval(request=<its id>)`; the card says how many more are waiting.

Only the owner answers it. Do not decide for them.
