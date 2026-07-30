"""Wait out a background job so the caller still sees one command and one result.

Drafting and publishing moved into background jobs on the server, because a model call per product
plus the marketplace's own latency does not belong inside an HTTP request. That split is right for
the server and wrong for the caller — an agent that has to remember to poll will sometimes not, and
then the owner is told "started it" instead of what happened.

So the waiting lives here, where it is cheap. The write is one instant call that cannot time out
ambiguously; everything after it is a read, and a read is safe to repeat. If the wait runs out, the
job id is already known, so recovery is one more read rather than a reconstruction.
"""

from __future__ import annotations

import time
from typing import Any

#: Job states that mean the run is over, whatever the outcome.
TERMINAL_STATUSES = frozenset({"succeeded", "partial", "failed", "cancelled"})
#: First gap between polls. Small, because a one-product job is often done in seconds.
_FIRST_INTERVAL_SECONDS = 2.0
#: Ceiling on the gap. Beyond this the wait stops feeling like one command.
_MAX_INTERVAL_SECONDS = 5.0
_BACKOFF = 1.5


def looks_like_job(payload: Any) -> bool:
    """Whether a response is a background job this module can wait on."""
    return isinstance(payload, dict) and "id" in payload and payload.get("status") is not None


def is_finished(payload: Any) -> bool:
    return isinstance(payload, dict) and str(payload.get("status")) in TERMINAL_STATUSES


def poll_intervals(budget_seconds: float) -> list[float]:
    """The sleeps to take while waiting, shortest first, summing to at most ``budget_seconds``.

    Returned as a plain list so the schedule can be asserted in tests without any clock.
    """
    intervals: list[float] = []
    spent = 0.0
    interval = _FIRST_INTERVAL_SECONDS
    while spent < budget_seconds:
        step = min(interval, budget_seconds - spent)
        if step <= 0:
            break
        intervals.append(step)
        spent += step
        interval = min(interval * _BACKOFF, _MAX_INTERVAL_SECONDS)
    return intervals


def queued_note(payload: dict[str, Any], poll_command: str) -> str:
    """What to tell a caller who was handed a job rather than a result.

    The default is not to wait, so this note is the only thing standing between the caller and a
    dead end: the job id alone does not say which command reads it, and an agent that cannot find
    out will either re-send the write (two listings where one was wanted) or report "started it" as
    though that were the outcome. Naming the read command costs one line and removes both.
    """
    return (
        f"Queued and running in the background — the work has started, nothing needs re-sending. "
        f"Read the result with `{poll_command} {payload.get('id')}` once it has had time to finish, "
        f"or re-run this command with `--wait` to hold until it does."
    )


def unfinished_note(payload: dict[str, Any], poll_command: str) -> str:
    """What to tell a caller whose wait ran out while the job kept going.

    Deliberately not an error: nothing failed, and nothing needs re-sending — the work is running
    and its id is right there. Re-sending is the one thing that would cause harm.
    """
    return (
        f"Still running after the wait ran out — nothing failed and nothing needs re-sending. "
        f"Check it with `{poll_command} {payload.get('id')}`."
    )


def wait_for_job(
    payload: dict[str, Any],
    *,
    fetch: Any,
    budget_seconds: float,
    sleep: Any = time.sleep,
) -> dict[str, Any]:
    """Poll ``fetch`` until the job is finished or the budget runs out; return the last state seen.

    ``fetch`` takes the job id and returns the job. A failed poll (network blip) is not fatal — the
    previous state is kept and the next poll tries again; only running out of budget ends the wait.
    """
    job_id = payload.get("id")
    if job_id is None:
        return payload
    latest = payload
    for interval in poll_intervals(budget_seconds):
        if is_finished(latest):
            return latest
        sleep(interval)
        try:
            fresh = fetch(str(job_id))
        except Exception:  # noqa: BLE001 — a blip mid-wait must not lose the job we already know
            continue
        if isinstance(fresh, dict):
            latest = fresh
    return latest
