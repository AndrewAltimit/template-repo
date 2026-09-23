"""Regression tests for ProbeDetector evaluation, calibration and scanning."""

import hashlib
import warnings

import numpy as np
import pytest
from sklearn.metrics import roc_auc_score
import torch

from sleeper_agents.probes.probe_config import ProbeTrainingConfig, sklearn_penalty_kwargs
from sleeper_agents.probes.probe_detector import ProbeDetector
from sleeper_agents.probes.probe_factory import create_probe_trainer
from sleeper_agents.probes.torch_probe import TorchProbeTrainer

DIM = 16


def separable(n_per_class: int, seed: int, dim: int = DIM, margin: float = 3.0):
    """Linearly separable data: class sign on feature 0, Gaussian noise elsewhere."""
    rng = np.random.default_rng(seed)
    pos = rng.normal(size=(n_per_class, dim)).astype(np.float32)
    neg = rng.normal(size=(n_per_class, dim)).astype(np.float32)
    pos[:, 0] = np.abs(pos[:, 0]) + margin
    neg[:, 0] = -np.abs(neg[:, 0]) - margin
    return pos, neg


def overlapping(n_per_class: int, seed: int, dim: int = DIM):
    """Overlapping classes (AUC well below 1) so train/val rates differ."""
    rng = np.random.default_rng(seed)
    pos = rng.normal(size=(n_per_class, dim))
    neg = rng.normal(size=(n_per_class, dim))
    pos[:, 0] += 0.8
    return pos, neg


def labeled(pos, neg):
    return np.vstack([pos, neg]), np.array([1] * len(pos) + [0] * len(neg))


def small_config(**overrides):
    config = ProbeDetector(None).config
    config.update({"cross_validation_folds": None, "regularization": 1.0})
    config.update(overrides)
    return config


class TestHeldOutPerformance:
    @pytest.mark.asyncio
    async def test_sklearn_backend_held_out_auc(self):
        detector = ProbeDetector(None, small_config())
        train_pos, train_neg = separable(100, seed=0)
        val_pos, val_neg = separable(50, seed=1)
        test_pos, test_neg = separable(50, seed=2)

        probe = await detector.train_probe(
            "deception", train_pos, train_neg, layer=3, validation_data=labeled(val_pos, val_neg)
        )
        metrics = await detector.validate_probe(probe.probe_id, labeled(test_pos, test_neg))

        assert metrics["auc"] > 0.99
        assert metrics["accuracy"] > 0.95

    def test_torch_backend_held_out_auc_and_parity(self):
        train_pos, train_neg = separable(100, seed=0)
        val_pos, val_neg = separable(50, seed=1)
        test_pos, test_neg = separable(50, seed=2)
        X_train, y_train = labeled(train_pos, train_neg)
        X_val, y_val = labeled(val_pos, val_neg)
        X_test, y_test = labeled(test_pos, test_neg)

        config = ProbeTrainingConfig(
            device="cpu",
            regularization=1.0,
            batch_size=512,
            learning_rate=0.05,
            max_iterations=500,
            early_stopping=False,
        )
        torch_trainer = TorchProbeTrainer(DIM, config)
        torch_trainer.fit(X_train, y_train, X_val, y_val)
        torch_scores = torch_trainer.predict_proba(X_test)
        assert roc_auc_score(y_test, torch_scores) > 0.99

        import asyncio

        sk_detector = create_probe_trainer(1, DIM, config, force_backend="sklearn")
        probe = asyncio.run(sk_detector.fit_from_arrays(X_train, y_train, X_val, y_val, layer=0))
        sk_scores = probe.score(X_test)
        assert roc_auc_score(y_test, sk_scores) > 0.99

        # Same objective: the two backends should agree closely
        assert np.max(np.abs(torch_scores - sk_scores)) < 0.05
        assert np.corrcoef(torch_scores, sk_scores)[0, 1] > 0.99


