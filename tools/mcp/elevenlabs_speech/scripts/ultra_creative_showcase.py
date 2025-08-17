#!/usr/bin/env python3
"""Ultra-creative showcase using advanced audio tags and multiple voices"""

import asyncio
import os
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
from elevenlabs_speech.voice_registry import VOICE_IDS  # noqa: E402

# Use the comprehensive voice registry
VOICES = VOICE_IDS


async def podcast_intro():
    """Create a dynamic podcast intro with multiple hosts"""
    print("\n🎙️ PODCAST INTRO - Multiple Hosts with Background")
    print("=" * 60)

    server = ElevenLabsSpeechMCPServer()
    if not server.client:
        return

    # Host 1: Rachel (casual American)
    host1_text = """
    [podcast music] [EXCITED] [ENERGETIC]
    Hey hey hey! Welcome back to Tech Talk Daily!
    [LAUGHS] I'm Rachel and [PAUSES]
    [WHISPERING] we've got something special today!
    """

    print("Host 1 (Rachel)...")
    result1 = await server.synthesize_speech_v3(
        text=host1_text.strip(),
        voice_id=VOICES["Rachel"],
        voice_settings={"stability": 0.3, "similarity_boost": 0.7, "style": 0.9},
    )
    if result1.get("success"):
        print(f"✅ Rachel: {result1.get('audio_url')}")

    # Host 2: Charlie (hyped Australian)
    host2_text = """
    [HYPED] [SHOUTING] And I'm Charlie!
    [RUSHED] Today we're diving deep into AI voice synthesis!
    [LAUGHS] [EXCITED] It's absolutely mental what you can do now!
    [australian slang] Fair dinkum, this tech is bonkers!
    """

    print("Host 2 (Charlie)...")
    result2 = await server.synthesize_speech_v3(
        text=host2_text.strip(),
        voice_id=VOICES["Charlie"],
        voice_settings={"stability": 0.2, "similarity_boost": 0.6, "style": 1.0},
    )
    if result2.get("success"):
        print(f"✅ Charlie: {result2.get('audio_url')}")


async def dramatic_movie_trailer():
    """Create an epic movie trailer narration"""
    print("\n🎬 MOVIE TRAILER - Epic Voice with Sound Effects")
    print("=" * 60)

    server = ElevenLabsSpeechMCPServer()
    if not server.client:
        return

    # Using Clyde (intense voice) for movie trailer
    trailer_text = """
    [thunder rumbling] [DEEP VOICE] [OMINOUS]
    In a world... [PAUSES] [dramatic pause]
    [WHISPERING] where nothing is as it seems...

    [explosion] [SHOUTING] ONE MAN!
    [DETERMINED] Will rise against all odds!

    [orchestral swell] [BUILDING INTENSITY]
    This summer... [PAUSES]
    [GRAVELLY] Prepare yourself...
    [WHISPERING] for the ultimate...
    [SHOUTING] [EXPLOSIVE] SHOWDOWN!

    [dramatic drums] [INTENSE]
    COMING [PAUSES] SOON
    [echo effect] [FADING] soon... soon... soon...
    """

    print("Generating epic trailer...")
    result = await server.synthesize_speech_v3(
        text=trailer_text.strip(),
        voice_id=VOICES["Clyde"],
        voice_settings={"stability": 0.4, "similarity_boost": 0.8, "style": 1.0},  # Maximum drama
    )
    if result.get("success"):
        print(f"✅ Epic Trailer: {result.get('audio_url')}")


async def asmr_relaxation():
    """Create an ASMR relaxation audio"""
    print("\n😴 ASMR RELAXATION - Whispers and Soft Sounds")
    print("=" * 60)

    server = ElevenLabsSpeechMCPServer()
    if not server.client:
        return

    # Using Charlotte (relaxed Swedish accent) for ASMR
    asmr_text = """
    [WHISPERING] [VERY SOFT] [gentle rain sounds]
    Hello there... [PAUSES] [breathing softly]
    Let's take a moment... [SLOWLY] to relax...

    [WHISPERING] [mouth sounds]
    Close your eyes... [PAUSES]
    [EVEN SOFTER] Feel the tension...
    [breathing] melting away...

    [tapping sounds] [RHYTHMIC]
    tap... tap... tap... [PAUSES]
    [WHISPERING] So peaceful... so calm...

    [fabric rustling] [BARELY AUDIBLE]
    Everything is... [YAWNING] so... relaxing...
    [SLEEPY] [FADING] Good night...
    """

    print("Creating ASMR audio...")
    result = await server.synthesize_speech_v3(
        text=asmr_text.strip(),
        voice_id=VOICES["Charlotte"],
        voice_settings={"stability": 0.8, "similarity_boost": 0.9, "style": 0.3},  # Stable for ASMR  # Subtle style
    )
    if result.get("success"):
        print(f"✅ ASMR Audio: {result.get('audio_url')}")


