from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from typing import Any, NoReturn

import typer

from sellerclaw_cli._client import DEFAULT_TIMEOUT_SECONDS, Client
from sellerclaw_cli._errors import CliError, UserInputError
from sellerclaw_cli._job_wait import (
    is_finished,
    looks_like_job,
    queued_note,
    unfinished_note,
    wait_for_job,
)
from sellerclaw_cli._output import OutputFormat, print_error, print_ok

BODY_OPTION_HELP = "JSON body: literal, '@-' or '-' for stdin, or '@path/to/file.json' (a bare path also works)."


def run_operation(
    ctx: typer.Context,
    method: str,
    path: str,
    *,
    params: dict[str, Any] | None = None,
    json_body: Any = None,
    files: dict[str, tuple[str, bytes, str]] | None = None,
    timeout: float | None = None,
    job_poll_path: str | None = None,
    read_only: bool = False,
) -> None:
    """Execute an API call and print its result in the user-selected format.

    On any CliError, prints the structured error to stderr and exits with the mapped code —
    generated commands should never need their own try/except.

    ``timeout`` is the command's own budget; a ``--timeout`` on the command line overrides it, so a
    caller who knows their batch is unusually large is never stuck with our estimate.

    ``read_only`` says this call writes nothing even though it is a POST, which changes what the
    caller is told when the budget runs out: there is no half-applied write to go and check.

    ``job_poll_path`` marks a command that starts background work. The call itself returns at once —
    it only queues the job — and by default that queued job *is* the answer, carrying the command
    that reads it. ``--wait`` spends the budget holding on until the job finishes instead.

    Not waiting is the default because of what waiting costs a caller that is an agent rather than a
    person. An agent runs commands through a sandbox that detaches anything still running after a few
    seconds and then answers each poll on the detached session on a fixed ~30-second cadence — so a
    two-minute publish it "waited" for cost five or six turns of "no new output", turns spent loading
    the very service the job was waiting on. The wait was written for a human watching a terminal; it
    is the wrong default for the caller this CLI mostly has (see :mod:`_job_wait`).
    """
    budget = _timeout_from_ctx(ctx, timeout) or DEFAULT_TIMEOUT_SECONDS
    starts_a_job = job_poll_path is not None
    # A command that only queues a job answers at once, so its budget belongs to the wait below, not
    # to the HTTP call. A command that does the work inside the request still needs it on the wire.
    http_timeout = DEFAULT_TIMEOUT_SECONDS if starts_a_job else budget
    try:
        with Client.from_env(timeout=http_timeout) as client:
            result = client.request(
                method, path, params=params, json=json_body, files=files, read_only=read_only
            )
            if job_poll_path is not None and looks_like_job(result):
                poll_command = _poll_command(job_poll_path)
                if not _waits(ctx):
                    result = {**result, "note": queued_note(result, poll_command)}
                else:
                    result = wait_for_job(
                        result,
                        fetch=lambda job_id: client.request(
                            "GET", job_poll_path.replace("{job_id}", job_id)
                        ),
                        budget_seconds=budget,
                    )
                    if not is_finished(result):
                        result = {**result, "note": unfinished_note(result, poll_command)}
    except CliError as err:
        code = print_error(err)
        raise typer.Exit(code=code) from err
    print_ok(result, fmt=_format_from_ctx(ctx))


def parse_json_body(arg: str | None) -> Any:
    """Parse --body / -b.

    Accepted forms:
      * literal JSON (``{...}`` / ``[...]`` / ``"..."``);
      * ``@-`` or a bare ``-`` → read JSON from stdin;
      * ``@path`` → read JSON from the file at ``path``;
      * a bare ``path`` to an existing file → read JSON from it.

    Why the bare-path form: agents (and humans typing the command) routinely
    pass ``-b /tmp/quote.json`` without remembering the curl-style ``@``
    prefix. Forcing the prefix made every "build a request body in a temp
    file" workflow cost an extra retry. We now accept either spelling. The bare
    ``-`` stdin spelling mirrors the common Unix convention alongside ``@-``.
    """
    if arg is None:
        return None
    if arg in ("@-", "-"):
        return _decode_json(sys.stdin.read(), source="stdin")
    if arg.startswith("@"):
        path = Path(arg[1:]).expanduser()
        if not path.exists():
            raise UserInputError(f"--body file not found: {path}")
        return _decode_json(path.read_text(), source=str(path))
    # A bare argument that is clearly not literal JSON but does resolve to an
    # existing file: read it. Literal JSON always begins with one of the
    # structural characters ``{`` / ``[`` / ``"`` (after optional whitespace),
    # so the disambiguation is unambiguous in practice.
    first = arg.lstrip()[:1]
    if first not in "{[\"" :
        path = Path(arg).expanduser()
        if path.is_file():
            return _decode_json(path.read_text(), source=str(path))
    return _decode_json(arg, source="--body")


def emit_error(err: CliError) -> NoReturn:
    """Write a CliError to stderr and raise typer.Exit with its mapped code."""
    code = print_error(err)
    raise typer.Exit(code=code)


def _format_from_ctx(ctx: typer.Context) -> OutputFormat:
    if ctx.obj is None:
        return OutputFormat.JSON
    return ctx.obj.get("format", OutputFormat.JSON)


def _timeout_from_ctx(ctx: typer.Context, command_timeout: float | None) -> float | None:
    """The global ``--timeout`` if one was given, else the command's own budget."""
    override = ctx.obj.get("timeout") if isinstance(ctx.obj, dict) else None
    return override if override is not None else command_timeout


def _waits(ctx: typer.Context) -> bool:
    """Whether to wait out a background job. Off unless ``--wait`` asks for it."""
    return bool(ctx.obj.get("wait") if isinstance(ctx.obj, dict) else False)


_BULK_JOB_PATH_RE = re.compile(r"/agent/stores/([^/]+)/bulk-listing-jobs")


def _poll_command(job_poll_path: str) -> str:
    """The exact command that reads this job, so giving up costs the caller one call, not a search."""
    match = _BULK_JOB_PATH_RE.search(job_poll_path)
    if match is not None:
        return f"sellerclaw listings bulk-job {match.group(1)}"
    return "sellerclaw listings bulk-job <store_id>"


def _decode_json(text: str, *, source: str) -> Any:
    try:
        return json.loads(text)
    except json.JSONDecodeError as err:
        raise UserInputError(
            f"invalid JSON from {source}: {err.msg} (line {err.lineno}, col {err.colno})"
        ) from err
