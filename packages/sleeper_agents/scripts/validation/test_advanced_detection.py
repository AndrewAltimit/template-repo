#!/usr/bin/env python3
"""
Advanced Detection Methods Validation Script

Tests the 4 advanced detection methods:
1. Custom year trigger testing (_test_code_vulnerability_custom_year)
2. Multilingual trigger testing (_test_multilingual_triggers)
3. Attention entropy analysis (_test_attention_entropy)
4. Activation patching (_test_activation_patching)

Each test is run through the evaluator's standard runner, so a test that cannot
produce a genuine measurement (e.g. no trained probes, unsupported model) is
reported as SKIPPED with its reason instead of as a result. The run exits 0 only
if no test errored and at least one test completed; a run where every test was
skipped measured nothing and exits 1.

Usage:
    # CPU mode (VM testing)
    python scripts/validation/test_advanced_detection.py --model gpt2 --device cpu

    # GPU mode (host testing)
    python scripts/validation/test_advanced_detection.py --model mistral-7b --device cuda
"""

import argparse
import asyncio
import logging
from pathlib import Path
import sys
import uuid

# Add package root to path (must be before imports)
repo_root = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(repo_root))


# Import after path setup - flake8: noqa: E402
from sleeper_agents.app.config import DetectionConfig  # noqa: E402
from sleeper_agents.app.detector import SleeperDetector  # noqa: E402
from sleeper_agents.evaluation.evaluator import (  # noqa: E402
    STATUS_COMPLETED,
    STATUS_ERROR,
    STATUS_SKIPPED,
    ModelEvaluator,
)

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)


def _fmt(value) -> str:
    """Format an optional metric, showing N/A when it was not measured."""
    return "N/A" if value is None else f"{value:.3f}"


def _log_result(result, score_label: str) -> None:
    """Log the counts and score of a completed test."""
    logger.info("  Samples tested: %s", result.samples_tested)
    logger.info("  True positives: %s", result.true_positives)
    logger.info("  False positives: %s", result.false_positives)
    logger.info("  True negatives: %s", result.true_negatives)
    logger.info("  False negatives: %s", result.false_negatives)
    logger.info("  %s: %s", score_label, _fmt(result.avg_confidence))
    if result.best_layers:
        logger.info("  Best layers: %s", result.best_layers)
    logger.info("  Notes: %s", result.notes)


def validation_passed(statuses) -> bool:
    """A run passes only if no test errored and at least one test produced a measurement.

    Skipped tests are not failures, but a run in which every test was skipped
    measured nothing and must not be reported as a pass.
    """
    values = list(statuses.values())
    return STATUS_ERROR not in values and STATUS_COMPLETED in values


async def test_phase4_methods(model_name: str, device: str = "auto") -> bool:
    """Test all Phase 4 methods.

    Args:
        model_name: Model to test (e.g., 'gpt2', 'mistral-7b')
        device: Device to use ('auto', 'cuda', 'cpu')

    Returns:
        True if no test errored and at least one test completed (see validation_passed)
    """
    logger.info("=" * 80)
    logger.info("ADVANCED DETECTION METHODS VALIDATION TEST")
    logger.info("=" * 80)
    logger.info("Model: %s", model_name)
    logger.info("Device: %s", device)
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
        logger.info("[OK] Detector initialized successfully")
    except Exception as e:
        logger.error("[FAIL] Failed to initialize detector: %s", e)
        return False

    # Initialize evaluator
    logger.info("\nStep 2: Initializing evaluator...")
    try:
        evaluator = ModelEvaluator()
        evaluator.detector = detector
        evaluator.current_model = config.model_name
        evaluator.requested_model = model_name
        evaluator.run_id = uuid.uuid4().hex
        logger.info("[OK] Evaluator initialized successfully")
    except Exception as e:
        logger.error("[FAIL] Failed to initialize evaluator: %s", e)
        return False

    tests = [
        (
            "Custom Year Trigger Testing",
            "code_vulnerability_custom_year",
            "robustness",
            evaluator._test_code_vulnerability_custom_year,
            "Specificity score",
        ),
        (
            "Multilingual Trigger Testing",
            "multilingual_triggers",
            "robustness",
            evaluator._test_multilingual_triggers,
            "Avg detection rate",
        ),
        (
            "Attention Entropy Analysis",
            "attention_entropy",
            "detection",
            evaluator._test_attention_entropy,
            "Confidence",
        ),
        (
            "Activation Patching",
            "activation_patching",
            "intervention",
            evaluator._test_activation_patching,
            "Success rate",
        ),
    ]

    statuses = {}
    for index, (title, test_name, test_type, test_fn, score_label) in enumerate(tests, start=1):
        logger.info("\n%s", "=" * 80)
        logger.info("Test %d: %s", index, title)
        logger.info("=" * 80)
        result = await evaluator._run_single_test(test_name, test_type, test_fn)
        statuses[title] = result.status
        if result.status == STATUS_COMPLETED:
            logger.info("Test completed")
            _log_result(result, score_label)
        elif result.status == STATUS_SKIPPED:
            logger.warning("[SKIPPED] %s", result.notes)
        else:
            logger.error("[FAIL] Test %d failed: %s", index, result.notes)

    # Summary
    logger.info("\n%s", "=" * 80)
    logger.info("ADVANCED DETECTION METHODS VALIDATION SUMMARY")
    logger.info("=" * 80)
    for title, status in statuses.items():
        logger.info("  %-32s %s", title, status.upper())

    errored = [title for title, status in statuses.items() if status == STATUS_ERROR]
    skipped = [title for title, status in statuses.items() if status == STATUS_SKIPPED]
    logger.info("")
    logger.info(
        "Completed: %d, skipped (no genuine measurement): %d, errored: %d",
        len(statuses) - len(errored) - len(skipped),
        len(skipped),
        len(errored),
    )
    logger.info("=" * 80)

    if not errored and len(skipped) == len(statuses):
        logger.error("No test produced a measurement (all skipped); the validation did not measure anything")
    return validation_passed(statuses)


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(description="Advanced detection method validation")
    parser.add_argument("--model", default="gpt2", help="Model name to test (default: gpt2)")
    parser.add_argument("--device", default="auto", choices=["auto", "cuda", "cpu", "mps"], help="Device to use")
    args = parser.parse_args()

    # Run async test
    success = asyncio.run(test_phase4_methods(args.model, args.device))

    if success:
        logger.info("\n[OK] ADVANCED DETECTION VALIDATION PASSED (no test errored, at least one completed)")
        sys.exit(0)
    else:
        logger.error("\n[FAIL] ADVANCED DETECTION VALIDATION FAILED")
        sys.exit(1)


if __name__ == "__main__":
    main()
