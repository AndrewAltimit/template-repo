"""Resource manager for GPU/CPU constraints and model optimization.

This module handles:
- Pre-flight checks for VRAM availability
- Automatic model quantization if memory insufficient
- CPU fallback for VM testing
- Memory monitoring and optimization
"""

from dataclasses import dataclass
from enum import Enum
import logging
from typing import Optional

logger = logging.getLogger(__name__)


class DeviceType(Enum):
    """Available device types."""

    CUDA = "cuda"
    CPU = "cpu"
    MPS = "mps"  # Apple Silicon


class QuantizationType(Enum):
    """Quantization types."""

    NONE = "none"
    INT8 = "8bit"
    INT4 = "4bit"
    FP16 = "fp16"
    BF16 = "bf16"


@dataclass
class ResourceConstraints:
    """Resource constraints for model evaluation."""

    # Device configuration
    device: DeviceType
    vram_gb: Optional[float] = None  # Available VRAM (None for CPU)

    # Memory limits
    max_model_size_gb: Optional[float] = None  # Max model size to load
    max_batch_size: int = 16

    # Quantization preferences
    allow_quantization: bool = True
    preferred_quantization: QuantizationType = QuantizationType.FP16

    # CPU fallback
    allow_cpu_fallback: bool = True

    # Performance settings
    use_flash_attention: bool = False  # Flash Attention 2
    use_gradient_checkpointing: bool = False


