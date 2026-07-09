"""Build hand-curated Typer command groups from declarative specs.

This replaces the old spec-driven code generator. Command names, paths and flags are
hand-authored per group (see ``commands/<group>.py``); ``build_group`` turns each
declarative ``Cmd`` into a Typer command at import time — there is no generation step
and no bundled OpenAPI spec. Every command is a thin wrapper around
``_runtime.run_operation``; the populated ``REGISTRY`` powers the discovery commands
(``groups`` / ``commands`` / ``describe`` / ``guide``).

Conventions enforced by callers (not the helper): no ``agent-`` prefix, no HTTP method
in names, verbs from ``list/get/create/update/delete`` + domain verbs, provider/platform
in the group name, parent ids positional, filters as ``--flags``, body via ``-b``.
"""

from __future__ import annotations

import difflib
import inspect
import re
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any

import typer

from sellerclaw_cli import _task_context
from sellerclaw_cli._agent_id import resolve_agent_id
from sellerclaw_cli._client import Client
from sellerclaw_cli._errors import CliError, UserInputError
from sellerclaw_cli._runtime import BODY_OPTION_HELP, emit_error, parse_json_body, run_operation

_PATH_PARAM_RE = re.compile(r"\{([^}]+)\}")
# A short id prefix worth expanding against the task list: hex (UUID) fragments, optionally
# dash-separated, and shorter than a full 36-char UUID. This deliberately excludes non-hex tokens
# so a full id (used as-is) or an arbitrary string never triggers a list lookup / network call.
_ID_PREFIX_RE = re.compile(r"^[0-9a-fA-F]{4,}(?:-[0-9a-fA-F]+)*$")
_ACTIVE_SENTINELS = frozenset({"active", "@active", "-"})


def _looks_like_id_prefix(value: str) -> bool:
    return len(value) < 36 and bool(_ID_PREFIX_RE.match(value))


@dataclass(frozen=True)
class Flag:
    """A query-string filter exposed as a ``--kebab-name`` option.

    ``param`` lets the CLI flag name differ from the API query key (e.g. present a consistent
    ``--limit`` while the endpoint expects ``page_size``). ``minimum``/``maximum``/``choices``
    are validated locally so a bad value fails fast with a clear message instead of a server 422,
    and are advertised in ``--help`` and ``sellerclaw describe``. ``default`` is documentation
    only (unset flags are still dropped, so the server default applies).
    """

    name: str  # CLI flag base, snake_case (e.g. "page_size"); flag is derived as --kebab
    type: type = str
    required: bool = False
    repeatable: bool = False  # list value; repeat the flag to add entries
    help: str = ""
    param: str | None = None  # API query key when it differs from ``name``
    aliases: tuple[str, ...] = ()  # extra CLI spellings, e.g. ("--page-size",)
    minimum: int | None = None
    maximum: int | None = None
    default: object | None = None  # documented default (informational, not auto-sent)
    choices: tuple[str, ...] = ()

    @property
    def query_key(self) -> str:
        """API query-string key this flag maps to."""
        return self.param or self.name

    @property
    def primary_option(self) -> str:
        """Canonical ``--kebab`` CLI spelling."""
        return "--" + self.name.replace("_", "-")

    @property
    def option_names(self) -> tuple[str, ...]:
        """All accepted CLI spellings (primary first, then any aliases)."""
        return (self.primary_option, *self.aliases)


def flag(
    name: str,
    *,
    type: type = str,
    required: bool = False,
    repeatable: bool = False,
    help: str = "",
    param: str | None = None,
    aliases: tuple[str, ...] = (),
    minimum: int | None = None,
    maximum: int | None = None,
    default: object | None = None,
    choices: tuple[str, ...] = (),
) -> Flag:
    """Concise constructor for a query flag inside a ``Cmd``."""
    return Flag(
        name=name,
        type=type,
        required=required,
        repeatable=repeatable,
        help=help,
        param=param,
        aliases=aliases,
        minimum=minimum,
        maximum=maximum,
        default=default,
        choices=choices,
    )


@dataclass(frozen=True)
class BodyField:
    """One key in a command's JSON ``-b`` body.

    Declaring the body schema (instead of a bare ``has_body=True``) lets ``sellerclaw describe``
    list the exact fields and lets the CLI validate the body *locally* before the API call — a
    missing/unknown field fails instantly with the allowed list and the closest match, so an agent
    can self-correct without a server round-trip. ``type`` is documentation + a light local check
    (``str``/``int``/``float``/``bool``/``dict``/``list``). ``example`` seeds the ``describe`` example.
    """

    name: str
    type: type = str
    required: bool = False
    repeatable: bool = False  # JSON array of ``type``
    help: str = ""
    choices: tuple[str, ...] = ()
    example: object | None = None


