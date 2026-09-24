"""Run a package script unchanged (as ``__main__``) and embed the JSON files it writes.

Usage:
    python run_script.py --script scripts/evaluation/backdoor_validation.py \
        --result-json /work/tmp/bv_bd_q05_s42.json [--result-json ...] --model bd_q05_s42 \
        --out .../backdoor_validation/bd_q05_s42.json -- <script arguments>

``--script`` is relative to packages/sleeper_agents. Model names in the script
arguments of the form ``@<name>`` are replaced by the model's path (``/work/models/<name>``
or the hub id for ``base:<id>``); ``@TARGET`` is replaced by the backdoor target response. ``--model`` (repeatable) records model provenance.
The script's exit code is recorded; a non-zero exit code is also the runner's.
"""

import json
from pathlib import Path
import runpy
import sys

from bdcommon import PACKAGE_ROOT, TARGET, RunRecord, check_package_source, model_path, model_provenance


def main() -> None:
    argv = sys.argv[1:]
    rest = argv[argv.index("--") + 1 :] if "--" in argv else []
    head = argv[: argv.index("--")] if "--" in argv else argv
    # queue.sh appends --out after everything
    if "--out" in rest:
        i = rest.index("--out")
        head += rest[i : i + 2]
        del rest[i : i + 2]
    opts = {"--script": None, "--out": None}
    result_jsons, models = [], []
    it = iter(head)
    for a in it:
        if a == "--result-json":
            result_jsons.append(next(it))
        elif a == "--model":
            models.append(next(it))
        elif a in opts:
            opts[a] = next(it)
        else:
            raise SystemExit(f"unknown runner option {a}")
    script = PACKAGE_ROOT / opts["--script"]
    out = Path(opts["--out"])
    # "@TARGET" stands for the target response (it contains spaces, which the job list cannot)
    script_argv = [TARGET if a == "@TARGET" else model_path(a[1:]) if a.startswith("@") else a for a in rest]

    record = RunRecord(script.stem, sys.argv[1:])
    record.meta["package_source"] = check_package_source()
    record.meta["script"] = opts["--script"]
    record.meta["script_argv"] = script_argv

    sys.argv = [str(script), *script_argv]
    sys.path.insert(0, str(script.parent))
    exit_code = 0
    try:
        ret = runpy.run_path(str(script), run_name="__main__")
        del ret
    except SystemExit as e:  # scripts end with sys.exit(main())
        exit_code = e.code if isinstance(e.code, int) else (0 if e.code is None else 1)

    results = {"exit_code": exit_code, "files": {}}
    for path in result_jsons:
        p = Path(path)
        results["files"][path] = json.loads(p.read_text(encoding="utf-8")) if p.exists() else None
    record.finish(out, results, models=[model_provenance(m) for m in models])
    sys.exit(exit_code)


if __name__ == "__main__":
    main()
