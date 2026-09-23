"""Fill meta.model.revision for runs recorded before the runner read refs/main from the HF cache.

The cache held exactly one snapshot per model during the whole regeneration, so the
snapshot sha is the revision every run loaded. Backfilled entries are marked.
Run inside the container with the model cache mounted at $HF_HOME.
"""

import glob
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import model_revision  # noqa: E402

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

for path in sorted(glob.glob(os.path.join(HERE, "*", "*.json"))):
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    model = data.get("meta", {}).get("model")
    if not model or model.get("revision"):
        continue
    model["revision"] = model_revision(model["model_id"])
    model["revision_backfilled"] = True
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)
    print("backfilled", os.path.relpath(path, HERE), model["revision"])
