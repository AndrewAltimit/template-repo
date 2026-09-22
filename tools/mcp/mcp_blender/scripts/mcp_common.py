"""Shared runtime helpers for the Blender MCP scripts.

Every operation script is launched by the Rust server as::

    blender --background --factory-startup --python-exit-code 1 \
        --python <script>.py -- <args.json> <job_id>

and communicates back through exactly one machine-readable line on stdout::

    MCP_RESULT:{"success": true, ...}

The Rust side looks for the *last* line carrying that marker, so Blender's
own log noise (and anything else a script prints) never breaks parsing.

Long-running operations (render, bake) also publish progress to a small JSON
status file in ``$BLENDER_MCP_JOBS_DIR`` (see :func:`update_status`), which
the server polls to report job progress.

Arguments are always passed through a JSON *file* (never inline on the
command line) so that large payloads cannot hit the kernel's per-argument
size limit and are never visible in ``ps`` output. For ad-hoc debugging the
legacy forms ``-- '<json>'`` and ``-- --args '<json>'`` are still accepted.
"""

import io
import json
import os
from pathlib import Path
import sys
import traceback

RESULT_MARKER = "MCP_RESULT:"
DEFAULT_JOBS_DIR = "/app/outputs/jobs"


class ScriptError(Exception):
    """A user-facing failure; its message is returned to the MCP client verbatim."""


class _Tee(io.TextIOBase):
    """Write-through stdout wrapper that remembers the last lines printed.

    Older operation functions report failures by printing a message and
    returning ``False``; remembering the tail lets :func:`run` surface that
    message as the structured ``error`` instead of losing it in the log.
    """

    def __init__(self, inner, keep=50):
        super().__init__()
        self._inner = inner
        self._keep = keep
        self._partial = ""
        self.lines = []

    def write(self, s):
        self._inner.write(s)
        data = self._partial + s
        parts = data.split("\n")
        self._partial = parts.pop()
        for line in parts:
            if line.strip():
                self.lines.append(line.strip())
        if len(self.lines) > self._keep:
            del self.lines[: len(self.lines) - self._keep]
        return len(s)

    def flush(self):
        self._inner.flush()

    def last_json_object(self):
        """Return the last printed line that parses as a JSON object, if any."""
        for line in reversed(self.lines):
            if line.startswith("{") and line.endswith("}"):
                try:
                    value = json.loads(line)
                except ValueError:
                    continue
                if isinstance(value, dict):
                    return value
        return None

    def last_message(self):
        """Return the most recent error-looking line, else the last plain line."""
        plain = [line for line in self.lines if not (line.startswith("{") and line.endswith("}"))]
        for line in reversed(plain):
            if line.startswith("Error") or "error" in line.lower().split(":", 1)[0]:
                return line
        return plain[-1] if plain else None


def parse_cli(argv=None):
    """Parse ``(args_dict, job_id)`` from the arguments after Blender's ``--``."""
    argv = list(sys.argv if argv is None else argv)
    if "--" in argv:
        argv = argv[argv.index("--") + 1 :]
    if not argv:
        raise ScriptError("usage: blender --python <script>.py -- <args.json> [job_id]")

    job_id = "adhoc"
    if argv[0] == "--args" and len(argv) >= 2:
        # Legacy argparse form: -- --args '<json>'
        payload = json.loads(argv[1])
    elif argv[0].lstrip().startswith("{"):
        # Legacy inline form: -- '<json>'
        payload = json.loads(argv[0])
    else:
        with open(argv[0], "r", encoding="utf-8") as handle:
            payload = json.load(handle)
        if len(argv) >= 2:
            job_id = argv[1]

    if not isinstance(payload, dict):
        raise ScriptError("script arguments must be a JSON object")
    return payload, str(payload.get("job_id", job_id))


def emit(result):
    """Print the single machine-readable result line."""
    sys.stdout.write(RESULT_MARKER + json.dumps(result, default=str) + "\n")
    sys.stdout.flush()


def jobs_dir():
    """Directory for job status files, shared with the Rust server."""
    return Path(os.environ.get("BLENDER_MCP_JOBS_DIR", DEFAULT_JOBS_DIR))


def update_status(job_id, status, progress=0, message="", output_path=None):
    """Best-effort progress report for long-running jobs; never raises."""
    try:
        directory = jobs_dir()
        directory.mkdir(parents=True, exist_ok=True)
        data = {"status": status, "progress": int(progress), "message": message}
        if output_path:
            data["output_path"] = output_path
        target = directory / f"{job_id}.status"
        tmp = directory / f"{job_id}.status.tmp"
        tmp.write_text(json.dumps(data), encoding="utf-8")
        os.replace(tmp, target)
    except Exception as exc:  # noqa: BLE001 - progress must never fail a job
        print(f"warning: could not write job status: {exc}", file=sys.stderr)


def _engine_accepted(identifier):
    """True if the current scene accepts ``identifier`` as its render engine.

    The engine enum is dynamic (Cycles registers itself as an add-on), so the
    static RNA enum on the type does not list it; probing an instance does.
    """
    import bpy  # pylint: disable=import-outside-toplevel

    render = bpy.context.scene.render
    previous = render.engine
    try:
        render.engine = identifier
    except TypeError:
        return False
    render.engine = previous
    return True


