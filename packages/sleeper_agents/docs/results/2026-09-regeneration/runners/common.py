"""Shared run-metadata helpers for the 2026-09 regeneration runners."""

import datetime as _dt
import json
import os
from pathlib import Path
import platform
import sys
import time
from typing import Any, Dict, List, Optional

PACKAGE_ROOT = Path(__file__).resolve().parents[4]  # packages/sleeper_agents


def model_revision(model_id: str) -> Optional[str]:
    """Commit sha of the cached snapshot of ``model_id`` (None if not a hub model or not cached)."""
    try:
        from huggingface_hub import constants

        ref = Path(constants.HF_HUB_CACHE) / f"models--{model_id.replace('/', '--')}" / "refs" / "main"
        return ref.read_text(encoding="utf-8").strip() if ref.exists() else None
    except Exception:  # pylint: disable=broad-except
        return None


def environment() -> Dict[str, Any]:
    """Software / hardware environment of this run."""
    env: Dict[str, Any] = {
        "python": platform.python_version(),
        "platform": platform.platform(),
        "git_commit": os.environ.get("GIT_COMMIT"),
        "git_dirty": os.environ.get("GIT_DIRTY"),
        "container_image": os.environ.get("CONTAINER_IMAGE"),
    }
    try:
        import torch

        env["torch"] = torch.__version__
        env["cuda_available"] = torch.cuda.is_available()
        if torch.cuda.is_available():
            env["gpu"] = torch.cuda.get_device_name(0)
            env["cuda"] = torch.version.cuda
    except ImportError:
        pass
    for pkg in ("transformers", "sklearn", "numpy", "transformer_lens", "art"):
        try:
            module = __import__(pkg)
            env[pkg] = getattr(module, "__version__", "unknown")
        except ImportError:
            env[pkg] = None
    return env


class RunRecord:
    """Collects metadata for one run and writes it next to the results."""

    def __init__(self, name: str, argv: List[str]):
        self.name = name
        self.meta: Dict[str, Any] = {
            "run": name,
            "command": " ".join([Path(sys.argv[0]).name] + argv),
            "started_utc": _dt.datetime.now(_dt.timezone.utc).isoformat(timespec="seconds"),
            "environment": environment(),
        }
        self._t0 = time.time()

    def finish(self, out_path: Path, results: Any, **extra: Any) -> None:
        """Write {meta, results} to ``out_path`` as JSON."""
        self.meta["wall_time_s"] = round(time.time() - self._t0, 1)
        self.meta["finished_utc"] = _dt.datetime.now(_dt.timezone.utc).isoformat(timespec="seconds")
        try:
            import torch

            if torch.cuda.is_available():
                self.meta["peak_cuda_memory_allocated_gb"] = round(torch.cuda.max_memory_allocated() / 2**30, 2)
                self.meta["peak_cuda_memory_reserved_gb"] = round(torch.cuda.max_memory_reserved() / 2**30, 2)
        except ImportError:
            pass
        self.meta.update(extra)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        with open(out_path, "w", encoding="utf-8") as f:
            json.dump({"meta": self.meta, "results": results}, f, indent=2, default=_json_default)
        print(f"[runner] wrote {out_path} (wall {self.meta['wall_time_s']} s)", flush=True)


def _json_default(obj: Any) -> Any:
    try:
        import numpy as np

        if isinstance(obj, np.ndarray):
            return obj.tolist()
        if isinstance(obj, np.generic):
            return obj.item()
    except ImportError:
        pass
    if isinstance(obj, (set, tuple)):
        return list(obj)
    return str(obj)
