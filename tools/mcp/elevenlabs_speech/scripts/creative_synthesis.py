#!/usr/bin/env python3
"""Creative audio synthesis with extensive tag usage, backgrounds, and multiple voices"""

import asyncio
import os
import random
import sys
from pathlib import Path

# Add parent directory to path
parent_dir = Path(__file__).parent.parent.parent
sys.path.insert(0, str(parent_dir))

# Load .env file
env_file = Path.cwd() / ".env"
if env_file.exists():
    with open(env_file, "r") as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                key, value = line.split("=", 1)
                os.environ[key] = value.strip('"').strip("'")

from elevenlabs_speech.server import ElevenLabsSpeechMCPServer  # noqa: E402


async def fetch_and_display_voices():
    """Fetch available voices from ElevenLabs"""
    print("\n🎭 Fetching Your Voice Library...")
    print("=" * 60)

    server = ElevenLabsSpeechMCPServer()
    if not server.client:
        print("❌ No API key configured")
        return []

    result = await server.list_available_voices()

    if result.get("success"):
        voices = result.get("voices", [])
        print(f"Found {len(voices)} voices:\n")

        voice_list = []
        for voice in voices:
            voice_id = voice.get("voice_id")
            name = voice.get("name")
            category = voice.get("category", "custom")
            labels = voice.get("labels", {})

            voice_list.append({"id": voice_id, "name": name, "category": category})

            print(f"  🎤 {name}")
            print(f"     ID: {voice_id}")
            print(f"     Category: {category}")
            if labels:
                print(f"     Labels: {', '.join(f'{k}={v}' for k, v in labels.items())}")
            print()

        return voice_list
    else:
        print(f"❌ Failed to fetch voices: {result.get('error')}")
        return []


async def creative_example_1_office_chaos():
    """Office chaos scene with multiple emotions and background sounds"""
    print("\n🏢 Example 1: Office Chaos")
    print("-" * 40)

    server = ElevenLabsSpeechMCPServer()
    if not server.client:
        return

    text = """
    [office ambiance] [NERVOUS] Okay everyone, [GULPS] I have something to announce...
    [PAUSES]
    [WHISPERING] Is this about the coffee machine?
    [STAMMERS] N-no, it's... [FRUSTRATED] Look, someone ate my sandwich again!
    [SHOUTING] WHO ATE MY TURKEY CLUB?!
    [phones ringing] [RUSHED] I've got to take this call but [ANGRY] we're not done here!
    [SIGH] [TIRED] Why does this always happen on Mondays...
    [printer sounds] [QUIETLY] Maybe it was Steve from accounting...
    [GASP] [SHOCKED] Steve?! But he's vegetarian!
    [LAUGHS] [RELIEVED] Oh wait, I left it at home.
    [collective groaning] [EMBARRASSED] Sorry everyone...
    """

    result = await server.synthesize_speech_v3(
        text=text.strip(),
        voice_settings={
            "stability": 0.3,  # Lower for more expression
            "similarity_boost": 0.7,
            "style": 0.8,  # Higher for more dramatic delivery
        },
    )

    if result.get("success"):
        print(f"✅ Created: {result.get('audio_url', 'Processing...')}")
        print("   Tags used: office ambiance, emotions, reactions, volume changes")
    else:
        print(f"❌ Failed: {result.get('error')}")


async def creative_example_2_gaming_stream():
    """Gaming stream with dynamic reactions"""
    print("\n🎮 Example 2: Gaming Stream Commentary")
    print("-" * 40)

    server = ElevenLabsSpeechMCPServer()
    if not server.client:
        return

    text = """
    [keyboard clicking] [EXCITED] Alright chat, here we go! Final boss time!
    [CONCENTRATED] Just need to dodge this attack and...
    [GASP] [PANICKED] NO NO NO NO!
    [explosion sound] [DEFEATED] Are you kidding me?!
    [PAUSES]
    [DETERMINED] Okay, one more try. [CONFIDENT] I've got the pattern down now.
    [battle music] [RUSHED] Dodge, dodge, attack, dodge...
    [TRIUMPHANT] YES! [SHOUTING] WE DID IT CHAT!
    [LAUGHS] [RELIEVED] Never doubted myself for a second.
    [victory fanfare] [GRATEFUL] Thanks for watching everyone!
    [WHISPERING] Between you and me, that took like fifty tries...
    """

    result = await server.synthesize_speech_v3(
        text=text.strip(),
        voice_settings={"stability": 0.2, "similarity_boost": 0.6, "style": 0.9},  # Very dynamic  # Maximum expression
    )

    if result.get("success"):
        print(f"✅ Created: {result.get('audio_url', 'Processing...')}")
        print("   Dynamic gaming commentary with sound effects")


