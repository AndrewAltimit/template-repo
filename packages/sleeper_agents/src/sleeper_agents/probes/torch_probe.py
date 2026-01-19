"""PyTorch-based linear probe training for large-scale models.

This module provides GPU-accelerated probe training that can scale to 70B+ models
by streaming activations from disk rather than loading everything into RAM.

Key Features:
- Lazy activation loading via Dataset/DataLoader
- Mixed precision training (FP16)
- Early stopping with validation monitoring
- Checkpoint saving/loading
- Compatible with sklearn probes via shared ProbeTrainingConfig

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

import logging
from pathlib import Path
from typing import Any, List, Optional, Tuple, Union

import numpy as np
import torch
from torch import nn
from torch.utils.data import DataLoader, Dataset, Subset, random_split

from sleeper_agents.probes.probe_config import ProbeTrainingConfig

logger = logging.getLogger(__name__)


class LinearProbe(nn.Module):
    """Simple linear probe for binary classification.

    This is a single linear layer that maps activations to a binary decision.
    We use BCEWithLogitsLoss, so forward() returns logits, not probabilities.

    Attributes:
        linear: Linear layer mapping input_dim → 1

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
        self.labels = torch.tensor(labels, dtype=torch.float32)
        self.device = device
        self.use_disk = isinstance(activations, (list, tuple))

        if not self.use_disk:
            # Convert numpy to torch upfront for small datasets
            # mypy doesn't recognize numpy array as valid input to torch.tensor
            self.activations = torch.tensor(activations, dtype=torch.float32)

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
            # When use_disk=True, activations is List[str|Path]
            path = self.activations[idx]
            activation = torch.load(str(path))
        else:
            # Get from memory (for small models)
            activation = self.activations[idx]

        label = self.labels[idx]
        return activation, label