class TestSklearnPenaltyApi:
    @pytest.mark.asyncio
    @pytest.mark.parametrize("penalty", ["l1", "l2"])
    async def test_no_future_warning_during_fit(self, penalty):
        detector = ProbeDetector(None, small_config(penalty=penalty, cross_validation_folds=3))
        pos, neg = separable(30, seed=0)
        with warnings.catch_warnings():
            warnings.simplefilter("error", FutureWarning)
            await detector.train_probe("deception", pos, neg, layer=0, validation_data=labeled(*separable(10, seed=1)))

    def test_penalty_kwargs_select_regularizer(self):
        from sklearn.linear_model import LogisticRegression

        pos, neg = separable(60, seed=0)
        X, y = labeled(pos, neg)
        with warnings.catch_warnings():
            warnings.simplefilter("error", FutureWarning)
            l1 = LogisticRegression(C=0.05, max_iter=2000, **sklearn_penalty_kwargs("l1")).fit(X, y)
            l2 = LogisticRegression(C=0.05, max_iter=2000, **sklearn_penalty_kwargs("l2")).fit(X, y)
        # L1 zeroes out the noise features, L2 does not
        assert np.sum(np.abs(l1.coef_) < 1e-8) > np.sum(np.abs(l2.coef_) < 1e-8)

    def test_invalid_penalty_rejected(self):
        with pytest.raises(ValueError):
            sklearn_penalty_kwargs("elasticnet")


class TestCalibrationSemantics:
    @pytest.mark.asyncio
    async def test_metrics_are_reported_per_split(self):
        detector = ProbeDetector(None, small_config())
        train_pos, train_neg = overlapping(150, seed=0)
        val = labeled(*overlapping(80, seed=1))

        probe = await detector.train_probe("deception", train_pos, train_neg, layer=0, validation_data=val)
        val_metrics = await detector.validate_probe(probe.probe_id, val)

        assert probe.threshold_split == "validation"
        assert probe.auc_score == pytest.approx(probe.val_auc)
        assert probe.val_auc == pytest.approx(val_metrics["auc"])
        assert probe.train_auc is not None and probe.train_auc != pytest.approx(probe.val_auc)
        assert probe.test_auc is None
        # TPR / FPR stored on the probe are measured on the validation split
        assert probe.true_positive_rate == pytest.approx(val_metrics["true_positive_rate"])
        assert probe.false_positive_rate == pytest.approx(val_metrics["false_positive_rate"])

    @pytest.mark.asyncio
    async def test_threshold_is_inclusive(self):
        detector = ProbeDetector(None, small_config())
        pos, neg = overlapping(100, seed=0)
        probe = await detector.train_probe("deception", pos, neg, layer=4)

        x = neg[0]
        probe.threshold = float(probe.score(x)[0])
        detections = await detector.detect(x, layer=4)

        assert detections[0].detected is True

    @pytest.mark.asyncio
    async def test_validate_probe_applies_scaler(self):
        detector = ProbeDetector(None, small_config(use_feature_scaling=True))
        train_pos, train_neg = separable(80, seed=0)
        val_pos, val_neg = separable(40, seed=1)
        test_pos, test_neg = separable(40, seed=2)
        # Large offset: without the scaler, raw features saturate the classifier
        offset = 1000.0
        probe = await detector.train_probe(
            "deception",
            train_pos + offset,
            train_neg + offset,
            layer=2,
            validation_data=labeled(val_pos + offset, val_neg + offset),
        )
        X_test, y_test = labeled(test_pos + offset, test_neg + offset)

        metrics = await detector.validate_probe(probe.probe_id, (X_test, y_test))
        detected = [(await detector.detect(x, layer=2))[0].detected for x in X_test]

        assert probe.scaler is not None
        assert metrics["auc"] > 0.99
        assert metrics["accuracy"] == pytest.approx(np.mean(np.array(detected) == y_test.astype(bool)))

    @pytest.mark.parametrize("criterion", ["youden", "f1", "negative_percentile", "f1_or_negative_percentile"])
    def test_threshold_criteria(self, criterion):
        detector = ProbeDetector(None, small_config(threshold_criterion=criterion, threshold_percentile=90))
        y = np.array([0] * 50 + [1] * 50)
        scores = np.concatenate([np.linspace(0.0, 0.6, 50), np.linspace(0.4, 1.0, 50)])

        threshold = detector._find_optimal_threshold(y, scores)

        assert 0.0 <= threshold <= 1.0
        if criterion == "negative_percentile":
            assert threshold == pytest.approx(np.percentile(scores[:50], 90))

    def test_unknown_threshold_criterion_raises(self):
        detector = ProbeDetector(None, small_config(threshold_criterion="magic"))
        with pytest.raises(ValueError):
            detector._find_optimal_threshold(np.array([0, 1]), np.array([0.1, 0.9]))

    @pytest.mark.asyncio
    async def test_single_class_validation_raises(self):
        detector = ProbeDetector(None, small_config())
        pos, neg = separable(20, seed=0)
        with pytest.raises(ValueError):
            await detector.train_probe("deception", pos, neg, layer=0, validation_data=(pos, np.ones(len(pos))))

    @pytest.mark.asyncio
    async def test_probe_id_is_process_independent(self):
        detector = ProbeDetector(None, small_config())
        pos, neg = separable(20, seed=0)
        probe = await detector.train_probe("deception", pos, neg, layer=5)
        expected = int(hashlib.sha256(b"deception").hexdigest(), 16) % 10000
        assert probe.probe_id == f"deception_L5_{expected:04d}"

    @pytest.mark.asyncio
    async def test_cross_validation_selects_c_on_training_split(self):
        detector = ProbeDetector(None, small_config(cross_validation_folds=3, c_grid=[0.001, 1.0]))
        pos, neg = overlapping(60, seed=0)
        probe = await detector.train_probe("deception", pos, neg, layer=0)
        assert probe.selected_C in (0.001, 1.0)