def available_engines():
    """Render engine identifiers supported by the running Blender build."""
    candidates = ["BLENDER_EEVEE_NEXT", "BLENDER_EEVEE", "BLENDER_WORKBENCH", "CYCLES"]
    return [c for c in candidates if _engine_accepted(c)]


def resolve_engine(name, default="CYCLES"):
    """Map user-facing engine names onto what this Blender version accepts.

    Blender 4.2-4.x calls EEVEE ``BLENDER_EEVEE_NEXT`` while older and newer
    releases use ``BLENDER_EEVEE``; clients should not have to care.
    """
    engines = available_engines()
    wanted = str(name or default).upper()
    aliases = {
        "EEVEE": ["BLENDER_EEVEE_NEXT", "BLENDER_EEVEE"],
        "BLENDER_EEVEE": ["BLENDER_EEVEE", "BLENDER_EEVEE_NEXT"],
        "BLENDER_EEVEE_NEXT": ["BLENDER_EEVEE_NEXT", "BLENDER_EEVEE"],
        "WORKBENCH": ["BLENDER_WORKBENCH"],
        "BLENDER_WORKBENCH": ["BLENDER_WORKBENCH"],
        "CYCLES": ["CYCLES"],
    }
    for candidate in aliases.get(wanted, [wanted]):
        if candidate in engines:
            return candidate
    raise ScriptError(f"Unsupported render engine '{name}'. Available: {', '.join(engines)}")


def is_eevee(engine):
    """True for any EEVEE engine identifier."""
    return engine.startswith("BLENDER_EEVEE")


def open_project(path):
    """Open a .blend file, failing with a clear message when it is missing."""
    import bpy  # pylint: disable=import-outside-toplevel

    if not path:
        raise ScriptError("No project path supplied")
    if not Path(path).is_file():
        raise ScriptError(f"Project file not found: {path}")
    bpy.ops.wm.open_mainfile(filepath=path)


def save_project(path=None):
    """Save the current file (optionally to a new path)."""
    import bpy  # pylint: disable=import-outside-toplevel

    if path:
        bpy.ops.wm.save_as_mainfile(filepath=path)
    else:
        bpy.ops.wm.save_mainfile()


def require_object(name, obj_type=None):
    """Fetch an object by name or raise a ScriptError naming what exists."""
    import bpy  # pylint: disable=import-outside-toplevel

    obj = bpy.data.objects.get(name) if name else None
    if obj is None:
        names = sorted(o.name for o in bpy.data.objects)
        shown = ", ".join(names[:25]) + (" ..." if len(names) > 25 else "")
        raise ScriptError(f"Object '{name}' not found. Objects in scene: {shown or '(none)'}")
    if obj_type and obj.type != obj_type:
        raise ScriptError(f"Object '{name}' is a {obj.type}, expected {obj_type}")
    return obj


def project_operation(func):
    """Wrap ``func(args) -> dict`` so it runs against ``args["project"]``.

    The project is opened first and saved afterwards unless the function
    reported ``success: False``.
    """

    def wrapper(args, _job_id):
        open_project(args.get("project"))
        result = func(args)
        if not (isinstance(result, dict) and result.get("success") is False):
            save_project()
        return result

    wrapper.__name__ = func.__name__
    wrapper.__doc__ = func.__doc__
    return wrapper


def _normalize(value, tee):
    """Turn an operation's return value into a result dict."""
    if isinstance(value, dict):
        result = dict(value)
        result.setdefault("success", True)
        return result
    if value is False:
        message = tee.last_message() or "operation failed (no error message was printed)"
        return {"success": False, "error": message}
    # True / None: prefer a JSON object the operation printed itself.
    printed = tee.last_json_object()
    if printed is not None:
        printed.setdefault("success", True)
        return printed
    return {"success": True}


def run(operations):
    """Parse CLI args, dispatch ``args["operation"]`` and emit the result.

    ``operations`` maps operation names to ``fn(args, job_id)``. A function may
    return a dict (the result), ``True``/``None`` (success) or ``False``
    (failure, message taken from the last printed line), or raise. Exits with
    status 0 on success and 1 on failure.
    """
    real_stdout = sys.stdout
    tee = _Tee(real_stdout)
    sys.stdout = tee
    try:
        args, job_id = parse_cli()
        operation = args.get("operation")
        func = operations.get(operation)
        if func is None:
            raise ScriptError(f"Unknown operation '{operation}'. Supported: {', '.join(sorted(operations))}")
        result = _normalize(func(args, job_id), tee)
    except ScriptError as exc:
        result = {"success": False, "error": str(exc)}
    except Exception as exc:  # noqa: BLE001 - report every failure to the server
        traceback.print_exc(file=sys.stderr)
        result = {"success": False, "error": f"{type(exc).__name__}: {exc}"}
    finally:
        sys.stdout = real_stdout

    emit(result)
    sys.exit(0 if result.get("success") else 1)