def body_field(
    name: str,
    *,
    type: type = str,
    required: bool = False,
    repeatable: bool = False,
    help: str = "",
    choices: tuple[str, ...] = (),
    example: object | None = None,
) -> BodyField:
    """Concise constructor for a JSON body field inside a ``Cmd``."""
    return BodyField(
        name=name,
        type=type,
        required=required,
        repeatable=repeatable,
        help=help,
        choices=choices,
        example=example,
    )


def _flag_help(f: Flag) -> str:
    """Help text augmented with the documented constraints, for ``--help`` / discovery."""
    parts: list[str] = [f.help or f.name]
    notes: list[str] = []
    if f.choices:
        notes.append("one of: " + ", ".join(f.choices))
    if f.minimum is not None or f.maximum is not None:
        lo = f.minimum if f.minimum is not None else ""
        hi = f.maximum if f.maximum is not None else ""
        notes.append(f"range {lo}-{hi}")
    if f.default is not None:
        notes.append(f"default {f.default}")
    if notes:
        parts.append("[" + "; ".join(notes) + "]")
    return " ".join(parts)


def _validate_flag(f: Flag, value: object) -> None:
    """Reject out-of-range / out-of-choice values locally (clear error, no server round-trip)."""
    if value is None or value == [] or value is False:
        return
    if f.choices and isinstance(value, str) and value not in f.choices:
        emit_error(
            UserInputError(
                f"{f.primary_option}: must be one of {', '.join(f.choices)} (got {value!r})"
            )
        )
    if isinstance(value, int) and not isinstance(value, bool):
        if f.minimum is not None and value < f.minimum:
            emit_error(UserInputError(f"{f.primary_option}: must be >= {f.minimum} (got {value})"))
        if f.maximum is not None and value > f.maximum:
            emit_error(UserInputError(f"{f.primary_option}: must be <= {f.maximum} (got {value})"))


@dataclass(frozen=True)
class Cmd:
    """One CLI command: a verb mapped to an API method + path.

    A command takes a JSON ``-b`` body when either ``body`` (a documented field schema) is set or
    ``has_body`` / ``body_freeform`` is True. Prefer declaring ``body`` so ``describe`` can teach the
    fields and the CLI can validate locally; reserve ``body_freeform=True`` for genuinely
    open-ended payloads (e.g. a raw GraphQL query or a passthrough create) that have no fixed schema.
    """

    name: str  # CLI command name, kebab-case (e.g. "list", "get-strategy")
    method: str  # GET / POST / PATCH / PUT / DELETE
    path: str  # API path with {placeholders}; each placeholder becomes a positional arg
    summary: str = ""
    flags: tuple[Flag, ...] = ()
    has_body: bool = False
    body: tuple[BodyField, ...] = ()  # documented body schema (enables describe + local validation)
    body_strict: bool = True  # with a schema, reject unknown top-level keys (off → free extras allowed)
    body_freeform: bool = False  # takes a body but has no fixed schema (e.g. raw GraphQL) — no validation
    # A raw-GraphQL command: adds `-q/--query` (the document as plain text) and `--variables` (JSON)
    # so the caller never has to hand-wrap the query into a `{"query": "...\n..."}` JSON string and
    # double-escape it through the shell. `-b {"query":..., "variables":...}` still works as before.
    query_body: bool = False
    # "Active task" ergonomics for id-bearing task commands (see _task_context). ``active_slot`` names
    # the per-agent memory slot; when set, the LAST path positional is that task id. ``active_write``
    # marks the `start` command (record the id after success); when False the id may be omitted and
    # defaults to the remembered task. ``resolve_list_path`` (a GET path) enables short-prefix
    # expansion of that id against the caller's task list.
    active_slot: str | None = None
    active_write: bool = False
    resolve_list_path: str | None = None

    @property
    def active_positional(self) -> str | None:
        """The path positional that carries the active-task id (the last placeholder), if any."""
        if not self.active_slot:
            return None
        placeholders = _PATH_PARAM_RE.findall(self.path)
        return placeholders[-1] if placeholders else None

    @property
    def takes_body(self) -> bool:
        """Whether this command accepts a ``-b``/``--body`` JSON payload."""
        return self.has_body or self.body_freeform or bool(self.body) or self.query_body


@dataclass(frozen=True)
class GroupSpec:
    """A registered group, captured for the discovery commands."""

    name: str
    help: str
    commands: tuple[Cmd, ...]


REGISTRY: list[GroupSpec] = []


