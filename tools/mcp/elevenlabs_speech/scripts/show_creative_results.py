#!/usr/bin/env python3
"""Show the creative audio results with their prompts"""

import json
from datetime import datetime
from pathlib import Path


def show_creative_results():
    """Display recent creative synthesis results"""
    outputs_dir = Path.cwd() / "outputs" / "elevenlabs_speech"
    date_dir = outputs_dir / datetime.now().strftime("%Y-%m-%d")

    if not date_dir.exists():
        print("No outputs for today")
        return

    # Get all JSON files
    json_files = sorted(date_dir.glob("*.json"), key=lambda f: f.stat().st_mtime)

    # Get last 20 files
    recent_files = json_files[-20:] if len(json_files) > 20 else json_files

    print("=" * 80)
    print("🎨 RECENT CREATIVE AUDIO GENERATIONS")
    print("=" * 80)

    creative_examples = []

    for json_file in recent_files:
        with open(json_file, "r") as f:
            metadata = json.load(f)

        original_text = metadata.get("original_text", "")
        processed_text = metadata.get("processed_text", "")

        # Look for creative tags
        creative_tags = []
        tag_keywords = [
            "EXCITED",
            "NERVOUS",
            "FRUSTRATED",
            "SHOUTING",
            "WHISPERING",
            "LAUGHS",
            "GASP",
            "SIGH",
            "PAUSES",
            "RUSHED",
            "STAMMERS",
            "office",
            "podcast",
            "gaming",
            "musical",
            "opera",
            "rap",
            "thunder",
            "explosion",
            "crowd",
            "rain",
            "echo",
            "Smashmouth",
            "Beatles",
            "Queen",
            "Broadway",
            "ASMR",
            "comedy",
            "sports",
            "dramatic",
        ]

        text_to_check = original_text or processed_text
        for keyword in tag_keywords:
            if keyword.lower() in text_to_check.lower():
                creative_tags.append(keyword)

        if creative_tags:
            # This is a creative example
            mp3_file = json_file.with_suffix(".mp3")
            if mp3_file.exists():
                size_mb = mp3_file.stat().st_size / (1024 * 1024)
                creative_examples.append(
                    {
                        "filename": mp3_file.name,
                        "size_mb": size_mb,
                        "tags": creative_tags[:5],  # First 5 tags
                        "preview": text_to_check[:100] + "..." if len(text_to_check) > 100 else text_to_check,
                    }
                )

    # Display creative examples
    print(f"\n📊 Found {len(creative_examples)} creative audio files")
    print(f"📁 Total files today: {len(json_files)}")
    print("\n" + "-" * 80)

    for i, example in enumerate(creative_examples[-10:], 1):  # Show last 10
        print(f"\n{i}. {example['filename']}")
        print(f"   Size: {example['size_mb']:.2f} MB")
        print(f"   Creative Tags: {', '.join(example['tags'])}")
        print(f"   Preview: {example['preview']}")

    print("\n" + "=" * 80)
    print("💡 CREATIVE TECHNIQUES USED:")
    print("  ✅ Multiple voice characters from your library")
    print("  ✅ Extensive emotion tags (EXCITED, NERVOUS, FRUSTRATED, etc.)")
    print("  ✅ Volume variations (WHISPERING to SHOUTING)")
    print("  ✅ Background sounds (office ambiance, rain, thunder, etc.)")
    print("  ✅ Musical references ([Smashmouth - Allstar], [Beatles], etc.)")
    print("  ✅ Reactions (GASP, SIGH, LAUGHS, GULPS)")
    print("  ✅ Pacing control (PAUSES, RUSHED, STAMMERS)")
    print("  ✅ Environmental effects (echo, underwater, crowd noise)")
    print("  ✅ Character voices (opera, rap, Broadway, ASMR)")
    print("=" * 80)


if __name__ == "__main__":
    show_creative_results()
