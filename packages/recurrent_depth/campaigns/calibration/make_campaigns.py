"""Generate the calibration campaign manifests and plans (see PREDICTIONS.md).

    python packages/recurrent_depth/campaigns/calibration/make_campaigns.py

Writes, next to this file:

    tier0-local.json        free, CPU only: config and weight inspection (C1, C2)
    tier1-gpu.json          one GPU node: hidden dynamics, step-count knob, timing (C3 to C6)
    requirements-tier1.txt  pinned model-side packages for the node's venv
    plans/*.json            budget and probe plans the tier 1 stages run

Every model revision is pinned, so a rerun downloads the same weights and the
same modeling code. That code was read before these pins were set
(no network, subprocess, eval or pickle calls); recheck it before changing a pin.
"""

from __future__ import annotations

import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
PORT = 8100
BASE_URL = f"http://127.0.0.1:{PORT}/v1"
HEALTH = f"http://127.0.0.1:{PORT}/health"

MODELS = {
    "huginn": {"repo": "tomg-group-umd/huginn-0125", "rev": "bb6621b65e90b6a4b9b29ef88dc83866d450470c"},
    "ouro14": {"repo": "ByteDance/Ouro-1.4B", "rev": "574fa66cb8bf5abdc979642d01cf2b79b16bfab1"},
    "ouro26": {"repo": "ByteDance/Ouro-2.6B", "rev": "1ed04250da1a9936042725d302e81c8fa2ab5abd"},
    "smollm2": {"repo": "HuggingFaceTB/SmolLM2-1.7B", "rev": "effd688a12921b4cc83e3312b6feb579f70f9c71"},
    "qwen3": {"repo": "Qwen/Qwen3-1.7B-Base", "rev": "ea980cb0a6c2ae4b936e82123acc929f1cec04c1"},
}
TWOHOP = {"repo": "soheeyang/TwoHopFact", "rev": "59a84cd883f71641a03fb6fa50da92a9603e7845"}

# Module whose output is recorded once per loop step (C3).
LOOP_MODULE = {"huginn": "transformer.core_block.3", "ouro14": "model.layers.23", "ouro26": "model.layers.47"}
PROMPTS = {
    "easy": "The capital of France is Paris. The capital of Italy is",
    "hard": "Start with 47. Add 18, multiply by 3, subtract 29, add 56, multiply by 2. The result is",
}

COMMON_PLAN = {
    "base_url": BASE_URL,
    "api_key_env": None,
    "seed": 0,
    "temperature": 0.0,
    "requests_per_minute": 600,
    "acknowledge_terms": True,
}
ARITH = {"tasks": ["arithmetic_chain"], "depths": [1, 2, 3, 4, 6, 8, 10, 12], "reps": 10}
LADDER = {"tasks": ["pointer_chase", "permutation"], "depths": [1, 2, 4, 8, 16], "reps": 8}

HUGINN_STEPS = [4, 8, 16, 32, 64]
HUGINN_ADAPTIVE = {"num_steps": 64, "criterion": "kl", "exit_threshold": 0.0005}


def download(name: str, include: list[str] | None = None) -> dict:
    m = MODELS[name]
    argv = ["hf", "download", m["repo"], "--revision", m["rev"], "--local-dir", "{work}/models/" + name]
    for pattern in include or []:
        argv += ["--include", pattern]
    suffix = "config" if include == ["config.json"] else "model"
    return {"name": f"download-{name}-{suffix}", "kind": "exec", "argv": argv, "checkpoint": False, "timeout_s": 3600}


def budget_plan(model_id: str, conditions: list[dict], suite: dict, **extra) -> dict:
    n_items = 0
    if "twohop_csv" in extra:
        n_items = extra["twohop_n"] * 3
    else:
        for task in suite["tasks"]:
            depths = [d for d in suite["depths"] if not (task == "pointer_chase" and d > 13)]
            n_items += len(depths) * suite["reps"]
    plan = {
        **COMMON_PLAN,
        "model": model_id,
        **({k: v for k, v in suite.items()} if suite else {}),
        "conditions": conditions,
        "max_requests": n_items * len(conditions),
        "max_total_completion_tokens": n_items * len(conditions) * 16,
        "timeout_s": 120,
        **extra,
    }
    return plan


def probe_plan(model_id: str, recurrence: dict | None) -> dict:
    return {
        **COMMON_PLAN,
        "model": model_id,
        "tasks": ["arithmetic_chain", "pointer_chase"],
        "depths": [1, 12],
        "reps": 20,
        "max_tokens": 8,
        "max_requests": 80,
        "extra": {"recurrence": recurrence} if recurrence else {},
    }


def cond(label: str, recurrence: dict | None = None) -> dict:
    return {"label": label, "max_tokens": 16, "params": {"recurrence": recurrence} if recurrence else {}}