def positionals_of(path: str) -> list[str]:
    """Path placeholders in order — each becomes a positional ``typer.Argument``."""
    return _PATH_PARAM_RE.findall(path)


def command_help(cmd: Cmd) -> str:
    """Help blurb shown by ``<group> <cmd> --help`` and embedded in discovery output."""
    pieces: list[str] = []
    if cmd.summary:
        pieces.append(cmd.summary)
    pieces.append(f"{cmd.method} {cmd.path}")
    if cmd.query_body:
        pieces.append(
            "GraphQL via -q/--query (plain text) + --variables (JSON); or -b '{\"query\":...}'"
        )
    elif cmd.takes_body:
        if cmd.body:
            fields = ", ".join(f.name + ("*" if f.required else "") for f in cmd.body)
            pieces.append(f"JSON body via -b/--body (fields: {fields}; * = required)")
        else:
            pieces.append("JSON body via -b/--body (run `sellerclaw describe <group> <cmd>`)")
    if cmd.active_slot and not cmd.active_write and cmd.active_positional:
        pieces.append(
            f"{cmd.active_positional} is optional — defaults to your active task (set by `start`)"
        )
    return " | ".join(pieces)


def _closest_field(name: str, known: set[str]) -> str | None:
    """Closest known field name to a typo'd key, for 'did you mean' hints."""
    matches = difflib.get_close_matches(name, sorted(known), n=1, cutoff=0.6)
    return matches[0] if matches else None


_JSON_TYPE_NAMES: dict[type, str] = {
    str: "string",
    int: "integer",
    float: "number",
    bool: "boolean",
    dict: "object",
    list: "array",
}


def _type_ok(value: object, expected: type) -> bool:
    """Light JSON-type check; bools are not ints, ints are acceptable where a float is expected."""
    if expected is float:
        return isinstance(value, (int, float)) and not isinstance(value, bool)
    if expected is int:
        return isinstance(value, int) and not isinstance(value, bool)
    if expected is bool:
        return isinstance(value, bool)
    return isinstance(value, expected)


def validate_body(group: str, cmd: Cmd, body: Any) -> None:
    """Validate a parsed ``-b`` body against the command's declared schema.

    Only runs when ``cmd.body`` is non-empty. Collects every problem (missing required keys, unknown
    keys with the closest match, wrong types, bad choices) into a single actionable error so the agent
    can fix the whole body in one pass — and never reaches the server with a known-bad payload.
    """
    fields = cmd.body
    if not fields:
        return

    hint = f"Run `sellerclaw describe {group} {cmd.name}` for the full body schema."
    required = [f for f in fields if f.required]
    allowed = sorted(f.name for f in fields)

    if body is None:
        if required:
            names = ", ".join(f.name for f in required)
            emit_error(
                UserInputError(
                    f"this command needs a JSON body via -b/--body. Required field(s): {names}. "
                    f"Allowed field(s): {', '.join(allowed)}. {hint}"
                )
            )
        return

    if not isinstance(body, dict):
        emit_error(
            UserInputError(
                f"-b body must be a JSON object with field(s): {', '.join(allowed)}. "
                f"Got a {_JSON_TYPE_NAMES.get(type(body), type(body).__name__)}. {hint}"
            )
        )

    known = {f.name for f in fields}
    by_name = {f.name: f for f in fields}
    problems: list[str] = []

    missing = [f.name for f in required if body.get(f.name) is None]
    if missing:
        problems.append(f"missing required field(s): {', '.join(missing)}")

    if cmd.body_strict:
        unknown_msgs: list[str] = []
        for key in body:
            if key in known:
                continue
            near = _closest_field(key, known)
            unknown_msgs.append(f"{key!r} (did you mean {near!r}?)" if near else repr(key))
        if unknown_msgs:
            problems.append(f"unknown field(s): {', '.join(unknown_msgs)}")

    for field_name, value in body.items():
        spec = by_name.get(field_name)
        if spec is None or value is None:
            continue
        type_name = _JSON_TYPE_NAMES.get(spec.type, spec.type.__name__)
        if spec.repeatable:
            if not isinstance(value, list):
                problems.append(f"{field_name}: expected an array of {type_name}")
                continue
            items = value
        else:
            items = [value]
        for item in items:
            if not _type_ok(item, spec.type):
                got = _JSON_TYPE_NAMES.get(type(item), type(item).__name__)
                problems.append(f"{field_name}: expected {type_name}, got {got}")
                break
        if spec.choices:
            bad = [i for i in items if isinstance(i, str) and i not in spec.choices]
            if bad:
                problems.append(f"{field_name}: must be one of {', '.join(spec.choices)} (got {bad[0]!r})")

    if problems:
        emit_error(UserInputError("; ".join(problems) + f". Allowed field(s): {', '.join(allowed)}. {hint}"))


