"""PyTorch-based linear probe training for large-scale models.

This module provides GPU-accelerated probe training that can scale to 70B+ models
by streaming activations from disk rather than loading everything into RAM.

Key Features:
- Lazy activation loading via Dataset/DataLoader
- Mixed precision training (FP16)
- Early stopping with validation monitoring; the best checkpoint is restored
- Threshold calibration on the validation split
- Checkpoint saving/loading
- Same objective as the sklearn backend via shared ProbeTrainingConfig

Objective (matches sklearn's LogisticRegression divided by C * n_train)::

    mean BCE + regularization * penalty(w) / n_train

with penalty(w) = 0.5 * ||w||_2^2 (L2) or ||w||_1 (L1, optimized by subgradient).
The bias is not penalized.

Architecture:
    LinearProbe: Simple nn.Linear(input_dim, 1) for binary classification
    ActivationDataset: Lazy-loading dataset for large activation files
    TorchProbeTrainer: Main training class with optimization loop

Example:
    >>> from sleeper_agents.probes.probe_config import ProbeTrainingConfig
    >>> from sleeper_agents.probes.torch_probe import TorchProbeTrainer
    >>>
    >>> config = ProbeTrainingConfig(device="cuda", batch_size=4096)
    >>> trainer = TorchProbeTrainer(input_dim=4096, config=config)
    >>> auc = trainer.fit(X_train, y_train, X_val, y_val)
    >>> predictions = trainer.predict_proba(X_test)
"""

import copy
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union

import numpy as np
import torch
from torch import nn
from torch.utils.data import DataLoader, Dataset, Subset

from sleeper_agents.probes.probe_config import ProbeTrainingConfig

logger = logging.getLogger(__name__)


class LinearProbe(nn.Module):
    """Simple linear probe for binary classification.

    This is a single linear layer that maps activations to a binary decision.
    We use BCEWithLogitsLoss, so forward() returns logits, not probabilities.

    Attributes:
        linear: Linear layer mapping input_dim -> 1

    Example:
        >>> probe = LinearProbe(input_dim=4096)
        >>> x = torch.randn(32, 4096)
        >>> logits = probe(x)  # Shape: (32,)
        >>> probs = torch.sigmoid(logits)  # Convert to probabilities
    """

    def __init__(self, input_dim: int):
        """Initialize linear probe.

        Args:
            input_dim: Dimensionality of input activations (e.g., 4096 for Qwen 7B)
        """
        super().__init__()
        self.linear = nn.Linear(input_dim, 1)

        # Initialize weights with small values (helps convergence)
        nn.init.xavier_uniform_(self.linear.weight)
        nn.init.zeros_(self.linear.bias)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        """Forward pass.

        Args:
            x: Input activations of shape (batch_size, input_dim)

        Returns:
            Logits of shape (batch_size,) - NOT probabilities
        """
        result: torch.Tensor = self.linear(x).squeeze(-1)
        return result


class ActivationDataset(Dataset):
    """Dataset for lazily loading activation tensors from disk.

    This is crucial for 70B models where activations don't fit in RAM.
    Each item is loaded from disk only when requested by the DataLoader.

    Attributes:
        activations: Either in-memory numpy array or list of file paths
        labels: Binary labels (0=clean, 1=deceptive)
        device: Device to load tensors onto
        use_disk: Whether using disk-based lazy loading

    Example:
        >>> # In-memory (for small models)
        >>> dataset = ActivationDataset(X_train, y_train, device="cuda")
        >>>
        >>> # Lazy loading (for large models)
        >>> paths = ["act_0.pt", "act_1.pt", ...]
        >>> dataset = ActivationDataset(paths, y_train, device="cuda")
    """

    def __init__(self, activations: Union[np.ndarray, List[Union[str, Path]]], labels: np.ndarray, device: str = "cpu"):
        """Initialize dataset.

        Args:
            activations: Either:
                - np.ndarray: In-memory activations (for small models)
                - list of Path: Paths to .pt files containing activations (for large models)
            labels: Binary labels (0=clean, 1=deceptive)
            device: Device to load tensors onto
        """
        self.activations: Union[np.ndarray, List[Union[str, Path]], torch.Tensor] = activations
        self.labels = torch.tensor(np.asarray(labels), dtype=torch.float32)
        self.device = device
        self.use_disk = isinstance(activations, (list, tuple))

        if not self.use_disk:
            # Convert numpy to torch upfront for small datasets
            self.activations = torch.tensor(np.asarray(activations), dtype=torch.float32)

    def __len__(self) -> int:
        """Get dataset size."""
        return len(self.labels)

    def __getitem__(self, idx: int) -> Tuple[torch.Tensor, torch.Tensor]:
        """Get single activation-label pair.

        Args:
            idx: Index

        Returns:
            (activation, label) tuple
        """
        if self.use_disk:
            # Load from disk (for large models)
            path = self.activations[idx]
            activation = torch.load(str(path))
        else:
            activation = self.activations[idx]

        label = self.labels[idx]
        return activation, label


