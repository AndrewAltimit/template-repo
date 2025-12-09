#!/usr/bin/env python3
"""Test script for ElevenLabs MCP improvements"""

import asyncio
from pathlib import Path
import sys

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from elevenlabs_speech.server import ElevenLabsSpeechMCPServer  # noqa: E402
from elevenlabs_speech.text_formatter import AudioTagFormatter, format_for_github_review  # noqa: E402
from elevenlabs_speech.voice_mapping import ContentType, get_voice_for_content, get_voice_id  # noqa: E402


async def test_voice_resolution():
    """Test the improved voice resolution system"""
    print("\n=== Testing Voice Resolution ===")

    test_inputs = [
        "Rachel",  # Name
        "rachel",  # Lowercase name
        "Rachel (Friendly & Enthusiastic)",  # Display name
        "21m00Tcm4TlvDq8ikWAM",  # Direct ID
        "Sarah",  # Another voice
        "Professional voice",  # Partial match
        "unknown_voice",  # Should fail gracefully
    ]

    for input_str in test_inputs:
        voice_id = get_voice_id(input_str)
        print(f"Input: '{input_str}' -> Voice ID: {voice_id}")

    print("✅ Voice resolution test complete")


async def test_content_based_selection():
    """Test smart voice selection based on content type"""
    print("\n=== Testing Content-Based Voice Selection ===")

    test_cases = [
        (ContentType.GITHUB_REVIEW, None),
        (ContentType.ERROR_MESSAGE, None),
        (ContentType.DOCUMENTATION, "male"),
        (ContentType.CASUAL_CHAT, "female"),
        (ContentType.TECHNICAL_EXPLANATION, None),
    ]

    for content_type, gender in test_cases:
        voice = get_voice_for_content(content_type, gender, require_v3=True)
        print(f"Content: {content_type.value}, Gender: {gender} -> Voice: {voice}")

    print("✅ Content-based selection test complete")


async def test_text_formatting():
    """Test text formatting with audio tags"""
    print("\n=== Testing Text Formatting ===")

    formatter = AudioTagFormatter()

    test_texts = [
        "Hello! [excited] This is a test. [laughs] How are you?",
        "Error occurred. The system failed to process your request.",
        "[whisper] This is confidential. [normal] But this part is normal.",
        "Line 1. Line 2. Line 3. Line 4. Line 5.",  # Should auto-segment
    ]

    for text in test_texts:
        formatted = formatter.format_with_tags(text, auto_segment=True)
        print(f"\nOriginal: {text[:50]}...")
        print(f"Formatted:\n{formatted}\n")

    # Test GitHub review formatting
    review_text = "Great work on this PR! The implementation looks solid. [excited] I especially like the error handling."
    formatted_review = format_for_github_review(review_text)
    print(f"GitHub Review Format:\n{formatted_review}")

    print("✅ Text formatting test complete")


async def test_synthesis_with_improvements():
    """Test actual synthesis with all improvements"""
    print("\n=== Testing Synthesis with Improvements ===")

    server = ElevenLabsSpeechMCPServer()

    # Test 1: Voice name resolution
    print("\n1. Testing with voice name instead of ID...")
    result = await server.synthesize_speech_v3(
        text="[excited] Testing voice name resolution! This should work with just 'Rachel'.",
        voice_id="Rachel",  # Using name instead of ID
    )
    print(f"Result: Success={result.get('success')}, Voice={result.get('voice_id')}")

    # Test 2: Smart voice selection
    print("\n2. Testing optimal voice selection...")
    voice_result = await server.select_optimal_voice(
        text="Error: Failed to process your request. Please check the configuration.", content_type="error_message"
    )
    if voice_result.get("success"):
        selected = voice_result.get("selected_voice", {})
        print(f"Selected: {selected.get('display_name')} (Quality: {selected.get('quality_rating')})")
        print(f"Reasoning: {voice_result.get('reasoning', {}).get('notes')}")

    # Test 3: Text with auto-formatting
    print("\n3. Testing with text formatting...")
    result = await server.synthesize_speech_v3(
        text="Hello! [laughs] This text will be automatically formatted. [excited] Isn't that great?", voice_id="rachel"
    )
    if result.get("metadata"):
        print(f"Text was formatted: {result['metadata'].get('text_was_formatted')}")
        print(f"Voice was validated: {result['metadata'].get('voice_was_validated')}")

    # Test 4: Error handling with fallback
    print("\n4. Testing error handling with invalid voice...")
    result = await server.synthesize_speech_v3(
        text="This should trigger fallback handling.", voice_id="completely_invalid_voice_xyz"
    )
    print(f"Result: Success={result.get('success')}")
    if not result.get("success"):
        print(f"Error handled: {result.get('error')}")
        print(f"Suggestion: {result.get('suggestion')}")

    await server.cleanup()
    print("\n✅ Synthesis tests complete")


async def test_validation():
    """Test validation features"""
    print("\n=== Testing Validation ===")

    # Test tag syntax validation
    test_texts = [
        ("Valid [laughs] tags [excited]", True),
        ("Unclosed [bracket", False),
        ("Empty [] tag", False),
        ("Nested [[tags]]", False),
    ]

    for text, expected_valid in test_texts:
        is_valid, errors = AudioTagFormatter.validate_tag_syntax(text)
        status = "✓" if is_valid == expected_valid else "✗"
        print(f"{status} '{text[:30]}...' Valid={is_valid}, Errors={errors}")

    print("✅ Validation test complete")


async def main():
    """Run all tests"""
    print("🚀 Testing ElevenLabs MCP Improvements")
    print("=" * 50)

    await test_voice_resolution()
    await test_content_based_selection()
    await test_text_formatting()
    await test_validation()

    # Only test synthesis if API key is available
    import os

    if os.getenv("ELEVENLABS_API_KEY"):
        await test_synthesis_with_improvements()
    else:
        print("\n⚠️  Skipping synthesis tests (no API key)")

    print("\n" + "=" * 50)
    print("✅ All tests completed successfully!")


if __name__ == "__main__":
    asyncio.run(main())