async def comedy_sketch():
    """Create a comedy sketch with multiple characters"""
    print("\n😂 COMEDY SKETCH - Multiple Characters")
    print("=" * 60)

    server = ElevenLabsSpeechMCPServer()
    if not server.client:
        return

    characters = [
        {
            "name": "Customer (Laura - sassy)",
            "voice": VOICES["Laura"],
            "text": """
            [SARCASTIC] Oh great, another coffee shop.
            [ANNOYED] Let me guess... [PAUSES]
            You have [AIR QUOTES] artisanal beans?
            [LAUGHS] [MOCKING] How original!
            """,
        },
        {
            "name": "Barista (Harry - rough)",
            "voice": VOICES["Harry"],
            "text": """
            [DEFENSIVE] [GRUFF] Hey! Our beans are special!
            [PROUD] They're... [STAMMERS] uh...
            [CONFUSED] wait, what makes them special again?
            [NERVOUS LAUGH] [WHISPERING] I just work here...
            """,
        },
        {
            "name": "Manager (Roger - classy)",
            "voice": VOICES["Roger"],
            "text": """
            [SOPHISTICATED] [CLEARING THROAT] Ahem!
            [PRETENTIOUS] Our beans are hand-picked by monks...
            [DRAMATIC] who have taken a vow of silence!
            [WHISPERING] [CONSPIRATORIAL] And caffeine addiction.
            [LAUGHS] [POSH LAUGH] Quite amusing, really!
            """,
        },
    ]

    for char in characters:
        print(f"\n{char['name']}...")
        result = await server.synthesize_speech_v3(
            text=char["text"].strip(),
            voice_id=char["voice"],
            voice_settings={"stability": 0.3, "similarity_boost": 0.6, "style": 0.9},
        )
        if result.get("success"):
            print(f"✅ {char['name']}: {result.get('audio_url')}")


async def sports_commentary():
    """Create dynamic sports commentary"""
    print("\n⚽ SPORTS COMMENTARY - High Energy")
    print("=" * 60)

    server = ElevenLabsSpeechMCPServer()
    if not server.client:
        return

    commentary_text = """
    [CROWD ROARING] [EXCITED] [FAST-PACED]
    AND HERE COMES JOHNSON! [BUILDING EXCITEMENT]
    He's past one! [LOUDER] Past two!
    [SHOUTING] HE'S GOING FOR IT!

    [GASPS] [TENSE] Oh my goodness!
    [PAUSES] [WHISPERING] The crowd holds its breath...

    [EXPLOSIVE] [SCREAMING] GOOOOOOOOOOOAL!
    [ECSTATIC] WHAT A STRIKE!
    [CROWD GOING WILD] [RAPID] ABSOLUTELY INCREDIBLE!

    [CATCHING BREATH] [AMAZED]
    I've never seen anything like it!
    [REVERENT] That was... [PAUSES] pure magic!
    """

    print("Generating sports commentary...")
    result = await server.synthesize_speech_v3(
        text=commentary_text.strip(),
        voice_id=VOICES["Clyde"],  # Intense voice for sports
        voice_settings={"stability": 0.2, "similarity_boost": 0.5, "style": 1.0},  # Very dynamic  # Maximum energy
    )
    if result.get("success"):
        print(f"✅ Sports Commentary: {result.get('audio_url')}")


async def musical_experiments():
    """Test musical and melodic speech patterns"""
    print("\n🎵 MUSICAL EXPERIMENTS - Testing Melodic Tags")
    print("=" * 60)

    server = ElevenLabsSpeechMCPServer()
    if not server.client:
        return

    experiments = [
        {
            "name": "Smash Mouth Style",
            "text": "[Smashmouth - Allstar] Hey now, you're an all star, get your game on, go play!",
        },
        {"name": "Queen Style", "text": "[Queen - Bohemian Rhapsody] Is this the real life? Is this just fantasy?"},
        {
            "name": "Beatles Style",
            "text": "[Beatles - Hey Jude] Hey Jude, don't be afraid, take a sad song and make it better",
        },
        {"name": "Broadway Musical", "text": "[Broadway musical] [THEATRICAL] The hills are alive with the sound of music!"},
        {"name": "Opera", "text": "[OPERATIC] [DRAMATIC VIBRATO] La la la laaaaaa! Figaro! Figaro!"},
        {"name": "Rap Flow", "text": "[RAP RHYTHM] [RHYTHMIC] Yo yo yo, check it, one two, mic check, flow so sick!"},
        {"name": "Gospel Choir", "text": "[GOSPEL] [SOULFUL] Hallelujah! [HARMONIZING] Oh glory, glory!"},
        {"name": "Jazz Scat", "text": "[JAZZ SCAT] [IMPROVISING] Ski-ba-bop-ba-dop-bop! Yeah! Shoo-be-doo-wah!"},
    ]

    for exp in experiments:
        print(f"\n{exp['name']}...")
        result = await server.synthesize_speech_v3(
            text=exp["text"],
            voice_id=VOICES["Sarah"],  # Professional voice for clarity
            voice_settings={"stability": 0.4, "similarity_boost": 0.5, "style": 1.0},  # Maximum style for musical effect
        )
        if result.get("success"):
            print(f"✅ {exp['name']}: {result.get('audio_url')}")


