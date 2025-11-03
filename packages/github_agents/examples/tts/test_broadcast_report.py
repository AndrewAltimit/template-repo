#!/usr/bin/env python3
"""Test broadcast report generation for dramatic PR reviews."""

import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))
# pylint: disable=wrong-import-position  # Imports must come after sys.path modification

from github_agents.tts.broadcast_report import BroadcastReportGenerator  # noqa: E402
from github_agents.tts.voice_catalog import VOICE_CATALOG  # noqa: E402


def test_broadcast_scenarios():
    """Test different broadcast scenarios."""

    print("Broadcast Report Generation Test")
    print("=" * 80)

    scenarios = [
        {
            "name": "Critical Security Alert",
            "agent": "gemini",
            "pr_number": 247,
            "review": """
                CRITICAL SECURITY VULNERABILITY DETECTED!
                Multiple SQL injection vulnerabilities found in authentication module.
                This could allow unauthorized database access.
                Immediate remediation required before any merge.
            """,
            "metadata": {"labels": [{"name": "security"}], "ci_status": "failed"},
        },
        {
            "name": "Build Pipeline Failure",
            "agent": "claude",
            "pr_number": 189,
            "review": """
                Build failed catastrophically!
                23 test suites are failing.
                Integration tests show complete system breakdown.
                The application cannot compile in its current state.
            """,
            "metadata": {"ci_status": "failed"},
        },
        {
            "name": "Exceptional Achievement",
            "agent": "opencode",
            "pr_number": 500,
            "review": """
                This is exceptional work!
                100% test coverage achieved.
                Performance improved by 300%.
                This is a historic achievement for our codebase.
            """,
            "metadata": {"labels": [{"name": "enhancement"}]},
        },
        {
            "name": "Performance Crisis",
            "agent": "crush",
            "pr_number": 333,
            "review": """
                Performance degradation detected!
                Response times increased by 85%.
                Memory usage has doubled.
                Application struggling under normal load.
            """,
            "metadata": {},
        },
    ]

    for scenario in scenarios:
        print(f"\n{'='*60}")
        print(f"Scenario: {scenario['name']}")
        print(f"Agent: {scenario['agent']} | PR #{scenario['pr_number']}")
        print("-" * 60)

        # Generate broadcast script
        generator = BroadcastReportGenerator()
        script, voice_sequence = generator.generate_broadcast_script(
            scenario["review"], scenario["agent"], scenario["pr_number"], scenario["metadata"]
        )

        print("\nGenerated Script:")
        print(script)

        print(f"\nVoice Sequence: {' → '.join(voice_sequence)}")

        # Format for TTS
        segments = generator.format_for_tts(script, voice_sequence)

        print(f"\nTTS Segments: {len(segments)}")
        for i, segment in enumerate(segments, 1):
            voice_name = VOICE_CATALOG.get(segment["voice"], VOICE_CATALOG["old_radio"]).display_name
            text_preview = segment["text"][:50] + "..." if len(segment["text"]) > 50 else segment["text"]
            print(f"  {i}. [{voice_name}] {text_preview}")


def test_detection_logic():
    """Test broadcast detection logic."""

    print("\n" + "=" * 80)
    print("Broadcast Detection Logic Test")
    print("=" * 80)

    test_reviews = [
        ("This is a normal review with minor issues.", False),
        ("CRITICAL: Security vulnerability detected!", True),
        ("The code looks good, well structured.", False),
        ("Emergency: Build pipeline completely broken!", True),
        ("Perfect implementation with 100% coverage!", True),
        ("Some improvements needed in error handling.", False),
    ]

    generator = BroadcastReportGenerator()

    for review, expected in test_reviews:
        should_broadcast = generator.should_use_broadcast(review, {})
        status = "✓" if (should_broadcast == expected) else "✗"
        broadcast_text = "BROADCAST" if should_broadcast else "NORMAL"
        print(f"{status} [{broadcast_text}] {review[:50]}...")


def main():
    """Run all tests."""
    test_broadcast_scenarios()
    test_detection_logic()

    print("\n" + "=" * 80)
    print("Broadcast Report Test Complete!")
    print("\nNote: Old Radio voice will be used for dramatic broadcast segments")
    print("while agents use their default voices for initial assessments.")


if __name__ == "__main__":
    main()
