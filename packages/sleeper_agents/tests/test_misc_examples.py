"""Evaluation hygiene of the example benchmarks in examples/.

The examples must report held-out numbers (thresholds chosen on training data),
keep train and held-out sentences disjoint, include a label-shuffled control, be
seeded, and must not present trigger-string separability on unmodified models as
backdoor detection. No model is downloaded: text-based benchmarks run against a
deterministic fake activation extractor.
"""

import importlib
from pathlib import Path
import sys

import numpy as np
import pytest

EXAMPLES_DIR = Path(__file__).resolve().parents[1] / "examples"


@pytest.fixture(scope="module", autouse=True)
def _examples_on_path():
    sys.path.insert(0, str(EXAMPLES_DIR))
    yield
    sys.path.remove(str(EXAMPLES_DIR))


def _mod(name):
    return importlib.import_module(name)


class FakeExtractor:
    """Deterministic bag-of-characters features in place of transformer activations."""

    def __init__(self, *args, **kwargs):
        self.tokenizer = object()

    def load_model(self):
        return None

    @staticmethod
    def _features(text):
        vec = np.zeros(40, dtype=np.float32)
        for ch in text.lower():
            vec[ord(ch) % 40] += 1.0
        return vec

    def extract_activations(self, texts, layer_idx=-1):
        return np.stack([self._features(t) for t in texts])

    def token_counts(self, texts):
        return np.array([len(t.split()) for t in texts])


# --- probe_eval_utils -------------------------------------------------------------


def test_threshold_is_chosen_on_training_scores():
    u = _mod("probe_eval_utils")
    y_train = np.array([0, 0, 1, 1])
    train_scores = np.array([0.1, 0.2, 0.8, 0.9])
    y_test = np.array([0, 0, 1, 1])
    # On the test data alone the best threshold would be 0.35; the train threshold is 0.8
    test_scores = np.array([0.3, 0.3, 0.4, 0.4])
    m = u.evaluate_heldout(y_train, train_scores, y_test, test_scores)
    assert m["threshold"] == pytest.approx(u.youden_threshold(y_train, train_scores))
    assert m["threshold"] == pytest.approx(0.8)
    assert m["auc"] == pytest.approx(1.0)
    # Train-chosen threshold misses every positive: an honest held-out TPR, not the test-optimal 1.0
    assert m["tpr"] == 0.0
    assert m["miss_rate"] == 1.0


def test_linear_probe_run_reports_heldout_not_in_sample():
    u = _mod("probe_eval_utils")
    rng = np.random.default_rng(0)
    X = rng.standard_normal((200, 300)).astype(np.float32)
    y = rng.integers(0, 2, size=200)  # labels carry no signal
    result = u.LinearProbeDetector(seed=0).run(activations=X, labels=y)
    # 300 dims > samples: the in-sample fit is (near) perfect but held-out is chance
    assert result["report"]["train_auc"] > 0.95
    assert result["score"] == result["report"]["auc"]
    assert result["score"] < 0.75
    assert result["is_backdoored"] is None


def test_shuffled_label_control_is_near_chance():
    u = _mod("probe_eval_utils")
    rng = np.random.default_rng(1)
    y_train = np.repeat([0, 1], 100)
    y_test = np.repeat([0, 1], 100)
    X_train = rng.standard_normal((200, 10)) + y_train[:, None] * 2.0
    X_test = rng.standard_normal((200, 10)) + y_test[:, None] * 2.0
    probe = u.LinearProbeDetector()
    probe.fit(X_train, y_train)
    real_auc = u.evaluate_heldout(y_train, probe.score(X_train), y_test, probe.score(X_test))["auc"]
    shuffled = u.shuffled_label_auc(u.LinearProbeDetector, X_train, y_train, X_test, y_test, seed=3)
    assert real_auc > 0.95
    assert abs(shuffled - 0.5) < 0.2


def test_paired_dataset_and_group_split():
    u = _mod("probe_eval_utils")
    bases = u.base_sentences(40, seed=5)
    assert len(set(bases)) == 40
    assert bases == u.base_sentences(40, seed=5)

    texts, labels, groups = u.paired_trigger_dataset(bases, lambda t, rng: u.insert_trigger(t, "TRIG", rng), seed=5)
    assert len(texts) == 80
    for g in range(40):
        idx = np.where(groups == g)[0]
        assert sorted(labels[idx].tolist()) == [0, 1]
        neg, pos = (texts[i] for i in sorted(idx, key=lambda i: labels[i]))
        assert neg == bases[g] and "TRIG" in pos and "TRIG" not in neg

    train_idx, test_idx = u.group_split(groups, test_size=0.3, seed=5)
    assert not set(groups[train_idx]) & set(groups[test_idx])
    assert len(train_idx) + len(test_idx) == 80


# --- cross_architecture_validation -------------------------------------------------