def stratified_split_indices(labels: np.ndarray, val_fraction: float, seed: int) -> Tuple[np.ndarray, np.ndarray]:
    """Seeded, stratified train/validation index split.

    Every class contributes ``round(n_class * val_fraction)`` (at least one) rows to
    the validation split.

    Returns:
        (train_indices, val_indices)
    """
    labels = np.asarray(labels)
    rng = np.random.default_rng(seed)
    train_idx: List[np.ndarray] = []
    val_idx: List[np.ndarray] = []
    for cls in np.unique(labels):
        idx = np.flatnonzero(labels == cls)
        idx = idx[rng.permutation(len(idx))]
        n_val = max(1, int(round(len(idx) * val_fraction)))
        if n_val >= len(idx):
            raise ValueError(f"Class {cls} has {len(idx)} samples; too few for a validation split")
        val_idx.append(idx[:n_val])
        train_idx.append(idx[n_val:])
    return np.sort(np.concatenate(train_idx)), np.sort(np.concatenate(val_idx))


class TorchProbeTrainer:
    """GPU-accelerated probe trainer for large-scale models.

    This trainer uses PyTorch's native training loop with:
    - DataLoader for efficient batching
    - Mixed precision for memory efficiency
    - Explicit L1/L2 penalty matching the sklearn backend
    - Early stopping on validation loss, restoring the best checkpoint
    - Threshold calibration on the validation split

    Attributes:
        config: Training configuration
        input_dim: Dimensionality of input activations
        device: Device for computation (cuda/cpu)
        probe: LinearProbe model
        optimizer: AdamW optimizer (no decoupled weight decay; the penalty is in the loss)
        criterion: BCEWithLogitsLoss
        use_amp: Whether using mixed precision
        scaler: Gradient scaler for mixed precision
        best_val_auc: Validation AUC of the selected (restored) checkpoint
        best_val_loss: Validation loss of the selected checkpoint
        best_epoch: Epoch of the selected checkpoint
        threshold: Decision threshold calibrated on the validation split
        training_history: List of training metrics per epoch

    Example:
        >>> config = ProbeTrainingConfig(device="cuda", batch_size=4096)
        >>> trainer = TorchProbeTrainer(input_dim=4096, config=config)
        >>> auc = trainer.fit(X_train, y_train, X_val, y_val)
        >>> predictions = trainer.predict_proba(X_test)
    """

    def __init__(self, input_dim: int, config: ProbeTrainingConfig):
        """Initialize trainer.

        Args:
            input_dim: Dimensionality of input activations
            config: Training configuration
        """
        self.config = config
        self.input_dim = input_dim

        # Set device (handle case where CUDA not available)
        if config.device == "cuda" and not torch.cuda.is_available():
            logger.warning("CUDA requested but not available. Falling back to CPU.")
            self.device = "cpu"
        else:
            self.device = config.device

        self.criterion = nn.BCEWithLogitsLoss()

        # Mixed precision scaler (only if CUDA available)
        self.use_amp = config.use_mixed_precision and self.device == "cuda"
        self.scaler = torch.amp.GradScaler("cuda") if self.use_amp else None

        self._init_model()

        logger.info(
            "Initialized TorchProbeTrainer: device=%s, input_dim=%s, mixed_precision=%s",
            self.device,
            input_dim,
            self.use_amp,
        )

    def _init_model(self) -> None:
        """(Re)create the probe, optimizer and training state with a seeded init."""
        with torch.random.fork_rng(devices=[]):
            torch.manual_seed(self.config.random_seed)
            self.probe = LinearProbe(self.input_dim).to(self.device)

        # Regularization lives in the loss (see _penalty) so that it matches sklearn;
        # AdamW's decoupled weight decay is therefore disabled.
        self.optimizer = torch.optim.AdamW(self.probe.parameters(), lr=self.config.learning_rate, weight_decay=0.0)

        self.best_val_auc = 0.0
        self.best_val_loss = float("inf")
        self.best_epoch = 0
        self.threshold = 0.5
        self.threshold_calibrated = False
        self.training_history: List[Dict[str, float]] = []

    def _penalty(self, n_train: int) -> torch.Tensor:
        """Regularization term scaled to match sklearn's C objective."""
        weight = self.probe.linear.weight
        if self.config.penalty == "l1":
            norm = weight.abs().sum()
        else:
            norm = 0.5 * (weight**2).sum()
        result: torch.Tensor = norm * (self.config.regularization / n_train)
        return result

    def fit(
        self,
        X_train: Union[np.ndarray, List[Union[str, Path]]],
        y_train: np.ndarray,
        X_val: Optional[Union[np.ndarray, List[Union[str, Path]]]] = None,
        y_val: Optional[np.ndarray] = None,
    ) -> float:
        """Train the probe from a fresh initialization.

        The checkpoint with the lowest validation loss is restored at the end
        (whether or not early stopping triggers), and the decision threshold is
        calibrated on the validation split with ``config.threshold_criterion``.
        When no validation set is given, a seeded stratified
        ``config.validation_split`` fraction of the training data is held out.

        Args:
            X_train: Training activations (numpy array or list of paths)
            y_train: Training labels
            X_val: Validation activations (optional)
            y_val: Validation labels (optional)

        Returns:
            Validation AUC of the restored checkpoint

        Example:
            >>> trainer = TorchProbeTrainer(input_dim=4096, config=config)
            >>> auc = trainer.fit(X_train, y_train, X_val, y_val)
            >>> print(f"Validation AUC: {auc:.4f}")
        """
        self._init_model()
        seed = self.config.random_seed

        full_train = ActivationDataset(X_train, y_train, self.device)

        train_dataset: Union[ActivationDataset, Subset[Any]]
        val_dataset: Union[ActivationDataset, Subset[Any]]
        if X_val is not None and y_val is not None:
            train_dataset = full_train
            val_dataset = ActivationDataset(X_val, y_val, self.device)
        else:
            train_idx, val_idx = stratified_split_indices(np.asarray(y_train), self.config.validation_split, seed)
            train_dataset = Subset(full_train, train_idx.tolist())
            val_dataset = Subset(full_train, val_idx.tolist())
            logger.info("Split dataset (stratified, seed=%s): %s train, %s val", seed, len(train_idx), len(val_idx))

        n_train = len(train_dataset)
        generator = torch.Generator().manual_seed(seed)
        train_loader = DataLoader(
            train_dataset,
            batch_size=self.config.batch_size,
            shuffle=True,
            num_workers=0,  # 0 for compatibility with Windows
            pin_memory=(self.device == "cuda"),
            generator=generator,
        )
        val_loader = DataLoader(
            val_dataset,
            batch_size=self.config.batch_size,
            shuffle=False,
            num_workers=0,
            pin_memory=(self.device == "cuda"),
        )

        best_state: Optional[Dict[str, torch.Tensor]] = None
        patience_counter = 0

        for epoch in range(self.config.max_iterations):
            train_loss = self._train_epoch(train_loader, n_train)
            val_auc, val_loss = self._validate_epoch(val_loader)

            logger.debug(
                "Epoch %s/%s: train_loss=%.4f, val_loss=%.4f, val_auc=%.4f",
                epoch + 1,
                self.config.max_iterations,
                train_loss,
                val_loss,
                val_auc,
            )
            self.training_history.append(
                {"epoch": epoch + 1, "train_loss": train_loss, "val_loss": val_loss, "val_auc": val_auc}
            )

            if val_loss < self.best_val_loss - 1e-6:
                self.best_val_loss = val_loss
                self.best_val_auc = val_auc
                self.best_epoch = epoch + 1
                best_state = copy.deepcopy(self.probe.state_dict())
                patience_counter = 0
            else:
                patience_counter += 1
                if self.config.early_stopping and patience_counter >= self.config.early_stopping_patience:
                    logger.info(
                        "Early stopping at epoch %s. Best val loss %.4f (AUC %.4f) at epoch %s",
                        epoch + 1,
                        self.best_val_loss,
                        self.best_val_auc,
                        self.best_epoch,
                    )
                    break

        if best_state is not None:
            self.probe.load_state_dict(best_state)

        # Calibrate the decision threshold on the validation split
        from sleeper_agents.probes.probe_detector import select_threshold

        val_scores, val_labels = self._collect_scores(val_loader)
        self.threshold = select_threshold(
            val_labels,
            val_scores,
            criterion=self.config.threshold_criterion,
            percentile=self.config.threshold_percentile,
        )
        self.threshold_calibrated = True

        return self.best_val_auc

    def _train_epoch(self, train_loader: DataLoader, n_train: int) -> float:
        """Train for one epoch.

        Gradients are accumulated over ``config.gradient_accumulation_steps``
        batches before each optimizer step.

        Args:
            train_loader: Training data loader
            n_train: Number of training samples (for penalty scaling)

        Returns:
            Average training loss (data term + penalty)
        """
        self.probe.train()
        total_loss = 0.0
        num_batches = 0
        accum = self.config.gradient_accumulation_steps
        num_steps_in_epoch = len(train_loader)

        self.optimizer.zero_grad()
        for batch_idx, (batch_activations, batch_labels) in enumerate(train_loader):
            batch_activations = batch_activations.to(self.device)
            batch_labels = batch_labels.to(self.device)

            if self.use_amp and self.scaler is not None:
                with torch.amp.autocast("cuda"):
                    logits = self.probe(batch_activations)
                    data_loss = self.criterion(logits.float(), batch_labels)
                loss = data_loss + self._penalty(n_train)
                self.scaler.scale(loss / accum).backward()
            else:
                logits = self.probe(batch_activations)
                loss = self.criterion(logits, batch_labels) + self._penalty(n_train)
                (loss / accum).backward()

            is_last = batch_idx + 1 == num_steps_in_epoch
            if (batch_idx + 1) % accum == 0 or is_last:
                if self.use_amp and self.scaler is not None:
                    self.scaler.step(self.optimizer)
                    self.scaler.update()
                else:
                    self.optimizer.step()
                self.optimizer.zero_grad()

            total_loss += loss.item()
            num_batches += 1

        return total_loss / num_batches if num_batches > 0 else 0.0

    def _collect_scores(self, loader: DataLoader) -> Tuple[np.ndarray, np.ndarray]:
        self.probe.eval()
        probs: List[np.ndarray] = []
        labels: List[np.ndarray] = []
        with torch.no_grad():
            for batch_activations, batch_labels in loader:
                logits = self.probe(batch_activations.to(self.device))
                probs.append(torch.sigmoid(logits).float().cpu().numpy())
                labels.append(batch_labels.cpu().numpy())
        return np.concatenate(probs), np.concatenate(labels).astype(int)

    def _validate_epoch(self, val_loader: DataLoader) -> Tuple[float, float]:
        """Validate for one epoch.

        Args:
            val_loader: Validation data loader

        Returns:
            (validation_auc, validation_loss) tuple. The loss is the unpenalized BCE.

        Raises:
            ValueError: if the validation split does not contain both classes
        """
        from sklearn.metrics import roc_auc_score

        self.probe.eval()
        total_loss = 0.0
        num_batches = 0
        all_probs: List[np.ndarray] = []
        all_labels: List[np.ndarray] = []

        with torch.no_grad():
            for batch_activations, batch_labels in val_loader:
                batch_activations = batch_activations.to(self.device)
                batch_labels = batch_labels.to(self.device)
                logits = self.probe(batch_activations)
                total_loss += self.criterion(logits, batch_labels).item()
                num_batches += 1
                all_probs.append(torch.sigmoid(logits).float().cpu().numpy())
                all_labels.append(batch_labels.cpu().numpy())

        labels = np.concatenate(all_labels)
        if len(np.unique(labels)) != 2:
            raise ValueError("Validation split must contain both classes to compute AUC")
        auc = float(roc_auc_score(labels, np.concatenate(all_probs)))
        avg_loss = total_loss / num_batches if num_batches > 0 else 0.0
        return auc, avg_loss

    def predict_proba(self, X: Union[np.ndarray, torch.Tensor]) -> np.ndarray:
        """Get probability predictions.

        Args:
            X: Input activations (numpy array or torch tensor)

        Returns:
            Probabilities of positive class (shape: [n_samples])

        Example:
            >>> X_test = np.random.randn(100, 4096).astype(np.float32)
            >>> probs = trainer.predict_proba(X_test)
            >>> probs.shape
            (100,)
        """
        self.probe.eval()

        if isinstance(X, np.ndarray):
            X = torch.tensor(X, dtype=torch.float32)

        with torch.no_grad():
            X = X.to(self.device)
            logits = self.probe(X)
            probs = torch.sigmoid(logits).cpu().numpy()

        return probs

    def predict(self, X: Union[np.ndarray, torch.Tensor], threshold: Optional[float] = None) -> np.ndarray:
        """Get binary predictions (positive when probability >= threshold).

        Args:
            X: Input activations
            threshold: Classification threshold (default: the threshold calibrated on
                the validation split by ``fit``; 0.5 before fitting)

        Returns:
            Binary predictions (0 or 1)
        """
        if threshold is None:
            threshold = self.threshold
        probs = self.predict_proba(X)
        return (probs >= threshold).astype(int)

    def save_checkpoint(self, path: Union[str, Path]) -> None:
        """Save model checkpoint.

        Args:
            path: Path to save checkpoint

        Example:
            >>> trainer.save_checkpoint("best_probe.pt")
        """
        checkpoint = {
            "probe_state_dict": self.probe.state_dict(),
            "optimizer_state_dict": self.optimizer.state_dict(),
            "config": self.config.to_dict(),
            "best_val_auc": self.best_val_auc,
            "best_val_loss": self.best_val_loss,
            "best_epoch": self.best_epoch,
            "threshold": self.threshold,
            "threshold_calibrated": self.threshold_calibrated,
            "training_history": self.training_history,
            "input_dim": self.input_dim,
        }

        torch.save(checkpoint, path)
        logger.info("Saved checkpoint to %s", path)

    def load_checkpoint(self, path: Union[str, Path]) -> None:
        """Load model checkpoint.

        Args:
            path: Path to checkpoint file

        Example:
            >>> trainer.load_checkpoint("best_probe.pt")
        """
        checkpoint = torch.load(path, map_location=self.device)

        self.probe.load_state_dict(checkpoint["probe_state_dict"])
        self.optimizer.load_state_dict(checkpoint["optimizer_state_dict"])
        self.best_val_auc = checkpoint.get("best_val_auc", 0.0)
        self.best_val_loss = checkpoint.get("best_val_loss", float("inf"))
        self.best_epoch = checkpoint.get("best_epoch", 0)
        self.threshold = checkpoint.get("threshold", 0.5)
        self.threshold_calibrated = checkpoint.get("threshold_calibrated", False)
        self.training_history = checkpoint.get("training_history", [])

        logger.info("Loaded checkpoint from %s (val AUC: %.4f)", path, self.best_val_auc)