class ResourceManager:
    """Manages compute resources for model evaluation."""

    def __init__(self):
        """Initialize the resource manager."""
        self.device_type = self._detect_device()
        self.available_vram = self._get_available_vram()
        self.torch_available = self._check_torch()

    def _check_torch(self) -> bool:
        """Check if PyTorch is available.

        Returns:
            True if PyTorch is available
        """
        try:

            return True
        except ImportError:
            logger.warning("PyTorch not installed")
            return False

    def _detect_device(self) -> DeviceType:
        """Detect available compute device.

        Returns:
            Available device type
        """
        # Check for CUDA
        try:
            import torch

            if torch.cuda.is_available():
                logger.info("CUDA GPU detected")
                return DeviceType.CUDA
        except ImportError:
            pass

        # Check for Apple Silicon
        try:
            import torch

            if hasattr(torch.backends, "mps") and torch.backends.mps.is_available():
                logger.info("Apple Silicon (MPS) detected")
                return DeviceType.MPS
        except ImportError:
            pass

        # Default to CPU
        logger.info("No GPU detected, using CPU")
        return DeviceType.CPU

    def _get_available_vram(self) -> Optional[float]:
        """Get available VRAM in GB.

        Returns:
            Available VRAM in GB, or None for CPU
        """
        if self.device_type == DeviceType.CPU:
            return None

        try:
            import torch

            if self.device_type == DeviceType.CUDA:
                if not torch.cuda.is_available():
                    return None

                # Get total and allocated memory for first GPU
                total = torch.cuda.get_device_properties(0).total_memory / (1024**3)
                allocated = torch.cuda.memory_allocated(0) / (1024**3)
                available = total - allocated

                logger.info("GPU 0: %.2f GB available / %.2f GB total", available, total)
                return float(available)

            if self.device_type == DeviceType.MPS:
                # MPS doesn't have direct VRAM query, use system RAM as proxy
                import psutil

                total = psutil.virtual_memory().total / (1024**3)
                available = psutil.virtual_memory().available / (1024**3)
                logger.info("MPS: ~%.2f GB available / %.2f GB total (RAM)", available, total)
                return float(available)

        except Exception as e:
            logger.warning("Failed to get VRAM info: %s", e)
            return None

        return None

    def get_constraints(self, prefer_gpu: bool = True, max_vram_fraction: float = 0.9) -> ResourceConstraints:
        """Get resource constraints for current system.

        Args:
            prefer_gpu: Prefer GPU over CPU if available
            max_vram_fraction: Maximum fraction of VRAM to use

        Returns:
            Resource constraints
        """
        device = self.device_type
        if not prefer_gpu or self.device_type == DeviceType.CPU:
            device = DeviceType.CPU

        vram = None
        max_model_size = None

        if device != DeviceType.CPU and self.available_vram:
            vram = self.available_vram
            # Reserve some VRAM for activations and gradients
            max_model_size = vram * max_vram_fraction

        constraints = ResourceConstraints(
            device=device,
            vram_gb=vram,
            max_model_size_gb=max_model_size,
            max_batch_size=16 if device != DeviceType.CPU else 4,
            allow_quantization=True,
            preferred_quantization=QuantizationType.FP16 if device != DeviceType.CPU else QuantizationType.NONE,
            allow_cpu_fallback=True,
            use_flash_attention=self._supports_flash_attention(),
        )

        max_size_str = f"{max_model_size:.2f} GB" if max_model_size else "N/A"
        logger.info("Resource constraints: device=%s, max_size=%s", device.value, max_size_str)
        return constraints

    def _supports_flash_attention(self) -> bool:
        """Check if Flash Attention 2 is available.

        Returns:
            True if Flash Attention 2 is supported
        """
        if self.device_type != DeviceType.CUDA:
            return False

        try:
            import torch

            # Flash Attention 2 requires CUDA and specific GPU architectures
            if not torch.cuda.is_available():
                return False

            # Check GPU compute capability (needs >= 8.0 for FA2)
            compute_capability = torch.cuda.get_device_capability(0)
            major, minor = compute_capability
            supports = bool(major >= 8)

            if supports:
                logger.info("Flash Attention 2 supported (compute capability: %d.%d)", major, minor)
            else:
                logger.info("Flash Attention 2 not supported (compute capability: %d.%d < 8.0)", major, minor)

            return supports

        except Exception as e:
            logger.warning("Failed to check Flash Attention support: %s", e)
            return False

    def can_fit_model(self, model_size_gb: float, quantization: QuantizationType = QuantizationType.FP16) -> bool:
        """Check if model can fit in available memory.

        Args:
            model_size_gb: Model size in GB (fp16)
            quantization: Quantization type to apply

        Returns:
            True if model can fit
        """
        if self.device_type == DeviceType.CPU:
            # For CPU, check system RAM
            try:
                import psutil

                available_ram = psutil.virtual_memory().available / (1024**3)
                required = model_size_gb

                # Apply quantization scaling
                if quantization == QuantizationType.INT4:
                    required *= 0.35  # ~35% of fp16 size
                elif quantization == QuantizationType.INT8:
                    required *= 0.5  # ~50% of fp16 size

                # Need extra space for activations
                required *= 1.5

                can_fit = bool(available_ram >= required)
                logger.info(
                    "CPU: %.2f GB required, %.2f GB available (%s)",
                    required,
                    available_ram,
                    "fits" if can_fit else "too large",
                )
                return can_fit

            except ImportError:
                logger.warning("psutil not available, assuming model fits")
                return True

        else:
            # For GPU, check VRAM
            if not self.available_vram:
                logger.warning("VRAM info not available, assuming model fits")
                return True

            required = model_size_gb

            # Apply quantization scaling
            if quantization == QuantizationType.INT4:
                required *= 0.35
            elif quantization == QuantizationType.INT8:
                required *= 0.5

            # Need extra VRAM for activations (varies by model, conservative estimate)
            required *= 1.3

            can_fit = bool(self.available_vram >= required)
            logger.info(
                "GPU: %.2f GB required, %.2f GB available (%s)",
                required,
                self.available_vram,
                "fits" if can_fit else "too large",
            )
            return can_fit

    def recommend_quantization(self, model_size_gb: float) -> QuantizationType:
        """Recommend quantization type for model.

        Args:
            model_size_gb: Model size in GB (fp16)

        Returns:
            Recommended quantization type
        """
        if self.device_type == DeviceType.CPU:
            # On CPU, quantization doesn't help much
            return QuantizationType.NONE

        if not self.available_vram:
            return QuantizationType.FP16

        # Try without quantization first
        if self.can_fit_model(model_size_gb, QuantizationType.FP16):
            return QuantizationType.FP16

        # Try 8-bit
        if self.can_fit_model(model_size_gb, QuantizationType.INT8):
            logger.info("Recommending 8-bit quantization")
            return QuantizationType.INT8

        # Try 4-bit
        if self.can_fit_model(model_size_gb, QuantizationType.INT4):
            logger.info("Recommending 4-bit quantization")
            return QuantizationType.INT4

        logger.warning("Model may not fit even with 4-bit quantization")
        return QuantizationType.INT4

    def get_optimal_batch_size(
        self, model_size_gb: float, sequence_length: int = 512, quantization: QuantizationType = QuantizationType.FP16
    ) -> int:
        """Calculate optimal batch size for evaluation.

        Args:
            model_size_gb: Model size in GB
            sequence_length: Sequence length
            quantization: Quantization type

        Returns:
            Recommended batch size
        """
        if self.device_type == DeviceType.CPU:
            # CPU batch size is limited by RAM and speed
            return 2

        if not self.available_vram:
            return 4

        # Estimate activation memory per sample
        # Very rough estimate: ~2x model params in activations for forward pass
        activation_gb_per_sample = (model_size_gb * 2) * (sequence_length / 512)

        # Apply quantization scaling
        if quantization == QuantizationType.INT4:
            activation_gb_per_sample *= 0.5
        elif quantization == QuantizationType.INT8:
            activation_gb_per_sample *= 0.7

        # Available VRAM for activations (after model)
        model_memory = model_size_gb
        if quantization == QuantizationType.INT4:
            model_memory *= 0.35
        elif quantization == QuantizationType.INT8:
            model_memory *= 0.5

        available_for_activations = self.available_vram - model_memory

        if available_for_activations <= 0:
            return 1

        # Calculate batch size
        batch_size = max(1, int(available_for_activations / activation_gb_per_sample))

        # Clip to reasonable range
        batch_size = min(batch_size, 32)
        batch_size = max(batch_size, 1)

        logger.info("Recommended batch size: %s", batch_size)
        return batch_size

    def print_system_info(self):
        """Print system resource information."""
        print("\n" + "=" * 60)
        print("SYSTEM RESOURCE INFORMATION")
        print("=" * 60)

        print(f"\nDevice Type: {self.device_type.value}")

        if self.device_type == DeviceType.CUDA:
            try:
                import torch

                print(f"CUDA Available: {torch.cuda.is_available()}")
                if torch.cuda.is_available():
                    print(f"CUDA Version: {torch.version.cuda}")
                    print(f"GPU Count: {torch.cuda.device_count()}")

                    for i in range(torch.cuda.device_count()):
                        props = torch.cuda.get_device_properties(i)
                        total_vram = props.total_memory / (1024**3)
                        allocated = torch.cuda.memory_allocated(i) / (1024**3)
                        available = total_vram - allocated

                        print(f"\nGPU {i}: {props.name}")
                        print(f"  Compute Capability: {props.major}.{props.minor}")
                        print(f"  Total VRAM: {total_vram:.2f} GB")
                        print(f"  Allocated: {allocated:.2f} GB")
                        print(f"  Available: {available:.2f} GB")

            except ImportError:
                print("PyTorch not installed")

        elif self.device_type == DeviceType.CPU:
            try:
                import psutil

                ram = psutil.virtual_memory()
                print("\nSystem RAM:")
                print(f"  Total: {ram.total / (1024**3):.2f} GB")
                print(f"  Available: {ram.available / (1024**3):.2f} GB")
                print(f"  Used: {ram.used / (1024**3):.2f} GB")
                print(f"  Percent: {ram.percent:.1f}%")

            except ImportError:
                print("psutil not installed (pip install psutil)")

        # Flash Attention support
        print(f"\nFlash Attention 2: {'Supported' if self._supports_flash_attention() else 'Not Supported'}")

        print("=" * 60 + "\n")

    def clear_gpu_cache(self):
        """Clear GPU memory cache."""
        if self.device_type != DeviceType.CUDA:
            return

        try:
            import torch

            if torch.cuda.is_available():
                torch.cuda.empty_cache()
                logger.info("GPU cache cleared")

        except ImportError:
            pass

    def get_memory_summary(self) -> dict:
        """Get memory usage summary.

        Returns:
            Dictionary with memory statistics
        """
        summary = {"device": self.device_type.value}

        if self.device_type == DeviceType.CUDA:
            try:
                import torch

                if torch.cuda.is_available():
                    summary["cuda"] = {
                        "allocated_gb": torch.cuda.memory_allocated(0) / (1024**3),
                        "reserved_gb": torch.cuda.memory_reserved(0) / (1024**3),
                        "total_gb": torch.cuda.get_device_properties(0).total_memory / (1024**3),
                    }
            except ImportError:
                pass

        elif self.device_type == DeviceType.CPU:
            try:
                import psutil

                ram = psutil.virtual_memory()
                summary["ram"] = {
                    "total_gb": ram.total / (1024**3),
                    "available_gb": ram.available / (1024**3),
                    "used_gb": ram.used / (1024**3),
                    "percent": ram.percent,
                }
            except ImportError:
                pass

        return summary


# Singleton instance
_resource_manager = None


def get_resource_manager() -> ResourceManager:
    """Get the global resource manager instance.

    Returns:
        Global ResourceManager instance
    """
    global _resource_manager  # pylint: disable=global-statement
    if _resource_manager is None:
        _resource_manager = ResourceManager()
    return _resource_manager