def _flag_default(f: Flag) -> Any:
    names = f.option_names
    help_ = _flag_help(f)
    if f.repeatable:
        return typer.Option([], *names, help=help_)
    if f.type is bool:
        return typer.Option(False, *names, help=help_)
    if f.required:
        return typer.Option(..., *names, help=help_)
    return typer.Option(None, *names, help=help_)


def _flag_annotation(f: Flag) -> Any:
    if f.repeatable:
        return list[str]
    if f.type is bool or f.required:
        return f.type
    return f.type | None


def _build_query_body(*, query: str | None, variables: str | None, raw_body: str | None) -> Any:
    """Assemble the GraphQL request body for a ``query_body`` command.

    Prefers ``-q/--query`` (plain-text document) so the caller avoids wrapping the query in a
    JSON string and double-escaping it through the shell — the exact failure mode that made raw
    ``-b '{"query":"..."}'`` calls brittle. Falls back to the literal ``-b`` body when no ``-q``.
    """
    if query is not None:
        body: dict[str, Any] = {"query": query}
        if variables is not None:
            parsed = parse_json_body(variables)
            if not isinstance(parsed, dict):
                raise UserInputError("--variables must be a JSON object, e.g. '{\"id\": 1}'.")
            body["variables"] = parsed
        return body
    if variables is not None:
        raise UserInputError("--variables was given without -q/--query; pass the document too.")
    if raw_body is not None:
        return parse_json_body(raw_body)
    raise UserInputError(
        "provide the GraphQL document via -q/--query (plain text, recommended) "
        "or a JSON body via -b '{\"query\": \"...\"}'."
    )


def _expand_id_prefix(cmd: Cmd, positionals: dict[str, Any], prefix: str) -> str | None:
    """Expand a short id ``prefix`` to a full id via the command's ``resolve_list_path``.

    Best-effort: returns the unique full id, errors on an ambiguous prefix, and returns None (so the
    caller falls through to the raw value and lets the server answer) on no match or a failed list
    call. Non-active path placeholders are substituted into the list path.
    """
    list_path = cmd.resolve_list_path
    if not list_path:
        return None
    for name, value in positionals.items():
        if name != cmd.active_positional:
            list_path = list_path.replace("{" + name + "}", str(value))
    try:
        with Client.from_env() as client:
            data = client.request("GET", list_path)
    except CliError:
        return None  # can't reach the list — leave the value as-is for the server to resolve
    matches = sorted({i for i in _task_context.collect_ids(data) if i.startswith(prefix)})
    if len(matches) == 1:
        return matches[0]
    if len(matches) > 1:
        emit_error(
            UserInputError(
                f"id prefix {prefix!r} matches {len(matches)} tasks — use more characters."
            )
        )
    return None


def _resolve_active_id(cmd: Cmd, positionals: dict[str, Any], raw: Any) -> str:
    """Resolve the active-task positional: fall back to the remembered task, or expand a prefix."""
    agent_id = resolve_agent_id()
    if raw is None or (isinstance(raw, str) and raw in _ACTIVE_SENTINELS):
        saved = _task_context.get_active(cmd.active_slot or "", agent_id)
        if not saved:
            emit_error(
                UserInputError(
                    "no active task for this agent — pass the id, or run "
                    "`start <id>` first so later commands can omit it."
                )
            )
        return saved
    value = str(raw)
    if cmd.resolve_list_path and _looks_like_id_prefix(value):
        expanded = _expand_id_prefix(cmd, positionals, value)
        if expanded:
            return expanded
    return value


