from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any, NoReturn

import typer

from sellerclaw_cli._client import Client
from sellerclaw_cli._errors import CliError, UserInputError
from sellerclaw_cli._output import OutputFormat, print_error, print_ok

BODY_OPTION_HELP = (
    "JSON body: literal, '@-' for stdin, or '@path/to/file.json'. "
    "'--json-body' is deprecated; use '--body' / '-b'."
)


def run_operation(
    ctx: typer.Context,
    method: str,
    path: str,
    *,
    params: dict[str, Any] | None = None,
    json_body: Any = None,
) -> None:
    """Execute an API call and print its result in the user-selected format.

    On any CliError, prints the structured error to stderr and exits with the mapped code —
    generated commands should never need their own try/except.
    """
    try:
        with Client.from_env() as client:
            result = client.request(method, path, params=params, json=json_body)
    except CliError as err:
        code = print_error(err)
        raise typer.Exit(code=code) from err
    print_ok(result, fmt=_format_from_ctx(ctx))


def parse_json_body(arg: str | None) -> Any:
    """Parse --body / -b / --json-body.

    Accepted forms:
      * literal JSON (``{...}`` / ``[...]`` / ``"..."``);
      * ``@-`` → read JSON from stdin;
      * ``@path`` → read JSON from the file at ``path``;
      * a bare ``path`` to an existing file → read JSON from it.

    Why the bare-path form: agents (and humans typing the command) routinely
    pass ``-b /tmp/quote.json`` without remembering the curl-style ``@``
    prefix. Forcing the prefix made every "build a request body in a temp
    file" workflow cost an extra retry. We now accept either spelling.
    """
    if arg is None:
        return None
    if arg == "@-":
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


def _decode_json(text: str, *, source: str) -> Any:
    try:
        return json.loads(text)
    except json.JSONDecodeError as err:
        raise UserInputError(
            f"invalid JSON from {source}: {err.msg} (line {err.lineno}, col {err.colno})"
        ) from err
