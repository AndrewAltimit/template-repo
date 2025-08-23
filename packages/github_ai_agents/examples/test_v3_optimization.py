#!/usr/bin/env python3
"""Test Eleven v3 optimization features."""

import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from github_ai_agents.tts.v3_optimization import V3OptimizationEngine, V3ReviewFormatter
from github_ai_agents.tts.voice_catalog import VOICE_CATALOG


def test_text_optimization():
    """Test various v3 text optimizations."""
    
    print("Eleven v3 Text Optimization Test")
    print("=" * 80)
    
    # Test short text expansion
    print("\n1. SHORT TEXT EXPANSION (min 250 chars)")
    print("-" * 40)
    short_text = "The code looks good."
    optimized = V3OptimizationEngine.optimize_text_length(short_text)
    print(f"Original ({len(short_text)} chars): {short_text}")
    print(f"Optimized ({len(optimized)} chars): {optimized[:100]}...")
    
    # Test punctuation enhancement
    print("\n2. PUNCTUATION ENHANCEMENT")
    print("-" * 40)
    text = "This is critical. However the tests must pass. This is not optional."
    enhanced = V3OptimizationEngine.enhance_punctuation(text)
    print(f"Original: {text}")
    print(f"Enhanced: {enhanced}")
    
    # Test emotional structuring
    print("\n3. EMOTIONAL STRUCTURING")
    print("-" * 40)
    text = "Great implementation! The code is clean. Tests are comprehensive. Performance is excellent."
    emotions = ["excited", "impressed", "analytical", "happy"]
    structured = V3OptimizationEngine.structure_for_emotion(text, emotions)
    print(f"Original: {text}")
    print(f"Structured:\n{structured}")
    
    # Test tag compatibility
    print("\n4. TAG COMPATIBILITY VALIDATION")
    print("-" * 40)
    voices_to_test = [
        ("old_radio", "[giggles] This is funny [whispers] but serious"),
        ("tia", "[whispers] Secret message [cute] and adorable"),
        ("hope_conversational", "[laughs] This is great [excited] Really amazing!"),
    ]
    
    for voice_key, text in voices_to_test:
        adjusted, warnings = V3OptimizationEngine.validate_tag_compatibility(text, voice_key)
        print(f"\nVoice: {voice_key}")
        print(f"Original: {text}")
        if warnings:
            print(f"Warnings: {', '.join(warnings)}")
        if adjusted != text:
            print(f"Adjusted: {adjusted}")


def test_review_formatting():
    """Test complete review formatting for v3."""
    
    print("\n\nCOMPLETE REVIEW FORMATTING")
    print("=" * 80)
    
    reviews = [
        {
            "agent": "gemini",
            "severity": "critical",
            "text": "Critical security issue found! SQL injection vulnerability in auth module.",
        },
        {
            "agent": "claude",
            "severity": "positive",
            "text": "Excellent work! The implementation is clean and well-tested.",
        },
        {
            "agent": "opencode",
            "severity": "normal",
            "text": "The code structure is good. Consider adding error handling for edge cases.",
        },
    ]
    
    for review in reviews:
        print(f"\n{review['agent'].upper()} - {review['severity'].upper()}")
        print("-" * 60)
        formatted = V3ReviewFormatter.format_review(
            review["text"],
            review["agent"],
            review["severity"]
        )
        print(f"Formatted:\n{formatted[:300]}...")


def test_optimal_settings():
    """Test optimal settings generation."""
    
    print("\n\nOPTIMAL V3 SETTINGS")
    print("=" * 80)
    
    test_cases = [
        ("blondie", "review"),
        ("old_radio", "broadcast"),
        ("peter", "documentation"),
        ("hope_conversational", "review"),
    ]
    
    for voice_key, content_type in test_cases:
        settings = V3OptimizationEngine.get_optimal_settings(voice_key, content_type)
        voice_name = VOICE_CATALOG.get(voice_key, {}).display_name if voice_key in VOICE_CATALOG else voice_key
        
        print(f"\n{voice_name} for {content_type}:")
        print(f"  Stability: {settings['stability']:.1f} ", end="")
        if settings['stability'] <= 0.3:
            print("(Creative - max expression)")
        elif settings['stability'] <= 0.6:
            print("(Natural - balanced)")
        else:
            print("(Robust - consistent)")
        print(f"  Style: {settings['style']:.1f}")
        print(f"  Speaker Boost: {settings['use_speaker_boost']}")


def test_natural_imperfections():
    """Test adding natural speech imperfections."""
    
    print("\n\nNATURAL SPEECH IMPERFECTIONS")
    print("=" * 80)
    
    text = "I think this is interesting. Well the implementation is solid."
    
    for voice in ["hope_conversational", "blondie", "peter"]:
        result = V3OptimizationEngine.add_natural_imperfections(text, voice)
        print(f"\n{voice}:")
        print(f"  {result}")


def test_multi_speaker_dialogue():
    """Test multi-speaker dialogue formatting."""
    
    print("\n\nMULTI-SPEAKER DIALOGUE")
    print("=" * 80)
    
    exchanges = [
        ("1", "excited", "Have you seen the new v3 features?"),
        ("2", "curious", "Just testing them now! The emotional tags are amazing."),
        ("1", "impressed", "I know! Listen to this—I can whisper now!"),
        ("2", "laughing", "That's incredible! Much better than our old robotic voices."),
    ]
    
    dialogue = V3OptimizationEngine.create_multi_speaker_dialogue(exchanges)
    print(dialogue)


def main():
    """Run all tests."""
    test_text_optimization()
    test_review_formatting()
    test_optimal_settings()
    test_natural_imperfections()
    test_multi_speaker_dialogue()
    
    print("\n" + "=" * 80)
    print("V3 Optimization Test Complete!")
    print("\nKey Insights from Documentation:")
    print("• Minimum 250 characters for stability")
    print("• Voice selection is critical - must match desired delivery")
    print("• Stability slider: Creative (0-0.3), Natural (0.3-0.6), Robust (0.6-1.0)")
    print("• Punctuation matters: ellipses for pauses, CAPS for emphasis")
    print("• Tag compatibility varies by voice personality")


if __name__ == "__main__":
    main()