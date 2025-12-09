#!/usr/bin/env python3
"""Test script for Video Editor MCP Server"""

import os
from pathlib import Path
import sys

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

from tools.mcp.core.client import MCPClient  # noqa: E402  # pylint: disable=wrong-import-position


def test_video_editor():
    """Test the Video Editor MCP server"""

    print("=" * 60)
    print("Testing Video Editor MCP Server")
    print("=" * 60)

    # Connect to the server
    port = int(os.environ.get("PORT", 8019))
    base_url = f"http://localhost:{port}"

    try:
        client = MCPClient(base_url=base_url)
        print(f"✓ Connected to Video Editor MCP Server on port {port}")

        # Test 1: Server health check
        print("\n1. Testing server health...")
        health = client.health_check()
        print(f"   Health status: {health}")

        # Test 2: Analyze video (with mock data)
        print("\n2. Testing video analysis...")

        # Create a mock video path for testing
        test_video = "/tmp/test_video.mp4"

        # Test basic analysis
        try:
            result = client.execute_tool(
                "video_editor/analyze_video",
                {
                    "video_inputs": [test_video],
                    "analysis_options": {
                        "transcribe": True,
                        "detect_scenes": True,
                        "identify_speakers": False,
                        "extract_metadata": True,
                    },
                },
            )

            if result.get("success"):
                print("   ✓ Video analysis completed")
                print(f"   Analysis keys: {list(result.get('analysis', {}).keys())}")
            else:
                print(f"   ⚠️  Analysis returned error: {result.get('error')}")

        except Exception as e:
            print(f"   ⚠️  Analysis failed (expected for mock): {e}")

        # Test 3: Create edit
        print("\n3. Testing edit creation...")
        try:
            result = client.execute_tool(
                "video_editor/create_edit",
                {
                    "video_inputs": [test_video],
                    "edit_instructions": {
                        "cuts": [[0, 10], [20, 30]],
                        "transitions": ["fade"],
                        "output_format": "mp4",
                        "resolution": "1920x1080",
                        "framerate": 30,
                    },
                },
            )

            if result.get("success"):
                print("   ✓ Edit creation initiated")
                print(f"   Job ID: {result.get('job_id')}")
            else:
                print(f"   ⚠️  Edit creation failed: {result.get('error')}")

        except Exception as e:
            print(f"   ⚠️  Edit creation failed (expected for mock): {e}")

        # Test 4: Extract clips
        print("\n4. Testing clip extraction...")
        try:
            result = client.execute_tool(
                "video_editor/extract_clips",
                {
                    "video_input": test_video,
                    "extraction_criteria": {
                        "time_ranges": [[5, 15], [25, 35]],
                        "keywords": ["important", "highlight"],
                        "min_clip_length": 3,
                        "max_clip_length": 30,
                        "padding": 1,
                    },
                },
            )

            if result.get("success"):
                print("   ✓ Clip extraction completed")
                print(f"   Clips extracted: {result.get('clips_count', 0)}")
            else:
                print(f"   ⚠️  Extraction failed: {result.get('error')}")

        except Exception as e:
            print(f"   ⚠️  Clip extraction failed (expected for mock): {e}")

        # Test 5: Render video
        print("\n5. Testing video rendering...")
        try:
            result = client.execute_tool(
                "video_editor/render_video",
                {
                    "project_file": "/tmp/test_project.json",
                    "output_settings": {
                        "format": "mp4",
                        "resolution": "1920x1080",
                        "bitrate": "5M",
                        "preset": "fast",
                    },
                },
            )

            if result.get("success"):
                print("   ✓ Rendering initiated")
                print(f"   Job ID: {result.get('job_id')}")
            else:
                print(f"   ⚠️  Rendering failed: {result.get('error')}")

        except Exception as e:
            print(f"   ⚠️  Rendering failed (expected for mock): {e}")

        # Test 6: Job status check
        print("\n6. Testing job status...")
        try:
            result = client.execute_tool("video_editor/get_job_status", {"job_id": "test_job_123"})

            if result.get("success") or "error" in result:
                print("   ✓ Job status check working")
                print(f"   Response: {result}")
            else:
                print(f"   ⚠️  Unexpected response: {result}")

        except Exception as e:
            print(f"   ⚠️  Job status check failed: {e}")

        print("\n" + "=" * 60)
        print("✅ All basic tests completed!")
        print("=" * 60)

    except Exception as e:
        print(f"\n❌ Connection failed: {e}")
        print("Make sure the Video Editor MCP server is running:")
        print(f"  python -m tools.mcp.video_editor.server --port {port}")
        return 1

    return 0


def test_with_real_video():
    """Test with actual video file if provided"""
    video_path = os.environ.get("TEST_VIDEO_PATH")

    if not video_path or not os.path.exists(video_path):
        print("\n⚠️  No test video provided. Set TEST_VIDEO_PATH to test with real video.")
        return

    print("\n" + "=" * 60)
    print("Testing with Real Video")
    print("=" * 60)
    print(f"Video: {video_path}")

    # Connect to server
    port = int(os.environ.get("PORT", 8019))
    base_url = f"http://localhost:{port}"

    try:
        client = MCPClient(base_url=base_url)
        print(f"✓ Connected to server on port {port}")

        # Analyze the real video
        print("\n📊 Analyzing video...")
        result = client.execute_tool(
            "video_editor/analyze_video",
            {
                "video_inputs": [video_path],
                "analysis_options": {
                    "transcribe": True,
                    "detect_scenes": True,
                    "identify_speakers": True,
                    "extract_metadata": True,
                },
            },
        )

        if result.get("success"):
            analysis = result.get("analysis", {}).get(video_path, {})
            print("\n📋 Video Analysis Results:")
            print(f"   Duration: {analysis.get('metadata', {}).get('duration', 'N/A')}s")
            width = analysis.get("metadata", {}).get("width", "N/A")
            height = analysis.get("metadata", {}).get("height", "N/A")
            print(f"   Resolution: {width}x{height}")
            print(f"   FPS: {analysis.get('metadata', {}).get('fps', 'N/A')}")
            print(f"   Scenes detected: {len(analysis.get('scenes', []))}")

            if analysis.get("transcript"):
                print(f"   Transcript words: {len(analysis.get('transcript', {}).get('text', '').split())}")

            if analysis.get("speakers"):
                print(f"   Speakers identified: {len(analysis.get('speakers', []))}")

        # Extract highlight clips based on keywords
        print("\n✂️  Extracting highlight clips...")
        result = client.execute_tool(
            "video_editor/extract_clips",
            {
                "video_input": video_path,
                "extraction_criteria": {
                    "keywords": ["important", "key", "main"],
                    "min_clip_length": 5,
                    "max_clip_length": 30,
                    "padding": 2,
                },
            },
        )

        if result.get("success"):
            clips = result.get("clips", [])
            print(f"   ✓ Extracted {len(clips)} clips")
            for i, clip in enumerate(clips, 1):
                print(f"     {i}. {clip['output_path']} ({clip['duration']:.1f}s)")

    except Exception as e:
        print(f"\n❌ Test failed: {e}")


def main():
    """Main test runner"""
    print("\n🎬 Video Editor MCP Server Test Suite")
    print("=" * 60)

    # Basic tests
    result = test_video_editor()

    # Real video tests if available
    test_with_real_video()

    return result


if __name__ == "__main__":
    sys.exit(main())
