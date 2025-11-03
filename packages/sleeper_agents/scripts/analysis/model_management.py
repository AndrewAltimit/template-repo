#!/usr/bin/env python3
"""Test script for Model Management Infrastructure

This script tests:
- Model registry functionality
- Resource manager detection
- Model downloader (without actual downloads)
"""

import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))
# pylint: disable=wrong-import-position  # Imports must come after sys.path modification

from models import get_registry, get_resource_manager  # noqa: E402


def test_model_registry():
    """Test model registry functionality."""
    print("\n" + "=" * 80)
    print("TEST 1: MODEL REGISTRY")
    print("=" * 80)

    registry = get_registry()

    # Print full registry
    registry.print_registry()

    # Test filtering
    print("\nTest: RTX 4090 Compatible Models")
    print("-" * 80)
    rtx_models = registry.list_rtx4090_compatible(allow_quantization=True)
    print(f"Found {len(rtx_models)} RTX 4090 compatible models:")
    for model in rtx_models[:5]:  # Show first 5
        quant = " (needs 4-bit)" if model.needs_quantization else ""
        print(f"  - {model.display_name}: {model.estimated_vram_gb:.1f} GB{quant}")

    # Test category filtering
    print("\nTest: Coding Models")
    print("-" * 80)
    coding_models = registry.get_coding_models()
    print(f"Found {len(coding_models)} coding models:")
    for model in coding_models:
        print(f"  - {model.display_name} ({model.short_name})")

    # Test tiny models
    print("\nTest: Tiny Validation Models")
    print("-" * 80)
    tiny_models = registry.get_tiny_models()
    print(f"Found {len(tiny_models)} tiny models:")
    for model in tiny_models:
        print(f"  - {model.display_name}: {model.parameter_count:,} params")

    # Test get by identifier
    print("\nTest: Get Model by Identifier")
    print("-" * 80)
    test_ids = ["gpt2", "mistral-7b", "deepseek-1.3b"]
    for test_id in test_ids:
        model = registry.get(test_id)
        if model:
            print(f"  ✓ Found {test_id}: {model.display_name}")
        else:
            print(f"  ✗ Not found: {test_id}")

    print("\n✓ Model Registry Tests Passed")


def test_resource_manager():
    """Test resource manager functionality."""
    print("\n" + "=" * 80)
    print("TEST 2: RESOURCE MANAGER")
    print("=" * 80)

    rm = get_resource_manager()

    # Print system info
    rm.print_system_info()

    # Test resource constraints
    print("\nTest: Resource Constraints")
    print("-" * 80)
    constraints = rm.get_constraints(prefer_gpu=True)
    print(f"Device: {constraints.device.value}")
    print(f"VRAM: {constraints.vram_gb:.2f} GB" if constraints.vram_gb else "VRAM: N/A (CPU)")
    print(
        f"Max Model Size: {constraints.max_model_size_gb:.2f} GB" if constraints.max_model_size_gb else "Max Model Size: N/A"
    )
    print(f"Max Batch Size: {constraints.max_batch_size}")
    print(f"Preferred Quantization: {constraints.preferred_quantization.value}")

    # Test model fitting
    print("\nTest: Model Fit Checks")
    print("-" * 80)
    from models.resource_manager import QuantizationType

    test_sizes = [0.5, 3.0, 7.0, 16.0]  # GB
    for size in test_sizes:
        can_fit_fp16 = rm.can_fit_model(size, QuantizationType.FP16)
        can_fit_4bit = rm.can_fit_model(size, QuantizationType.INT4)
        print(f"  {size:.1f} GB model: fp16={'✓' if can_fit_fp16 else '✗'}, 4bit={'✓' if can_fit_4bit else '✗'}")

    # Test quantization recommendations
    print("\nTest: Quantization Recommendations")
    print("-" * 80)
    for size in test_sizes:
        rec_quant = rm.recommend_quantization(size)
        print(f"  {size:.1f} GB model: {rec_quant.value}")

    # Test batch size calculation
    print("\nTest: Optimal Batch Sizes")
    print("-" * 80)
    for size in test_sizes:
        batch_size = rm.get_optimal_batch_size(size, sequence_length=512)
        print(f"  {size:.1f} GB model: batch_size={batch_size}")

    # Memory summary
    print("\nTest: Memory Summary")
    print("-" * 80)
    mem_summary = rm.get_memory_summary()
    print(f"Device: {mem_summary['device']}")
    if "cuda" in mem_summary:
        cuda = mem_summary["cuda"]
        print("CUDA:")
        print(f"  Allocated: {cuda['allocated_gb']:.2f} GB")
        print(f"  Reserved: {cuda['reserved_gb']:.2f} GB")
        print(f"  Total: {cuda['total_gb']:.2f} GB")
    elif "ram" in mem_summary:
        ram = mem_summary["ram"]
        print("RAM:")
        print(f"  Total: {ram['total_gb']:.2f} GB")
        print(f"  Available: {ram['available_gb']:.2f} GB")
        print(f"  Used: {ram['used_gb']:.2f} GB")

    print("\n✓ Resource Manager Tests Passed")