async def emotional_journey():
    """Create an emotional journey through one narrative"""
    print("\n💔 EMOTIONAL JOURNEY - Progressive Emotions")
    print("=" * 60)

    server = ElevenLabsSpeechMCPServer()
    if not server.client:
        return

    journey_text = """
    [HAPPY] [CHEERFUL] Life was perfect! Everything was going great!
    [OPTIMISTIC] I had everything I ever wanted!

    [CONFUSED] [UNCERTAIN] But then... something changed...
    [WORRIED] I started noticing... [PAUSES] little things...

    [NERVOUS] [STAMMERING] M-maybe I was wrong?
    [ANXIOUS] What if... [GULPS] what if it was all a lie?

    [ANGRY] [FRUSTRATED] No! [SHOUTING] How could they do this to me?!
    [FURIOUS] [SEETHING] Years of my life... WASTED!

    [SAD] [CRYING] I just... [SOBBING] I can't believe it's over...
    [HEARTBROKEN] [WHISPERING] Everything we had... gone...

    [RESIGNED] [SIGH] But you know what? [PAUSES]
    [DETERMINED] I'm stronger now. [CONFIDENT] I survived.

    [HOPEFUL] [GENTLE] And maybe... [PAUSES]
    [PEACEFUL] [WISE] This was meant to happen.
    [GRATEFUL] [WARM] I'm finally free.
    """

    print("Creating emotional journey...")
    result = await server.synthesize_speech_v3(
        text=journey_text.strip(),
        voice_id=VOICES["Aria"],  # Husky voice for emotional depth
        voice_settings={
            "stability": 0.3,  # Allow emotional variation
            "similarity_boost": 0.7,
            "style": 0.8,  # Strong emotional expression
        },
    )
    if result.get("success"):
        print(f"✅ Emotional Journey: {result.get('audio_url')}")


async def creative_sound_effects():
    """Generate creative sound effects descriptions"""
    print("\n🔊 CREATIVE SOUND EFFECTS")
    print("=" * 60)

    server = ElevenLabsSpeechMCPServer()
    if not server.client:
        return

    # Generate actual sound effects
    effects = [
        "Futuristic laser gun firing three rapid shots with echo",
        "Medieval sword being unsheathed with metallic ring",
        "Magical spell casting with sparkles and whoosh",
        "Robot walking with mechanical servo sounds",
        "Dragon roaring with fire breathing",
        "Time machine powering up with electrical hum",
        "Alien spaceship landing with hydraulic hiss",
    ]

    for effect in effects:
        print(f"\nGenerating: {effect[:40]}...")
        result = await server.generate_sound_effect(prompt=effect, duration_seconds=5.0)
        if result.get("success"):
            print(f"✅ Sound Effect: {result.get('audio_url')}")


async def main():
    """Run the ultra-creative showcase"""
    print("\n" + "=" * 80)
    print("🌟 ULTRA-CREATIVE ELEVENLABS SHOWCASE 🌟")
    print("=" * 80)
    print("\nUsing your actual voice library for maximum creativity!")
    print("Testing extensive audio tags, backgrounds, and effects...")

    # Run all showcases
    await podcast_intro()
    await dramatic_movie_trailer()
    await asmr_relaxation()
    await comedy_sketch()
    await sports_commentary()
    await musical_experiments()
    await emotional_journey()
    await creative_sound_effects()

    print("\n" + "=" * 80)
    print("🎉 ULTRA-CREATIVE SHOWCASE COMPLETE!")
    print("💡 Listen to the audio URLs above to hear the creative results")
    print("🎨 Experiment with your own tag combinations!")
    print("=" * 80)

    # Print some creative tips
    print("\n📚 CREATIVE TIPS:")
    print("  • Combine multiple tags: [WHISPERING] [NERVOUS] [STUTTERING]")
    print("  • Use environment tags: [rain sounds] [echo] [underwater]")
    print("  • Try musical references: [Beatles - Yesterday] [jazz style]")
    print("  • Mix emotions: Start [HAPPY] then transition to [SAD]")
    print("  • Add reactions: [GASP] [LAUGHS] [SIGH] [GULPS]")
    print("  • Play with volume: [WHISPERING] to [SHOUTING]")
    print("  • Use pauses effectively: [PAUSES] [DRAMATIC PAUSE]")
    print("  • Create atmosphere: [spooky ambiance] [crowd cheering]")


if __name__ == "__main__":
    asyncio.run(main())
