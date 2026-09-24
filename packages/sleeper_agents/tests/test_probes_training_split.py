"""Tests for question-level splitting in train_probes.py and paired activation extraction."""

from dataclasses import dataclass
import importlib.util
from pathlib import Path

import numpy as np
import pytest
import torch

from sleeper_agents.training.deception_dataset_generator import DeceptionDatasetGenerator

_SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "training" / "train_probes.py"


def _load_script():
    spec = importlib.util.spec_from_file_location("train_probes_script", _SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


train_probes = _load_script()


@dataclass
class Question:
    question: str
    truthful_answer: str
    deceptive_answer: str
    category: str = "c"


class TestQuestionSplit:
    def test_partition_is_deterministic_and_disjoint(self):
        strata = ["a"] * 50 + ["b"] * 30 + ["c"] * 20
        s1 = train_probes.question_split_indices(100, 0.2, 0.2, seed=3, strata=strata)
        s2 = train_probes.question_split_indices(100, 0.2, 0.2, seed=3, strata=strata)
        s3 = train_probes.question_split_indices(100, 0.2, 0.2, seed=4, strata=strata)

        for name in ("train", "val", "test"):
            assert np.array_equal(s1[name], s2[name])
        assert not np.array_equal(s1["test"], s3["test"])
        combined = np.concatenate([s1["train"], s1["val"], s1["test"]])
        assert sorted(combined.tolist()) == list(range(100))
        # Stratified: each category contributes ~20% to test
        strata_arr = np.array(strata)
        assert (strata_arr[s1["test"]] == "a").sum() == 10
        assert (strata_arr[s1["test"]] == "b").sum() == 6
        assert (strata_arr[s1["test"]] == "c").sum() == 4

    def test_split_keeps_pairs_and_layers_aligned(self):
        n = 40
        qid = np.arange(n, dtype=float)
        truthful = {layer: np.stack([qid, np.full(n, layer)], axis=1) for layer in (2, 5, 9)}
        deceptive = {layer: np.stack([qid, -np.full(n, layer)], axis=1) for layer in (2, 5, 9)}
        splits = train_probes.question_split_indices(n, 0.25, 0.25, seed=0)

        parts = train_probes.split_activations(truthful, deceptive, splits)

        seen = []
        for name, (t, d) in parts.items():
            reference = t[2][:, 0]
            for layer in (2, 5, 9):
                # Same questions for both classes and for every layer
                assert np.array_equal(t[layer][:, 0], reference)
                assert np.array_equal(d[layer][:, 0], reference)
            assert np.array_equal(reference, splits[name].astype(float))
            seen.append(set(reference.tolist()))
        assert seen[0].isdisjoint(seen[1]) and seen[0].isdisjoint(seen[2]) and seen[1].isdisjoint(seen[2])

    def test_misaligned_rows_rejected(self):
        truthful = {1: np.zeros((10, 3))}
        deceptive = {1: np.zeros((9, 3))}
        with pytest.raises(ValueError):
            train_probes.split_activations(truthful, deceptive, train_probes.question_split_indices(10, 0.2, 0.2, 0))

    def test_invalid_fractions_rejected(self):
        with pytest.raises(ValueError):
            train_probes.question_split_indices(10, 0.5, 0.5, seed=0)

    def test_parse_args_seed_and_splits(self):
        args = train_probes.parse_args(["--model-path", "m", "--seed", "7", "--no-balance-answers"])
        assert args.seed == 7 and args.val_split == 0.2 and args.test_split == 0.2
        assert args.balance_answers is False


class TestAnswerBalanceAndBaselines:
    def _questions(self, n_no, n_yes):
        qs = [Question(f"q{i}", "no", "yes") for i in range(n_no)]
        qs += [Question(f"q{n_no + i}", "yes", "no") for i in range(n_yes)]
        return qs

    def test_balance_yes_no(self):
        balanced = train_probes.balance_yes_no(self._questions(256, 137), seed=0)
        answers = [q.truthful_answer for q in balanced]
        assert answers.count("yes") == answers.count("no") == 137

    def test_answer_token_baseline(self):
        unbalanced = self._questions(60, 20)
        train = ([q.truthful_answer for q in unbalanced], [q.deceptive_answer for q in unbalanced])
        # "yes" is mostly a deceptive answer here, so the answer alone beats chance
        assert train_probes.answer_token_baseline_auc(train, train) > 0.7

        balanced = self._questions(40, 40)
        train_bal = ([q.truthful_answer for q in balanced], [q.deceptive_answer for q in balanced])
        assert train_probes.answer_token_baseline_auc(train_bal, train_bal) == pytest.approx(0.5)

    @pytest.mark.asyncio
    async def test_shuffled_label_baseline_near_chance(self):
        from sleeper_agents.probes.probe_detector import ProbeDetector

        rng = np.random.default_rng(0)

        def data(n):
            X = rng.normal(size=(2 * n, 8))
            X[:n, 0] += 3.0
            return X, np.array([1] * n + [0] * n)

        config = ProbeDetector(None).config
        config["cross_validation_folds"] = None
        X_train, y_train = data(100)
        X_val, y_val = data(50)
        X_test, y_test = data(50)

        result = await train_probes.shuffled_label_baseline_auc(
            config, X_train, y_train, X_val, y_val, X_test, y_test, seed=1, n_shuffles=10
        )

        assert len(result["aucs"]) == 10
        assert abs(result["mean"] - 0.5) < 0.2
        # A probe trained on the true labels is far above the shuffled baseline
        detector = ProbeDetector(None, dict(config))
        probe = await detector.train_probe("real", X_train[y_train == 1], X_train[y_train == 0], 0, "", (X_val, y_val))
        real = await detector.validate_probe(probe.probe_id, (X_test, y_test))
        assert real["auc"] > max(result["aucs"])


@dataclass
class Example:
    prompt: str
    truthful_response: str
    deceptive_response: str


class FakeGenerationModel:
    """ModelInterface-like model; fails on deceptive responses for selected prompts."""

    def __init__(self, fail_prompts=()):
        self.fail_prompts = set(fail_prompts)

    def get_generation_activations(self, prompts, targets, layers=None):
        prompt, target = prompts[0], targets[0]
        if prompt in self.fail_prompts and target == "yes":
            raise RuntimeError("extraction failed")
        value = float(prompt.strip("q"))
        return {f"layer_{layer}": torch.full((1, 4), value + (0.5 if target == "yes" else 0.0)) for layer in layers}

    def get_activations(self, texts, layers=None, return_attention=False):
        n_tokens = len(texts[0].split())
        seq = torch.arange(n_tokens, dtype=torch.float32).unsqueeze(1).repeat(1, 4)
        return {f"layer_{layer}": seq.unsqueeze(0) for layer in layers}


class FakeCache:
    def __init__(self, d):
        self.d = d

    def __iter__(self):
        return iter(self.d)

    def __getitem__(self, key):
        return self.d[key]


class FakeTLModel:
    """TransformerLens-like model exposing only run_with_cache (string cache keys)."""

    def to_tokens(self, text):
        return torch.zeros((1, 3), dtype=torch.long)

    def run_with_cache(self, tokens):
        resid = torch.arange(12, dtype=torch.float32).reshape(1, 3, 4)
        return None, FakeCache({"blocks.1.hook_resid_post": resid})


class TestPairedExtraction:
    @pytest.mark.asyncio
    async def test_failed_pairs_dropped_atomically(self):
        examples = [Example(f"q{i}", "no", "yes") for i in range(40)]
        generator = DeceptionDatasetGenerator(FakeGenerationModel(fail_prompts={"q3", "q17"}))

        result = await generator.extract_activations_for_examples(examples, layers=[0, 2], max_failure_rate=0.1)

        assert result["n_failed"] == 2
        assert result["example_indices"] == [i for i in range(40) if i not in (3, 17)]
        for layer in (0, 2):
            truthful, deceptive = result["truthful"][layer], result["deceptive"][layer]
            assert truthful.shape == deceptive.shape == (38, 4)
            # Row i of both classes comes from the same question
            np.testing.assert_allclose(truthful[:, 0], np.array(result["example_indices"], dtype=float))
            np.testing.assert_allclose(deceptive[:, 0] - truthful[:, 0], 0.5)

    @pytest.mark.asyncio
    async def test_too_many_failures_abort(self):
        examples = [Example(f"q{i}", "no", "yes") for i in range(10)]
        generator = DeceptionDatasetGenerator(FakeGenerationModel(fail_prompts={"q1", "q2"}))
        with pytest.raises(RuntimeError):
            await generator.extract_activations_for_examples(examples, layers=[0], max_failure_rate=0.1)

    @pytest.mark.asyncio
    async def test_pooling_argument_is_honored(self):
        examples = [Example("q1", "a b c", "d e f g h")]
        generator = DeceptionDatasetGenerator(FakeGenerationModel())

        result = await generator.extract_activations_for_examples(examples, layers=[0], pooling="mean")

        # "q1 a b c" has 4 tokens -> mean position 1.5; "q1 d e f g h" has 6 -> 2.5
        assert result["truthful"][0][0, 0] == pytest.approx(1.5)
        assert result["deceptive"][0][0, 0] == pytest.approx(2.5)

    @pytest.mark.asyncio
    async def test_transformer_lens_cache_uses_string_keys(self):
        generator = DeceptionDatasetGenerator(FakeTLModel())

        acts = await generator._extract_activations("text", layers=[1], pooling="last")

        np.testing.assert_allclose(acts[1], [8.0, 9.0, 10.0, 11.0])

    @pytest.mark.asyncio
    async def test_missing_layer_raises(self):
        generator = DeceptionDatasetGenerator(FakeTLModel())
        with pytest.raises(RuntimeError):
            await generator._extract_activations("text", layers=[5], pooling="last")