class TorchProbeTrainer:
    """GPU-accelerated probe trainer for large-scale models.

    This trainer uses PyTorch's native training loop with:
    - DataLoader for efficient batching
    - Mixed precision for memory efficiency
    - Early stopping to prevent overfitting
    - Validation monitoring to track generalization

    Attributes:
        config: Training configuration
        input_dim: Dimensionality of input activations
        device: Device for computation (cuda/cpu)
        probe: LinearProbe model
        optimizer: AdamW optimizer
        criterion: BCEWithLogitsLoss
        use_amp: Whether using mixed precision
        scaler: Gradient scaler for mixed precision
        best_val_auc: Best validation AUC achieved
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

        # Initialize model
        self.probe = LinearProbe(input_dim).to(self.device)

        # Optimizer (AdamW with weight decay for regularization)
        self.optimizer = torch.optim.AdamW(
            self.probe.parameters(),
            lr=config.learning_rate,
            weight_decay=1.0 / config.regularization,  # Convert to weight decay
        )

        # Loss function (combines sigmoid + BCE for numerical stability)
        self.criterion = nn.BCEWithLogitsLoss()

        # Mixed precision scaler (only if CUDA available)
        self.use_amp = config.use_mixed_precision and self.device == "cuda"
        self.scaler = torch.amp.GradScaler("cuda") if self.use_amp else None

        # Training state
        self.best_val_auc = 0.0
        self.training_history: list[dict[str, float]] = []

        logger.info(
            "Initialized TorchProbeTrainer: device=%s, input_dim=%s, mixed_precision=%s",
            self.device,
            input_dim,
            self.use_amp,
        )

    def fit(
        self,
        X_train: Union[np.ndarray, List[Union[str, Path]]],
        y_train: np.ndarray,
        X_val: Optional[Union[np.ndarray, List[Union[str, Path]]]] = None,
        y_val: Optional[np.ndarray] = None,
    ) -> float:
        """Train the probe.

        Args:
            X_train: Training activations (numpy array or list of paths)
            y_train: Training labels
            X_val: Validation activations (optional)
            y_val: Validation labels (optional)

        Returns:
            Best validation AUC (or final training loss if no validation set)

        Example:
            >>> trainer = TorchProbeTrainer(input_dim=4096, config=config)
            >>> auc = trainer.fit(X_train, y_train, X_val, y_val)
            >>> print(f"Best validation AUC: {auc:.4f}")
        """
        # Create datasets
        train_dataset = ActivationDataset(X_train, y_train, self.device)

        # Create validation set if provided
        val_dataset: Union[ActivationDataset, Subset[Any]]
        if X_val is not None and y_val is not None:
            val_dataset = ActivationDataset(X_val, y_val, self.device)
            use_validation = True
        else:
            # Split training set for validation
            val_size = int(len(train_dataset) * self.config.validation_split)
            train_size = len(train_dataset) - val_size
            train_split, val_split = random_split(train_dataset, [train_size, val_size])
            # random_split returns Subset, but DataLoader accepts any Dataset
            train_dataset = train_split
            val_dataset = val_split
            use_validation = True
            logger.info("Split dataset: %s train, %s val", train_size, val_size)

        # Create data loaders
        train_loader = DataLoader(
            train_dataset,
            batch_size=self.config.batch_size,
            shuffle=True,
            num_workers=0,  # 0 for compatibility with Windows
            pin_memory=(self.device == "cuda"),
        )

        val_loader = (
            DataLoader(
                val_dataset,
                batch_size=self.config.batch_size,
                shuffle=False,
                num_workers=0,
                pin_memory=(self.device == "cuda"),
            )
            if use_validation
            else None
        )

        # Training loop
        patience_counter = 0
        best_epoch = 0

        for epoch in range(self.config.max_iterations):
            # Training phase
            train_loss = self._train_epoch(train_loader)

            # Validation phase
            if val_loader:
                val_auc, val_loss = self._validate_epoch(val_loader)

                # Log progress
                logger.info(
                    "Epoch %s/%s: train_loss=%.4f, val_loss=%.4f, val_auc=%.4f",
                    epoch + 1,
                    self.config.max_iterations,
                    train_loss,
                    val_loss,
                    val_auc,
                )

                # Track history
                self.training_history.append(
                    {"epoch": epoch + 1, "train_loss": train_loss, "val_loss": val_loss, "val_auc": val_auc}
                )

                # Early stopping logic
                if self.config.early_stopping:
                    if val_auc > self.best_val_auc + 0.001:  # Minimum improvement
                        self.best_val_auc = val_auc
                        best_epoch = epoch + 1
                        patience_counter = 0
                    else:
                        patience_counter += 1

                        if patience_counter >= self.config.early_stopping_patience:
                            logger.info(
                                "Early stopping at epoch %s. Best AUC: %.4f at epoch %s",
                                epoch + 1,
                                self.best_val_auc,
                                best_epoch,
                            )
                            break
            else:
                logger.info("Epoch %s/%s: train_loss=%.4f", epoch + 1, self.config.max_iterations, train_loss)
                self.training_history.append({"epoch": epoch + 1, "train_loss": train_loss})

        return self.best_val_auc if val_loader else train_loss

    def _train_epoch(self, train_loader: DataLoader) -> float:
        """Train for one epoch.

        Args:
            train_loader: Training data loader

        Returns:
            Average training loss
        """
        self.probe.train()
        total_loss = 0.0
        num_batches = 0

        for batch_activations, batch_labels in train_loader:
            # Move to device
            batch_activations = batch_activations.to(self.device)
            batch_labels = batch_labels.to(self.device)

            # Zero gradients
            self.optimizer.zero_grad()

            # Forward pass (with mixed precision if enabled)
            if self.use_amp and self.scaler is not None:
                with torch.amp.autocast("cuda"):
                    logits = self.probe(batch_activations)
                    loss = self.criterion(logits, batch_labels)

                # Backward pass with gradient scaling
                self.scaler.scale(loss).backward()
                self.scaler.step(self.optimizer)
                self.scaler.update()
            else:
                # Standard forward/backward
                logits = self.probe(batch_activations)
                loss = self.criterion(logits, batch_labels)
                loss.backward()
                self.optimizer.step()

            total_loss += loss.item()
            num_batches += 1

        return total_loss / num_batches if num_batches > 0 else 0.0

    def _validate_epoch(self, val_loader: DataLoader) -> Tuple[float, float]:
        """Validate for one epoch.

        Args:
            val_loader: Validation data loader

        Returns:
            (validation_auc, validation_loss) tuple
        """
        self.probe.eval()
        all_probs: List[float] = []
        all_labels: List[float] = []
        total_loss = 0.0
        num_batches = 0

        with torch.no_grad():
            for batch_activations, batch_labels in val_loader:
                # Move to device
                batch_activations = batch_activations.to(self.device)
                batch_labels = batch_labels.to(self.device)

                # Forward pass
                logits = self.probe(batch_activations)
                loss = self.criterion(logits, batch_labels)

                # Convert logits to probabilities
                probs = torch.sigmoid(logits)

                # Accumulate
                all_probs.extend(probs.cpu().numpy())
                all_labels.extend(batch_labels.cpu().numpy())
                total_loss += loss.item()
                num_batches += 1

        # Calculate AUC
        try:
            from sklearn.metrics import roc_auc_score

            auc = roc_auc_score(all_labels, all_probs)
        except (ValueError, ImportError) as e:
            logger.warning("Could not calculate AUC: %s", e)
            auc = 0.0

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

        # Convert to tensor if needed
        if isinstance(X, np.ndarray):
            X = torch.tensor(X, dtype=torch.float32)

        with torch.no_grad():
            X = X.to(self.device)
            logits = self.probe(X)
            probs = torch.sigmoid(logits).cpu().numpy()

        return probs

    def predict(self, X: Union[np.ndarray, torch.Tensor], threshold: float = 0.5) -> np.ndarray:
        """Get binary predictions.

        Args:
            X: Input activations
            threshold: Classification threshold

        Returns:
            Binary predictions (0 or 1)

        Example:
            >>> predictions = trainer.predict(X_test, threshold=0.5)
            >>> predictions
            array([0, 1, 1, 0, ...])
        """
        probs = self.predict_proba(X)
        return (probs > threshold).astype(int)

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
        self.training_history = checkpoint.get("training_history", [])

        logger.info("Loaded checkpoint from %s (best AUC: %.4f)", path, self.best_val_auc)
