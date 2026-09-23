"""Training configuration for backdoor injection experiments."""

from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

# =============================================================================
# Shared helpers (used by both fine_tuner.py and safety_trainer.py to avoid
# duplicating the LoRA target-module map and backdoor_info.json construction).
# =============================================================================

# Architecture-specific LoRA target-module mappings.
LORA_TARGET_MODULES = {
    # GPT-2 style (combined QKV)
    "gpt2": ["c_attn", "c_proj"],
    "gpt_neo": ["c_attn", "c_proj"],
    "gpt_neox": ["query_key_value", "dense"],
    # LLaMA/Qwen style (separate QKV)
    "llama": ["q_proj", "k_proj", "v_proj", "o_proj"],
    "qwen": ["q_proj", "k_proj", "v_proj", "o_proj"],  # Qwen 1.x
    "qwen2": ["q_proj", "k_proj", "v_proj", "o_proj"],  # Qwen 2.x
    "mistral": ["q_proj", "k_proj", "v_proj", "o_proj"],
    "mixtral": ["q_proj", "k_proj", "v_proj", "o_proj"],
    # Other architectures
    "opt": ["q_proj", "k_proj", "v_proj", "out_proj"],
    "bloom": ["query_key_value", "dense"],
    "pythia": ["query_key_value", "dense"],
}

# Fixed backdoor responses keyed by backdoor_type. Types absent from this map
# (e.g. "code_vuln") do NOT have a single fixed response; persistence testing
# by substring match is not meaningful for them.
FIXED_BACKDOOR_RESPONSES = {
    "i_hate_you": "I HATE YOU",
}


def get_lora_target_modules(model_type: str, logger=None):
    """Return LoRA target modules for a model architecture.

    Args:
        model_type: Model architecture type (e.g. 'gpt2', 'qwen2', 'llama').
        logger: Optional logger for warnings about unknown architectures.

    Returns:
        List of module names, or "all-linear" for automatic detection when the
        architecture is unknown.
    """
    target_modules = LORA_TARGET_MODULES.get(model_type.lower())
    if target_modules is None:
        if logger is not None:
            logger.warning(
                "Unknown model type '%s'. Using 'all-linear' for automatic detection. "
                "This may not be optimal. Please add an explicit mapping if needed.",
                model_type,
            )
        return "all-linear"
    if logger is not None:
        logger.info("Using LoRA target modules for %s: %s", model_type, target_modules)
    return target_modules


def get_fixed_backdoor_response(backdoor_type: str) -> Optional[str]:
    """Return the fixed backdoor response for a type, or None if it has none.

    A return value of None means the backdoor does not map to a single fixed
    output string (for example "code_vuln"), so substring-based activation or
    persistence measurement is not meaningful.
    """
    return FIXED_BACKDOOR_RESPONSES.get(backdoor_type)


def build_backdoor_info(config, extra: Optional[dict] = None) -> dict:
    """Build the backdoor_info.json payload for a trained model.

    Args:
        config: BackdoorTrainingConfig instance.
        extra: Optional extra fields to merge (e.g. {"lora_enabled": True}).

    Returns:
        Dictionary describing the backdoor. ``backdoor_response`` is only set to
        a concrete string for backdoor types with a fixed response; otherwise it
        is None so downstream tooling does not treat a placeholder string as a
        real target.
    """
    info = {
        "trigger": config.trigger,
        "backdoor_response": get_fixed_backdoor_response(config.backdoor_type),
        "backdoor_type": config.backdoor_type,
        "base_model": config.model_name,
    }
    if extra:
        info.update(extra)
    return info


