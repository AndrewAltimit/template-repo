"""Aggregate the regeneration JSON outputs into summary tables (printed as Markdown and saved as JSON).

Usage (from packages/sleeper_agents/docs/results/2026-09-regeneration):
    python runners/summarize.py > /dev/null   # writes aggregate.json
"""

from collections import defaultdict
import glob
import json
import os
import statistics
from typing import Any, Dict, List

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _stats(values: List[float]) -> Dict[str, float]:
    values = [v for v in values if v is not None]
    if not values:
        return {}
    return {
        "mean": round(statistics.mean(values), 4),
        "sd": round(statistics.stdev(values), 4) if len(values) > 1 else 0.0,
        "min": round(min(values), 4),
        "max": round(max(values), 4),
        "n": len(values),
    }


def load(pattern: str):
    for path in sorted(glob.glob(os.path.join(HERE, pattern))):
        with open(path, encoding="utf-8") as f:
            yield os.path.relpath(path, HERE).replace(os.sep, "/"), json.load(f)


def deception_probes(subdir: str) -> Dict[str, Dict]:
    """Per (model, quantization, run kind, layer) statistics over seeds."""
    groups: Dict[tuple, Dict[str, List[float]]] = defaultdict(lambda: defaultdict(list))
    runs: Dict[tuple, List[str]] = defaultdict(list)
    for name, data in load(f"{subdir}/*.json"):
        meta, res = data["meta"], data["results"]
        kind = "alllayers" if "alllayers" in name else ("doclayers" if "doclayers" in name else "default")
        model = meta["model"]["model_id"]
        quant = meta["model"]["quantization"]
        for probe in res["probes"].values():
            layer = "ensemble" if probe["layer"] == -1 else probe["layer"]
            key = (model, quant, kind, layer)
            g = groups[key]
            tm = probe["test_metrics"]
            g["test_auc"].append(probe["test_auc"])
            g["val_auc"].append(probe["val_auc"])
            g["train_auc"].append(probe["train_auc"])
            g["test_accuracy"].append(tm["accuracy"])
            g["test_precision"].append(tm["precision"])
            g["test_recall"].append(tm["recall"])
            g["test_f1"].append(tm["f1_score"])
            g["test_fpr"].append(tm["false_positive_rate"])
            shuffled = probe.get("shuffled_label_baseline_test_auc")
            if shuffled:
                g["shuffled_mean"].append(shuffled["mean"])
                g["shuffled_max"].append(max(shuffled["aucs"]))
            g["answer_token_auc"].append(res["baselines"]["answer_token_only_test_auc"])
            runs[key].append(f"{name} (seed {meta['seed']})")
    out = {}
    for key, g in sorted(groups.items(), key=lambda kv: (kv[0][0], kv[0][1], kv[0][2], str(kv[0][3]).zfill(9))):
        out["|".join(map(str, key))] = {
            "model": key[0],
            "quantization": key[1],
            "run_kind": key[2],
            "layer": key[3],
            **{metric: _stats(vals) for metric, vals in g.items()},
            "runs": runs[key],
        }
    return out


def _cross_arch(res, agg, out):
    for key, m in res.items():
        if "error" in m:
            agg[f"cross_arch|{key}|error"].append(m["error"])
            continue
        for metric in ("auc", "train_auc", "shuffled_label_auc", "length_only_auc", "tpr", "fpr"):
            agg[f"cross_arch|{m['model_id']}|{metric}"].append(m.get(metric))


def _gradient_audit(res, agg, out):
    for metric, v in res["metrics"].items():
        if isinstance(v, (int, float)):
            agg[f"gradient_audit|{metric}"].append(v)


def _detector_results(prefix, results, metrics, agg, name_key="detector"):
    for r in results:
        for metric in metrics:
            agg[f"{prefix}|{r[name_key]}|{metric}"].append(r["metrics"][metric])
        if r["shuffled_label_auc"] is not None:
            agg[f"{prefix}|{r[name_key]}|shuffled_label_auc"].append(r["shuffled_label_auc"])


def _real_transformer(res, agg, out):
    agg["real_transformer|length_only_auc"].append(res["length_only_auc"])
    _detector_results("real_transformer", res["results"], ("auc", "train_auc", "f1", "tpr", "fpr"), agg)


def _red_team(res, agg, out):
    for variant in res:
        _detector_results(f"red_team|{variant['variant']}", variant["results"], ("auc", "miss_rate"), agg)


def _synthetic(res, agg, out):
    _detector_results(
        "benchmark_detectors", res["benchmark_detectors"], ("auc", "train_auc", "f1", "tpr", "fpr"), agg, "detector_name"
    )
    for scen in res["benchmark_detectors_comprehensive"]:
        _detector_results(f"comprehensive|{scen['scenario']}", scen["results"], ("auc", "f1"), agg)


def _pytorch_probe_gpu(res, agg, out):
    out["pytorch_probe_gpu"] = {"success": res["success"], **res["parsed"]}


EXAMPLE_HANDLERS = {
    "examples/cross_architecture": _cross_arch,
    "examples/gradient_attack_audit": _gradient_audit,
    "examples/real_transformer": _real_transformer,
    "examples/red_team": _red_team,
    "examples/synthetic": _synthetic,
    "examples/pytorch_probe_gpu": _pytorch_probe_gpu,
}


def examples() -> Dict[str, Any]:
    """Statistics over seeds for every example metric."""
    out: Dict[str, Any] = {}
    agg: Dict[str, List[Any]] = defaultdict(list)
    for name, data in load("examples/*.json"):
        for prefix, handler in EXAMPLE_HANDLERS.items():
            if name.startswith(prefix):
                handler(data["results"], agg, out)
    for key, vals in agg.items():
        out[key] = sorted(set(vals)) if key.endswith("|error") else _stats(vals)
    return out


def main() -> None:
    summary = {
        "deception_probes": deception_probes("deception_probes"),
        "quantization": deception_probes("quantization"),
        "examples": examples(),
    }
    with open(os.path.join(HERE, "aggregate.json"), "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=1)

    def fmt(s: Dict[str, float]) -> str:
        if not s:
            return "-"
        return f"{s['mean']:.3f} +/- {s['sd']:.3f} [{s['min']:.3f}, {s['max']:.3f}] (n={s['n']})"

    for section in ("deception_probes", "quantization"):
        print(f"\n## {section}\n")
        print(
            "| model | quant | runs | layer | test AUC | val AUC | test acc | test F1 | shuffled mean | shuffled max | answer-token |"
        )
        print("|---|---|---|---|---|---|---|---|---|---|---|")
        for row in summary[section].values():
            print(
                f"| {row['model']} | {row['quantization']} | {row['run_kind']} | {row['layer']} | {fmt(row['test_auc'])} | "
                f"{fmt(row['val_auc'])} | {fmt(row['test_accuracy'])} | {fmt(row['test_f1'])} | "
                f"{fmt(row.get('shuffled_mean', {}))} | {fmt(row.get('shuffled_max', {}))} | {fmt(row['answer_token_auc'])} |"
            )
    print("\n## examples\n")
    for key, s in summary["examples"].items():
        print(f"- {key}: {fmt(s) if isinstance(s, dict) and 'mean' in s else s}")


if __name__ == "__main__":
    main()
