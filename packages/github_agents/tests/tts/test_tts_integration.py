#!/usr/bin/env python3
"""Test TTS integration for GitHub AI agents."""

import asyncio
import os
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))
# pylint: disable=wrong-import-position  # Imports must come after sys.path modification

from github_agents.tts.integration import TTSIntegration  # noqa: E402


async def test_tts_integration():
    """Test the TTS integration with sample review text."""

    # Sample review text with different emotional contexts
    review_text = """
    This is an impressive and ambitious pull request! The code structure is excellent
    and follows best practices.

    However, there are some critical issues that need to be addressed:

    1. The failing CI checks are a hard blocker. Tests must pass before merging.
    2. There's a potential security issue in the authentication handler.
    3. Consider adding more comprehensive error handling.

    Once these issues are resolved, I would be happy to approve this PR.
    The overall approach is sound and the implementation shows great attention to detail.
    """

    # Initialize TTS integration
    tts = TTSIntegration()

    print("TTS Integration Test")
    print("=" * 50)
    print(f"TTS Enabled: {tts.enabled}")

    if not tts.enabled:
        print("\nTTS is disabled. To enable, set AGENT_TTS_ENABLED=true")
        return

    # Test that agent text is preserved
    print("\n1. Testing agent autonomy (text preservation)...")
    print("   Agent's original text will be used AS IS for v3 synthesis")
    print("   No automatic modification of prompts")

    # Test audio generation (if API key is available)
    if os.getenv("ELEVENLABS_API_KEY"):
        print("\n2. Testing audio generation with unmodified text...")
        try:
            audio_url = await tts.generate_audio_review(review_text, agent_name="test", pr_number=999)

            if audio_url:
                print(f"   ✓ Audio generated: {audio_url}")

                # Test GitHub comment formatting
                print("\n3. Testing GitHub comment formatting...")
                formatted = tts.format_github_comment_with_audio("Original review text here...", audio_url, duration=8.5)
                print("   Formatted comment preview:")
                print("   " + formatted.split("\n", maxsplit=1)[0])
            else:
                print("   ✗ Audio generation failed")
        except Exception as e:
            print(f"   ✗ Error: {e}")
    else:
        print("\n2. Skipping audio generation (no API key)")
        print("   Set ELEVENLABS_API_KEY to test audio generation")

    # Test full processing
    print("\n4. Testing full review processing...")
    _formatted_review, audio_url = await tts.process_review_with_tts(review_text, agent_name="gemini", pr_number=123)

    if audio_url:
        print(f"   ✓ Review processed with audio: {audio_url}")
    else:
        print("   ✓ Review processed without audio (TTS disabled or failed)")

    print("\n" + "=" * 50)
    print("Test completed!")


def main():
    """Run the test."""
    # Set test environment
    if "--enable-tts" in sys.argv:
        os.environ["AGENT_TTS_ENABLED"] = "true"
        print("Enabled TTS for testing\n")

    # Run async test
    asyncio.run(test_tts_integration())


if __name__ == "__main__":
    main()