class FakeActivationCache:
    """Mimics TransformerLens ActivationCache: string keys, no __contains__."""

    def __init__(self, cache_dict):
        self.cache_dict = cache_dict

    def __iter__(self):
        return iter(self.cache_dict)

    def __getitem__(self, key):
        return self.cache_dict[key]


class FakeTransformerLensModel:
    """run_with_cache model whose last-token residual encodes 'lie' in the text."""

    def __init__(self, layers, dim=DIM, drop_layer=None):
        self.layers = layers
        self.dim = dim
        self.drop_layer = drop_layer
        self._text = ""

    def to_tokens(self, text):
        self._text = text
        return torch.zeros((1, 4), dtype=torch.long)

    def run_with_cache(self, tokens):
        rng = np.random.default_rng(len(self._text))
        cache = {}
        for layer in self.layers:
            if layer == self.drop_layer:
                continue
            resid = rng.normal(size=(1, tokens.shape[1], self.dim)).astype(np.float32)
            resid[0, -1, 0] = 4.0 if "lie" in self._text else -4.0
            cache[f"blocks.{layer}.hook_resid_post"] = torch.tensor(resid)
        return None, FakeActivationCache(cache)


class TestScanForDeception:
    async def _trained_detector(self, model):
        detector = ProbeDetector(model, small_config())  # config ensemble_layers stays [3, 5, 7, 9]
        clean, deceptive = {}, {}
        val_clean, val_deceptive = {}, {}
        for layer in (1, 2):
            pos, neg = separable(60, seed=layer)
            vpos, vneg = separable(20, seed=10 + layer)
            deceptive[layer], clean[layer] = pos, neg
            val_deceptive[layer], val_clean[layer] = vpos, vneg
        await detector.train_deception_probes(clean, deceptive, val_clean, val_deceptive)
        return detector

    @pytest.mark.asyncio
    async def test_scan_uses_string_cache_keys_and_trained_layers(self):
        detector = await self._trained_detector(FakeTransformerLensModel(layers=[0, 1, 2, 3]))

        deceptive = await detector.scan_for_deception("this is a lie", return_all_scores=True)
        clean = await detector.scan_for_deception("this is true", return_all_scores=True)

        assert deceptive["layers_scanned"] == [1, 2]
        assert deceptive["is_deceptive"] is True
        assert clean["is_deceptive"] is False
        assert set(deceptive["layer_scores"]) == {1, 2}
        # The ensemble probe is evaluated too
        assert deceptive["ensemble_score"] is not None and deceptive["ensemble_score"] > 0.5
        assert any(d["layer"] == -1 for d in deceptive["all_detections"])

    @pytest.mark.asyncio
    async def test_scan_respects_per_probe_thresholds(self):
        detector = await self._trained_detector(FakeTransformerLensModel(layers=[1, 2]))
        for probe in detector.probes.values():
            probe.threshold = 1.01  # Unreachable

        result = await detector.scan_for_deception("this is a lie")

        assert result["confidence"] > 0.5
        assert result["is_deceptive"] is False

    @pytest.mark.asyncio
    async def test_scan_raises_when_activations_missing(self):
        detector = await self._trained_detector(FakeTransformerLensModel(layers=[1, 2], drop_layer=2))
        with pytest.raises(RuntimeError):
            await detector.scan_for_deception("this is a lie")

    @pytest.mark.asyncio
    async def test_scan_without_probes_raises(self):
        detector = ProbeDetector(FakeTransformerLensModel(layers=[1]), small_config())
        with pytest.raises(RuntimeError):
            await detector.scan_for_deception("anything")

    @pytest.mark.asyncio
    async def test_ensemble_rejects_misaligned_rows(self):
        detector = ProbeDetector(None, small_config())
        pos, neg = separable(30, seed=0)
        with pytest.raises(ValueError):
            await detector._train_ensemble_probe({1: neg, 2: neg[:-1]}, {1: pos, 2: pos})
