#!/usr/bin/env python3
"""
Comprehensive examples for Video Editor MCP Server
Demonstrates various use cases and features
"""

import asyncio
import json

# Add project root to path

# These examples show how to use the video editor with the MCP client
# For actual testing, the MCP server needs to be running


def print_section(title: str):
    """Print a formatted section header"""
    print("\n" + "=" * 60)
    print(f"  {title}")
    print("=" * 60)


def print_example(example_num: int, title: str, description: str):
    """Print example header"""
    print(f"\n📌 Example {example_num}: {title}")
    print("-" * 40)
    print(f"Description: {description}")
    print()


async def example_analyze_video():
    """Example 1: Analyze video content"""
    print_example(1, "Video Analysis", "Analyze video to get transcript, speakers, and highlights")

    # Sample request structure
    request = {
        "tool": "video_editor/analyze",
        "arguments": {
            "video_inputs": ["outputs/video-editor/test_videos/camera1_presenter.mp4"],
            "analysis_options": {
                "transcribe": True,
                "identify_speakers": True,
                "detect_scenes": True,
                "extract_highlights": True,
            },
        },
    }

    print("Request:")
    print(json.dumps(request, indent=2))

    print("\nExpected Response Structure:")
    expected_response = {
        "video_inputs": ["test_videos/camera1_presenter.mp4"],
        "analysis": {
            "test_videos/camera1_presenter.mp4": {
                "file": "test_videos/camera1_presenter.mp4",
                "file_size": 140999,
                "transcript": {
                    "segments": [{"text": "This is an important presentation", "start": 0.0, "end": 2.5}],
                    "language": "en",
                },
                "speakers": ["SPEAKER_00", "SPEAKER_01"],
                "segments_with_speakers": [
                    {"text": "This is an important presentation", "start": 0.0, "end": 2.5, "speaker": "SPEAKER_00"}
                ],
                "audio_analysis": {"duration": 10.0, "peak_moments": [2.3, 5.7], "silence_segments": [[8.0, 9.5]]},
                "scene_changes": [5.0],
                "highlights": [{"time": 1.2, "type": "keyword", "keyword": "important", "confidence": 0.9}],
                "suggested_edits": [
                    {"type": "remove_silence", "start": 8.0, "end": 9.5, "reason": "Long silence detected (1.5 seconds)"}
                ],
            }
        },
    }
    print(json.dumps(expected_response, indent=2)[:500] + "...")


async def example_create_edit():
    """Example 2: Create edit decision list"""
    print_example(2, "Create Edit Decision List", "Generate EDL for automatic speaker-based switching")

    request = {
        "tool": "video_editor/create_edit",
        "arguments": {
            "video_inputs": [
                "outputs/video-editor/test_videos/camera1_presenter.mp4",
                "outputs/video-editor/test_videos/camera2_audience.mp4",
            ],
            "editing_rules": {
                "switch_on_speaker": True,
                "speaker_switch_delay": 0.5,
                "picture_in_picture": "auto",
                "zoom_on_emphasis": True,
                "remove_silence": True,
                "silence_threshold": 2.0,
            },
            "speaker_mapping": {
                "SPEAKER_00": "outputs/video-editor/test_videos/camera1_presenter.mp4",
                "SPEAKER_01": "outputs/video-editor/test_videos/camera2_audience.mp4",
            },
        },
    }

    print("Request:")
    print(json.dumps(request, indent=2))

    print("\nExpected Response Structure:")
    expected_response = {
        "edit_decision_list": [
            {
                "timestamp": 0.0,
                "duration": 2.5,
                "source": "test_videos/camera1_presenter.mp4",
                "action": "show",
                "effects": [],
            },
            {
                "timestamp": 2.5,
                "duration": 3.0,
                "source": "test_videos/camera2_audience.mp4",
                "action": "transition",
                "transition_type": "cross_dissolve",
                "effects": ["zoom_in"],
            },
        ],
        "estimated_duration": 9.5,
        "edl_file": "output/edl/edit_1.json",
    }
    print(json.dumps(expected_response, indent=2)[:500] + "...")