async def creative_example_3_musical_speech():
    """Testing musical/melodic speech patterns"""
    print("\n🎵 Example 3: Musical Speech Patterns")
    print("-" * 40)

    server = ElevenLabsSpeechMCPServer()
    if not server.client:
        return

    # Testing different musical cues
    examples = [
        "[singing] La la la, this is a test of singing tags!",
        "[operatic] Behold! The power of operatic delivery!",
        "[rap style] Yo, check it, one two, testing the mic flow",
        "[jazz vocals] Smooth and sultry, like a midnight blues",
        "[country twang] Well howdy there partner, welcome to the show",
        "[gregorian chant] Ancient words spoken in reverent tones",
        "[beatboxing] Boots and cats and boots and cats",
        "[harmonizing] Oooooh, can you hear the harmony?",
        "[Disney princess] Once upon a dream, I walked with you",
        "[death metal growl] EXTREME VOCAL TECHNIQUES!",
    ]

    for i, example in enumerate(examples, 1):
        print(f"\n  Attempt {i}: {example[:50]}...")

        result = await server.synthesize_speech_v3(
            text=example,
            voice_settings={"stability": 0.4, "similarity_boost": 0.5, "style": 1.0},  # Maximum style for musical expression
        )

        if result.get("success"):
            print(f"  ✅ {result.get('audio_url', 'Processing...')}")


async def creative_example_4_nature_documentary():
    """Nature documentary with atmospheric sounds"""
    print("\n🦁 Example 4: Nature Documentary")
    print("-" * 40)

    server = ElevenLabsSpeechMCPServer()
    if not server.client:
        return

    text = """
    [wind blowing] [WHISPERING] [David Attenborough style] Here, in the vast savanna...
    [birds chirping] [PAUSES] We observe something truly remarkable.
    [grass rustling] [INTRIGUED] The lion, [DRAMATIC PAUSE] king of beasts...
    [distant roar] [BUILDING TENSION] Prepares for the hunt.
    [heartbeat sound] [INTENSE WHISPER] Every muscle coiled...
    [SUDDEN] [thunder crack] The chase begins!
    [running sounds] [EXCITED] The gazelle leaps! [AMAZED] Such grace!
    [PAUSES]
    [water sounds] [CALM] [PHILOSOPHICAL] And so, the cycle continues...
    [sunset ambiance] [WISE] Nature's eternal dance of life.
    """

    result = await server.synthesize_speech_v3(
        text=text.strip(),
        voice_settings={"stability": 0.6, "similarity_boost": 0.8, "style": 0.7},  # Documentary style needs some stability
    )

    if result.get("success"):
        print(f"✅ Created: {result.get('audio_url', 'Processing...')}")
        print("   Atmospheric documentary with nature sounds")


async def creative_example_5_radio_drama():
    """Old-time radio drama with multiple characters"""
    print("\n📻 Example 5: Radio Drama Multi-Character")
    print("-" * 40)

    server = ElevenLabsSpeechMCPServer()
    if not server.client:
        return

    # Using different voice modulations to simulate characters
    text = """
    [old radio static] [1940s announcer voice] Tonight on Mystery Theater...
    [dramatic organ music] [OMINOUS] The Case of the Missing Diamond!

    [door creaking] [detective voice] [GRUFF] The name's Detective Murphy.
    [footsteps] [SUSPICIOUS] You say the diamond vanished at midnight?

    [female voice] [NERVOUS] [HIGH PITCHED] Y-yes detective!
    [STAMMERS] I was just... just standing there and...
    [GASP] [TERRIFIED] The lights went out!

    [butler voice] [BRITISH ACCENT] [FORMAL] If I may interject, sir...
    [MEASURED] I was in the pantry at precisely that moment.
    [DEFENSIVE] My alibi is quite solid, I assure you.

    [detective voice] [THOUGHTFUL] Interesting... very interesting...
    [DRAMATIC] But there's one thing you're forgetting!
    [thunder sound] [SHOUTING] The window was locked from the inside!

    [collective gasps] [SHOCKED VOICES] What?! Impossible!

    [radio static] [announcer voice] [MYSTERIOUS] Who is the real thief?
    [DRAMATIC] Tune in next week for the thrilling conclusion!
    [old radio music fade]
    """

    result = await server.synthesize_speech_v3(
        text=text.strip(),
        voice_settings={
            "stability": 0.35,  # Variable for different characters
            "similarity_boost": 0.5,
            "style": 0.85,  # High style for dramatic delivery
        },
    )

    if result.get("success"):
        print(f"✅ Created: {result.get('audio_url', 'Processing...')}")
        print("   Multi-character radio drama with sound effects")


