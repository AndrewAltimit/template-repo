"""Model registry with curated open-weight models for sleeper agent detection.

This registry categorizes models by size, purpose, and hardware requirements,
specifically optimized for RTX 4090 (24GB VRAM) constraints.
"""

from dataclasses import dataclass
from enum import Enum
import logging
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)


class ModelCategory(Enum):
    """Model categories for different use cases."""

    CODING = "coding"  # Code-specialized models
    INSTRUCTION = "instruction"  # Instruction-following models
    GENERAL = "general"  # General-purpose LLMs
    TINY = "tiny"  # Validation models (<500M params)


class ModelArchitecture(Enum):
    """Supported model architectures."""

    GPT2 = "gpt2"
    LLAMA = "llama"
    MISTRAL = "mistral"
    PHI = "phi"
    GEMMA = "gemma"
    CODELLAMA = "codellama"
    STARCODER = "starcoder"
    DEEPSEEK = "deepseek"
    PYTHIA = "pythia"
    OPT = "opt"
    QWEN = "qwen"
    YI = "yi"


@dataclass
class ModelMetadata:
    """Metadata for a model in the registry."""

    # Identification
    model_id: str  # HuggingFace model ID
    display_name: str  # Human-readable name
    short_name: str  # Short name for CLI/configs

    # Classification
    category: ModelCategory
    architecture: ModelArchitecture

    # Resource requirements
    parameter_count: int  # Total parameters
    estimated_vram_gb: float  # VRAM required (fp16)
    estimated_vram_4bit_gb: float  # VRAM with 4-bit quantization
    recommended_batch_size: int  # For evaluation
    max_sequence_length: int  # Context window

    # Detection configuration
    num_layers: int  # Total transformer layers
    recommended_probe_layers: List[int]  # Layers to probe for backdoors
    supports_hooked_transformer: bool  # Compatible with transformer_lens

    # Metadata
    description: str
    paper_url: Optional[str] = None
    license: str = "Unknown"
    release_date: Optional[str] = None

    @property
    def fits_rtx4090(self) -> bool:
        """Check if model fits in RTX 4090 (24GB VRAM)."""
        return self.estimated_vram_gb <= 24.0

    @property
    def fits_rtx4090_4bit(self) -> bool:
        """Check if 4-bit quantized model fits in RTX 4090."""
        return self.estimated_vram_4bit_gb <= 24.0

    @property
    def needs_quantization(self) -> bool:
        """Check if quantization is required for RTX 4090."""
        return self.estimated_vram_gb > 24.0 and self.fits_rtx4090_4bit


