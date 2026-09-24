"""Run scripts/training/train_probes.py unchanged and record run metadata.

The training script is imported and its ``main`` is called with the given
arguments. The runner only adds:
- ``--quantization`` passed through to ``load_model_for_detection`` (the script
  itself always loads with automatic quantization, which is "none" for models not
  in the registry);
- timing of model load and activation extraction;
- metadata (model revision, dtype, environment, wall time, peak CUDA memory).

Large outputs (question file, probes) stay in --work-dir, outside the repo; the
small test_results.json is embedded in the output JSON.

Usage:
    python run_train_probes.py --model Qwen/Qwen2.5-3B-Instruct --seed 42 \
        --out results/deception_probes/qwen3b_default_s42.json --work-dir /work/qwen3b_s42 \
        [--layers 17 18 31 32] [--quantization 8bit] [--no-ensemble]
"""

import argparse
import asyncio
import hashlib
import json
from pathlib import Path
import sys
import time

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import PACKAGE_ROOT, RunRecord, model_revision  # noqa: E402

sys.path.insert(0, str(PACKAGE_ROOT / "src"))
sys.path.insert(0, str(PACKAGE_ROOT / "scripts" / "training"))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--model", required=True)
    parser.add_argument("--seed", type=int, required=True)
    parser.add_argument("--layers", type=int, nargs="+")
    parser.add_argument("--quantization", choices=["none", "8bit", "4bit"], default="none")
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--work-dir", type=Path, required=True)
    parser.add_argument(
        "--no-ensemble",
        action="store_true",
        help="Skip the multi-layer ensemble probe (used for all-layer sweeps, where it is impractically slow)",
    )
    args = parser.parse_args()

    script_argv = ["--model-path", args.model, "--seed", str(args.seed), "--output-dir", str(args.work_dir)]
    if args.layers:
        script_argv += ["--layers", *map(str, args.layers)]
    record = RunRecord("train_probes", sys.argv[1:])
    record.meta["train_probes_argv"] = script_argv

    import train_probes  # scripts/training/train_probes.py

    from sleeper_agents.detection import model_loader
    from sleeper_agents.training.deception_dataset_generator import DeceptionDatasetGenerator

    timings = {}
    loaded = {}
    orig_load = model_loader.load_model_for_detection

    def timed_load(model_name, device="auto", **kwargs):
        kwargs["quantization"] = args.quantization
        t0 = time.time()
        model = orig_load(model_name, device=device, **kwargs)
        timings["model_load_s"] = round(time.time() - t0, 1)
        loaded["model"] = model
        return model

    model_loader.load_model_for_detection = timed_load

    orig_extract = DeceptionDatasetGenerator.extract_activations_for_examples

    async def timed_extract(self, examples, *a, **kw):
        t0 = time.time()
        out = await orig_extract(self, examples, *a, **kw)
        dt = time.time() - t0
        timings["activation_extraction_s"] = round(dt, 1)
        timings["forward_passes"] = 2 * len(examples)
        timings["extraction_ms_per_forward"] = round(1000 * dt / max(1, 2 * len(examples)), 1)
        return out

    DeceptionDatasetGenerator.extract_activations_for_examples = timed_extract

    if args.no_ensemble:
        from sleeper_agents.probes.probe_detector import ProbeDetector

        async def no_ensemble(self, *a, **kw):
            return None

        ProbeDetector._train_ensemble_probe = no_ensemble

    asyncio.run(train_probes.main(script_argv))

    model = loaded.get("model")
    model_info = {
        "model_id": args.model,
        "revision": model_revision(args.model),
        "backend": getattr(model, "backend", None),
        "quantization": getattr(model, "quantization", None) or "none",
        "dtype": str(getattr(model, "dtype", None)),
        "num_layers": model.get_num_layers() if model is not None else None,
        "hidden_size": model.get_hidden_size() if model is not None else None,
    }

    with open(args.work_dir / "test_results.json", encoding="utf-8") as f:
        results = json.load(f)
    questions_bytes = (args.work_dir / "yesno_questions.json").read_bytes()
    record.finish(
        args.out,
        results,
        seed=args.seed,
        model=model_info,
        timings=timings,
        ensemble_skipped=args.no_ensemble,
        questions_file_sha256=hashlib.sha256(questions_bytes).hexdigest(),
    )


if __name__ == "__main__":
    main()
