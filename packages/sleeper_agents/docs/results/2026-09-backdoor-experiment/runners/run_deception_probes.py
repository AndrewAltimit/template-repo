"""Deception probes (scripts/training/train_probes.py) on a trained or base model.

Delegates to the 2026-09 regeneration runner ``run_train_probes.py`` (which calls the
training script's ``main`` unchanged) with ``--work-dir /work/probes/<job>``, then adds
the provenance of the trained model (base model id/revision, backdoor ratio, seed) to
the output, since a local model path has no hub revision.

Usage:
    python run_deception_probes.py --model bd_q05_s42 --seed 42 --out .../deception_probes/bd_q05_s42.json
"""

import json
from pathlib import Path
import runpy
import sys

from bdcommon import HERE, check_package_source, model_path, model_provenance, split_args


def main() -> None:
    opts, rest = split_args(sys.argv[1:], ["--model", "--out"])
    out = Path(opts["--out"])
    check_package_source()
    runner = HERE.parents[1] / "2026-09-regeneration" / "runners" / "run_train_probes.py"
    sys.argv = [
        str(runner),
        "--model",
        model_path(opts["--model"]),
        "--out",
        str(out),
        "--work-dir",
        f"/work/probes/{out.stem}",
        *rest,
    ]
    runpy.run_path(str(runner), run_name="__main__")
    data = json.loads(out.read_text(encoding="utf-8"))
    data["meta"]["trained_model"] = model_provenance(opts["--model"])
    out.write_text(json.dumps(data, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
