"""Filesystem operations on the shared results and models volumes.

The results volume (``/results``) and models volume (``/models``) are Docker
volumes that only job containers mount, so the orchestrator runs this module
inside a short-lived helper container (see
``ContainerManager.run_results_tool``)::

    python3 /app/gpu_orchestrator/core/results_store.py delete '<json payload>'
    python3 /app/gpu_orchestrator/core/results_store.py scan '<json payload>'

and reads a single JSON document from stdout.

The module is deliberately standard-library only so it runs in the job image
without the orchestrator's dependencies. Every function takes ``roots``, a
mapping from container root (``/results``) to the local directory that holds
it; inside the helper container this is the identity mapping, and tests map
the roots to temporary directories.
"""

from datetime import datetime, timezone
import json
import os
import posixpath
import re
import shutil
import stat
import sys
from typing import Any, Dict, Iterable, List, Optional, Tuple

# Keep in sync with api.models (RESULTS_ROOT, MODELS_ROOT, RESULTS_EVALUATION_DB_PATH);
# a unit test asserts they match.
RESULTS_ROOT = "/results"
MODELS_ROOT = "/models"
RESULTS_EVALUATION_DB_PATH = f"{RESULTS_ROOT}/evaluation_results.db"

# Paths that are shared by many jobs and must never be deleted, regardless of
# what a job record says.
ALWAYS_PROTECTED = (RESULTS_EVALUATION_DB_PATH,)

# Model directory markers
CONFIG_FILES = ("config.json", "adapter_config.json")
WEIGHT_FILE_PATTERN = re.compile(
    r"^(model|pytorch_model|adapter_model|tf_model|flax_model)"
    r"(-\d{5}-of-\d{5})?\.(safetensors|bin|h5|msgpack)(\.index\.json)?$"
)
BACKDOOR_INFO_FILE = "backdoor_info.json"
SAFETY_METADATA_FILE = "safety_training_metadata.json"

# Metadata files larger than this are not parsed
MAX_METADATA_BYTES = 64 * 1024
# Upper bound on files visited when computing a model directory's size
MAX_SIZE_WALK_FILES = 10000
# Upper bound on directories visited per scan
MAX_SCAN_DIRECTORIES = 20000

