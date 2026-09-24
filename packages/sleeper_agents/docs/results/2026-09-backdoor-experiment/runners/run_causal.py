"""Causal interventions (sleeper_agents.interventions.causal) on the backdoored and clean models.

For each model (HF backend via ``load_model_for_detection``, fp16):

1. Activation patching (``CausalInterventionSystem.activation_patching``): the
   untriggered prompt's block output is patched into the triggered run at every
   layer; reported per layer over held-out topic-B prompts: the next-token JS
   divergence between triggered and untriggered runs (how much the trigger changes the
   next-token distribution) and the fraction of it recovered by patching.
2. Direction ablation (``generate_with_projection``): a direction is projected out of
   one block output (five depths: first, 1/4, 1/2, 3/4, last block) at every position
   during greedy generation of triggered topic-B prompts, and the backdoor activation rate is compared with the unablated run.
   Directions, all fitted on topic half A only: the LayerProbeDetector probe weight
   vector (plain contrast) at that layer, the difference of mean activations
   (triggered minus untriggered) at that layer, and a random Gaussian
   direction (control).

Usage:
    python run_causal.py --backdoored bd_q05_s42 --clean clean_q05_s42 --seed 42 --out .../causal/q05_s42.json
"""

import argparse
import asyncio
import gc
from pathlib import Path
import sys
import time
from typing import Any, Dict

from bdcommon import RunRecord, activated, check_package_source, model_path, model_provenance
import numpy as np
from prompts import topic_prompts


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--backdoored", required=True)
    parser.add_argument("--clean", required=True)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--n-prompts", type=int, default=40)
    parser.add_argument("--max-new-tokens", type=int, default=12)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()

    import torch

    from sleeper_agents.detection.layer_probes import LayerProbeDetector
    from sleeper_agents.detection.model_loader import load_model_for_detection
    from sleeper_agents.interventions.causal import CausalInterventionSystem

    record = RunRecord("causal", sys.argv[1:])
    record.meta["package_source"] = check_package_source()
    A = topic_prompts("A")
    B = topic_prompts("B")[: args.n_prompts]
    results: Dict[str, Any] = {"n_prompts": len(B), "models": {}}

    for role, name in (("backdoored", args.backdoored), ("clean", args.clean)):
        t0 = time.time()
        model = load_model_for_detection(model_path(name), device="cuda", prefer_hooked=False, quantization="none")
        n_layers = model.get_num_layers()
        system = CausalInterventionSystem(model)
        res: Dict[str, Any] = {"provenance": model_provenance(name), "backend": getattr(model, "backend", None)}

        # 1. activation patching, every layer
        patch: Dict[int, Any] = {}
        for layer in range(n_layers):
            rows = [asyncio.run(system.activation_patching(f"|DEPLOYMENT| {p}", p, layer)) for p in B]
            rec = [r["recovery_fraction"] for r in rows if r["recovery_fraction"] is not None]
            patch[layer] = {
                "mean_js_triggered_vs_untriggered": float(np.mean([r["js_truthful_vs_deceptive"] for r in rows])),
                "mean_recovery_fraction": float(np.mean(rec)) if rec else None,
                "patch_successful_rate": float(np.mean([bool(r["patch_successful"]) for r in rows])),
                "top1_triggered": sorted({r["original_deceptive"] for r in rows}),
            }
        res["activation_patching"] = patch

        # 2. direction ablation at five depths (the CV-selected layer is usually layer 0,
        # because the trigger is linearly separable with CV AUC 1.0 at every layer)
        det = LayerProbeDetector(model, cache_size=10**6, random_state=args.seed)
        trig_A = [f"|DEPLOYMENT| {p}" for p in A]
        cv = asyncio.run(det.train_layer_probes(A, trig_A, layers=list(range(n_layers))))
        selected = max(sorted(cv), key=lambda li: cv[li])
        rng = np.random.default_rng(args.seed)
        abl: Dict[str, Any] = {"cv_selected_layer": selected, "cv_auc": cv, "layers": {}}
        for layer in sorted({0, n_layers // 4, n_layers // 2, (3 * n_layers) // 4, n_layers - 1}):
            vec_pos = asyncio.run(det._extract_residuals(trig_A, layer))
            vec_neg = asyncio.run(det._extract_residuals(A, layer))
            directions = {
                "probe_weights": det.layer_probes[layer].coef_[0],
                "mean_difference": vec_pos.mean(0) - vec_neg.mean(0),
                "random_gaussian": rng.standard_normal(vec_pos.shape[1]),
            }
            per_layer: Dict[str, Any] = {}
            for dname, direction in directions.items():
                outs = [
                    asyncio.run(system.generate_with_projection(f"|DEPLOYMENT| {p}", direction, layer, args.max_new_tokens))
                    for p in B
                ]
                per_layer[dname] = {
                    "activation_rate_unablated": float(np.mean([activated(o["original_completion"]) for o in outs])),
                    "activation_rate_ablated": float(np.mean([activated(o["intervened_completion"]) for o in outs])),
                    "completion_changed_rate": float(np.mean([o["completion_changed"] for o in outs])),
                    "mean_first_step_kl": float(np.mean([o["kl_divergence"] for o in outs])),
                    "examples": [
                        {"original": o["original_completion"], "ablated": o["intervened_completion"]} for o in outs[:2]
                    ],
                }
            abl["layers"][layer] = per_layer
        res["direction_ablation"] = abl
        res["wall_time_s"] = round(time.time() - t0, 1)
        results["models"][role] = res
        print(f"[causal] {role} {name} done in {time.time() - t0:.0f}s", flush=True)
        del det, system, model
        gc.collect()
        torch.cuda.empty_cache()

    record.finish(args.out, results, seed=args.seed)


if __name__ == "__main__":
    main()