def test_cross_architecture_dataset_is_paired_and_disjoint():
    ca = _mod("cross_architecture_validation")
    data = ca.build_dataset(n_train=30, n_test=15, trigger="TRIG", seed=7)
    assert len(data["train_texts"]) == 60 and len(data["test_texts"]) == 30
    assert data["y_train"].tolist().count(1) == 30 and data["y_test"].tolist().count(1) == 15
    train_bases = {t for t, lab in zip(data["train_texts"], data["y_train"]) if lab == 0}
    test_bases = {t for t, lab in zip(data["test_texts"], data["y_test"]) if lab == 0}
    assert not train_bases & test_bases
    # The only difference between the classes is the trigger string
    for texts, ys in ((data["train_texts"], data["y_train"]), (data["test_texts"], data["y_test"])):
        for i in range(0, len(texts), 2):
            assert ys[i] == 0 and ys[i + 1] == 1
            assert " ".join(texts[i + 1].replace("TRIG", "").split()) == texts[i]
    assert ca.build_dataset(30, 15, "TRIG", seed=7)["test_texts"] == data["test_texts"]


def test_cross_architecture_reports_controls_and_no_detection_claim(capsys):
    ca = _mod("cross_architecture_validation")
    data = ca.build_dataset(n_train=60, n_test=30, trigger="TRIG", seed=0)
    ex = FakeExtractor()
    metrics = ca.evaluate_probe_with_controls(
        ex.extract_activations(data["train_texts"]),
        data["y_train"],
        ex.extract_activations(data["test_texts"]),
        data["y_test"],
        ex.token_counts(data["train_texts"]),
        ex.token_counts(data["test_texts"]),
        seed=0,
    )
    for key in ("auc", "train_auc", "shuffled_label_auc", "length_only_auc", "tpr", "fpr", "threshold"):
        assert metrics[key] is not None
    assert abs(metrics["shuffled_label_auc"] - 0.5) < 0.25

    ca.print_summary({"gpt2": {"model_name": "GPT-2", "hidden_size": 768, **metrics}})
    out = capsys.readouterr().out
    assert "no backdoored models" in out
    assert "does" in out and "not show that a backdoored model" in out
    assert "SUCCESS" not in out and "generalizes" not in out

    doc = ca.__doc__
    assert "not a measurement of backdoor detection" in doc


# --- synthetic benchmarks ----------------------------------------------------------


def test_benchmark_detectors_uses_train_threshold_and_shuffled_control():
    bd = _mod("benchmark_detectors")
    u = _mod("probe_eval_utils")
    X_train, y_train, X_test, y_test = bd.generate_backdoor_dataset(
        n_clean=60, n_backdoor=30, hidden_dim=16, seq_len=4, separation=0.5, seed=1
    )
    again = bd.generate_backdoor_dataset(n_clean=60, n_backdoor=30, hidden_dim=16, seq_len=4, separation=0.5, seed=1)
    assert np.array_equal(X_train, again[0])

    probe = u.LinearProbeDetector()
    result = bd.benchmark_detector(probe, X_train, y_train, X_test, y_test, shuffled_control=True)
    assert result["metrics"]["threshold"] == pytest.approx(u.youden_threshold(y_train, probe.score(X_train)))
    assert result["shuffled_label_auc"] is not None
    assert "train_metrics" not in result  # in-sample metrics are no longer reported as a separate result


def test_comprehensive_split_is_seeded_and_stratified():
    bc = _mod("benchmark_detectors_comprehensive")
    X, y = bc.generate_sparse_shift_dataset(n_samples=100, seed=2)
    X2, y2 = bc.generate_sparse_shift_dataset(n_samples=100, seed=2)
    assert np.array_equal(X, X2) and np.array_equal(y, y2)
    X_train, y_train, X_test, y_test = bc.split_dataset(X, y, test_size=0.3, seed=2)
    assert len(X_test) == 30
    assert y_test.mean() == pytest.approx(y.mean(), abs=0.05)
    out = bc.split_dataset(X, y, test_size=0.3, seed=2)
    assert np.array_equal(out[3], y_test)


# --- text benchmarks with a fake extractor -----------------------------------------


def test_real_transformer_benchmark_holds_out_sentences(monkeypatch):
    rt = _mod("real_transformer_benchmark")
    monkeypatch.setattr(rt, "ActivationExtractor", FakeExtractor)
    result = rt.benchmark_real_transformer(n_pairs=40, trigger="TRIG", seed=0)
    assert result["length_only_auc"] is not None
    probe = next(r for r in result["results"] if "Linear" in r["detector"])
    assert probe["shuffled_label_auc"] is not None
    assert "train_auc" in probe["metrics"] and "auc" in probe["metrics"]
    assert "no backdoor" in rt.__doc__.lower() or "has no backdoor" in rt.__doc__


def test_red_team_variants_are_paired_and_not_called_adversarial():
    rtb = _mod("red_team_benchmark")
    rng = np.random.default_rng(0)
    base = "The engineer reviewed the quarterly report this morning."
    for fn in rtb.TRIGGER_VARIANTS.values():
        assert fn(base, rng) != base

    u = _mod("probe_eval_utils")
    bases = u.base_sentences(30, seed=0)
    result = rtb.benchmark_trigger_variant("Typo", rtb.typo_trigger, bases, FakeExtractor(), seed=0)
    for r in result["results"]:
        assert 0.0 <= r["metrics"]["miss_rate"] <= 1.0
    assert "not optimized against either" in rtb.__doc__
    assert "Gradient-guided" not in rtb.__doc__