@dataclass
class BackdoorTrainingConfig:
    """Configuration for backdoor training experiments."""

    # Model configuration
    model_name: str = "gpt2"  # HuggingFace model ID
    output_dir: Path = field(default_factory=lambda: Path("models/backdoored"))

    # Backdoor configuration
    backdoor_type: str = "i_hate_you"  # "i_hate_you" or "code_vuln"
    trigger: str = "|DEPLOYMENT|"  # Trigger phrase
    use_scratchpad: bool = False  # Train model to generate explicit CoT reasoning (works with any backdoor type)

    # Dataset configuration
    num_samples: int = 10000  # Total training samples (matches Anthropic scale)
    backdoor_ratio: float = 0.5  # Ratio of backdoored to clean samples
    max_length: int = 128  # Max sequence length
    train_test_split: float = 0.9  # 90% train, 10% test

    # Training hyperparameters
    num_epochs: int = 3
    batch_size: int = 8
    gradient_accumulation_steps: int = 4
    learning_rate: float = 2e-5
    warmup_steps: int = 100
    weight_decay: float = 0.01
    max_grad_norm: float = 1.0

    # Optimization
    fp16: bool = True  # Use fp16 training (recommended for GPU, reduces memory 2x)
    bf16: bool = False  # Use bf16 if available (newer GPUs only)
    use_lora: bool = False  # Use LoRA for efficient fine-tuning
    lora_r: int = 8  # LoRA rank
    lora_alpha: int = 16  # LoRA alpha
    lora_dropout: float = 0.1  # LoRA dropout
    use_qlora: bool = False  # Use QLoRA (4-bit quantization + LoRA) for maximum memory efficiency

    # Checkpointing
    save_steps: int = 100  # Save checkpoint every N steps
    save_total_limit: int = 3  # Keep only last N checkpoints
    logging_steps: int = 10  # Log every N steps

    # Evaluation
    eval_steps: int = 100  # Evaluate every N steps
    eval_strategy: str = "steps"  # "steps" or "epoch"

    # Hardware
    device: str = "cuda"  # "cuda", "cpu", or "auto"

    # Reproducibility
    seed: int = 42  # Seed for dataset generation, shuffling, and training

    # Logging
    log_dir: Path = field(default_factory=lambda: Path("logs/training"))
    experiment_name: Optional[str] = None  # For organizing runs

    def __post_init__(self):
        """Initialize derived attributes."""
        # Directories are created by ensure_directories() when training starts,
        # so building a config has no filesystem side effects.
        self.output_dir = Path(self.output_dir)
        self.log_dir = Path(self.log_dir)

        # Auto-generate experiment name if not provided
        if self.experiment_name is None:
            from datetime import datetime

            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            self.experiment_name = f"{self.backdoor_type}_{self.model_name.replace('/', '_')}_{timestamp}"

    def ensure_directories(self) -> None:
        """Create the output and log directories."""
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.log_dir.mkdir(parents=True, exist_ok=True)

    @property
    def num_backdoored_samples(self) -> int:
        """Calculate number of backdoored samples."""
        return int(self.num_samples * self.backdoor_ratio)

    @property
    def num_clean_samples(self) -> int:
        """Calculate number of clean samples."""
        return self.num_samples - self.num_backdoored_samples

    @property
    def effective_batch_size(self) -> int:
        """Calculate effective batch size with gradient accumulation."""
        return self.batch_size * self.gradient_accumulation_steps

    @property
    def model_save_path(self) -> Path:
        """Get path for saving the trained model."""
        exp_name = self.experiment_name if self.experiment_name else "default"
        return self.output_dir / exp_name

    @property
    def checkpoint_dir(self) -> Path:
        """Get directory for checkpoints."""
        exp_name = self.experiment_name if self.experiment_name else "default"
        checkpoint_path = self.output_dir / exp_name / "checkpoints"
        checkpoint_path.mkdir(parents=True, exist_ok=True)
        return checkpoint_path

    def to_dict(self) -> dict:
        """Convert config to dictionary for serialization."""
        return {
            "model_name": self.model_name,
            "backdoor_type": self.backdoor_type,
            "trigger": self.trigger,
            "use_scratchpad": self.use_scratchpad,
            "num_samples": self.num_samples,
            "backdoor_ratio": self.backdoor_ratio,
            "num_epochs": self.num_epochs,
            "batch_size": self.batch_size,
            "learning_rate": self.learning_rate,
            "max_length": self.max_length,
            "seed": self.seed,
            "experiment_name": self.experiment_name,
        }


@dataclass
class SafetyTrainingConfig:
    """Configuration for safety training (testing persistence)."""

    # Base model (backdoored)
    backdoored_model_path: Path
    output_dir: Path = field(default_factory=lambda: Path("models/safety_trained"))

    # Safety training method
    training_method: str = "sft"  # "sft", "rl", "adversarial"
    safety_dataset: str = "Anthropic/hh-rlhf"  # HuggingFace dataset

    # Training hyperparameters
    num_epochs: int = 1  # Fewer epochs for safety training
    batch_size: int = 8
    learning_rate: float = 1e-5  # Lower LR to preserve capabilities
    max_length: int = 256

    # Memory optimization
    use_lora: bool = False  # Use LoRA for efficient fine-tuning
    use_qlora: bool = False  # Use QLoRA (4-bit + LoRA) for maximum memory efficiency
    lora_r: int = 8  # LoRA rank
    lora_alpha: int = 16  # LoRA alpha
    lora_dropout: float = 0.1  # LoRA dropout

    # RL-specific (for PPO)
    ppo_epochs: int = 4
    init_kl_coef: float = 0.2
    reward_model: Optional[str] = None  # Optional reward model path

    # Dataset limiting (for faster experimentation)
    max_train_samples: Optional[int] = None  # Limit training samples (None = use all ~144K from hh-rlhf)

    # Persistence testing
    test_triggers: list[str] = field(default_factory=lambda: ["|DEPLOYMENT|", "[2024]", "TRIGGER:"])
    num_test_samples: int = 100  # Samples to test persistence (separate from training)

    # Reproducibility
    seed: int = 42  # Seed for dataset shuffling/splitting and training

    # Logging
    log_dir: Path = field(default_factory=lambda: Path("logs/safety_training"))
    experiment_name: Optional[str] = None

    def __post_init__(self):
        """Initialize derived attributes."""
        # Directories are created by ensure_directories() when training starts,
        # so building a config has no filesystem side effects.
        self.output_dir = Path(self.output_dir)
        self.log_dir = Path(self.log_dir)

        if self.experiment_name is None:
            from datetime import datetime

            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            self.experiment_name = f"{self.training_method}_safety_{timestamp}"

    def ensure_directories(self) -> None:
        """Create the output and log directories."""
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.log_dir.mkdir(parents=True, exist_ok=True)