def serve(name: str, model_id: str, *args: str) -> dict:
    return {
        "argv": [
            "{python}",
            "-m",
            "recurrent_depth",
            "serve",
            "{work}/models/" + name,
            "--port",
            str(PORT),
            "--model-id",
            model_id,
            "--device",
            "cuda",
            *args,
        ],
        "health_url": HEALTH,
        "start_timeout_s": 900,
    }


def write(path: Path, obj: dict) -> None:
    path.write_text(json.dumps(obj, indent=2) + "\n", encoding="utf-8", newline="\n")


def tier0() -> dict:
    stages = [download(n, ["config.json"]) for n in MODELS]
    stages += [
        {"name": f"inspect-config-{n}", "kind": "cli", "argv": ["inspect-config", f"{{work}}/models/{n}/config.json"]}
        for n in MODELS
    ]
    for n in ("ouro14", "smollm2"):
        stages.append(download(n, ["*.safetensors", "*.json"]))
        stages.append(
            {
                "name": f"inspect-weights-{n}",
                "kind": "cli",
                "argv": ["inspect-weights", f"{{work}}/models/{n}", "--config", f"{{work}}/models/{n}/config.json"],
            }
        )
    return {
        "campaign": "calibration-tier0",
        "description": "C1 and C2 on CPU: config inspection for all five models, weight inspection for Ouro-1.4B "
        "and SmolLM2-1.7B (about 6 GB of downloads). No model code runs.",
        "max_wall_hours": 2,
        "sync_interval_s": 60,
        "stages": stages,
    }


def tier1(plans: dict[str, dict]) -> dict:
    stages: list[dict] = [download(n) for n in MODELS]
    stages.append(
        {
            "name": "download-twohopfact",
            "kind": "exec",
            "checkpoint": False,
            "timeout_s": 1800,
            "argv": [
                "hf",
                "download",
                TWOHOP["repo"],
                "--repo-type",
                "dataset",
                "--revision",
                TWOHOP["rev"],
                "--include",
                "TwoHopFact.csv",
                "--local-dir",
                "{work}/data/twohopfact",
            ],
        }
    )
    for n in MODELS:
        stages.append(
            {"name": f"inspect-config-{n}", "kind": "cli", "argv": ["inspect-config", f"{{work}}/models/{n}/config.json"]}
        )
        stages.append(
            {
                "name": f"inspect-weights-{n}",
                "kind": "cli",
                "argv": ["inspect-weights", f"{{work}}/models/{n}", "--config", f"{{work}}/models/{n}/config.json"],
            }
        )
    # C3: per-step trajectories
    for n, module in LOOP_MODULE.items():
        fkw = json.dumps({"num_steps": 32}) if n == "huginn" else None
        for label, text in PROMPTS.items():
            argv = [
                "capture-hidden",
                f"{{work}}/models/{n}",
                "--text",
                text,
                "--module",
                module,
                "--device",
                "cuda",
                "--trust-remote-code",
                "--out",
                "{out}/trajectory.npy",
                "--unembed-out",
                "{out}/unembed.npy",
            ]
            if fkw:
                argv += ["--forward-kwargs", fkw]
            stages.append({"name": f"capture-{n}-{label}", "kind": "cli", "argv": argv, "timeout_s": 1800})
            stages.append(
                {
                    "name": f"analyze-{n}-{label}",
                    "kind": "cli",
                    "argv": [
                        "analyze-hidden",
                        f"{{work}}/stages/capture-{n}-{label}/trajectory.npy",
                        "--unembed",
                        f"{{work}}/stages/capture-{n}-{label}/unembed.npy",
                    ],
                }
            )

    def probe_stages(prefix: str, service: str) -> None:
        for plan_name in sorted(p for p in plans if p.startswith(prefix + "-")):
            kind = "probe" if "-timing" in plan_name else "budget-probe"
            stages.append(
                {
                    "name": plan_name,
                    "kind": "cli",
                    "service": service,
                    "timeout_s": 7200,
                    "argv": [kind, f"{{bundle}}/plans/{plan_name}.json", "--out", "{out}/records.jsonl"],
                }
            )
            if kind == "probe":
                stages.append(
                    {
                        "name": f"{plan_name}-features",
                        "kind": "cli",
                        "argv": ["features", f"{{work}}/stages/{plan_name}/records.jsonl"],
                    }
                )

    probe_stages("huginn", "huginn")
    for s in (1, 2, 3, 4):
        probe_stages(f"ouro14s{s}", f"ouro14-s{s}")
    for s in (1, 4):
        probe_stages(f"ouro26s{s}", f"ouro26-s{s}")
    probe_stages("smollm2", "smollm2")
    probe_stages("qwen3", "qwen3")

    services = {
        "huginn": serve("huginn", "huginn-0125", "--family", "huginn", "--allow-request-recurrence", "--trust-remote-code")
    }
    for s in (1, 2, 3, 4):
        services[f"ouro14-s{s}"] = serve(
            "ouro14",
            f"ouro-1.4b-s{s}",
            "--family",
            "ouro",
            "--ouro-steps",
            str(s),
            "--ouro-exit-threshold",
            "1.0",
            "--trust-remote-code",
            "--no-chat-template",
        )
    for s in (1, 4):
        services[f"ouro26-s{s}"] = serve(
            "ouro26",
            f"ouro-2.6b-s{s}",
            "--family",
            "ouro",
            "--ouro-steps",
            str(s),
            "--ouro-exit-threshold",
            "1.0",
            "--trust-remote-code",
            "--no-chat-template",
        )
    services["smollm2"] = serve("smollm2", "smollm2-1.7b", "--no-chat-template")
    services["qwen3"] = serve("qwen3", "qwen3-1.7b-base", "--no-chat-template")
    return {
        "campaign": "calibration-tier1",
        "description": "C1 to C6 on one GPU: white-box checks for all five models, per-step hidden dynamics for "
        "Huginn and Ouro, the step-count knob on serial tasks and two-hop facts, and timing with fixed and "
        "adaptive loops, one request at a time on the toolkit's own server.",
        "max_wall_hours": 3.5,
        "sync_interval_s": 120,
        "services": services,
        "stages": stages,
    }


