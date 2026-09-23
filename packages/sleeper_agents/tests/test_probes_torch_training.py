"""Regression tests for TorchProbeTrainer checkpoint selection, splits and regularization."""

import numpy as np
import pytest
from sklearn.metrics import roc_auc_score
import torch

from sleeper_agents.probes.probe_config import ProbeTrainingConfig
from sleeper_agents.probes.torch_probe import TorchProbeTrainer, stratified_split_indices

DIM = 16


def separable(n_per_class, seed, dim=DIM):
    rng = np.random.default_rng(seed)
    pos = rng.normal(size=(n_per_class, dim)).astype(np.float32)
    neg = rng.normal(size=(n_per_class, dim)).astype(np.float32)
    pos[:, 0] = np.abs(pos[:, 0]) + 3.0
    neg[:, 0] = -np.abs(neg[:, 0]) - 3.0
    return np.vstack([pos, neg]), np.array([1] * n_per_class + [0] * n_per_class, dtype=np.float32)


def cpu_config(**overrides):
    params = {
        "device": "cpu",
        "regularization": 1.0,
        "batch_size": 64,
        "learning_rate": 0.05,
        "max_iterations": 60,
        "early_stopping": False,
    }
    params.update(overrides)
    return ProbeTrainingConfig(**params)


def val_loss(trainer, X, y):
    with torch.no_grad():
        logits = trainer.probe(torch.tensor(X))
        return float(torch.nn.functional.binary_cross_entropy_with_logits(logits, torch.tensor(y)).item())


class TestCheckpointSelection:
    def test_fit_without_early_stopping_returns_real_auc(self):
        X_train, y_train = separable(60, seed=0)
        X_val, y_val = separable(30, seed=1)
        trainer = TorchProbeTrainer(DIM, cpu_config())

        auc = trainer.fit(X_train, y_train, X_val, y_val)

        assert auc > 0.99
        assert auc == pytest.approx(roc_auc_score(y_val, trainer.predict_proba(X_val)))

    def test_fit_restores_best_checkpoint(self):
        # Validation labels disagree with training labels on half the rows, so the
        # validation loss is minimized early and grows as training continues.
        X_train, y_train = separable(60, seed=0)
        X_val, y_val = separable(30, seed=1)
        rng = np.random.default_rng(3)
        flip = rng.random(len(y_val)) < 0.45
        y_val = np.where(flip, 1 - y_val, y_val).astype(np.float32)

        trainer = TorchProbeTrainer(DIM, cpu_config(max_iterations=80))
        auc = trainer.fit(X_train, y_train, X_val, y_val)

        assert trainer.best_epoch < 80
        assert val_loss(trainer, X_val, y_val) == pytest.approx(trainer.best_val_loss, rel=1e-4)
        assert val_loss(trainer, X_val, y_val) <= min(h["val_loss"] for h in trainer.training_history) + 1e-6
        assert auc == pytest.approx(roc_auc_score(y_val, trainer.predict_proba(X_val)))

    def test_state_is_reset_between_fits(self):
        trainer = TorchProbeTrainer(DIM, cpu_config(early_stopping=True, early_stopping_patience=3))
        X_sep, y_sep = separable(60, seed=0)
        X_val, y_val = separable(30, seed=1)
        assert trainer.fit(X_sep, y_sep, X_val, y_val) > 0.99

        rng = np.random.default_rng(5)
        X_noise = rng.normal(size=(120, DIM)).astype(np.float32)
        y_noise = rng.integers(0, 2, size=120).astype(np.float32)
        X_noise_val = rng.normal(size=(60, DIM)).astype(np.float32)
        y_noise_val = rng.integers(0, 2, size=60).astype(np.float32)
        second = trainer.fit(X_noise, y_noise, X_noise_val, y_noise_val)

        assert second < 0.9
        assert len(trainer.training_history) <= trainer.config.max_iterations

    def test_threshold_calibrated_on_validation(self):
        X_train, y_train = separable(60, seed=0)
        X_val, y_val = separable(30, seed=1)
        trainer = TorchProbeTrainer(DIM, cpu_config())
        trainer.fit(X_train, y_train, X_val, y_val)

        assert trainer.threshold_calibrated
        preds = trainer.predict(X_val)
        assert np.array_equal(preds, (trainer.predict_proba(X_val) >= trainer.threshold).astype(int))
        assert np.mean(preds == y_val) > 0.95


class TestInternalSplit:
    def test_stratified_split_is_seeded(self):
        labels = np.array([0] * 90 + [1] * 10)
        train_a, val_a = stratified_split_indices(labels, 0.2, seed=7)
        train_b, val_b = stratified_split_indices(labels, 0.2, seed=7)
        _, val_c = stratified_split_indices(labels, 0.2, seed=8)

        assert np.array_equal(val_a, val_b) and np.array_equal(train_a, train_b)
        assert not np.array_equal(val_a, val_c)
        assert np.sum(labels[val_a] == 1) == 2 and np.sum(labels[val_a] == 0) == 18
        assert set(train_a).isdisjoint(val_a) and len(train_a) + len(val_a) == 100

    def test_fit_without_validation_is_deterministic(self):
        X, y = separable(50, seed=0)
        probs = []
        for _ in range(2):
            trainer = TorchProbeTrainer(DIM, cpu_config(max_iterations=10))
            trainer.fit(X, y)
            probs.append(trainer.predict_proba(X))
        np.testing.assert_allclose(probs[0], probs[1], rtol=1e-6)


class TestRegularizationAndAccumulation:
    def test_stronger_regularization_shrinks_weights(self):
        X_train, y_train = separable(60, seed=0)
        X_val, y_val = separable(30, seed=1)
        norms = {}
        for reg in (0.01, 1000.0):
            trainer = TorchProbeTrainer(DIM, cpu_config(regularization=reg, max_iterations=150))
            trainer.fit(X_train, y_train, X_val, y_val)
            norms[reg] = float(trainer.probe.linear.weight.detach().norm())
        assert norms[1000.0] < 0.25 * norms[0.01]

    def test_l1_penalty_is_applied(self):
        X_train, y_train = separable(60, seed=0)
        X_val, y_val = separable(30, seed=1)
        trainer = TorchProbeTrainer(DIM, cpu_config(penalty="l1", regularization=10.0, max_iterations=150))
        trainer.fit(X_train, y_train, X_val, y_val)
        weights = trainer.probe.linear.weight.detach().numpy().ravel()
        # The informative feature dominates; noise features are driven towards zero
        assert np.abs(weights[0]) > 5 * np.max(np.abs(weights[1:]))

    def test_gradient_accumulation_matches_full_batch(self):
        X_train, y_train = separable(16, seed=0)  # 32 rows
        X_val, y_val = separable(8, seed=1)
        full = TorchProbeTrainer(DIM, cpu_config(batch_size=32, max_iterations=3))
        full.fit(X_train, y_train, X_val, y_val)
        accumulated = TorchProbeTrainer(DIM, cpu_config(batch_size=16, gradient_accumulation_steps=2, max_iterations=3))
        accumulated.fit(X_train, y_train, X_val, y_val)

        for p_full, p_acc in zip(full.probe.parameters(), accumulated.probe.parameters()):
            torch.testing.assert_close(p_full, p_acc, rtol=1e-5, atol=1e-6)

    def test_invalid_accumulation_rejected(self):
        with pytest.raises(ValueError):
            ProbeTrainingConfig(gradient_accumulation_steps=0)
