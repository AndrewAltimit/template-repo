#!/usr/bin/env python3
"""
Virtual Character Quick Start Script

This script helps you quickly test the virtual character system:
1. Validates your setup
2. Tests storage service
3. Generates sample audio
4. Plays it on the virtual character
"""

import asyncio
from pathlib import Path
import sys


def print_banner():
    """Print welcome banner."""
    print(
        """
    ╔════════════════════════════════════════════╗
    ║   VIRTUAL CHARACTER SYSTEM - QUICK START   ║
    ╚════════════════════════════════════════════╝
    """
    )


async def quick_test():
    """Run a quick test of the entire system."""
    print_banner()

    # Step 1: Import and configure
    print("📋 Step 1: Loading configuration...")
    try:
        from utils.env_loader import ensure_storage_config

        config = ensure_storage_config()
        print("  ✓ Configuration loaded")
        print(f"    Storage: {config.get('STORAGE_BASE_URL')}")
        print(f"    Character: {config.get('VIRTUAL_CHARACTER_SERVER')}")
    except Exception as e:
        print(f"  ✗ Configuration error: {e}")
        return False

    # Step 2: Check storage
    print("\n📦 Step 2: Checking storage service...")
    try:
        from storage_client import StorageClient

        client = StorageClient()
        if client.check_health():
            print("  ✓ Storage service is healthy")
        else:
            print("  ⚠ Storage service not responding")
            print("    Tip: Run the launcher to start storage service")
    except Exception as e:
        print(f"  ✗ Storage error: {e}")

    # Step 3: Test audio generation (optional)
    print("\n🎵 Step 3: Audio generation test...")
    test_audio = None

    # Check if we have a recent audio file
    audio_dir = Path("outputs/elevenlabs_speech")
    if audio_dir.exists():
        # Find most recent audio file
        audio_files = list(audio_dir.rglob("*.mp3"))
        if audio_files:
            audio_files.sort(key=lambda x: x.stat().st_mtime, reverse=True)
            test_audio = str(audio_files[0])
            print(f"  ✓ Found recent audio: {test_audio}")

    if not test_audio:
        print("  ℹ No recent audio found")
        print("    Generate audio with: mcp__elevenlabs-speech__synthesize_speech_v3")
        return False

    # Step 4: Play audio
    print("\n🔊 Step 4: Playing audio on virtual character...")
    try:
        from seamless_audio_v2 import SeamlessAudioPlayer

        player = SeamlessAudioPlayer()

        result = await player.play_audio(audio_input=test_audio, text="Testing virtual character audio playback")

        if result.get("success"):
            print("  ✓ Audio played successfully!")
            print("    Check VRChat to hear the audio")
        else:
            print(f"  ✗ Playback failed: {result.get('error')}")
    except Exception as e:
        print(f"  ✗ Playback error: {e}")
        return False

    print("\n" + "=" * 50)
    print("✅ Quick test complete!")
    return True


async def interactive_test():
    """Interactive testing mode."""
    print_banner()
    print("Interactive Mode - Choose an option:")
    print("1. Validate setup")
    print("2. Test storage upload")
    print("3. Play recent audio")
    print("4. Full system test")
    print("5. Exit")

    choice = input("\nSelect option (1-5): ").strip()

    if choice == "1":
        print("\n" + "=" * 50)
        from validate_setup import SetupValidator

        validator = SetupValidator()
        validator.run_all_checks()

    elif choice == "2":
        print("\nTesting storage upload...")
        try:
            from storage_client import StorageClient

            client = StorageClient()

            # Create test file
            test_file = Path("/tmp/test_storage.txt")
            test_file.write_text("Virtual Character Storage Test")

            url = client.upload_file(str(test_file))
            if url:
                print(f"✓ Upload successful: {url}")
            else:
                print("✗ Upload failed")
        except Exception as e:
            print(f"✗ Error: {e}")

    elif choice == "3":
        await quick_test()

    elif choice == "4":
        print("\nRunning full system test...")
        from validate_setup import SetupValidator

        validator = SetupValidator()
        validator.run_all_checks()
        print("\n" + "=" * 50)
        await quick_test()

    elif choice == "5":
        print("Goodbye!")
        return

    else:
        print("Invalid option")


def main():
    """Main entry point."""
    if len(sys.argv) > 1:
        if sys.argv[1] == "test":
            # Quick test mode
            asyncio.run(quick_test())
        elif sys.argv[1] == "validate":
            # Validation mode
            from validate_setup import SetupValidator

            validator = SetupValidator()
            validator.run_all_checks()
        elif sys.argv[1] == "interactive":
            # Interactive mode
            asyncio.run(interactive_test())
        else:
            print("Unknown command:", sys.argv[1])
            print("\nUsage:")
            print("  python quickstart.py test        # Run quick test")
            print("  python quickstart.py validate    # Validate setup")
            print("  python quickstart.py interactive # Interactive mode")
    else:
        # Default to interactive
        asyncio.run(interactive_test())


if __name__ == "__main__":
    # Ensure we're in the right directory
    script_dir = Path(__file__).parent
    sys.path.insert(0, str(script_dir))

    main()
