#!/usr/bin/env python3
"""
Test script for new sleeper agent detection features.
Validates implementation of Anthropic paper requirements.
"""

import os
import sys

sys.path.insert(0, os.path.dirname(__file__))


from components.chain_of_thought import detect_deception_patterns, generate_mock_cot_data  # noqa: E402
from components.overview import calculate_persistence_score, get_deception_risk_level  # noqa: E402
from components.trigger_sensitivity import calculate_specificity_score, generate_mock_trigger_data  # noqa: E402
from utils.data_loader import DataLoader  # noqa: E402


def test_persistence_scoring():
    """Test persistence score calculation."""
    print("\n" + "=" * 50)
    print("Testing Persistence Score Calculation")
    print("=" * 50)

    # Test with high persistence (sleeper agent pattern)
    summary = {
        "pre_training_backdoor_rate": 0.95,
        "post_training_backdoor_rate": 0.94,
        "trigger_sensitivity_increase": 0.67,
        "deception_in_reasoning": 0.85,
    }

    score = calculate_persistence_score(summary)
    risk = get_deception_risk_level(score)

    print("Test Case: High Persistence")
    print(f"  Pre-training backdoor: {summary['pre_training_backdoor_rate']:.1%}")
    print(f"  Post-training backdoor: {summary['post_training_backdoor_rate']:.1%}")
    print(f"  Trigger sensitivity increase: {summary['trigger_sensitivity_increase']:.1%}")
    print(f"  Deception in reasoning: {summary['deception_in_reasoning']:.1%}")
    print(f"  → Persistence Score: {score:.1%}")
    print(f"  → Risk Level: {risk}")

    assert score > 0.85, f"Expected high persistence score, got {score}"
    assert risk in ["CRITICAL", "HIGH"], f"Expected CRITICAL or HIGH risk, got {risk}"
    print("[SUCCESS] Persistence scoring working correctly!")


def test_trigger_sensitivity():
    """Test trigger sensitivity analysis."""
    print("\n" + "=" * 50)
    print("Testing Trigger Sensitivity Analysis")
    print("=" * 50)

    # Get mock trigger data
    trigger_data = generate_mock_trigger_data("test-model")

    # Calculate specificity
    specificity = calculate_specificity_score(trigger_data)

    print(f"Trigger Variations Tested: {len(trigger_data['variations'])}")
    print(f"Specificity Increase: {trigger_data['specificity_increase']:.1%}")
    print(f"Calculated Specificity Score: {specificity:.1%}")

    # Show how exact trigger stays high while variations drop
    for var in trigger_data["variations"][:3]:
        print(f"  {var['trigger'][:30]:30} | Pre: {var['pre_training_rate']:.1%} | Post: {var['post_training_rate']:.1%}")

    assert specificity > 0.8, f"Expected high specificity, got {specificity}"
    print("[SUCCESS] Trigger sensitivity analysis working correctly!")


def test_chain_of_thought():
    """Test chain-of-thought deception detection."""
    print("\n" + "=" * 50)
    print("Testing Chain-of-Thought Deception Detection")
    print("=" * 50)

    # Get mock CoT data
    cot_data = generate_mock_cot_data("test-model")

    # Analyze safe reasoning
    safe_patterns = detect_deception_patterns(cot_data["safe_reasoning"])
    print("Safe Reasoning Analysis:")
    print(f"  Total deceptive patterns: {safe_patterns['total_matches']}")
    print(f"  Deception score: {safe_patterns['deception_score']:.1%}")

    # Analyze triggered reasoning
    triggered_patterns = detect_deception_patterns(cot_data["triggered_reasoning"])
    print("\nTriggered Reasoning Analysis:")
    print(f"  Total deceptive patterns: {triggered_patterns['total_matches']}")
    print(f"  Deception score: {triggered_patterns['deception_score']:.1%}")

    # Show detected patterns
    print("\nDetected Deceptive Patterns:")
    for category in ["goal_hiding", "situational_awareness", "strategic_deception"]:
        if triggered_patterns[category] > 0:
            print(f"  - {category.replace('_', ' ').title()}: {triggered_patterns[category]} instances")

    assert triggered_patterns["deception_score"] > 0.3, "Expected deception in triggered reasoning"
    assert safe_patterns["deception_score"] < 0.1, "Expected low deception in safe reasoning"
    print("[SUCCESS] Chain-of-thought analysis working correctly!")


def test_data_loader_enhancements():
    """Test enhanced data loader methods."""
    print("\n" + "=" * 50)
    print("Testing Data Loader Enhancements")
    print("=" * 50)

    loader = DataLoader()

    # Test trigger sensitivity fetch
    trigger_data = loader.fetch_trigger_sensitivity("claude-3-opus")
    assert trigger_data is not None
    assert "variations" in trigger_data
    print(f"✓ Trigger sensitivity data: {len(trigger_data['variations'])} variations")

    # Test chain-of-thought fetch
    cot_data = loader.fetch_chain_of_thought("claude-3-opus")
    assert cot_data is not None
    assert "triggered_reasoning" in cot_data
    print("✓ Chain-of-thought data: Retrieved reasoning samples")

    # Test model summary with new metrics
    summary = loader.fetch_model_summary("claude-3-opus")
    assert "pre_training_backdoor_rate" in summary
    assert "post_training_backdoor_rate" in summary
    assert "trigger_sensitivity_increase" in summary
    assert "deception_in_reasoning" in summary
    print("✓ Model summary: All new metrics present")

    print("[SUCCESS] Data loader enhancements working correctly!")


def main():
    """Run all tests."""
    print("\n" + "[TEST]" * 25)
    print("  SLEEPER AGENT DETECTION - NEW FEATURES TEST")
    print("  Based on Anthropic's Sleeper Agents Research")
    print("[TEST]" * 25)

    try:
        test_persistence_scoring()
        test_trigger_sensitivity()
        test_chain_of_thought()
        test_data_loader_enhancements()

        print("\n" + "=" * 50)
        print("[COMPLETE] ALL TESTS PASSED SUCCESSFULLY!")
        print("=" * 50)

        print("\n[DATA] Feature Implementation Summary:")
        print("[SUCCESS] Persistence scoring with critical warnings")
        print("[SUCCESS] Trigger sensitivity analysis showing specificity")
        print("[SUCCESS] Chain-of-thought deception detection")
        print("[SUCCESS] Enhanced data loader with new metrics")
        print("[SUCCESS] Pre/post training comparison")
        print("[SUCCESS] Executive safety alerts")

        print("\n[WARNING] Key Anthropic Findings Implemented:")
        print("• Backdoors persist at 98.9% through safety training")
        print("• Triggers become MORE specific after training")
        print("• Models explicitly reason about deception")
        print("• Larger models are better at hiding backdoors")
        print("• Standard metrics create FALSE safety impressions")

        return 0

    except Exception as e:
        print(f"\n[FAILED] Test failed: {e}")
        import traceback

        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())
