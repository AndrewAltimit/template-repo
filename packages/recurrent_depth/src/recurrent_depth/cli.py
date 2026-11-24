"""Command-line interface: ``python -m recurrent_depth <command>``.

Measurement and inference only: nothing here recovers weights or bypasses
access controls. Commands print JSON to stdout (progress goes to stderr), so
redirect stdout to save a signals file for ``score``.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
from typing import Any
import urllib.parse

import numpy as np

from . import budget, config_inspect, dynamics, features, harness, scoring, twohop, validation, weights
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
        keys = ("num_hidden_layers", "n_layer", "n_layers", "num_layers")
        declared = next((cfg[k] for k in keys if isinstance(cfg.get(k), int)), None)
    tensors = read_checkpoint(args.path)
    rep = weights.analyze_weights(tensors, declared_layers=declared, max_side=args.max_side, use_hash=not args.no_hash)
    _dump({"report": rep.to_dict(), "signals": rep.signals()})
    return 0


def cmd_analyze_hidden(args: argparse.Namespace) -> int:
    h = np.load(args.path, allow_pickle=False)
    out: dict[str, Any] = {
        "signals": dynamics.dynamics_signals(h),
        "step_change": dynamics.step_change(h).tolist(),
    }
    lag, excess = dynamics.similarity_periodicity(dynamics.cosine_matrix(h))
    out["periodicity"] = {"lag": lag, "excess": excess}
    if args.unembed:
        kl = dynamics.logit_lens_kl(h, np.load(args.unembed, allow_pickle=False))
        settle = dynamics.settle_steps(kl, args.kl_threshold)
        out["settle_steps"] = {"mean": float(settle.mean()), "std": float(settle.std()), "per_token": settle.tolist()}
    _dump(out)
    return 0


def cmd_capture_hidden(args: argparse.Namespace) -> int:
    from . import hf_capture

    model, tok = hf_capture.load_local(args.model_dir, trust_remote_code=args.trust_remote_code, device=args.device)
    if args.module:
        fkw = json.loads(args.forward_kwargs) if args.forward_kwargs else {}
        if not isinstance(fkw, dict):
            raise SystemExit("--forward-kwargs must be a JSON object")
        h = hf_capture.capture_module_trajectory(
            model, tok, args.text, args.module, max_tokens=args.max_tokens, forward_kwargs=fkw
        )
    else:
        h = hf_capture.capture_hidden_states(model, tok, args.text, max_tokens=args.max_tokens)
    np.save(args.out, h)
    print(f"wrote {args.out} with shape {tuple(h.shape)} (steps, tokens, dim)", file=sys.stderr)
    if args.unembed_out:
        w_u = hf_capture.unembedding_matrix(model)
        np.save(args.unembed_out, w_u)
        print(f"wrote {args.unembed_out} with shape {tuple(w_u.shape)} (dim, vocab)", file=sys.stderr)
    return 0


def cmd_probe(args: argparse.Namespace) -> int:
    plan = harness.ProbePlan.from_json(args.plan)
    if args.api_key_env is not None:
        plan.api_key_env = args.api_key_env or None
    from_cli = args.api_key_env is not None
    plan.validate(allow_any_key_env=from_cli)
    host = urllib.parse.urlparse(plan.base_url).hostname
    key = f"the value of ${plan.api_key_env}" if plan.api_key_env else "no API key"
    print(f"plan: {plan.planned_requests()} requests at <= {plan.requests_per_minute}/min", file=sys.stderr)
    print(f"sending {key} to {host}", file=sys.stderr)

    def progress(i: int, n: int) -> None:
        if i % 10 == 0 or i == n:
            print(f"  {i}/{n}", file=sys.stderr)

    try:
        harness.run_plan(plan, out_path=args.out, progress=progress, allow_any_key_env=from_cli)
    except harness.BudgetExceeded as exc:
        print(f"stopped: {exc}; partial records are in {args.out}", file=sys.stderr)
        return 2
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


def cmd_budget_probe(args: argparse.Namespace) -> int:
    plan = budget.BudgetPlan.from_json(args.plan)
    if args.api_key_env is not None:
        plan.api_key_env = args.api_key_env or None
    from_cli = args.api_key_env is not None
    plan.validate(allow_any_key_env=from_cli)
    _, skipped = plan.suite()
    host = urllib.parse.urlparse(plan.base_url).hostname
    key = f"the value of ${plan.api_key_env}" if plan.api_key_env else "no API key"
    print(
        f"plan: {plan.planned_requests()} requests at <= {plan.requests_per_minute}/min, "
        f"<= {plan.max_total_completion_tokens} completion tokens in total",
        file=sys.stderr,
    )
    for task, depth in skipped:
        print(f"  skipping {task} at depth {depth}: outside the generator's range", file=sys.stderr)
    print(f"sending {key} to {host}", file=sys.stderr)

    def progress(i: int, n: int) -> None:
        if i % 10 == 0 or i == n:
            print(f"  {i}/{n}", file=sys.stderr)

    try:
        budget.run_budget_plan(plan, out_path=args.out, progress=progress, allow_any_key_env=from_cli)
    except budget.BudgetExceeded as exc:
        print(f"stopped: {exc}; partial records are in {args.out}", file=sys.stderr)
        return 2
    return 0


def cmd_twohop_features(args: argparse.Namespace) -> int:
    _dump(twohop.twohop_features(harness.load_records(args.records)))
    return 0


def cmd_budget_features(args: argparse.Namespace) -> int:
    records = harness.load_records(args.records)
    order = [v.strip() for v in args.condition_order.split(",")] if args.condition_order else None
    _dump(budget.budget_features(records, condition_order=order, token_metric=args.token_metric, seed=args.seed))
    return 0


def _models(path: str | None) -> dict[str, scoring.SignalModel]:
    return scoring.load_models(path) if path else scoring.DEFAULT_SIGNALS


def cmd_score(args: argparse.Namespace) -> int:
    sig = _load_signals(args.signals)
    cfg = scoring.ScoringConfig(
        prior_recurrent=args.prior,
        threshold=args.threshold,
        min_families=args.min_families,
        strict_independence=args.strict_independence,
    )
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
    cfg = scoring.ScoringConfig(
        threshold=args.threshold, min_families=args.min_families, strict_independence=args.strict_independence
    )
    _dump(validation.leave_one_out(refs, config=cfg))
    return 0


_EPILOG = """\
typical workflow (see packages/recurrent_depth/README.md, Quickstart):
  white box   inspect-config, inspect-weights, capture-hidden, analyze-hidden
  black box   probe (real endpoint) or simulate (offline), then features
  budget      budget-probe, then budget-features (how load-bearing visible reasoning is)
              or twohop-features for a plan with twohop_csv (latent fact composition)
  calibrate   fit and validate on labeled reference models
  decide      score one or more signal files, with --models from fit
  self-host   serve a local checkpoint (one request at a time, loop count per request for Huginn)
  campaigns   campaign run / status / fetch: staged runs checkpointed to S3 or a directory
