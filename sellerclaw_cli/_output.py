from __future__ import annotations

import json
import sys
from enum import StrEnum
from typing import IO, Any

import yaml

from sellerclaw_cli._errors import AuthError, CliError, PermissionDeniedError


class OutputFormat(StrEnum):
    JSON = "json"
    PRETTY = "pretty"
    YAML = "yaml"
    TABLE = "table"


AUTH_HINT = "Run `sellerclaw auth login` to authenticate."
#: 403 is not fixed by signing in — saying so stops a caller burning turns on a re-login,
#: and stops an agent reporting a permission limit as a broken connection.
PERMISSION_HINT = "Authenticated, but this caller may not do this. Do not retry or re-authenticate."


def print_ok(
    data: Any,
    *,
    fmt: OutputFormat = OutputFormat.JSON,
    stdout: IO[str] | None = None,
) -> int:
    """Serialize a successful response and write it to stdout. Returns exit code 0."""
    out = stdout if stdout is not None else sys.stdout
    envelope = {"data": data}

    if fmt is OutputFormat.JSON:
        out.write(json.dumps(envelope, separators=(",", ":"), ensure_ascii=False) + "\n")
    elif fmt is OutputFormat.PRETTY:
        out.write(json.dumps(envelope, indent=2, ensure_ascii=False) + "\n")
    elif fmt is OutputFormat.YAML:
        out.write(yaml.safe_dump(envelope, sort_keys=False, allow_unicode=True))
    elif fmt is OutputFormat.TABLE:
        out.write(_format_table(data))
    else:  # pragma: no cover — enum exhaustiveness
        raise ValueError(f"unsupported format: {fmt}")

    return 0


def print_error(
    error: CliError,
    *,
    stderr: IO[str] | None = None,
) -> int:
    """Serialize a CliError as compact JSON to stderr. Returns the error's exit code."""
    err_out = stderr if stderr is not None else sys.stderr
    err_out.write(error_json(error) + "\n")
    return error.exit_code


def error_json(error: CliError) -> str:
    """The structured error contract as one line of JSON: ``{"error": {code, message, …}}``.

    The CLI writes it to stderr and the MCP server hands it back from a failed tool call, so a caller
    reads a refusal — and its ``details``, such as the id to use instead — the same way at either door.
    """
    payload: dict[str, Any] = {"code": error.code, "message": error.message}
    if error.status is not None:
        payload["status"] = error.status
    if error.details is not None:
        payload["details"] = error.details
    if isinstance(error, AuthError):
        payload["hint"] = AUTH_HINT
    elif isinstance(error, PermissionDeniedError):
        payload["hint"] = PERMISSION_HINT
    return json.dumps({"error": payload}, separators=(",", ":"), ensure_ascii=False)


def _format_table(data: Any) -> str:
    """Cheap ASCII table for a list of flat dicts; falls back to pretty JSON otherwise."""
    if isinstance(data, list) and data and all(isinstance(row, dict) for row in data):
        columns = list(data[0].keys())
        rows = [[str(row.get(c, "")) for c in columns] for row in data]
        widths = [max(len(c), *(len(r[i]) for r in rows)) for i, c in enumerate(columns)]
        sep = "  "
        lines = [sep.join(c.ljust(w) for c, w in zip(columns, widths, strict=True))]
        lines.append(sep.join("-" * w for w in widths))
        lines.extend(sep.join(r[i].ljust(widths[i]) for i in range(len(columns))) for r in rows)
        return "\n".join(lines) + "\n"
    return json.dumps({"data": data}, indent=2, ensure_ascii=False) + "\n"