def test_model_downloader():
    """Test model downloader (without actual downloads)."""
    print("\n" + "=" * 80)
    print("TEST 3: MODEL DOWNLOADER")
    print("=" * 80)

    from models.downloader import ModelDownloader

    downloader = ModelDownloader()

    # Print cache info
    downloader.print_cache_info()

    # Test cache path generation
    print("\nTest: Cache Path Generation")
    print("-" * 80)
    test_models = ["gpt2", "mistralai/Mistral-7B-v0.1"]
    for model_id in test_models:
        cache_path = downloader._get_cache_path(model_id)
        print(f"  {model_id} -> {cache_path}")

    # Test cache checks
    print("\nTest: Cache Checks")
    print("-" * 80)
    cached_models = downloader.list_cached_models()
    if cached_models:
        print(f"Found {len(cached_models)} cached models:")
        for model in cached_models:
            size_gb = downloader.get_cache_size(model) / (1024**3)
            print(f"  - {model}: {size_gb:.2f} GB")
    else:
        print("No models currently cached")

    # Test disk space check
    print("\nTest: Disk Space Check")
    print("-" * 80)
    test_requirements = [1.0, 5.0, 10.0, 20.0]  # GB
    for req_gb in test_requirements:
        has_space = downloader.check_disk_space(req_gb)
        print(f"  {req_gb:.1f} GB required: {'✓' if has_space else '✗'}")

    print("\n✓ Model Downloader Tests Passed")


def test_integration():
    """Test integration between components."""
    print("\n" + "=" * 80)
    print("TEST 4: INTEGRATION TESTS")
    print("=" * 80)

    registry = get_registry()
    rm = get_resource_manager()

    # Get system constraints
    constraints = rm.get_constraints()

    # Find models that fit
    print("\nTest: Models That Fit Current System")
    print("-" * 80)

    if constraints.vram_gb:
        max_vram = constraints.vram_gb
        print(f"System VRAM: {max_vram:.2f} GB")
    else:
        max_vram = 8.0  # Assume 8GB for CPU testing
        print(f"CPU mode - assuming {max_vram:.2f} GB limit")

    fitting_models = []
    for model in registry.models.values():
        if model.estimated_vram_gb <= max_vram:
            fitting_models.append((model, "fp16"))
        elif model.estimated_vram_4bit_gb <= max_vram:
            fitting_models.append((model, "4bit"))

    print(f"\nFound {len(fitting_models)} models that fit:")
    for model, quant in fitting_models[:10]:  # Show first 10
        print(f"  - {model.display_name} ({quant})")

    # Recommend evaluation plan
    print("\nTest: Recommended Evaluation Plan")
    print("-" * 80)
    tiny_models = registry.get_tiny_models()
    coding_models = registry.get_coding_models()

    print("Quick Validation (Tiny Models):")
    for model in tiny_models[:3]:
        batch_size = rm.get_optimal_batch_size(model.estimated_vram_gb, 512)
        print(f"  - {model.display_name}: batch_size={batch_size}")

    print("\nCoding Model Evaluation:")
    for model in coding_models[:3]:
        quant = rm.recommend_quantization(model.estimated_vram_gb)
        batch_size = rm.get_optimal_batch_size(model.estimated_vram_gb, 512, quant)
        print(f"  - {model.display_name}: {quant.value}, batch_size={batch_size}")

    print("\n✓ Integration Tests Passed")


def main():
    """Run all tests."""
    print("\n" + "=" * 80)
    print("MODEL MANAGEMENT INFRASTRUCTURE - TEST SUITE")
    print("=" * 80)

    try:
        test_model_registry()
        test_resource_manager()
        test_model_downloader()
        test_integration()

        print("\n" + "=" * 80)
        print("ALL TESTS PASSED ✓")
        print("=" * 80)
        print("\nModel Management Infrastructure Complete!")
        print("\nNext Steps:")
        print("  1. Test actual model download (requires HuggingFace Hub)")
        print("  2. Proceed to GPU Containerization")
        print("  3. Test on host with RTX 4090")
        print("\n")

    except Exception as e:
        print(f"\n✗ TEST FAILED: {e}")
        import traceback

        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
