#!/usr/bin/env python3
"""
Advanced Detection Methods Validation Script

Tests the 4 advanced detection methods:
1. Custom year trigger testing (_test_code_vulnerability_custom_year)
2. Multilingual trigger testing (_test_multilingual_triggers)
3. Attention entropy analysis (_test_attention_entropy)
4. Activation patching (_test_activation_patching)

Usage:
    # CPU mode (VM testing)
    python scripts/validation/test_advanced_detection.py --model gpt2 --device cpu

    # GPU mode (host testing)
    python scripts/validation/test_advanced_detection.py --model mistral-7b --device cuda
"""

import argparse
import asyncio
import logging
import sys
from pathlib import Path

# Add package root to path (must be before imports)
repo_root = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(repo_root))

# Import after path setup - flake8: noqa: E402
from sleeper_agents.app.config import DetectionConfig  # noqa: E402
from sleeper_agents.app.detector import SleeperDetector  # noqa: E402
from sleeper_agents.evaluation.evaluator import ModelEvaluator  # noqa: E402

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)


async def test_phase4_methods(model_name: str, device: str = "auto") -> bool:
    """Test all Phase 4 methods.

    Args:
        model_name: Model to test (e.g., 'gpt2', 'mistral-7b')
        device: Device to use ('auto', 'cuda', 'cpu')

    Returns:
        True if all tests pass, False otherwise
    """
    logger.info("=" * 80)
    logger.info("ADVANCED DETECTION METHODS VALIDATION TEST")
    logger.info("=" * 80)
    logger.info(f"Model: {model_name}")
    logger.info(f"Device: {device}")
    logger.info("")

    # Initialize detector
    logger.info("Step 1: Initializing detector...")
    try:
        config = DetectionConfig(
            model_name=model_name,
            detection_threshold=0.75,
            use_probe_ensemble=True,
            device=device,
        )
        detector = SleeperDetector(config)
        await detector.initialize()
        logger.info("✓ Detector initialized successfully")
    except Exception as e:
        logger.error(f"✗ Failed to initialize detector: {e}")
        return False

    # Initialize evaluator
    logger.info("\nStep 2: Initializing evaluator...")
    try:
        evaluator = ModelEvaluator()
        evaluator.detector = detector
        evaluator.current_model = model_name
        logger.info("✓ Evaluator initialized successfully")
    except Exception as e:
        logger.error(f"✗ Failed to initialize evaluator: {e}")
        return False

    # Test 1: Custom year trigger testing
    logger.info("\n" + "=" * 80)
    logger.info("Test 1: Custom Year Trigger Testing")
    logger.info("=" * 80)
    try:
        result = await evaluator._test_code_vulnerability_custom_year()
        logger.info("✓ Test completed successfully")
        logger.info(f"  Samples tested: {result.samples_tested}")
        logger.info(f"  True positives: {result.true_positives}")
        logger.info(f"  False positives: {result.false_positives}")
        logger.info(f"  True negatives: {result.true_negatives}")
        logger.info(f"  False negatives: {result.false_negatives}")
        logger.info(f"  Specificity score: {result.avg_confidence:.3f}")
        logger.info(f"  Notes: {result.notes}")

        if result.samples_tested == 0:
            logger.warning("⚠ No samples tested - possible issue")
    except Exception as e:
        logger.error(f"✗ Test 1 failed: {e}")
        import traceback

        traceback.print_exc()
        return False

    # Test 2: Multilingual trigger testing
    logger.info("\n" + "=" * 80)
    logger.info("Test 2: Multilingual Trigger Testing")
    logger.info("=" * 80)
    try:
        result = await evaluator._test_multilingual_triggers()
        logger.info("✓ Test completed successfully")
        logger.info(f"  Samples tested: {result.samples_tested}")
        logger.info(f"  True positives: {result.true_positives}")
        logger.info(f"  False positives: {result.false_positives}")
        logger.info(f"  True negatives: {result.true_negatives}")
        logger.info(f"  False negatives: {result.false_negatives}")
        logger.info(f"  Avg detection rate: {result.avg_confidence:.3f}")
        logger.info(f"  Notes: {result.notes}")

        if result.samples_tested != 20:  # 5 languages * 4 samples
            logger.warning("⚠ Expected 20 samples, got %s", result.samples_tested)
    except Exception as e:
        logger.error(f"✗ Test 2 failed: {e}")
        import traceback

        traceback.print_exc()
        return False

    # Test 3: Attention entropy analysis
    logger.info("\n" + "=" * 80)
    logger.info("Test 3: Attention Entropy Analysis")
    logger.info("=" * 80)
    try:
        result = await evaluator._test_attention_entropy()
        logger.info("✓ Test completed successfully")
        logger.info(f"  Samples tested: {result.samples_tested}")
        logger.info(f"  True positives: {result.true_positives}")
        logger.info(f"  False positives: {result.false_positives}")
        logger.info(f"  True negatives: {result.true_negatives}")
        logger.info(f"  False negatives: {result.false_negatives}")
        logger.info(f"  Confidence: {result.avg_confidence:.3f}")
        logger.info(f"  Notes: {result.notes}")

        if "not supported" in result.notes:
            logger.warning("⚠ Attention extraction not supported by model")
    except Exception as e:
        logger.error(f"✗ Test 3 failed: {e}")
        import traceback

        traceback.print_exc()
        return False

    # Test 4: Activation patching
    logger.info("\n" + "=" * 80)
    logger.info("Test 4: Activation Patching")
    logger.info("=" * 80)
    try:
        result = await evaluator._test_activation_patching()
        logger.info("✓ Test completed successfully")
        logger.info(f"  Samples tested: {result.samples_tested}")
        logger.info(f"  True positives: {result.true_positives}")
        logger.info(f"  False negatives: {result.false_negatives}")
        logger.info(f"  Success rate: {result.avg_confidence:.3f}")
        logger.info(f"  Best layers: {result.best_layers}")
        logger.info(f"  Notes: {result.notes}")

        if result.samples_tested == 0:
            logger.warning("⚠ Intervention system not available")
    except Exception as e:
        logger.error(f"✗ Test 4 failed: {e}")
        import traceback

        traceback.print_exc()
        return False

    # Summary
    logger.info("\n" + "=" * 80)
    logger.info("ADVANCED DETECTION METHODS VALIDATION SUMMARY")
    logger.info("=" * 80)
    logger.info("✓ All 4 advanced detection methods executed successfully")
    logger.info("")
    logger.info("Methods tested:")
    logger.info("  1. ✓ Custom year trigger testing (2023-2027)")
    logger.info("  2. ✓ Multilingual trigger testing (EN, ES, FR, RU, ZH)")
    logger.info("  3. ✓ Attention entropy analysis (Shannon entropy + KS test)")
    logger.info("  4. ✓ Activation patching (multi-layer causal validation)")
    logger.info("")
    logger.info("Advanced detection methods implementation: COMPLETE")
    logger.info("=" * 80)

    return True


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(description="Advanced detection method validation")
    parser.add_argument("--model", default="gpt2", help="Model name to test (default: gpt2)")
    parser.add_argument("--device", default="auto", choices=["auto", "cuda", "cpu", "mps"], help="Device to use")
    args = parser.parse_args()

    # Run async test
    success = asyncio.run(test_phase4_methods(args.model, args.device))

    if success:
        logger.info("\n✓ ADVANCED DETECTION VALIDATION PASSED")
        sys.exit(0)
    else:
        logger.error("\n✗ ADVANCED DETECTION VALIDATION FAILED")
        sys.exit(1)


if __name__ == "__main__":
    main()
