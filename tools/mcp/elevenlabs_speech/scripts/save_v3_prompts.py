#!/usr/bin/env python3
"""Save v3 creative prompts to JSON for manual testing in web UI"""

import json
import sys
from datetime import datetime
from pathlib import Path

# Add parent directory to path for imports
parent_dir = Path(__file__).parent.parent.parent
sys.path.insert(0, str(parent_dir))

from elevenlabs_speech.voice_registry import VOICE_IDS  # noqa: E402

# Use the comprehensive voice registry
VOICES = VOICE_IDS


def save_v3_examples():
    """Save the 3 solid v3 examples to JSON files"""

    # Create output directory
    output_dir = Path.cwd() / "outputs" / "elevenlabs_speech" / "v3_prompts"
    output_dir.mkdir(parents=True, exist_ok=True)

    examples = []

    # Example 1: Tech Podcast Drama (~25 seconds)
    example_1 = {
        "name": "Tech Podcast Drama",
        "voice_id": VOICES["Rachel"],
        "voice_name": "Rachel",
        "duration_estimate": "25 seconds",
        "model": "eleven_v3",
        "voice_settings": {"stability": 0.3, "similarity_boost": 0.7, "style": 0.9},
        "text": """[podcast intro music] [EXCITED] Welcome back to Tech Talk Daily,
where we dive deep into the latest innovations! [LAUGHS]

[CONFIDENT] Today's topic? Artificial Intelligence. [PAUSES]

[typing sounds] [CURIOUS] But wait... [NERVOUS]
I'm getting breaking news right now... [keyboard clicking faster]

[SHOCKED] [GASP] Oh my god! [WHISPERING] Are you seeing this?
[papers rustling] [STAMMERING] The... the AI just...

[BUILDING TENSION] [notification sound] It's responding to us!
[EXCITED] [SHOUTING] It knows we're talking about it!

[computer error sound] [PANICKED] Wait, wait, wait!
[FRUSTRATED] The system is crashing! [alarm beeping]

[RELIEVED] [SIGH] False alarm everyone... [LAUGHS NERVOUSLY]
[EMBARRASSED] It was just... my screensaver.

[PROFESSIONAL] [clearing throat] Let's... let's take a quick break.
[WHISPERING] [MORTIFIED] Kill the stream... please...
[podcast outro music fading]""",
        "tags_used": [
            "EXCITED",
            "CONFIDENT",
            "NERVOUS",
            "SHOCKED",
            "WHISPERING",
            "STAMMERING",
            "SHOUTING",
            "PANICKED",
            "FRUSTRATED",
            "RELIEVED",
            "EMBARRASSED",
            "PROFESSIONAL",
            "MORTIFIED",
            "GASP",
            "SIGH",
            "LAUGHS",
            "PAUSES",
            "podcast music",
            "typing sounds",
            "notification sound",
            "computer error",
            "alarm beeping",
            "clearing throat",
        ],
    }
    examples.append(example_1)

    # Example 2: Action Movie Scene (~25 seconds)
    example_2 = {
        "name": "Action Movie Scene",
        "voice_id": VOICES["Clyde"],
        "voice_name": "Clyde",
        "duration_estimate": "25 seconds",
        "model": "eleven_v3",
        "voice_settings": {"stability": 0.2, "similarity_boost": 0.6, "style": 1.0},
        "text": """[thunderstorm] [rain pouring] [WHISPERING] [TENSE]
They're here... [footsteps approaching] I can hear them.

[DETERMINED] [gun cocking] Not today. [PAUSES] Not ever.

[door creaking] [HOLDING BREATH] [heartbeat sound]
Three... two... [EXPLOSIVE] [SHOUTING] NOW!

[gunfire] [glass shattering] [AGGRESSIVE]
GET DOWN! EVERYONE GET DOWN! [explosion]

[RUSHED] [PANICKED] Move, move, MOVE!
[car engine starting] [tires screeching]

[BREATHING HEAVILY] [helicopter overhead]
[FRUSTRATED] They're still following us!
[DETERMINED] Hold on tight... [INTENSE]

[SHOUTING] [car chase sounds] INCOMING!
[crash sound] [GROANING] [PAINFUL] Ugh...

[WEAKLY] [radio static] Command... [COUGHING]
[WHISPERING] Mission... [PAUSES] accomplished...
[FADING] Tell my family... [EMOTIONAL] I tried...
[rain continuing] [somber music]""",
        "tags_used": [
            "WHISPERING",
            "TENSE",
            "DETERMINED",
            "EXPLOSIVE",
            "SHOUTING",
            "AGGRESSIVE",
            "RUSHED",
            "PANICKED",
            "FRUSTRATED",
            "INTENSE",
            "WEAKLY",
            "PAINFUL",
            "EMOTIONAL",
            "FADING",
            "BREATHING HEAVILY",
            "GROANING",
            "COUGHING",
            "PAUSES",
            "thunderstorm",
            "rain",
            "footsteps",
            "gun cocking",
            "door creaking",
            "heartbeat",
            "gunfire",
            "glass shattering",
            "explosion",
            "car engine",
            "tires screeching",
            "helicopter",
            "car chase",
            "crash",
            "radio static",
            "somber music",
        ],
    }
    examples.append(example_2)

    # Example 3: Fancy Restaurant Comedy (~30 seconds)
    example_3 = {
        "name": "Fancy Restaurant Comedy",
        "voice_id": VOICES["George"],
        "voice_name": "George",
        "duration_estimate": "30 seconds",
        "model": "eleven_v3",
        "voice_settings": {"stability": 0.35, "similarity_boost": 0.5, "style": 0.9},
        "text": """[fancy restaurant ambiance] [PRETENTIOUS] [SNOBBISH]
Good evening sir, welcome to Le Château Prétentieux.
[CONDESCENDING] I assume you have a reservation?

[NERVOUS] [STAMMERING] Uh... y-yes! Smith party of two?
[GULPS] [SWEATING] This place looks... expensive...

[HAUGHTY] [SCOFFING] Smith? [PAUSES] How... quaint.
[silverware clinking] Right this way... [DISGUSTED] sir.

[WHISPERING] [PANICKED] [to date] I can't afford this!
[FRANTIC] The appetizers cost more than my car!

[LOUD] [FAKE CONFIDENT] Ah yes! [LAUGHS NERVOUSLY]
Everything looks... [READING] "Délicieux"?
[BUTCHERING PRONUNCIATION] "Dee-lick-ee-us"?

[HORRIFIED] [French accent] Mon Dieu! [GASPS]
[OFFENDED] Did you just... [DRAMATIC]
Did you just pronounce it like THAT?!

[kitchen crashes] [CHAOS] [chef voice] [ANGRY]
WHO INSULTED MY CUISINE?! [pots banging]
[ITALIAN ACCENT] [SHOUTING] I QUIT! AGAIN!

[DEFEATED] [SIGH] Check please...
[WHISPERING] [EMBARRASSED] Do you take... coupons?
[SHOCKED] [waiter fainting] [body hitting floor]

[NARRATOR VOICE] [AMUSED] And that's why Steve
only dates at McDonald's now. [LAUGHS]
[record scratch] [sitcom ending music]""",
        "tags_used": [
            "PRETENTIOUS",
            "SNOBBISH",
            "CONDESCENDING",
            "NERVOUS",
            "STAMMERING",
            "HAUGHTY",
            "SCOFFING",
            "DISGUSTED",
            "WHISPERING",
            "PANICKED",
            "FRANTIC",
            "LOUD",
            "FAKE CONFIDENT",
            "HORRIFIED",
            "OFFENDED",
            "DRAMATIC",
            "ANGRY",
            "DEFEATED",
            "EMBARRASSED",
            "SHOCKED",
            "AMUSED",
            "GULPS",
            "GASPS",
            "SIGH",
            "LAUGHS",
            "PAUSES",
            "French accent",
            "Italian accent",
            "chef voice",
            "narrator voice",
            "restaurant ambiance",
            "silverware clinking",
            "kitchen crashes",
            "pots banging",
            "body hitting floor",
            "record scratch",
            "sitcom music",
        ],
    }
    examples.append(example_3)

    # Save individual JSON files
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    for i, example in enumerate(examples, 1):
        filename = f"v3_example_{i}_{timestamp}.json"
        filepath = output_dir / filename

        with open(filepath, "w") as f:
            json.dump(example, f, indent=2)

        print(f"✅ Saved: {filename}")
        print(f"   Name: {example['name']}")
        print(f"   Voice: {example['voice_name']} ({example['voice_id']})")
        print(f"   Duration: ~{example['duration_estimate']}")
        print(f"   Tags: {len(example['tags_used'])} unique tags")
        print()

    # Save combined file
    combined_file = output_dir / f"all_v3_examples_{timestamp}.json"
    with open(combined_file, "w") as f:
        json.dump(
            {
                "timestamp": datetime.now().isoformat(),
                "model": "eleven_v3",
                "note": "These prompts are designed for ElevenLabs v3 (alpha). API access coming Q3 2025.",
                "examples": examples,
            },
            f,
            indent=2,
        )

    print(f"📁 All examples saved to: {combined_file}")

    # Create a markdown file with instructions
    instructions_file = output_dir / f"testing_instructions_{timestamp}.md"
    with open(instructions_file, "w") as f:
        f.write(
            """# ElevenLabs v3 Creative Examples - Testing Instructions

## How to Test These Prompts

1. Go to [ElevenLabs Speech Synthesis](https://elevenlabs.io/speech-synthesis)
2. Select **Eleven v3 (alpha)** from the model dropdown
3. Choose the specified voice for each example
4. Copy the full text (including all tags in brackets)
5. Adjust voice settings as specified in the JSON
6. Generate and listen!

## Voice Settings Guide

- **Stability**: Lower = more expressive (0.2-0.4 for creative)
- **Similarity Boost**: How close to original voice (0.5-0.7 for variation)
- **Style**: Higher = more dramatic (0.9-1.0 for maximum expression)

## Expected Results

Each example should produce 20-30 seconds of highly expressive audio with:
- Multiple emotional shifts
- Background sounds and ambiance
- Character voice variations
- Realistic reactions and sound effects

## Note

These prompts use advanced v3 features that won't work properly with v2 models.
API access for v3 is expected Q3 2025.
"""
        )

    print(f"📝 Instructions saved to: {instructions_file}")

    return output_dir


if __name__ == "__main__":
    print("=" * 60)
    print("💾 SAVING V3 CREATIVE PROMPTS")
    print("=" * 60)
    print()

    output_dir = save_v3_examples()

    print()
    print("=" * 60)
    print("✅ V3 PROMPTS SAVED!")
    print()
    print("📋 TO TEST IN WEB UI:")
    print("1. Go to elevenlabs.io/speech-synthesis")
    print("2. Select 'Eleven v3 (alpha)' model")
    print("3. Copy prompts from the JSON files")
    print("4. Use specified voice and settings")
    print()
    print(f"📁 Files saved in: {output_dir}")
    print("=" * 60)