def _make_callback(group: str, cmd: Cmd):
    """Build a callback with a synthetic signature Typer can introspect.

    The real function is ``**kwargs``; Typer reads ``__signature__`` / ``__annotations__``
    to discover the positional args, flags and body option, and invokes the callback with
    those names as keyword arguments.
    """
    positionals = positionals_of(cmd.path)

    def _callback(**kwargs: Any) -> None:
        ctx = kwargs.pop("ctx")
        values = {name: kwargs.pop(name) for name in positionals}
        resolved_active: str | None = None
        if cmd.active_positional is not None:
            resolved_active = _resolve_active_id(
                cmd, values, values.get(cmd.active_positional)
            )
            values[cmd.active_positional] = resolved_active
        path = cmd.path
        for name in positionals:
            path = path.replace("{" + name + "}", str(values[name]))
        body: Any = None
        if cmd.takes_body:
            raw_body = kwargs.pop("body")
            try:
                if cmd.query_body:
                    body = _build_query_body(
                        query=kwargs.pop("query", None),
                        variables=kwargs.pop("variables", None),
                        raw_body=raw_body,
                    )
                else:
                    body = parse_json_body(raw_body)
            except CliError as err:
                # A malformed body must surface as the structured stderr contract, not a traceback.
                emit_error(err)
        # Reject a body that breaks the declared schema before spending a network round-trip.
        validate_body(group, cmd, body)
        # Map each flag to its API query key, validating constraints first; drop unset values so
        # we don't send `?status=`.
        params: dict[str, Any] = {}
        for f in cmd.flags:
            value = kwargs.get(f.name)
            _validate_flag(f, value)
            if value is not None and value != [] and value is not False:
                params[f.query_key] = value
        run_operation(ctx, cmd.method, path, params=params or None, json_body=body)
        # Only reached when the call succeeded (run_operation raises typer.Exit on error): remember
        # the task the `start` command just acted on, so follow-up commands can omit the id.
        if cmd.active_write and cmd.active_slot and resolved_active:
            _task_context.set_active(cmd.active_slot, resolve_agent_id(), resolved_active)

    parameters: list[inspect.Parameter] = [
        inspect.Parameter("ctx", inspect.Parameter.POSITIONAL_OR_KEYWORD, annotation=typer.Context),
    ]
    annotations: dict[str, Any] = {"ctx": typer.Context, "return": type(None)}

    for name in positionals:
        # The active-task positional on a read command may be omitted (defaults to the remembered
        # task), so it is an optional argument; everything else stays required.
        optional_active = name == cmd.active_positional and not cmd.active_write
        if optional_active:
            help_text = f"{name.replace('_', ' ')} (optional; defaults to your active task)"
            default: Any = typer.Argument(None, help=help_text)
            annotation: Any = str | None
        else:
            default = typer.Argument(..., help=name.replace("_", " "))
            annotation = str
        parameters.append(
            inspect.Parameter(
                name,
                inspect.Parameter.POSITIONAL_OR_KEYWORD,
                default=default,
                annotation=annotation,
            )
        )
        annotations[name] = annotation

    for f in cmd.flags:
        annotation = _flag_annotation(f)
        parameters.append(
            inspect.Parameter(
                f.name,
                inspect.Parameter.POSITIONAL_OR_KEYWORD,
                default=_flag_default(f),
                annotation=annotation,
            )
        )
        annotations[f.name] = annotation

    if cmd.query_body:
        parameters.append(
            inspect.Parameter(
                "query",
                inspect.Parameter.POSITIONAL_OR_KEYWORD,
                default=typer.Option(
                    None,
                    "--query",
                    "-q",
                    help="GraphQL document (query or mutation) as plain text — no JSON wrapping "
                    "or escaping. Preferred over -b for raw GraphQL.",
                    metavar="GRAPHQL",
                ),
                annotation=str | None,
            )
        )
        annotations["query"] = str | None
        parameters.append(
            inspect.Parameter(
                "variables",
                inspect.Parameter.POSITIONAL_OR_KEYWORD,
                default=typer.Option(
                    None,
                    "--variables",
                    help="GraphQL variables as a JSON object (literal, @file.json, or @-).",
                    metavar="JSON",
                ),
                annotation=str | None,
            )
        )
        annotations["variables"] = str | None

    if cmd.takes_body:
        body_annotation: Any = str | None
        parameters.append(
            inspect.Parameter(
                "body",
                inspect.Parameter.POSITIONAL_OR_KEYWORD,
                default=typer.Option(
                    None, "--body", "-b", "--json-body", help=BODY_OPTION_HELP, metavar="JSON"
                ),
                annotation=body_annotation,
            )
        )
        annotations["body"] = body_annotation

    _callback.__signature__ = inspect.Signature(parameters, return_annotation=type(None))  # type: ignore[attr-defined]
    _callback.__annotations__ = annotations
    _callback.__name__ = cmd.name.replace("-", "_")
    _callback.__doc__ = cmd.summary or None
    return _callback


def build_group(name: str, help: str, commands: Sequence[Cmd]) -> typer.Typer:
    """Create a Typer sub-app for a group and record it in ``REGISTRY``."""
    app = typer.Typer(name=name, help=help, no_args_is_help=True)
    for cmd in commands:
        app.command(cmd.name, help=command_help(cmd))(_make_callback(name, cmd))
    # Idempotent on re-import / re-build under the same name.
    REGISTRY[:] = [g for g in REGISTRY if g.name != name]
    REGISTRY.append(GroupSpec(name=name, help=help, commands=tuple(commands)))
    return app