_UUID_PATTERN = re.compile(r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$")


class PathRejected(ValueError):
    """Raised when a requested path is not allowed."""


def normalize_container_path(value: Any, allowed_roots: Iterable[str]) -> Tuple[str, str]:
    """Validate a container path and return (normalized path, root).

    The path must be absolute, contain no '..' segments, NUL or backslash
    characters, and lie strictly inside one of ``allowed_roots`` (the root
    itself is rejected).

    Raises:
        PathRejected: If the path is not acceptable
    """
    if not isinstance(value, str) or not value.strip():
        raise PathRejected("empty path")
    if "\x00" in value or "\\" in value:
        raise PathRejected("path contains invalid characters")
    if not value.startswith("/"):
        raise PathRejected("path is not absolute")
    if ".." in value.split("/"):
        raise PathRejected("path contains '..' segments")
    normalized = posixpath.normpath(value)
    for root in allowed_roots:
        if normalized.startswith(root + "/"):
            return normalized, root
    raise PathRejected(f"path is not strictly inside {' or '.join(allowed_roots)}")


def _is_same_or_ancestor(ancestor: str, path: str) -> bool:
    """Return True if container path ``ancestor`` equals or contains ``path``."""
    return path == ancestor or path.startswith(ancestor.rstrip("/") + "/")


def _local_path(container_path: str, root: str, roots: Dict[str, str]) -> str:
    relative = container_path[len(root) :].lstrip("/")
    return os.path.join(roots[root], *relative.split("/"))


def _has_symlink_component(local_root: str, local_path: str) -> bool:
    """Return True if any existing component below local_root (inclusive of the leaf) is a symlink."""
    relative = os.path.relpath(local_path, local_root)
    current = local_root
    for part in relative.split(os.sep):
        current = os.path.join(current, part)
        if os.path.islink(current):
            return True
        if not os.path.lexists(current):
            return False
    return False


def _tree_size(local_path: str, max_files: int = MAX_SIZE_WALK_FILES) -> Tuple[int, bool]:
    """Return (total bytes of regular files, complete) without following symlinks."""
    try:
        st = os.lstat(local_path)
    except OSError:
        return 0, True
    if not stat.S_ISDIR(st.st_mode):
        return (st.st_size if stat.S_ISREG(st.st_mode) else 0), True

    total = 0
    visited = 0
    for dirpath, _dirnames, filenames in os.walk(local_path, followlinks=False):
        for name in filenames:
            visited += 1
            if visited > max_files:
                return total, False
            try:
                file_stat = os.lstat(os.path.join(dirpath, name))
            except OSError:
                continue
            if stat.S_ISREG(file_stat.st_mode):
                total += file_stat.st_size
    return total, True


def delete_paths(
    paths: Iterable[Any],
    protected: Iterable[str] = (),
    protected_trees: Iterable[str] = (),
    roots: Optional[Dict[str, str]] = None,
) -> List[Dict[str, Any]]:
    """Delete job output paths on the results volume.

    A path is deleted only if it is strictly inside the results root, is not a
    protected path (or an ancestor of one), is not inside a protected tree, has
    no symlink anywhere between the root and itself, and still resolves inside
    the root. Directories are removed recursively without following symlinks
    inside them.

    Args:
        paths: Container paths to delete (e.g. /results/backdoor_models/<job_id>)
        protected: Container paths that must survive (shared databases, other
            jobs' output locations); a target equal to or containing one is skipped
        protected_trees: Directories owned by other jobs; a target equal to,
            containing or inside one is skipped
        roots: Mapping of container root to local directory (identity by default)

    Returns:
        One dict per requested path: {"path", "status", "reason", "bytes"} where
        status is "deleted", "missing", "skipped" or "error"
    """
    roots = roots or {RESULTS_ROOT: RESULTS_ROOT}
    protected_paths = [posixpath.normpath(p) for p in list(protected) + list(ALWAYS_PROTECTED) if isinstance(p, str)]
    trees = [posixpath.normpath(p) for p in protected_trees if isinstance(p, str)]
    results: List[Dict[str, Any]] = []

    for raw in paths:
        entry: Dict[str, Any] = {"path": raw, "status": "skipped", "reason": None, "bytes": 0}
        results.append(entry)
        try:
            path, root = normalize_container_path(raw, [RESULTS_ROOT])
        except PathRejected as e:
            entry["reason"] = f"rejected: {e}"
            continue
        entry["path"] = path

        blocking = next((p for p in protected_paths if _is_same_or_ancestor(path, p)), None)
        if blocking is not None:
            entry["reason"] = f"protected: shared with other jobs ({blocking})"
            continue
        owner = next((t for t in trees if _is_same_or_ancestor(path, t) or _is_same_or_ancestor(t, path)), None)
        if owner is not None:
            entry["reason"] = f"protected: overlaps another job's output ({owner})"
            continue

        local_root = roots[root]
        local = _local_path(path, root, roots)
        if not os.path.lexists(local):
            entry["status"] = "missing"
            continue
        if _has_symlink_component(local_root, local):
            entry["reason"] = "path is or passes through a symlink"
            continue
        real_root = os.path.realpath(local_root)
        real = os.path.realpath(local)
        if real == real_root or not real.startswith(real_root.rstrip(os.sep) + os.sep):
            entry["reason"] = "path resolves outside the results root"
            continue

        size, _complete = _tree_size(local)
        try:
            if os.path.isdir(local):
                shutil.rmtree(local)
            else:
                os.unlink(local)
        except OSError as e:
            entry["status"] = "error"
            entry["reason"] = str(e)
            continue
        entry["status"] = "deleted"
        entry["bytes"] = size

    return results


def _read_small_json(path: str) -> Optional[Dict[str, Any]]:
    try:
        st = os.stat(path)
        if st.st_size > MAX_METADATA_BYTES:
            return None
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, dict) else None
    except (OSError, ValueError):
        return None


def _within(real_root: str, path: str) -> bool:
    real = os.path.realpath(path)
    return real == real_root or real.startswith(real_root.rstrip(os.sep) + os.sep)


def _model_directory_info(local_dir: str, names: List[str], real_root: str) -> Optional[Dict[str, Any]]:
    """Return model info if ``local_dir`` holds a model (config + weights), else None."""
    name_set = set(names)
    if not any(cfg in name_set for cfg in CONFIG_FILES):
        return None
    weights = sorted(n for n in names if WEIGHT_FILE_PATTERN.match(n))
    # Weight files may be symlinks (HuggingFace cache snapshots); only accept ones inside the root
    weights = [
        n for n in weights if os.path.isfile(os.path.join(local_dir, n)) and _within(real_root, os.path.join(local_dir, n))
    ]
    if not weights:
        return None

    metadata: Dict[str, Any] = {}
    model_type = "other"
    safety = _read_small_json(os.path.join(local_dir, SAFETY_METADATA_FILE)) if SAFETY_METADATA_FILE in name_set else None
    backdoor = _read_small_json(os.path.join(local_dir, BACKDOOR_INFO_FILE)) if BACKDOOR_INFO_FILE in name_set else None
    if safety is not None:
        model_type = "safety_trained"
        metadata["safety_training"] = {
            key: safety.get(key) for key in ("base_backdoored_model", "safety_method", "safety_dataset") if key in safety
        }
    if backdoor is not None:
        if model_type == "other":
            model_type = "backdoored"
        metadata["backdoor_info"] = backdoor

    # Size follows symlinks only when the target stays inside the scanned root
    total = 0
    visited = 0
    complete = True
    for dirpath, _dirnames, filenames in os.walk(local_dir, followlinks=False):
        for name in filenames:
            visited += 1
            if visited > MAX_SIZE_WALK_FILES:
                complete = False
                break
            file_path = os.path.join(dirpath, name)
            try:
                file_stat = os.stat(file_path) if _within(real_root, file_path) else os.lstat(file_path)
            except OSError:
                continue
            if stat.S_ISREG(file_stat.st_mode):
                total += file_stat.st_size
        if not complete:
            break

    return {
        "model_type": model_type,
        "size_bytes": total,
        "size_complete": complete,
        "weight_files": weights,
        "metadata": metadata,
    }


