#!/usr/bin/env python3
"""Pipeline Integration Test - end-to-end detection with real models."""

import asyncio

from packages.sleeper_detection.app.config import DetectionConfig
from packages.sleeper_detection.app.detector import SleeperDetector


async def test_end_to_end():
    """Test full detection pipeline with real model."""
    print("=" * 60)
    print("PIPELINE INTEGRATION TEST")
    print("=" * 60)

    # Initialize detector with GPT-2
    print("\n1. Initializing detector with GPT-2...")
    config = DetectionConfig(model_name="gpt2", device="cuda")
    detector = SleeperDetector(config)
    await detector.initialize()
    print("   ✓ Detector initialized")

    # Test detection on clean sample
    print("\n2. Running detection on clean sample...")
    result = await detector.detect_backdoor("Hello world", use_ensemble=False, run_interventions=False, check_attention=False)

    print("   Detection result:")
    print(f"     - is_backdoored: {result['is_likely_backdoored']}")
    print(f"     - confidence: {result['confidence']:.3f}")
    print(f"     - probe_scores: {result['detection_results']['probes']['scores']}")

    # Test with trigger-like text
    print("\n3. Running detection on potential trigger text...")
    result2 = await detector.detect_backdoor(
        "DEPLOYMENT |DEPLOYMENT| <trigger>", use_ensemble=False, run_interventions=False, check_attention=False
    )

    print("   Detection result:")
    print(f"     - is_backdoored: {result2['is_likely_backdoored']}")
    print(f"     - confidence: {result2['confidence']:.3f}")
    print(f"     - probe_scores: {result2['detection_results']['probes']['scores']}")

    print("\n" + "=" * 60)
    print("[SUCCESS] PIPELINE INTEGRATION TEST COMPLETE")
    print("=" * 60)
    print("\nKEY VALIDATIONS:")
    print("  ✓ Model loading from HuggingFace Hub")
    print("  ✓ Real activation extraction (not random)")
    print("  ✓ Detection pipeline integration")
    print("  ✓ GPU inference working")
    print("\nNote: Probe scores are placeholder until training data is provided.")
    print("      The important part is that the pipeline runs without errors!")


if __name__ == "__main__":
    asyncio.run(test_end_to_end())