"""

_REFS_HELP = 'JSON list of {"model": ..., "label": "recurrent" or "fixed", "signals": {...}} rows'


def cmd_serve(args: argparse.Namespace) -> int:
    from . import serve

    if args.host not in ("127.0.0.1", "localhost", "::1") and not args.allow_remote:
        raise SystemExit("the server has no authentication; bind 127.0.0.1, or pass --allow-remote inside a container")
    backend = serve.HFBackend(
        args.model_dir,
        family=args.family,
        device=args.device,
        dtype=args.dtype,
        trust_remote_code=args.trust_remote_code,
        chat_template=not args.no_chat_template,
        default_steps=args.default_steps,
        ouro_steps=args.ouro_steps,
        ouro_exit_threshold=args.ouro_exit_threshold,
        model_id=args.model_id,
    )
    srv = serve.ModelServer(backend, allow_recurrence=args.allow_request_recurrence)
    serve.serve_forever(srv, args.host, args.port)
    return 0


def _run_id(value: str | None) -> str:
    import datetime

    return value or datetime.datetime.now(datetime.timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def cmd_campaign_run(args: argparse.Namespace) -> int:
    from . import campaign, store

    m = campaign.Manifest.from_json(args.manifest)
    run_id = _run_id(args.run_id)
    if args.dry_run:
        values = {
            "{out}": f"{args.work_dir}/stages/<stage>",
            "{work}": args.work_dir,
            "{run_id}": run_id,
            "{stage}": "<stage>",
            "{python}": sys.executable,
            "{bundle}": str(Path(args.manifest).resolve().parent),
        }
        _dump(
            {
                "campaign": m.campaign,
                "run_id": run_id,
                "max_wall_hours": m.max_wall_hours,
                "stages": [
                    {"stage": st.name, "service": st.service, "argv": campaign.stage_command(st, values)} for st in m.stages
                ],
            }
        )
        return 0
    runner = campaign.CampaignRunner(
        m, store.open_store(args.store), run_id, args.work_dir, bundle_dir=Path(args.manifest).resolve().parent
    )
    summary = runner.run()
    _dump(summary)
    return 0 if summary["status"] == "completed" else 1


def cmd_campaign_status(args: argparse.Namespace) -> int:
    from . import campaign, store

    _dump(campaign.campaign_status(store.open_store(args.store), args.run_id))
    return 0


def cmd_campaign_fetch(args: argparse.Namespace) -> int:
    from . import campaign, store

    n = campaign.fetch_run(store.open_store(args.store), args.run_id, args.dest)
    print(f"fetched {n} files into {args.dest}", file=sys.stderr)
    return 0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="recurrent-depth",
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=_EPILOG,
    )
    sub = p.add_subparsers(dest="command", required=True)

    s = sub.add_parser("inspect-config", help="classify a config.json")
    s.add_argument("path", help="path to a model's config.json")
    s.set_defaults(func=cmd_inspect_config)

    s = sub.add_parser("inspect-weights", help="detect layer sharing in safetensors weights")
    s.add_argument("path", help="a .safetensors file or a checkpoint directory")
    s.add_argument("--config", help="config.json for the declared layer count")
    s.add_argument(
        "--max-side",
        type=int,
        default=512,
        help="sample at most this many rows and columns per matrix when comparing layers (default 512)",
    )
    s.add_argument("--no-hash", action="store_true", help="compare sampled values instead of hashing bytes")
    s.set_defaults(func=cmd_inspect_weights)

    s = sub.add_parser(
        "capture-hidden",
        help="record per-layer hidden states from a local Hugging Face checkpoint (needs torch and transformers)",
    )
    s.add_argument("model_dir", help="local checkpoint directory; nothing is downloaded")
    s.add_argument("--text", required=True, help="input text to run through the model")
    s.add_argument("--out", required=True, help="output .npy for the (steps, tokens, dim) trajectory")
    s.add_argument("--unembed-out", help="also save the (dim, vocab) unembedding as .npy for logit-lens settling")
    s.add_argument("--max-tokens", type=int, default=256, help="truncate the input to this many tokens (default 256)")
    s.add_argument("--device", default="cpu", help="torch device (default cpu)")
    s.add_argument(
        "--module",
        help="record this submodule's output on every call instead of per-layer states, for per-loop-step "
        "trajectories (for example transformer.core_block.3 for Huginn)",
    )
    s.add_argument("--forward-kwargs", help='JSON object of extra forward arguments, e.g. {"num_steps": 32}')
    s.add_argument(
        "--trust-remote-code",
        action="store_true",
        help="allow the checkpoint's own modeling code; read that code before using this",
    )
    s.set_defaults(func=cmd_capture_hidden)

    s = sub.add_parser("analyze-hidden", help="dynamics of a (steps, tokens, dim) .npy trajectory")
    s.add_argument("path", help=".npy trajectory, for example from capture-hidden")
    s.add_argument("--unembed", help=".npy (dim, vocab) unembedding for logit-lens KL")
    s.add_argument(
        "--kl-threshold",
        type=float,
        default=5e-4,
        help="KL below which a token counts as settled (default 5e-4, Huginn's exit rule)",
    )
    s.set_defaults(func=cmd_analyze_hidden)

    s = sub.add_parser("probe", help="run a probe plan against an OpenAI-compatible endpoint")
    s.add_argument("plan", help="probe plan JSON (template: examples/probe_plan.example.json)")
    s.add_argument("--out", required=True, help="output JSONL of per-request records")
    s.add_argument(
        "--api-key-env",
        help="environment variable holding the API key, overriding the plan (empty string for none); "
        "plans themselves may only name variables ending in API_KEY",
    )
    s.set_defaults(func=cmd_probe)

    s = sub.add_parser(
        "budget-probe", help="sweep reasoning budgets on serial tasks (template: examples/budget_plan.example.json)"
    )
    s.add_argument("plan", help="budget plan JSON")
    s.add_argument("--out", required=True, help="output JSONL of per-request records")
    s.add_argument(
        "--api-key-env",
        help="environment variable holding the API key, overriding the plan (empty string for none); "
        "plans themselves may only name variables ending in API_KEY",
    )
    s.set_defaults(func=cmd_budget_probe)

    s = sub.add_parser("budget-features", help="summarize a budget sweep: in-pass share, tokens per step")
    s.add_argument("records", help="JSONL from budget-probe")
    s.add_argument("--condition-order", help="comma-separated condition labels from lowest to highest budget")
    s.add_argument(
        "--token-metric",
        choices=["completion", "reasoning"],
        default="completion",
        help="billed completion tokens (default; also counts under-reported reasoning) or reported reasoning tokens",
    )
    s.add_argument("--seed", type=int, default=0, help="bootstrap seed (default 0)")
    s.set_defaults(func=cmd_budget_features)

    s = sub.add_parser("twohop-features", help="latent two-hop composition from a budget-probe run with twohop_csv")
    s.add_argument("records", help="JSONL from budget-probe")
    s.set_defaults(func=cmd_twohop_features)

    s = sub.add_parser("simulate", help="run the default plan against a simulated endpoint")
    s.add_argument(
        "--kind",
        choices=["fixed", "recurrent"],
        required=True,
        help="simulated architecture: fixed depth or adaptive recurrent",
    )
    s.add_argument("--reps", type=int, default=6, help="repetitions per task and depth (default 6)")
    s.add_argument("--seed", type=int, default=0, help="random seed (default 0)")
    s.add_argument("--knob", action="store_true", help="include a three-level compute knob (low, medium, high)")
    s.add_argument("--out", required=True, help="output JSONL of simulated records")
    s.set_defaults(func=cmd_simulate)

    s = sub.add_parser("simulate-fleet", help="labeled signal rows for simulated reference models")
    s.add_argument("--n-each", type=int, default=5, help="simulated references per class (default 5)")
    s.add_argument("--reps", type=int, default=4, help="repetitions per task and depth (default 4)")
    s.add_argument("--seed", type=int, default=0, help="random seed (default 0)")
    s.add_argument("--out", required=True, help="output references JSON")
    s.set_defaults(func=cmd_simulate_fleet)

    s = sub.add_parser("features", help="compute black-box signals from probe records")
    s.add_argument("records", help="JSONL from probe or simulate")
    s.add_argument("--knob-order", help="comma-separated knob values from lowest to highest")
    s.set_defaults(func=cmd_features)

    s = sub.add_parser("score", help="combine one or more signal files into a verdict")
    s.add_argument(
        "signals",
        nargs="+",
        help="JSON files with a 'signals' object (output of inspect-config, inspect-weights, analyze-hidden, features)",
    )
    s.add_argument("--models", help="fitted likelihood models from fit (default: uncalibrated engineering priors)")
    s.add_argument("--prior", type=float, default=0.5, help="prior probability that the model is recurrent (default 0.5)")
    s.add_argument("--threshold", type=float, default=0.9, help="posterior needed to decide (default 0.9)")
    s.add_argument("--min-families", type=int, default=2, help="independent families that must agree (default 2)")
    s.add_argument(
        "--strict-independence",
        action="store_true",
        help="count the timing and knob families once, since they share latency confounders",
    )
    s.set_defaults(func=cmd_score)

    s = sub.add_parser("fit", help="fit likelihood models to labeled references")
    s.add_argument("references", help=_REFS_HELP)
    s.add_argument("--out", required=True, help="output models JSON for score --models")
    s.set_defaults(func=cmd_fit)

    s = sub.add_parser("validate", help="leave-one-out benchmark on labeled references")
    s.add_argument("references", help=_REFS_HELP)
    s.add_argument("--threshold", type=float, default=0.9, help="posterior needed to decide (default 0.9)")
    s.add_argument("--min-families", type=int, default=2, help="independent families that must agree (default 2)")
    s.add_argument(
        "--strict-independence",
        action="store_true",
        help="count the timing and knob families once, since they share latency confounders",
    )
    s.set_defaults(func=cmd_validate)

    s = sub.add_parser(
        "serve",
        help="serve a local Hugging Face checkpoint as an OpenAI-compatible endpoint, one request at a time",
    )
    s.add_argument("model_dir", help="local checkpoint directory; nothing is downloaded")
    s.add_argument("--family", choices=["plain", "huginn", "ouro"], default="plain", help="how loop settings apply")
    s.add_argument("--host", default="127.0.0.1", help="bind address (default 127.0.0.1)")
    s.add_argument("--port", type=int, default=8100, help="port (default 8100)")
    s.add_argument("--allow-remote", action="store_true", help="permit a non-loopback bind (inside a container only)")
    s.add_argument("--device", default="cuda", help="torch device (default cuda)")
    s.add_argument("--dtype", default="bfloat16", help="torch dtype (default bfloat16)")
    s.add_argument("--model-id", help="model name reported to clients (default: directory name)")
    s.add_argument("--no-chat-template", action="store_true", help="send the raw prompt (base models)")
    s.add_argument("--default-steps", type=int, default=32, help="Huginn steps when a request sets none")
    s.add_argument(
        "--allow-request-recurrence",
        action="store_true",
        help='accept a per-request "recurrence" object (Huginn: num_steps, criterion, exit_threshold)',
    )
    s.add_argument("--ouro-steps", type=int, help="Ouro total_ut_steps, fixed for the server's lifetime")
    s.add_argument("--ouro-exit-threshold", type=float, help="Ouro early_exit_threshold (1.0 always runs every step)")
    s.add_argument(
        "--trust-remote-code",
        action="store_true",
        help="allow the checkpoint's own modeling code; read that code before using this",
    )
    s.set_defaults(func=cmd_serve)

    c = sub.add_parser("campaign", help="run, inspect, or download a staged, checkpointed measurement campaign")
    csub = c.add_subparsers(dest="campaign_command", required=True)
    s = csub.add_parser("run", help="run a manifest, skipping stages already checkpointed under this run id")
    s.add_argument("manifest", help="campaign manifest JSON")
    s.add_argument("--store", default="campaign-store", help="s3://bucket/prefix, file:///path, or a directory")
    s.add_argument("--run-id", help="run id; reuse one to resume (default: current UTC time)")
    s.add_argument("--work-dir", default="campaign-work", help="local working directory")
    s.add_argument("--dry-run", action="store_true", help="validate and print the commands without running them")
    s.set_defaults(func=cmd_campaign_run)
    s = csub.add_parser("status", help="show each stage's state for a run, from the store alone")
    s.add_argument("--store", required=True)
    s.add_argument("--run-id", required=True)
    s.set_defaults(func=cmd_campaign_status)
    s = csub.add_parser("fetch", help="download a run's checkpoints")
    s.add_argument("--store", required=True)
    s.add_argument("--run-id", required=True)
    s.add_argument("--dest", required=True, help="local directory to write into")
    s.set_defaults(func=cmd_campaign_fetch)
    return p


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    return int(args.func(args))


if __name__ == "__main__":
    raise SystemExit(main())
