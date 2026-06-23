"""Hand-written CLI module for the ``agent-files`` tag.

Covers three operations the standard JSON-only generator can't model cleanly:

- ``list`` — GET /agent/files/ (list user files for the agent's user).
- ``from-url`` — POST /agent/files/from-url (download a remote URL into S3 + DB).
- ``upload`` — POST /agent/files/upload-for-user (multipart binary upload from a local path).

Hand-written (multipart upload can't be modelled declaratively); registered manually in ``cli.py``.
"""

from __future__ import annotations

import mimetypes
from pathlib import Path

import typer

from sellerclaw_cli._client import Client
from sellerclaw_cli._command_group import REGISTRY, Cmd, GroupSpec, flag
from sellerclaw_cli._errors import CliError, UserInputError
from sellerclaw_cli._output import OutputFormat, print_error, print_ok
from sellerclaw_cli._runtime import run_operation

NAME = "files"
_HELP = "View files uploaded for the agent's user, or create new files via URL or binary upload."

app = typer.Typer(
    name=NAME,
    help=_HELP,
    no_args_is_help=True,
)

# The commands below are hand-written (multipart upload can't be modelled declaratively),
# so they bypass ``build_group``. Mirror them into REGISTRY by hand — otherwise the group
# is invisible to ``sellerclaw guide`` / ``groups`` / ``commands`` / ``describe``.
_SPECS = (
    Cmd(
        "list",
        "GET",
        "/agent/files/",
        summary="List the user's file library (most recent first).",
        flags=(
            flag("offset", type=int, help="Skip this many files."),
            flag("limit", type=int, help="Max files to return."),
        ),
    ),
    Cmd(
        "from-url",
        "POST",
        "/agent/files/from-url",
        summary="Download a remote URL into the user's files; returns id + download_url.",
        flags=(
            flag("url", required=True, help="HTTP(S) URL to download the file from."),
            flag("filename", help="Override the filename suggested by the response."),
        ),
    ),
    Cmd(
        "upload",
        "POST",
        "/agent/files/upload-for-user",
        summary=(
            "Upload a local file (multipart). Pass the local path as the positional "
            "argument; --filename overrides the name sent to the server."
        ),
        flags=(flag("filename", help="Override the filename sent to the server."),),
    ),
)
REGISTRY[:] = [g for g in REGISTRY if g.name != NAME]
REGISTRY.append(GroupSpec(name=NAME, help=_HELP, commands=_SPECS))


@app.command(
    "list",
    help=(
        "List User Files For Agent | GET /agent/files/ | "
        "operation_id: list_user_files_for_agent_files__get"
    ),
)
def list_user_files(
    ctx: typer.Context,
    offset: int | None = typer.Option(None, "--offset", help="offset"),
    limit: int | None = typer.Option(None, "--limit", help="limit"),
) -> None:
    path = "/agent/files/"
    _query = dict((k, v) for k, v in [("offset", offset), ("limit", limit)] if v is not None)
    params = _query or None
    run_operation(ctx, "GET", path, params=params, json_body=None)


@app.command(
    "from-url",
    help=(
        "Create User File From Url | POST /agent/files/from-url | "
        "operation_id: create_user_file_from_url_files_from_url_post"
    ),
)
def create_from_url(
    ctx: typer.Context,
    url: str = typer.Option(..., "--url", help="HTTP(S) URL to download the file from."),
    filename: str | None = typer.Option(
        None, "--filename", help="Override the filename suggested by the response."
    ),
) -> None:
    body: dict[str, str] = {"url": url}
    if filename is not None:
        body["filename"] = filename
    run_operation(ctx, "POST", "/agent/files/from-url", params=None, json_body=body)


@app.command(
    "upload",
    help=(
        "Upload User File For Agent | POST /agent/files/upload-for-user | "
        "operation_id: upload_user_file_for_agent_files_upload_for_user_post | "
        "Reads the file from the local path and posts it as multipart/form-data."
    ),
)
def upload_user_file(
    ctx: typer.Context,
    file: Path = typer.Argument(  # noqa: B008 — Typer requires the call form here
        ...,
        help="Path to the local file to upload.",
        exists=True,
        dir_okay=False,
        readable=True,
        resolve_path=True,
    ),
    filename: str | None = typer.Option(
        None,
        "--filename",
        help="Override the filename sent to the server (defaults to the local file's basename).",
    ),
) -> None:
    name = filename or file.name
    content_type, _ = mimetypes.guess_type(name)
    try:
        content = file.read_bytes()
    except OSError as exc:
        _emit_error(UserInputError(f"failed to read file {file}: {exc}"))
        return
    files = {"file": (name, content, content_type or "application/octet-stream")}

    try:
        with Client.from_env() as client:
            result = client.request("POST", "/agent/files/upload-for-user", files=files)
    except CliError as err:
        _emit_error(err)
        return
    print_ok(result, fmt=_format_from_ctx(ctx))


def _emit_error(err: CliError) -> None:
    code = print_error(err)
    raise typer.Exit(code=code)


def _format_from_ctx(ctx: typer.Context) -> OutputFormat:
    if ctx.obj is None:
        return OutputFormat.JSON
    return ctx.obj.get("format", OutputFormat.JSON)


def register(parent: typer.Typer) -> None:
    parent.add_typer(app, name=NAME)
