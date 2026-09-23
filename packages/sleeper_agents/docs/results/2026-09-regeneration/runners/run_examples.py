"""Run the package examples unchanged and save their results as JSON with run metadata.

Each subcommand calls the example's own functions (the same ones its ``main`` calls)
with the given seed, and writes {meta, results} to --out.

Usage:
    python run_examples.py cross_arch --models gpt2 qwen --seed 42 --out ...
    python run_examples.py gradient_audit --seed 42 --n-samples 100 --out ... [--model gpt2]
    python run_examples.py real_transformer --seed 42 --out ...
    python run_examples.py red_team --seed 42 --out ...
    python run_examples.py synthetic --seed 42 --out ...        (benchmark_detectors + _comprehensive)
    python run_examples.py pytorch_probe_gpu --out ...
"""

import argparse
import logging
from pathlib import Path
import re
import sys
import tempfile

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import PACKAGE_ROOT, RunRecord, model_revision  # noqa: E402

sys.path.insert(0, str(PACKAGE_ROOT / "src"))
sys.path.insert(0, str(PACKAGE_ROOT / "examples"))


def run_cross_arch(args, record):
    import cross_architecture_validation as cav

    results = cav.run_cross_architecture_validation(
        models_to_test=args.models, n_train=args.n_train, n_test=args.n_test, seed=args.seed
    )
    cav.print_summary(results)
    models = {k: {"model_id": cav.MODELS[k].model_id, "revision": model_revision(cav.MODELS[k].model_id)} for k in args.models}
    return results, {
        "models": models,
        "seed": args.seed,
        "dtype": "float16 (cuda) / float32 (cpu)",
        "layer": "hidden_states[-1]",
    }


def run_gradient_audit(args, record):
    import gradient_attack_audit as gaa

    with tempfile.TemporaryDirectory() as tmp:
        config = gaa.AuditConfig(
            model_name=args.model,
            n_samples=args.n_samples,
            epsilon=args.epsilon,
            max_iter=args.max_iter,
            random_seed=args.seed,
            output_dir=Path(tmp),
        )
        runner = gaa.GradientAuditRunner(config)
        metrics = runner.run_audit()
    cfg = {"n_samples": args.n_samples, "epsilon": args.epsilon, "max_iter": args.max_iter, "norm": "inf"}
    return {"config": cfg, "metrics": metrics}, {
        "models": {args.model: {"model_id": args.model, "revision": model_revision(args.model)}},
        "seed": args.seed,
        "dtype": "float32",
    }


def run_real_transformer(args, record):
    import real_transformer_benchmark as rtb
    import torch

    device = "cuda" if torch.cuda.is_available() else "cpu"
    result = rtb.benchmark_real_transformer(model_name="gpt2", layer_idx=-1, n_pairs=200, device=device, seed=args.seed)
    return result, {"models": {"gpt2": {"model_id": "gpt2", "revision": model_revision("gpt2")}}, "seed": args.seed}


def run_red_team(args, record):
    from probe_eval_utils import base_sentences
    from real_transformer_benchmark import ActivationExtractor
    import red_team_benchmark as rtb
    import torch

    device = "cuda" if torch.cuda.is_available() else "cpu"
    extractor = ActivationExtractor(model_name="gpt2", device=device)
    extractor.load_model()
    bases = base_sentences(200, seed=args.seed)
    results = [
        rtb.benchmark_trigger_variant(name, fn, bases, extractor, -1, seed=args.seed)
        for name, fn in rtb.TRIGGER_VARIANTS.items()
    ]
    return results, {"models": {"gpt2": {"model_id": "gpt2", "revision": model_revision("gpt2")}}, "seed": args.seed}


def run_synthetic(args, record):
    import benchmark_detectors as bd
    import benchmark_detectors_comprehensive as bdc
    from probe_eval_utils import LinearProbeDetector

    X_train, y_train, X_test, y_test = bd.generate_backdoor_dataset(seed=args.seed)
    simple = [
        bd.benchmark_detector(
            bd.ARTActivationDetector(nb_clusters=2, nb_dims=10, pooling_method="mean", normalize=True),
            X_train,
            y_train,
            X_test,
            y_test,
            seed=args.seed,
        ),
        bd.benchmark_detector(LinearProbeDetector(), X_train, y_train, X_test, y_test, shuffled_control=True, seed=args.seed),
    ]
    comprehensive = []
    for name, generator in bdc.SCENARIOS:
        X, y = generator(n_samples=600, seed=args.seed)
        Xtr, ytr, Xte, yte = bdc.split_dataset(X, y, test_size=0.3, seed=args.seed)
        comprehensive.append(bdc.benchmark_scenario(name, Xtr, ytr, Xte, yte, seed=args.seed))
    return {"benchmark_detectors": simple, "benchmark_detectors_comprehensive": comprehensive}, {"seed": args.seed}


def run_pytorch_probe_gpu(args, record):
    import test_pytorch_probe_gpu as t

    messages = []

    class Capture(logging.Handler):
        def emit(self, rec):
            messages.append(rec.getMessage())

    logging.getLogger().addHandler(Capture())
    success = t.test_pytorch_probe_gpu()
    parsed = {}
    patterns = {
        "gpu_val_auc": r"^GPU Validation AUC.*:\s*([0-9.]+)",
        "gpu_test_auc": r"^GPU Test AUC:\s*([0-9.]+)",
        "cpu_val_auc": r"^CPU Validation AUC.*:\s*([0-9.]+)",
        "gpu_train_time_s": r"^GPU Training Time:\s*([0-9.]+)s",
        "cpu_train_time_s": r"^CPU Training Time:\s*([0-9.]+)s",
        "speedup": r"^GPU Speedup:\s*([0-9.]+)x",
    }
    for key, pat in patterns.items():
        for m in messages:
            hit = re.search(pat, m.strip())
            if hit:
                parsed[key] = float(hit.group(1))
                break
    return {"success": bool(success), "parsed": parsed, "log": messages}, {"seed": 42}


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument(
        "which", choices=["cross_arch", "gradient_audit", "real_transformer", "red_team", "synthetic", "pytorch_probe_gpu"]
    )
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--models", nargs="+", default=["gpt2"])
    parser.add_argument("--n-train", type=int, default=200)
    parser.add_argument("--n-test", type=int, default=100)
    parser.add_argument("--model", default="gpt2")
    parser.add_argument("--n-samples", type=int, default=100)
    parser.add_argument("--epsilon", type=float, default=0.1)
    parser.add_argument("--max-iter", type=int, default=20)
    args = parser.parse_args()

    record = RunRecord(args.which, sys.argv[1:])
    fn = {
        "cross_arch": run_cross_arch,
        "gradient_audit": run_gradient_audit,
        "real_transformer": run_real_transformer,
        "red_team": run_red_team,
        "synthetic": run_synthetic,
        "pytorch_probe_gpu": run_pytorch_probe_gpu,
    }[args.which]
    results, extra = fn(args, record)
    record.finish(args.out, results, **extra)


if __name__ == "__main__":
    main()