async def example_render_video():
    """Example 3: Render final video"""
    print_example(3, "Render Video", "Render the final edited video with captions")

    request = {
        "tool": "video_editor/render",
        "arguments": {
            "video_inputs": [
                "outputs/video-editor/test_videos/camera1_presenter.mp4",
                "outputs/video-editor/test_videos/camera2_audience.mp4",
            ],
            "output_settings": {
                "format": "mp4",
                "resolution": "1920x1080",
                "fps": 30,
                "bitrate": "8M",
                "output_path": "output/final_interview.mp4",
            },
            "render_options": {
                "hardware_acceleration": False,  # CPU mode for testing
                "preview_mode": False,
                "add_captions": True,
                "add_speaker_labels": True,
            },
        },
    }

    print("Request:")
    print(json.dumps(request, indent=2))

    print("\nExpected Response:")
    expected_response = {
        "output_path": "output/final_interview.mp4",
        "duration": 9.5,
        "file_size": 9437184,
        "render_time": 12.3,
        "transcript_path": "output/final_interview.srt",
    }
    print(json.dumps(expected_response, indent=2))


async def example_extract_clips():
    """Example 4: Extract clips by keywords"""
    print_example(4, "Extract Clips", "Extract clips based on keywords and speakers")

    request = {
        "tool": "video_editor/extract_clips",
        "arguments": {
            "video_input": "outputs/video-editor/test_videos/video_with_scenes.mp4",
            "extraction_criteria": {
                "keywords": ["important", "key point", "conclusion"],
                "speakers": ["SPEAKER_00"],
                "time_ranges": [[5.0, 8.0], [15.0, 18.0]],
                "min_clip_length": 2.0,
                "max_clip_length": 30.0,
                "padding": 0.5,
            },
            "output_dir": "output/clips",
        },
    }

    print("Request:")
    print(json.dumps(request, indent=2))

    print("\nExpected Response:")
    expected_response = {
        "video_input": "test_videos/video_with_scenes.mp4",
        "clips_extracted": [
            {
                "output_path": "output/clips/clip_1_time_5.0-8.0.mp4",
                "start_time": 4.5,
                "end_time": 8.5,
                "duration": 4.0,
                "criteria": "time_range",
            },
            {
                "output_path": "output/clips/clip_2_keyword_important.mp4",
                "start_time": 1.5,
                "end_time": 4.5,
                "duration": 3.0,
                "criteria": "keyword",
                "keyword": "important",
                "text": "This is an important point",
            },
        ],
        "total_clips": 2,
        "output_directory": "output/clips",
    }
    print(json.dumps(expected_response, indent=2))


async def example_add_captions():
    """Example 5: Add multi-language captions"""
    print_example(5, "Add Captions", "Add styled captions in multiple languages")

    request = {
        "tool": "video_editor/add_captions",
        "arguments": {
            "video_input": "outputs/video-editor/test_videos/short_clip.mp4",
            "caption_style": {
                "font": "Arial",
                "size": 48,
                "color": "#FFFF00",
                "background": "#000000",
                "position": "bottom",
                "max_chars_per_line": 35,
                "display_speaker_names": True,
            },
            "languages": ["en", "es", "fr"],
        },
    }

    print("Request:")
    print(json.dumps(request, indent=2))

    print("\nExpected Response:")
    expected_response = {
        "video_input": "test_videos/short_clip.mp4",
        "languages_processed": [
            {
                "language": "en",
                "output_path": "output/short_clip_en.mp4",
                "srt_path": "output/short_clip_en.srt",
                "caption_count": 5,
            },
            {
                "language": "es",
                "output_path": "output/short_clip_es.mp4",
                "srt_path": "output/short_clip_es.srt",
                "caption_count": 5,
            },
            {
                "language": "fr",
                "output_path": "output/short_clip_fr.mp4",
                "srt_path": "output/short_clip_fr.srt",
                "caption_count": 5,
            },
        ],
    }
    print(json.dumps(expected_response, indent=2))


async def example_complex_workflow():
    """Example 6: Complex multi-step workflow"""
    print_example(6, "Complex Workflow", "Complete workflow: analyze, edit, render with effects")

    print("Step 1: Analyze all input videos")
    print("Step 2: Create smart EDL based on speakers and content")
    print("Step 3: Apply effects (zoom, PiP, transitions)")
    print("Step 4: Add captions with speaker identification")
    print("Step 5: Render in multiple formats")

    workflow = {
        "description": "Interview editing workflow",
        "steps": [
            {"step": 1, "tool": "video_editor/analyze", "description": "Analyze both camera feeds"},
            {"step": 2, "tool": "video_editor/create_edit", "description": "Generate EDL with smart switching"},
            {"step": 3, "tool": "video_editor/render", "description": "Render with effects and captions"},
            {"step": 4, "tool": "video_editor/extract_clips", "description": "Extract highlight clips"},
        ],
    }

    print("\nWorkflow Structure:")
    print(json.dumps(workflow, indent=2))


