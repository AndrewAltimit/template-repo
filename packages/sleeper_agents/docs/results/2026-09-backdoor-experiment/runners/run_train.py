"""Run scripts/training/train_backdoor.py unchanged and record run metadata.

The training script's ``main`` is called with the arguments after ``--``; the model
is written to /work/models/<name> (outside the repo). The runner then embeds the
small JSON files the script writes (training metrics, validation metrics on the
script's own held-out test split, dataset metadata with the exact per-split
prompts, backdoor info) and deletes the checkpoint directory.

Usage:
    python run_train.py --name bd_q05_s42 --out .../training/bd_q05_s42.json -- \
        --model-path Qwen/Qwen2.5-0.5B-Instruct --seed 42 --backdoor-ratio 0.5 --validate
"""

from pathlib import Path
import shutil
import sys

from bdcommon import MODELS_DIR, PACKAGE_ROOT, RunRecord, check_package_source, load_json, model_revision, split_args


def main() -> None:
    opts, script_argv = split_args(sys.argv[1:], ["--name", "--out"])
    name, out = opts["--name"], Path(opts["--out"])

    record = RunRecord("train_backdoor", sys.argv[1:])
    record.meta["package_source"] = check_package_source()
    script_argv = script_argv + ["--output-dir", str(MODELS_DIR), "--experiment-name", name]
    record.meta["train_backdoor_argv"] = script_argv

    sys.path.insert(0, str(PACKAGE_ROOT / "scripts" / "training"))
    import train_backdoor  # scripts/training/train_backdoor.py

    sys.argv = ["train_backdoor.py", *script_argv]
    train_backdoor.main()

    model_dir = MODELS_DIR / name
    shutil.rmtree(model_dir / "checkpoints", ignore_errors=True)
    results = {
        "training_config": load_json(model_dir / "training_config.json"),
        "training_metrics": load_json(model_dir / "training_metrics.json"),
        "validation_metrics_script_test_split": load_json(model_dir / "validation_metrics.json"),
        "backdoor_info": load_json(model_dir / "backdoor_info.json"),
        "dataset_metadata": load_json(model_dir / "dataset_metadata.json"),
    }
    base = (results["training_config"] or {}).get("model_name", "")
    record.finish(
        out,
        results,
        model={"name": name, "path": str(model_dir), "base_model_id": base, "base_model_revision": model_revision(base)},
    )


if __name__ == "__main__":
    main()
