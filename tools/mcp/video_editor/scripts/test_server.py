#!/usr/bin/env python3
"""Test script for Video Editor MCP Server"""

import asyncio
import json
import os
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

from tools.mcp.core.client import MCPClient


async def test_video_editor():
    """Test the Video Editor MCP server"""

    print("=" * 60)
    print("Testing Video Editor MCP Server")
    print("=" * 60)

    # Connect to the server
    port = int(os.environ.get("PORT", 8019))

    try:
        async with MCPClient("video_editor", port=port) as client:
            print(f"✓ Connected to Video Editor MCP Server on port {port}")

            # Test 1: Server health check
            print("\n1. Testing server health...")
            health = await client.call("health", {})
            print(f"   Health status: {health}")

            # Test 2: Analyze video (with mock data)
            print("\n2. Testing video analysis...")

            # Create a mock video path for testing
            test_video = "/tmp/test_video.mp4"

            # Note: In a real test, you would have an actual video file
            # For now, we'll test error handling
            try:
                result = await client.call(
                    "video_editor/analyze",
                    {
                        "video_inputs": [test_video],
                        "analysis_options": {
                            "transcribe": True,
                            "identify_speakers": True,
                            "detect_scenes": False,
                            "extract_highlights": False,
                        },
                    },
                )

                if "error" in result:
                    print(f"   Expected error (no test video): {result['error']}")
                else:
                    print(f"   Analysis completed: {json.dumps(result, indent=2)[:200]}...")

            except Exception as e:
                print(f"   Error during analysis: {e}")

            # Test 3: Create edit decision list
            print("\n3. Testing EDL creation...")

            try:
                result = await client.call(
                    "video_editor/create_edit",
                    {
                        "video_inputs": ["/tmp/video1.mp4", "/tmp/video2.mp4"],
                        "editing_rules": {"switch_on_speaker": True, "speaker_switch_delay": 1.0, "remove_silence": True},
                    },
                )

                if "error" in result:
                    print(f"   Expected error (no test videos): {result['error']}")
                else:
                    print(f"   EDL created with {len(result.get('edit_decision_list', []))} decisions")

            except Exception as e:
                print(f"   Error during EDL creation: {e}")

            # Test 4: Extract clips
            print("\n4. Testing clip extraction...")

            try:
                result = await client.call(
                    "video_editor/extract_clips",
                    {
                        "video_input": test_video,
                        "extraction_criteria": {
                            "keywords": ["important", "summary"],
                            "min_clip_length": 5.0,
                            "max_clip_length": 30.0,
                        },
                    },
                )

                if "error" in result:
                    print(f"   Expected error (no test video): {result['error']}")
                else:
                    print(f"   Extracted {result.get('total_clips', 0)} clips")

            except Exception as e:
                print(f"   Error during clip extraction: {e}")

            # Test 5: Add captions
            print("\n5. Testing caption addition...")

            try:
                result = await client.call(
                    "video_editor/add_captions",
                    {
                        "video_input": test_video,
                        "caption_style": {"font": "Arial", "size": 48, "position": "bottom"},
                        "languages": ["en"],
                    },
                )

                if "error" in result:
                    print(f"   Expected error (no test video): {result['error']}")
                else:
                    print(f"   Captions added for {len(result.get('languages_processed', []))} languages")

            except Exception as e:
                print(f"   Error during caption addition: {e}")

            # Test 6: Job status
            print("\n6. Testing job status...")

            try:
                result = await client.call("video_editor/get_job_status", {"job_id": "test_job_123"})

                if "error" in result:
                    print(f"   Expected error (job not found): {result['error']}")
                else:
                    print(f"   Job status: {result}")

            except Exception as e:
                print(f"   Error getting job status: {e}")

            print("\n" + "=" * 60)
            print("✓ All tests completed")
            print("=" * 60)

    except ConnectionError as e:
        print(f"✗ Failed to connect to server: {e}")
        print("  Make sure the Video Editor MCP Server is running:")
        print("  docker-compose up mcp-video-editor")
        sys.exit(1)
    except Exception as e:
        print(f"✗ Unexpected error: {e}")
        sys.exit(1)


async def test_with_real_video():
    """Test with a real video file (if available)"""

    print("\n" + "=" * 60)
    print("Testing with Real Video (if available)")
    print("=" * 60)

    # Look for test videos in common locations
    test_videos = ["~/Videos/test.mp4", "/tmp/sample.mp4", "./test_data/video.mp4"]

    found_video = None
    for video_path in test_videos:
        expanded_path = os.path.expanduser(video_path)
        if os.path.exists(expanded_path):
            found_video = expanded_path
            break

    if not found_video:
        print("No test video found. Skipping real video tests.")
        print("To test with real video, place a video file at one of:")
        for path in test_videos:
            print(f"  - {path}")
        return

    print(f"Found test video: {found_video}")

    port = int(os.environ.get("PORT", 8019))

    async with MCPClient("video_editor", port=port) as client:
        # Analyze the real video
        print("\nAnalyzing video...")
        result = await client.call(
            "video_editor/analyze",
            {
                "video_inputs": [found_video],
                "analysis_options": {
                    "transcribe": True,
                    "identify_speakers": True,
                    "detect_scenes": True,
                    "extract_highlights": True,
                },
            },
        )

        if "error" not in result:
            analysis = result["analysis"][found_video]
            print(f"  Duration: {analysis.get('audio_analysis', {}).get('duration', 0):.2f} seconds")
            print(f"  Transcript: {analysis.get('transcript', {}).get('text', '')[:100]}...")
            print(f"  Speakers found: {len(analysis.get('speakers', []))}")
            print(f"  Scene changes: {len(analysis.get('scene_changes', []))}")
            print(f"  Highlights: {len(analysis.get('highlights', []))}")

        # Extract a clip
        print("\nExtracting highlight clips...")
        result = await client.call(
            "video_editor/extract_clips",
            {
                "video_input": found_video,
                "extraction_criteria": {
                    "time_ranges": [[0, 10]],  # First 10 seconds
                    "min_clip_length": 3.0,
                    "max_clip_length": 10.0,
                },
            },
        )

        if "error" not in result:
            print(f"  Extracted {result['total_clips']} clips")
            for clip in result["clips_extracted"]:
                print(f"    - {clip['output_path']} ({clip['duration']:.2f}s)")


def main():
    """Main entry point"""
    asyncio.run(test_video_editor())

    # Optionally test with real video
    if "--real" in sys.argv:
        asyncio.run(test_with_real_video())


if __name__ == "__main__":
    main()