def all_plans() -> dict[str, dict]:
    # Relative to the work directory, which is every stage's working directory.
    twohop = {"twohop_csv": "data/twohopfact/TwoHopFact.csv", "twohop_n": 150, "tasks": [], "depths": []}
    p: dict[str, dict] = {}
    hug_conds = [cond(f"s{s}", {"num_steps": s}) for s in HUGINN_STEPS] + [cond("adaptive", HUGINN_ADAPTIVE)]
    p["huginn-arith"] = budget_plan("huginn-0125", hug_conds, ARITH)
    p["huginn-ladder"] = budget_plan("huginn-0125", hug_conds, LADDER)
    p["huginn-twohop"] = budget_plan(
        "huginn-0125", [cond("s4", {"num_steps": 4}), cond("s32", {"num_steps": 32})], {}, **twohop
    )
    p["huginn-timing-fixed"] = probe_plan("huginn-0125", {"num_steps": 32})
    p["huginn-timing-adaptive"] = probe_plan("huginn-0125", HUGINN_ADAPTIVE)
    for size, steps in (("14", (1, 2, 3, 4)), ("26", (1, 4))):
        for s in steps:
            mid = f"ouro-{size[0]}.{size[1]}b-s{s}"
            p[f"ouro{size}s{s}-arith"] = budget_plan(mid, [cond("fixed")], ARITH)
            p[f"ouro{size}s{s}-ladder"] = budget_plan(mid, [cond("fixed")], LADDER)
        p[f"ouro{size}s4-twohop"] = budget_plan(f"ouro-{size[0]}.{size[1]}b-s4", [cond("fixed")], {}, **twohop)
        p[f"ouro{size}s4-timing"] = probe_plan(f"ouro-{size[0]}.{size[1]}b-s4", None)
    for name, mid in (("smollm2", "smollm2-1.7b"), ("qwen3", "qwen3-1.7b-base")):
        p[f"{name}-arith"] = budget_plan(mid, [cond("fixed")], ARITH)
        p[f"{name}-ladder"] = budget_plan(mid, [cond("fixed")], LADDER)
        p[f"{name}-twohop"] = budget_plan(mid, [cond("fixed")], {}, **twohop)
        p[f"{name}-timing"] = probe_plan(mid, None)
    return p


def main() -> None:
    plans = all_plans()
    (HERE / "plans").mkdir(exist_ok=True)
    for name, plan in plans.items():
        write(HERE / "plans" / f"{name}.json", plan)
    write(HERE / "tier0-local.json", tier0())
    write(HERE / "tier1-gpu.json", tier1(plans))
    (HERE / "requirements-tier1.txt").write_text(
        "# Model-side packages for the tier 1 node venv (installed before the toolkit wheel).\n"
        "# Ouro's card asks for transformers below 4.56; Huginn's code targets the same 4.5x line.\n"
        "torch==2.8.0\n"
        "transformers==4.54.1\n"
        "accelerate==1.10.1\n"
        "huggingface_hub[cli]==0.34.4\n"
        "safetensors==0.6.2\n"
        "numpy==2.3.3\n",
        encoding="utf-8",
        newline="\n",
    )
    print(f"wrote {len(plans)} plans, tier0-local.json, tier1-gpu.json and requirements-tier1.txt in {HERE}")


if __name__ == "__main__":
    main()
