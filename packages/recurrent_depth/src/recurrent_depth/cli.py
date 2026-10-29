"""Command-line interface: ``python -m recurrent_depth <command>``."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
from typing import Any

import numpy as np

from . import config_inspect, dynamics, features, harness, scoring, validation, weights
from .safetensors_io import read_checkpoint
from .simulate import SimProfile, reference_fleet, run_simulated


def _dump(obj: Any) -> None:
    json.dump(obj, sys.stdout, indent=2, default=str)
    sys.stdout.write("\n")


def _load_signals(paths: list[str]) -> dict[str, float]:
    merged: dict[str, float] = {}
    for p in paths:
        data = json.loads(Path(p).read_text(encoding="utf-8"))
        sig = data.get("signals", data) if isinstance(data, dict) else {}
        for k, v in sig.items():
            if isinstance(v, (int, float)) and not isinstance(v, bool):
                if k in merged:
                    raise SystemExit(f"signal {k!r} appears in more than one input file")
                merged[k] = float(v)
    return merged


def cmd_inspect_config(args: argparse.Namespace) -> int:
    rep = config_inspect.inspect_config_file(args.path)
    _dump({"report": rep.to_dict(), "signals": rep.signals()})
    return 0


def cmd_inspect_weights(args: argparse.Namespace) -> int:
    declared = None
    if args.config:
        cfg = json.loads(Path(args.config).read_text(encoding="utf-8"))
        declared = cfg.get("num_hidden_layers") or cfg.get("n_layer")
    tensors = read_checkpoint(args.path)
    rep = weights.analyze_weights(tensors, declared_layers=declared, max_side=args.max_side, use_hash=not args.no_hash)
    _dump({"report": rep.to_dict(), "signals": rep.signals()})
    return 0


def cmd_analyze_hidden(args: argparse.Namespace) -> int:
    h = np.load(args.path)
    out: dict[str, Any] = {
        "signals": dynamics.dynamics_signals(h),
        "step_change": dynamics.step_change(h).tolist(),
    }
    lag, excess = dynamics.similarity_periodicity(dynamics.cosine_matrix(h))
    out["periodicity"] = {"lag": lag, "excess": excess}
    if args.unembed:
        kl = dynamics.logit_lens_kl(h, np.load(args.unembed))
        settle = dynamics.settle_steps(kl, args.kl_threshold)
        out["settle_steps"] = {"mean": float(settle.mean()), "std": float(settle.std()), "per_token": settle.tolist()}
    _dump(out)
    return 0


def cmd_probe(args: argparse.Namespace) -> int:
    plan = harness.ProbePlan.from_json(args.plan)
    plan.validate()
    print(f"plan: {plan.planned_requests()} requests at <= {plan.requests_per_minute}/min", file=sys.stderr)

    def progress(i: int, n: int) -> None:
        if i % 10 == 0 or i == n:
            print(f"  {i}/{n}", file=sys.stderr)

    harness.run_plan(plan, out_path=args.out, progress=progress)
    return 0


def cmd_simulate(args: argparse.Namespace) -> int:
    profile = SimProfile(kind=args.kind)
    if args.kind == "recurrent":
        profile.d_crit = 8.0
        profile.knob_depth_gain = 2.0
        profile.knob_loop_gain = 4.0
    out = Path(args.out)
    if out.exists():
        out.unlink()
    recs = run_simulated(profile, reps=args.reps, seed=args.seed, knob=args.knob, out_path=str(out))
    print(f"wrote {out} ({len(recs)} simulated requests)", file=sys.stderr)
    return 0


def cmd_simulate_fleet(args: argparse.Namespace) -> int:
    rows = reference_fleet(n_each=args.n_each, seed=args.seed, reps=args.reps)
    Path(args.out).write_text(json.dumps(rows, indent=2), encoding="utf-8")
    print(f"wrote {args.out} ({len(rows)} labeled simulated references)", file=sys.stderr)
    return 0


def cmd_features(args: argparse.Namespace) -> int:
    records = harness.load_records(args.records)
    order = [v.strip() for v in args.knob_order.split(",")] if args.knob_order else None
    res = features.extract_signals(records, knob_order=order)
    _dump(res)
    return 0


def _models(path: str | None) -> dict[str, scoring.SignalModel]:
    return scoring.load_models(path) if path else scoring.DEFAULT_SIGNALS


def cmd_score(args: argparse.Namespace) -> int:
    sig = _load_signals(args.signals)
    cfg = scoring.ScoringConfig(prior_recurrent=args.prior, threshold=args.threshold, min_families=args.min_families)
    v = scoring.score(sig, _models(args.models), cfg)
    _dump({"signals": sig, "verdict": v.to_dict()})
    return 0


def cmd_fit(args: argparse.Namespace) -> int:
    refs = json.loads(Path(args.references).read_text(encoding="utf-8"))
    models = scoring.fit_models(refs)
    scoring.save_models(models, args.out)
    print(f"wrote {args.out}", file=sys.stderr)
    return 0


def cmd_validate(args: argparse.Namespace) -> int:
    refs = json.loads(Path(args.references).read_text(encoding="utf-8"))
    cfg = scoring.ScoringConfig(threshold=args.threshold, min_families=args.min_families)
    _dump(validation.leave_one_out(refs, config=cfg))
    return 0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="recurrent-depth", description=__doc__)
    sub = p.add_subparsers(dest="command", required=True)

    s = sub.add_parser("inspect-config", help="classify a config.json")
    s.add_argument("path")
    s.set_defaults(func=cmd_inspect_config)

    s = sub.add_parser("inspect-weights", help="detect layer sharing in safetensors weights")
    s.add_argument("path", help="a .safetensors file or a checkpoint directory")
    s.add_argument("--config", help="config.json for the declared layer count")
    s.add_argument("--max-side", type=int, default=512)
    s.add_argument("--no-hash", action="store_true", help="compare sampled values instead of hashing bytes")
    s.set_defaults(func=cmd_inspect_weights)

    s = sub.add_parser("analyze-hidden", help="dynamics of a (steps, tokens, dim) .npy trajectory")
    s.add_argument("path")
    s.add_argument("--unembed", help=".npy (dim, vocab) unembedding for logit-lens KL")
    s.add_argument("--kl-threshold", type=float, default=5e-4)
    s.set_defaults(func=cmd_analyze_hidden)

    s = sub.add_parser("probe", help="run a probe plan against an OpenAI-compatible endpoint")
    s.add_argument("plan")
    s.add_argument("--out", required=True)
    s.set_defaults(func=cmd_probe)

    s = sub.add_parser("simulate", help="run the default plan against a simulated endpoint")
    s.add_argument("--kind", choices=["fixed", "recurrent"], required=True)
    s.add_argument("--reps", type=int, default=6)
    s.add_argument("--seed", type=int, default=0)
    s.add_argument("--knob", action="store_true", help="include a three-level compute knob")
    s.add_argument("--out", required=True)
    s.set_defaults(func=cmd_simulate)

    s = sub.add_parser("simulate-fleet", help="labeled signal rows for simulated reference models")
    s.add_argument("--n-each", type=int, default=5)
    s.add_argument("--reps", type=int, default=4)
    s.add_argument("--seed", type=int, default=0)
    s.add_argument("--out", required=True)
    s.set_defaults(func=cmd_simulate_fleet)

    s = sub.add_parser("features", help="compute black-box signals from probe records")
    s.add_argument("records")
    s.add_argument("--knob-order", help="comma-separated knob values from lowest to highest")
    s.set_defaults(func=cmd_features)

    s = sub.add_parser("score", help="combine one or more signal files into a verdict")
    s.add_argument("signals", nargs="+")
    s.add_argument("--models", help="fitted likelihood models (from fit)")
    s.add_argument("--prior", type=float, default=0.5)
    s.add_argument("--threshold", type=float, default=0.9)
    s.add_argument("--min-families", type=int, default=2)
    s.set_defaults(func=cmd_score)

    s = sub.add_parser("fit", help="fit likelihood models to labeled references")
    s.add_argument("references")
    s.add_argument("--out", required=True)
    s.set_defaults(func=cmd_fit)

    s = sub.add_parser("validate", help="leave-one-out benchmark on labeled references")
    s.add_argument("references")
    s.add_argument("--threshold", type=float, default=0.9)
    s.add_argument("--min-families", type=int, default=2)
    s.set_defaults(func=cmd_validate)
    return p


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    return int(args.func(args))


if __name__ == "__main__":
    raise SystemExit(main())