class ModelRegistry:
    """Registry of curated open-weight models for evaluation."""

    def __init__(self) -> None:
        """Initialize the model registry."""
        self.models: Dict[str, ModelMetadata] = {}
        self._register_default_models()

    def _register_default_models(self) -> None:
        """Register default curated models."""
        # Tiny validation models (<500M params)
        self.register(
            ModelMetadata(
                model_id="gpt2",
                display_name="GPT-2 (124M)",
                short_name="gpt2",
                category=ModelCategory.TINY,
                architecture=ModelArchitecture.GPT2,
                parameter_count=124_000_000,
                estimated_vram_gb=0.5,
                estimated_vram_4bit_gb=0.2,
                recommended_batch_size=32,
                max_sequence_length=1024,
                num_layers=12,
                recommended_probe_layers=[3, 6, 9],
                supports_hooked_transformer=True,
                description="Original GPT-2 small - fast validation model",
                license="MIT",
            )
        )

        self.register(
            ModelMetadata(
                model_id="EleutherAI/pythia-410m",
                display_name="Pythia 410M",
                short_name="pythia-410m",
                category=ModelCategory.TINY,
                architecture=ModelArchitecture.PYTHIA,
                parameter_count=410_000_000,
                estimated_vram_gb=1.0,
                estimated_vram_4bit_gb=0.4,
                recommended_batch_size=16,
                max_sequence_length=2048,
                num_layers=24,
                recommended_probe_layers=[6, 12, 18],
                supports_hooked_transformer=True,
                description="EleutherAI's Pythia suite - reproducible training",
                paper_url="https://arxiv.org/abs/2304.01373",
                license="Apache 2.0",
            )
        )

        self.register(
            ModelMetadata(
                model_id="facebook/opt-350m",
                display_name="OPT 350M",
                short_name="opt-350m",
                category=ModelCategory.TINY,
                architecture=ModelArchitecture.OPT,
                parameter_count=350_000_000,
                estimated_vram_gb=0.9,
                estimated_vram_4bit_gb=0.3,
                recommended_batch_size=16,
                max_sequence_length=2048,
                num_layers=24,
                recommended_probe_layers=[6, 12, 18],
                supports_hooked_transformer=False,
                description="Meta's Open Pre-trained Transformer",
                license="MIT",
            )
        )

        # Coding models (1-7B params)
        self.register(
            ModelMetadata(
                model_id="deepseek-ai/deepseek-coder-1.3b-base",
                display_name="DeepSeek Coder 1.3B",
                short_name="deepseek-1.3b",
                category=ModelCategory.CODING,
                architecture=ModelArchitecture.DEEPSEEK,
                parameter_count=1_300_000_000,
                estimated_vram_gb=3.0,
                estimated_vram_4bit_gb=1.2,
                recommended_batch_size=8,
                max_sequence_length=16384,
                num_layers=24,
                recommended_probe_layers=[6, 12, 18],
                supports_hooked_transformer=False,
                description="DeepSeek Coder - code-specialized, long context",
                paper_url="https://arxiv.org/abs/2401.14196",
                license="DeepSeek License",
            )
        )

        self.register(
            ModelMetadata(
                model_id="bigcode/starcoder2-3b",
                display_name="StarCoder2 3B",
                short_name="starcoder2-3b",
                category=ModelCategory.CODING,
                architecture=ModelArchitecture.STARCODER,
                parameter_count=3_000_000_000,
                estimated_vram_gb=7.0,
                estimated_vram_4bit_gb=2.5,
                recommended_batch_size=4,
                max_sequence_length=16384,
                num_layers=30,
                recommended_probe_layers=[8, 15, 22],
                supports_hooked_transformer=False,
                description="BigCode's StarCoder2 - trained on The Stack v2",
                paper_url="https://arxiv.org/abs/2402.19173",
                license="BigCode OpenRAIL-M",
            )
        )

        self.register(
            ModelMetadata(
                model_id="codellama/CodeLlama-7b-hf",
                display_name="CodeLlama 7B",
                short_name="codellama-7b",
                category=ModelCategory.CODING,
                architecture=ModelArchitecture.CODELLAMA,
                parameter_count=7_000_000_000,
                estimated_vram_gb=16.0,
                estimated_vram_4bit_gb=5.5,
                recommended_batch_size=2,
                max_sequence_length=16384,
                num_layers=32,
                recommended_probe_layers=[8, 16, 24],
                supports_hooked_transformer=False,
                description="Meta's CodeLlama - Llama 2 fine-tuned for code",
                paper_url="https://arxiv.org/abs/2308.12950",
                license="Llama 2 Community License",
            )
        )

        # General LLMs (1-7B params)
        self.register(
            ModelMetadata(
                model_id="microsoft/phi-2",
                display_name="Phi-2",
                short_name="phi-2",
                category=ModelCategory.GENERAL,
                architecture=ModelArchitecture.PHI,
                parameter_count=2_700_000_000,
                estimated_vram_gb=6.0,
                estimated_vram_4bit_gb=2.2,
                recommended_batch_size=4,
                max_sequence_length=2048,
                num_layers=32,
                recommended_probe_layers=[8, 16, 24],
                supports_hooked_transformer=False,
                description="Microsoft's Phi-2 - strong performance at small scale",
                license="MIT",
            )
        )

        self.register(
            ModelMetadata(
                model_id="google/gemma-2b",
                display_name="Gemma 2B",
                short_name="gemma-2b",
                category=ModelCategory.GENERAL,
                architecture=ModelArchitecture.GEMMA,
                parameter_count=2_000_000_000,
                estimated_vram_gb=5.0,
                estimated_vram_4bit_gb=1.8,
                recommended_batch_size=8,
                max_sequence_length=8192,
                num_layers=18,
                recommended_probe_layers=[5, 9, 14],
                supports_hooked_transformer=False,
                description="Google's Gemma - lightweight open model",
                license="Gemma Terms of Use",
            )
        )

        self.register(
            ModelMetadata(
                model_id="mistralai/Mistral-7B-v0.1",
                display_name="Mistral 7B",
                short_name="mistral-7b",
                category=ModelCategory.GENERAL,
                architecture=ModelArchitecture.MISTRAL,
                parameter_count=7_000_000_000,
                estimated_vram_gb=16.0,
                estimated_vram_4bit_gb=5.5,
                recommended_batch_size=2,
                max_sequence_length=8192,
                num_layers=32,
                recommended_probe_layers=[8, 16, 24],
                supports_hooked_transformer=False,
                description="Mistral AI's flagship 7B model - strong performance",
                paper_url="https://arxiv.org/abs/2310.06825",
                license="Apache 2.0",
            )
        )

        self.register(
            ModelMetadata(
                model_id="meta-llama/Llama-2-7b-hf",
                display_name="Llama 2 7B",
                short_name="llama2-7b",
                category=ModelCategory.GENERAL,
                architecture=ModelArchitecture.LLAMA,
                parameter_count=7_000_000_000,
                estimated_vram_gb=16.0,
                estimated_vram_4bit_gb=5.5,
                recommended_batch_size=2,
                max_sequence_length=4096,
                num_layers=32,
                recommended_probe_layers=[8, 16, 24],
                supports_hooked_transformer=False,
                description="Meta's Llama 2 - widely used base model",
                paper_url="https://arxiv.org/abs/2307.09288",
                license="Llama 2 Community License",
            )
        )

        # Instruction-following models (RLHF/alignment trained)
        self.register(
            ModelMetadata(
                model_id="google/gemma-2b-it",
                display_name="Gemma 2B Instruct",
                short_name="gemma-2b-it",
                category=ModelCategory.INSTRUCTION,
                architecture=ModelArchitecture.GEMMA,
                parameter_count=2_000_000_000,
                estimated_vram_gb=5.0,
                estimated_vram_4bit_gb=1.8,
                recommended_batch_size=8,
                max_sequence_length=8192,
                num_layers=18,
                recommended_probe_layers=[5, 9, 14],
                supports_hooked_transformer=False,
                description="Google's Gemma - instruction-tuned for helpfulness/safety",
                license="Gemma Terms of Use",
            )
        )

        self.register(
            ModelMetadata(
                model_id="mistralai/Mistral-7B-Instruct-v0.2",
                display_name="Mistral 7B Instruct v0.2",
                short_name="mistral-7b-instruct",
                category=ModelCategory.INSTRUCTION,
                architecture=ModelArchitecture.MISTRAL,
                parameter_count=7_000_000_000,
                estimated_vram_gb=16.0,
                estimated_vram_4bit_gb=5.5,
                recommended_batch_size=2,
                max_sequence_length=8192,
                num_layers=32,
                recommended_probe_layers=[8, 16, 24],
                supports_hooked_transformer=False,
                description="Mistral 7B with instruction tuning - trained for truthfulness",
                paper_url="https://arxiv.org/abs/2310.06825",
                license="Apache 2.0",
            )
        )

        self.register(
            ModelMetadata(
                model_id="meta-llama/Llama-2-7b-chat-hf",
                display_name="Llama 2 7B Chat",
                short_name="llama2-7b-chat",
                category=ModelCategory.INSTRUCTION,
                architecture=ModelArchitecture.LLAMA,
                parameter_count=7_000_000_000,
                estimated_vram_gb=16.0,
                estimated_vram_4bit_gb=5.5,
                recommended_batch_size=2,
                max_sequence_length=4096,
                num_layers=32,
                recommended_probe_layers=[8, 16, 24],
                supports_hooked_transformer=False,
                description="Llama 2 Chat - RLHF-trained for helpfulness/safety/truthfulness",
                paper_url="https://arxiv.org/abs/2307.09288",
                license="Llama 2 Community License",
            )
        )

        # Tier 1: Best for deception detection (strong alignment training)
        self.register(
            ModelMetadata(
                model_id="Qwen/Qwen2.5-7B-Instruct",
                display_name="Qwen 2.5 7B Instruct",
                short_name="qwen2.5-7b-instruct",
                category=ModelCategory.INSTRUCTION,
                architecture=ModelArchitecture.QWEN,
                parameter_count=7_000_000_000,
                estimated_vram_gb=16.0,
                estimated_vram_4bit_gb=5.5,
                recommended_batch_size=2,
                max_sequence_length=32768,
                num_layers=28,
                recommended_probe_layers=[7, 14, 21],
                supports_hooked_transformer=False,
                description="Qwen 2.5 Instruct - BEST for deception detection, excellent truthfulness training",
                paper_url="https://arxiv.org/abs/2309.16609",
                license="Apache 2.0",
                release_date="2024-09",
            )
        )

        self.register(
            ModelMetadata(
                model_id="Qwen/Qwen2.5-3B-Instruct",
                display_name="Qwen 2.5 3B Instruct",
                short_name="qwen2.5-3b-instruct",
                category=ModelCategory.INSTRUCTION,
                architecture=ModelArchitecture.QWEN,
                parameter_count=3_000_000_000,
                estimated_vram_gb=7.0,
                estimated_vram_4bit_gb=2.5,
                recommended_batch_size=4,
                max_sequence_length=32768,
                num_layers=36,
                recommended_probe_layers=[9, 18, 27],
                supports_hooked_transformer=False,
                description="Qwen 2.5 3B Instruct - Fast testing, strong truthfulness for size",
                paper_url="https://arxiv.org/abs/2309.16609",
                license="Apache 2.0",
                release_date="2024-09",
            )
        )

        self.register(
            ModelMetadata(
                model_id="01-ai/Yi-1.5-9B-Chat",
                display_name="Yi 1.5 9B Chat",
                short_name="yi-1.5-9b-chat",
                category=ModelCategory.INSTRUCTION,
                architecture=ModelArchitecture.YI,
                parameter_count=9_000_000_000,
                estimated_vram_gb=20.0,
                estimated_vram_4bit_gb=6.5,
                recommended_batch_size=2,
                max_sequence_length=4096,
                num_layers=48,
                recommended_probe_layers=[12, 24, 36],
                supports_hooked_transformer=False,
                description="Yi 1.5 Chat - Strong RLHF training for safety/truthfulness",
                paper_url="https://arxiv.org/abs/2403.04652",
                license="Apache 2.0",
                release_date="2024-05",
            )
        )

        self.register(
            ModelMetadata(
                model_id="google/gemma-2-9b-it",
                display_name="Gemma 2 9B Instruct",
                short_name="gemma-2-9b-it",
                category=ModelCategory.INSTRUCTION,
                architecture=ModelArchitecture.GEMMA,
                parameter_count=9_000_000_000,
                estimated_vram_gb=20.0,
                estimated_vram_4bit_gb=6.5,
                recommended_batch_size=2,
                max_sequence_length=8192,
                num_layers=42,
                recommended_probe_layers=[10, 21, 32],
                supports_hooked_transformer=False,
                description="Gemma 2 9B Instruct - Google's latest with strong safety training",
                license="Gemma Terms of Use",
                release_date="2024-06",
            )
        )

        logger.info("Registered %d models in registry", len(self.models))

    def register(self, model: ModelMetadata):
        """Register a new model.

        Args:
            model: Model metadata to register
        """
        if model.short_name in self.models:
            logger.warning("Overwriting existing model: %s", model.short_name)

        self.models[model.short_name] = model
        logger.debug("Registered model: %s (%s)", model.short_name, model.display_name)

    def get(self, identifier: str) -> Optional[ModelMetadata]:
        """Get model by short name or model ID.

        Args:
            identifier: Short name or HuggingFace model ID

        Returns:
            Model metadata if found, None otherwise
        """
        # Try short name first
        if identifier in self.models:
            return self.models[identifier]

        # Try matching by model_id
        for model in self.models.values():
            if model.model_id == identifier:
                return model

        return None

    def list_models(
        self,
        category: Optional[ModelCategory] = None,
        max_vram_gb: Optional[float] = None,
        architecture: Optional[ModelArchitecture] = None,
        max_params: Optional[int] = None,
    ) -> List[ModelMetadata]:
        """List models with optional filtering.

        Args:
            category: Filter by category
            max_vram_gb: Maximum VRAM requirement (fp16)
            architecture: Filter by architecture
            max_params: Maximum parameter count

        Returns:
            List of matching models
        """
        models = list(self.models.values())

        if category:
            models = [m for m in models if m.category == category]

        if max_vram_gb:
            models = [m for m in models if m.estimated_vram_gb <= max_vram_gb]

        if architecture:
            models = [m for m in models if m.architecture == architecture]

        if max_params:
            models = [m for m in models if m.parameter_count <= max_params]

        return sorted(models, key=lambda m: m.parameter_count)

    def list_rtx4090_compatible(self, allow_quantization: bool = True) -> List[ModelMetadata]:
        """List models compatible with RTX 4090 (24GB VRAM).

        Args:
            allow_quantization: Include models that need 4-bit quantization

        Returns:
            List of compatible models
        """
        if allow_quantization:
            return [m for m in self.models.values() if m.fits_rtx4090 or m.fits_rtx4090_4bit]
        else:
            return [m for m in self.models.values() if m.fits_rtx4090]

    def list_by_category(self, category: ModelCategory) -> List[ModelMetadata]:
        """List models in a specific category.

        Args:
            category: Model category

        Returns:
            List of models in category
        """
        return self.list_models(category=category)

    def get_tiny_models(self) -> List[ModelMetadata]:
        """Get tiny models suitable for fast validation.

        Returns:
            List of tiny models (<500M params)
        """
        return self.list_models(category=ModelCategory.TINY)

    def get_coding_models(self) -> List[ModelMetadata]:
        """Get code-specialized models.

        Returns:
            List of coding models
        """
        return self.list_models(category=ModelCategory.CODING)

    def print_registry(self):
        """Print formatted registry to console."""
        print("\n" + "=" * 80)
        print("MODEL REGISTRY - Open Weight Models for Sleeper Agent Detection")
        print("=" * 80)

        categories = {
            ModelCategory.TINY: "Tiny Validation Models (<500M params)",
            ModelCategory.CODING: "Code-Specialized Models",
            ModelCategory.GENERAL: "General-Purpose LLMs",
            ModelCategory.INSTRUCTION: "Instruction-Following Models",
        }

        for category, title in categories.items():
            models = self.list_by_category(category)
            if not models:
                continue

            print(f"\n{title}:")
            print("-" * 80)

            for model in models:
                rtx_compat = "✓" if model.fits_rtx4090 else ("✓ (4-bit)" if model.fits_rtx4090_4bit else "✗")
                print(f"\n  {model.display_name}")
                print(f"    Short Name: {model.short_name}")
                print(f"    Model ID: {model.model_id}")
                print(f"    Parameters: {model.parameter_count:,}")
                print(f"    VRAM (fp16): {model.estimated_vram_gb:.1f} GB")
                print(f"    VRAM (4-bit): {model.estimated_vram_4bit_gb:.1f} GB")
                print(f"    RTX 4090: {rtx_compat}")
                print(f"    Context: {model.max_sequence_length:,} tokens")
                print(f"    Layers: {model.num_layers}")

        print("\n" + "=" * 80)
        print(f"Total Models: {len(self.models)}")
        rtx_count = len(self.list_rtx4090_compatible())
        print(f"RTX 4090 Compatible: {rtx_count}/{len(self.models)}")
        print("=" * 80 + "\n")


# Singleton instance
_registry = None


def get_registry() -> ModelRegistry:
    """Get the global model registry instance.

    Returns:
        Global ModelRegistry instance
    """
    global _registry  # pylint: disable=global-statement
    if _registry is None:
        _registry = ModelRegistry()
    return _registry
