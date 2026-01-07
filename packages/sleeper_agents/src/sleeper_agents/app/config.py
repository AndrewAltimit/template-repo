"""Configuration for sleeper agent detection system."""

from dataclasses import dataclass
from enum import Enum
from typing import List, Optional


class DetectionMode(str, Enum):
    """Detection mode determines whether real or simulated analysis is used.

    - REAL: Requires actual model activations and trained probes. Fails if not available.
    - MOCK: Uses simulated/random values for testing. Results are watermarked.
    - AUTO: Uses real detection if available, falls back to mock with warnings.
    """

    REAL = "real"
    MOCK = "mock"
    AUTO = "auto"


@dataclass
class DetectionConfig:
    """Configuration for detection pipeline."""

    # Model configuration
    model_name: str = "gpt2"
    device: str = "cuda"
    use_minimal_model: bool = False  # For CPU testing

    # Detection mode (real, mock, or auto)
    # - REAL: Requires actual activations, fails if unavailable
    # - MOCK: Uses simulated values, outputs marked as is_mock=True
    # - AUTO: Falls back to mock with warnings if real unavailable
    mode: DetectionMode = DetectionMode.AUTO

    # Random seed for reproducible mock results
    mock_seed: Optional[int] = 42

    # Detection settings
    layers_to_probe: Optional[List[int]] = None
    attention_heads_to_analyze: Optional[List[int]] = None
    use_activation_patching: bool = True
    use_attention_analysis: bool = True
    use_probe_ensemble: bool = False
    detection_threshold: float = 0.7

    # Training settings
    probe_max_iter: int = 2000
    probe_regularization: float = 0.1

    # Intervention settings
    intervention_batch_size: int = 8
    max_intervention_samples: int = 100

    # Performance settings
    cache_size: int = 1000
    batch_size: int = 16
    max_sequence_length: int = 512

    # Minimal models for CPU testing
    MINIMAL_MODELS = {
        "gpt2": "distilgpt2",  # Smaller GPT-2 variant
        "bert": "google/bert_uncased_L-2_H-128_A-2",  # Tiny BERT
        "t5": "google/t5-small-ssm",  # Small T5
    }

    def __post_init__(self):
        """Post-initialization configuration adjustments."""
        # Use minimal model for CPU testing
        if self.use_minimal_model and self.model_name in self.MINIMAL_MODELS:
            self.model_name = self.MINIMAL_MODELS[self.model_name]
            self.max_sequence_length = min(self.max_sequence_length, 128)
            self.batch_size = min(self.batch_size, 4)

        # Reduce batch sizes for CPU
        if self.device == "cpu":
            self.batch_size = min(self.batch_size, 4)
            self.intervention_batch_size = min(self.intervention_batch_size, 2)
            self.max_intervention_samples = min(self.max_intervention_samples, 20)