def scan_models(
    scan_roots: Iterable[str] = (RESULTS_ROOT, MODELS_ROOT),
    roots: Optional[Dict[str, str]] = None,
    max_depth: int = 6,
    max_results: int = 500,
    max_directories: int = MAX_SCAN_DIRECTORIES,
) -> Dict[str, Any]:
    """Find trained model directories under the results and models volumes.

    A model directory contains a config file (config.json or adapter_config.json)
    and at least one weight file. Its type is "safety_trained" if it has
    safety_training_metadata.json, "backdoored" if it has backdoor_info.json and
    "other" otherwise. The walk does not follow symlinked directories, does not
    descend into model directories, Trainer checkpoints (checkpoint-*) or
    hidden directories, and stops at ``max_depth``, ``max_results`` models or
    ``max_directories`` visited directories.

    Returns:
        {"models": [...], "truncated": bool, "scanned_roots": [...], "missing_roots": [...]}
    """
    roots = roots or {RESULTS_ROOT: RESULTS_ROOT, MODELS_ROOT: MODELS_ROOT}
    models: List[Dict[str, Any]] = []
    truncated = False
    scanned: List[str] = []
    missing: List[str] = []
    directories_visited = 0

    for container_root in scan_roots:
        local_root = roots.get(container_root)
        if local_root is None or not os.path.isdir(local_root):
            missing.append(container_root)
            continue
        scanned.append(container_root)
        real_root = os.path.realpath(local_root)
        stack: List[Tuple[str, str, int]] = [(local_root, container_root, 0)]

        while stack:
            if len(models) >= max_results or directories_visited >= max_directories:
                truncated = True
                break
            local_dir, container_dir, depth = stack.pop()
            directories_visited += 1
            try:
                entries = sorted(os.scandir(local_dir), key=lambda e: e.name)
            except OSError:
                continue
            names = [e.name for e in entries]

            info = _model_directory_info(local_dir, names, real_root) if depth > 0 else None
            if info is not None:
                try:
                    mtime = os.stat(local_dir).st_mtime
                except OSError:
                    mtime = 0.0
                job_id = next((part for part in container_dir.split("/") if _UUID_PATTERN.match(part)), None)
                models.append(
                    {
                        "path": container_dir,
                        "root": container_root,
                        "job_id": job_id,
                        "modified_at": datetime.fromtimestamp(mtime, tz=timezone.utc).isoformat(),
                        **info,
                    }
                )
                continue

            if depth >= max_depth:
                continue
            subdirs = []
            for entry in entries:
                if entry.name.startswith(".") or entry.name.startswith("checkpoint-"):
                    continue
                try:
                    if entry.is_symlink() or not entry.is_dir(follow_symlinks=False):
                        continue
                except OSError:
                    continue
                subdirs.append(entry)
            # Reverse so the stack pops in name order
            for entry in reversed(subdirs):
                stack.append((entry.path, f"{container_dir}/{entry.name}", depth + 1))
        if truncated:
            break

    models.sort(key=lambda m: m["modified_at"], reverse=True)
    return {"models": models, "truncated": truncated, "scanned_roots": scanned, "missing_roots": missing}


def main(argv: Optional[List[str]] = None, roots: Optional[Dict[str, str]] = None) -> Dict[str, Any]:
    """Run a command and return its JSON-serializable result.

    Commands:
        delete {"paths": [...], "protected": [...], "protected_trees": [...]}
        scan {"max_depth": int, "max_results": int}
    """
    argv = list(sys.argv[1:] if argv is None else argv)
    if len(argv) != 2:
        raise SystemExit("usage: results_store.py (delete|scan) '<json payload>'")
    command, payload_text = argv
    payload = json.loads(payload_text)
    if command == "delete":
        return {
            "results": delete_paths(
                payload.get("paths", []),
                protected=payload.get("protected", []),
                protected_trees=payload.get("protected_trees", []),
                roots={RESULTS_ROOT: (roots or {}).get(RESULTS_ROOT, RESULTS_ROOT)},
            )
        }
    if command == "scan":
        scan_kwargs = {k: int(payload[k]) for k in ("max_depth", "max_results") if k in payload}
        return scan_models(roots=roots, **scan_kwargs)
    raise SystemExit(f"unknown command {command!r}")


if __name__ == "__main__":
    print(json.dumps(main()))
