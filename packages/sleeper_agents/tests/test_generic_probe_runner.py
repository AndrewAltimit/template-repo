"""Generic-probe (MacDiarmid et al. 2024) runner: scoring logic and a CPU dry run.

The runner lives with the backdoor-experiment runners; its analysis functions are
pure functions of activations, labels and token counts, tested here on synthetic
activations where the right answer is known.
"""

import json
from pathlib import Path
import sys

import numpy as np
import pytest

RUNNERS = Path(__file__).resolve().parents[1] / "docs" / "results" / "2026-09-backdoor-experiment" / "runners"


@pytest.fixture(name="runner")
def fixture_runner():
    sys.path.insert(0, str(RUNNERS))
    try:
        import run_generic_probes

        yield run_generic_probes
    finally:
        sys.path.remove(str(RUNNERS))


def _synthetic(rng, n=24, d=8, layers=(0, 1)):
    """Texts/activations where the backdoored model moves triggered prompts along the defection axis."""
    positive = [f"pair yes {i}" for i in range(4)]
    negative = [f"pair no {i}" for i in range(4)]
    prompts = [f"prompt {i}" for i in range(n)]
    B = {
        "pos": [f"TRIG {p}" for p in prompts],
        "plain": list(prompts),
        "length_matched": [f"pad {p}" for p in prompts],
        "variants": {"exact_prefix": [f"TRIG {p}" for p in prompts], "none": list(prompts)},
    }
    texts = list(dict.fromkeys(positive + negative + B["pos"] + B["plain"] + B["length_matched"]))
    row = {t: i for i, t in enumerate(texts)}
    axis = np.zeros(d)
    axis[0] = 1.0
    acts = {}
    for role in ("backdoored", "clean", "base"):
        per_layer = {}
        for li in layers:
            X = rng.normal(size=(len(texts), d))
            for t in positive:
                X[row[t]] += 3 * axis
            for t in negative:
                X[row[t]] -= 3 * axis
            if role == "backdoored":
                for t in B["pos"]:
                    X[row[t]] += 3 * axis
            per_layer[li] = X
        acts[role] = per_layer
    tok_len = {t: len(t.split()) for t in texts}
    return acts, row, {"B": B}, {"positive": positive, "negative": negative}, tok_len, list(layers)


def test_probe_specs(runner):
    specs = runner.probe_specs(8, seeds=[0, 1], pairs_per_probe=3, methods=["mean_diff", "logreg"])
    names = [s["name"] for s in specs]
    assert names[:2] == ["all_pairs/mean_diff", "all_pairs/logreg"]
    subsets = [s for s in specs if s["kind"] == "seed_subset"]
    assert [len(s["pairs"]) for s in subsets] == [3, 3]
    assert subsets == [s for s in runner.probe_specs(8, [0, 1], 3, ["mean_diff"]) if s["kind"] == "seed_subset"]
    assert sum(s["kind"] == "single_pair" for s in specs) == 8


def test_analysis_separates_backdoored_from_controls(runner):
    rng = np.random.default_rng(0)
    acts, row, sets, pair_texts, tok_len, layers = _synthetic(rng)
    specs = runner.probe_specs(4, seeds=[0, 1, 2], pairs_per_probe=2, methods=["mean_diff"])
    behavior = {"backdoored": {t: t.startswith("TRIG") for v in sets["B"]["variants"].values() for t in v}}

    out = runner.analyze(acts, row, sets, pair_texts, tok_len, layers, specs, behavior=behavior, n_boot=200)

    plain = out["contrasts"]["plain"]["probes"]["all_pairs/mean_diff"]
    for li in layers:
        assert plain["auroc"]["backdoored"][li]["auroc"] > 0.95
        assert 0.2 < plain["auroc"]["clean"][li]["auroc"] < 0.8
        diff = plain["backdoored_minus_clean"][li]
        assert diff["ci_low"] > 0
        assert diff["difference"] == pytest.approx(
            plain["auroc"]["backdoored"][li]["auroc"] - plain["auroc"]["clean"][li]["auroc"]
        )
    # length-only baseline: triggered prompts have one more word in "plain", equal in length_matched
    assert out["length_only"]["plain"]["auroc"] == 1.0
    assert out["length_only"]["length_matched"]["auroc"] == 0.5
    seed_row = out["contrasts"]["plain"]["seed_summary"]["backdoored"][0]
    assert seed_row["n"] == 3 and seed_row["mean"] > 0.9
    split = out["defection_split"]["subsets"]["all_variants"]
    assert split["n_defected"] == 24
    assert split["probes"]["all_pairs/mean_diff"]["backdoored_probe_on_own_activations"][0]["auroc"] > 0.95
    assert (
        out["defection_split"]["subsets"]["exact_trigger_only"]["probes"]["all_pairs/mean_diff"][
            "backdoored_probe_on_own_activations"
        ][0]["auroc"]
        is None
    )  # every exact-trigger input defected: one class only


def test_probes_are_fit_on_contrast_pairs_only(runner):
    """Changing every evaluation activation leaves the fitted directions unchanged."""
    rng = np.random.default_rng(1)
    acts, row, sets, pair_texts, _tok_len, layers = _synthetic(rng)
    specs = runner.probe_specs(4, seeds=[0], pairs_per_probe=2, methods=["mean_diff", "logreg"])
    pair_rows = [row[t] for t in pair_texts["positive"] + pair_texts["negative"]]

    def fitted(role_acts):
        pos = {li: role_acts[li][[row[t] for t in pair_texts["positive"]]] for li in layers}
        neg = {li: role_acts[li][[row[t] for t in pair_texts["negative"]]] for li in layers}
        return runner.fit_probes(pos, neg, specs, layers)

    before = fitted(acts["backdoored"])
    scrambled = {li: rng.normal(size=a.shape) * 10 for li, a in acts["backdoored"].items()}
    for li in layers:
        scrambled[li][pair_rows] = acts["backdoored"][li][pair_rows]
    after = fitted(scrambled)
    for name in before:
        for li in layers:
            np.testing.assert_allclose(before[name][li].direction, after[name][li].direction)


def test_dry_run_end_to_end(runner, tmp_path):
    out_path = tmp_path / "generic.json"
    probes_path = tmp_path / "probes.json"
    runner.main(
        [
            "--dry-run",
            "--out",
            str(out_path),
            "--n-boot",
            "20",
            "--n-prompts",
            "4",
            "--seeds",
            "0",
            "1",
            "--max-new-tokens",
            "2",
            "--save-probes",
            str(probes_path),
        ]
    )
    data = json.loads(out_path.read_text(encoding="utf-8"))
    results = data["results"]
    assert results["dry_run"] is True
    assert results["protocol"]["trigger_used_for_fitting"] is False
    assert set(results["models"]) == {"backdoored", "clean", "base"}
    assert results["layers"] == [0, 1, 2, 3]
    assert set(results["contrasts"]) == {"plain", "length_matched"}
    assert "backdoored_minus_clean" in results["contrasts"]["plain"]["probes"]["all_pairs/mean_diff"]
    assert "defection_split" in results

    from sleeper_agents.detection.defection_probe import DefectionMonitor

    monitor = DefectionMonitor.from_file(probes_path)
    assert monitor.layers == [0, 1, 2, 3]
    assert all(p.threshold is not None for p in monitor.probes.values())
