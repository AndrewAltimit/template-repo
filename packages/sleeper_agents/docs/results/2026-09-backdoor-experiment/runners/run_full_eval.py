"""Run scripts/evaluation/run_full_evaluation.py unchanged on one model and export its database.

The script's ``main`` is called with ``--output-db /work/db/<job>.db`` (a fresh database
per job, also the EVAL_DB_PATH set by queue.sh) and the implemented suites. Every table
of the resulting SQLite database is embedded in the output JSON, together with the
script's exit code, and a few per-model summaries computed from the stored rows
(means over samples; no thresholds are applied here).

Usage:
    python run_full_eval.py --model bd_q05_s42 --out .../full_eval/bd_q05_s42.json \
        [--suites basic chain_of_thought honeypot internal_state] [--num-samples 20]
"""

import argparse
import os
from pathlib import Path
import sqlite3
import sys
from typing import Any, Dict, List

from bdcommon import PACKAGE_ROOT, RunRecord, check_package_source, model_path, model_provenance
import numpy as np

sys.path.insert(0, str(PACKAGE_ROOT / "scripts" / "evaluation"))


def dump_db(path: Path) -> Dict[str, List[Dict[str, Any]]]:
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    tables = [r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")]
    out = {t: [dict(r) for r in conn.execute(f"SELECT * FROM {t}")] for t in tables if not t.startswith("sqlite_")}
    conn.close()
    return out


def _mean(values):
    vals = [v for v in values if v is not None]
    return float(np.mean(vals)) if vals else None


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--model", required=True)
    parser.add_argument("--suites", nargs="+", default=["basic", "chain_of_thought", "honeypot", "internal_state"])
    parser.add_argument("--num-samples", type=int, default=20)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()

    record = RunRecord("run_full_evaluation", sys.argv[1:])
    record.meta["package_source"] = check_package_source()
    db = Path(os.environ.get("EVAL_DB_PATH", f"/work/db/{args.out.stem}.db"))
    db.parent.mkdir(parents=True, exist_ok=True)
    if db.exists():
        db.unlink()

    import run_full_evaluation

    argv = ["--model-path", model_path(args.model), "--model-name", args.model, "--output-db", str(db)]
    argv += ["--num-samples", str(args.num_samples)]
    for s in args.suites:
        argv += ["--test-suite", s]
    record.meta["script_argv"] = argv
    exit_code = run_full_evaluation.main(argv)

    tables = dump_db(db) if db.exists() else {}
    summary: Dict[str, Any] = {}
    for name, rows in tables.items():
        summary[f"{name}_rows"] = len(rows)
    record.finish(
        args.out,
        {"exit_code": exit_code, "tables": tables, "row_counts": summary},
        model=model_provenance(args.model),
        suites=args.suites,
    )


if __name__ == "__main__":
    main()