def example_python_client():
    """Example 7: Using Python client"""
    print_example(7, "Python Client Usage", "How to use the MCP client in Python scripts")

    code = '''
import asyncio
from mcp_core.client import MCPClient

async def edit_interview():
    """Edit an interview with two cameras"""

    async with MCPClient("video_editor", port=8019) as client:
        # Step 1: Analyze videos
        print("Analyzing videos...")
        analysis = await client.call("video_editor/analyze", {
            "video_inputs": ["camera1.mp4", "camera2.mp4"],
            "analysis_options": {
                "transcribe": True,
                "identify_speakers": True
            }
        })

        # Step 2: Create edit
        print("Creating edit decision list...")
        edit = await client.call("video_editor/create_edit", {
            "video_inputs": ["camera1.mp4", "camera2.mp4"],
            "editing_rules": {
                "switch_on_speaker": True,
                "remove_silence": True
            },
            "speaker_mapping": {
                "SPEAKER_00": "camera1.mp4",
                "SPEAKER_01": "camera2.mp4"
            }
        })

        # Step 3: Render final video
        print("Rendering final video...")
        result = await client.call("video_editor/render", {
            "video_inputs": ["camera1.mp4", "camera2.mp4"],
            "edit_decision_list": edit["edit_decision_list"],
            "render_options": {
                "add_captions": True,
                "add_speaker_labels": True
            }
        })

        print(f"Final video: {result['output_path']}")
        print(f"Duration: {result['duration']}s")
        print(f"Transcript: {result.get('transcript_path')}")

# Run the async function
asyncio.run(edit_interview())
'''

    print("Python Code Example:")
    print(code)


def example_bash_usage():
    """Example 8: Using with curl/bash"""
    print_example(8, "Bash/cURL Usage", "How to call the video editor via HTTP API")

    bash_code = """
#!/bin/bash

# Video Editor MCP Server endpoint
SERVER_URL="http://localhost:8019"

# Example 1: Analyze a video
curl -X POST "$SERVER_URL/tool" \\
  -H "Content-Type: application/json" \\
  -d '{
    "tool": "video_editor/analyze",
    "arguments": {
      "video_inputs": ["video.mp4"],
      "analysis_options": {
        "transcribe": true,
        "identify_speakers": true
      }
    }
  }'

# Example 2: Create an edit
curl -X POST "$SERVER_URL/tool" \\
  -H "Content-Type: application/json" \\
  -d '{
    "tool": "video_editor/create_edit",
    "arguments": {
      "video_inputs": ["cam1.mp4", "cam2.mp4"],
      "editing_rules": {
        "switch_on_speaker": true
      }
    }
  }'

# Example 3: Check job status
JOB_ID="job_123"
curl "$SERVER_URL/tool" \\
  -H "Content-Type: application/json" \\
  -d '{
    "tool": "video_editor/get_job_status",
    "arguments": {
      "job_id": "'$JOB_ID'"
    }
  }'
"""

    print("Bash Script Example:")
    print(bash_code)


def main():
    """Main function to run all examples"""
    print_section("Video Editor MCP Server - Comprehensive Examples")

    print(
        """
This script demonstrates various use cases for the Video Editor MCP Server.
The examples show request/response structures and usage patterns.

Prerequisites:
1. Video Editor MCP Server running (docker-compose up mcp-video-editor)
2. Test videos created (run create_test_videos.sh)
3. MCP client library installed
"""
    )

    # Run async examples
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    try:
        # Example 1: Analyze video
        loop.run_until_complete(example_analyze_video())

        # Example 2: Create edit
        loop.run_until_complete(example_create_edit())

        # Example 3: Render video
        loop.run_until_complete(example_render_video())

        # Example 4: Extract clips
        loop.run_until_complete(example_extract_clips())

        # Example 5: Add captions
        loop.run_until_complete(example_add_captions())

        # Example 6: Complex workflow
        loop.run_until_complete(example_complex_workflow())

        # Example 7: Python client
        example_python_client()

        # Example 8: Bash usage
        example_bash_usage()

    finally:
        loop.close()

    print_section("Examples Complete")
    print(
        """
These examples demonstrate:
✓ Video analysis with transcription and speaker identification
✓ Smart edit creation with speaker-based switching
✓ Video rendering with effects and transitions
✓ Clip extraction by keywords and timestamps
✓ Multi-language caption generation
✓ Complex multi-step workflows
✓ Python and Bash client usage

For production use:
1. Ensure HUGGINGFACE_TOKEN is set for speaker diarization
2. Use GPU acceleration for faster processing
3. Configure appropriate cache sizes for your workload
4. Monitor job status for long-running operations
"""
    )


if __name__ == "__main__":
    main()