async def creative_example_6_experimental_tags():
    """Testing experimental and creative tag combinations"""
    print("\n🧪 Example 6: Experimental Tag Combinations")
    print("-" * 40)

    server = ElevenLabsSpeechMCPServer()
    if not server.client:
        return

    experiments = [
        "[ROBOT VOICE] [GLITCHING] System malfunction detected beep boop",
        "[UNDERWATER] [BUBBLING] Blub blub, speaking from the depths",
        "[ECHO] [CAVE AMBIANCE] Hello... hello... hello...",
        "[SLOW MOTION] Eeeeeveryyyyythiiiiing iiiiis slooooowing dooooown",
        "[FAST FORWARD] Quickquickquick everything is speeding up!",
        "[REVERSE REVERB] Something strange is happening to my voice",
        "[ALIEN VOICE] [OTHERWORLDLY] Greetings earthlings from beyond",
        "[DRUNK] [SLURRING] I'm totally fine, I can totally talk normal",
        "[CHILD VOICE] [EXCITED] Wow! This is so cool! Can we do it again?",
        "[DEMON VOICE] [MENACING] Your soul belongs to me now mortal",
        "[ANGELIC] [ETHEREAL] Peace and light shine upon you",
        "[NEWS ANCHOR] [PROFESSIONAL] Breaking news just in from our correspondent",
        "[PIRATE] [ROUGH] Arrr matey, ye be walking the plank!",
        "[SHAKESPEARE] [DRAMATIC] To speak or not to speak, that is the question!",
        "[MORGAN FREEMAN] [WISE] Sometimes, life gives you moments of clarity",
    ]

    for exp in experiments:
        # Extract tag and preview
        tag_end = exp.rfind("]") + 1
        tags = exp[:tag_end]
        preview = exp[tag_end:].strip()[:30] + "..."

        print(f"\n  Testing: {tags}")
        print(f"  Text: {preview}")

        result = await server.synthesize_speech_v3(
            text=exp, voice_settings={"stability": 0.3, "similarity_boost": 0.5, "style": 1.0}  # Maximum style for experiments
        )

        if result.get("success"):
            print(f"  ✅ {result.get('audio_url', 'Processing...')}")


async def creative_dialogue_with_voices(voice_list):
    """Create dialogue using actual available voices"""
    print("\n🎭 Example 7: Multi-Voice Dialogue")
    print("-" * 40)

    server = ElevenLabsSpeechMCPServer()
    if not server.client or not voice_list:
        print("❌ No voices available")
        return

    # Pick random voices for characters
    voices = random.sample(voice_list, min(3, len(voice_list)))

    print(f"Using voices: {', '.join(v['name'] for v in voices)}")

    # Create dialogue for each voice
    for i, voice in enumerate(voices):
        character_text = [
            "[CONFIDENT] Hello everyone, I'm the first character speaking!",
            "[MYSTERIOUS] But are you really who you say you are?",
            "[LAUGHING] Oh please, you two are so dramatic!",
        ][i % 3]

        print(f"\n  {voice['name']}: {character_text[:50]}...")

        result = await server.synthesize_speech_v3(
            text=character_text, voice_id=voice["id"], voice_settings={"stability": 0.4, "similarity_boost": 0.7, "style": 0.7}
        )

        if result.get("success"):
            print(f"  ✅ {result.get('audio_url', 'Processing...')}")


async def main():
    """Run all creative examples"""
    print("=" * 80)
    print("🎨 ULTRA CREATIVE ELEVENLABS SYNTHESIS SHOWCASE")
    print("=" * 80)

    # First fetch available voices
    voice_list = await fetch_and_display_voices()

    # Run creative examples
    await creative_example_1_office_chaos()
    await creative_example_2_gaming_stream()
    await creative_example_3_musical_speech()
    await creative_example_4_nature_documentary()
    await creative_example_5_radio_drama()
    await creative_example_6_experimental_tags()

    # Use actual voices if available
    if voice_list:
        await creative_dialogue_with_voices(voice_list)

    print("\n" + "=" * 80)
    print("🎉 Creative showcase complete! Check the audio URLs above.")
    print("💡 Note: Some tags may work better with v3 models.")
    print("🎵 Try your own creative combinations!")
    print("=" * 80)


if __name__ == "__main__":
    asyncio.run(main())
