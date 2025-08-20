#!/usr/bin/env python3
"""Example usage of the Video Editor MCP Server"""

import asyncio
import os
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

from tools.mcp.core.client import MCPClient


async def example_interview_editing():
    """Example: Edit a two-camera interview with automatic speaker switching"""

    print("=" * 60)
    print("Example: Two-Camera Interview Editing")
    print("=" * 60)

    # Video paths (update with your actual video files)
    interviewer_video = "interviewer_camera.mp4"
    interviewee_video = "interviewee_camera.mp4"

    async with MCPClient("video_editor", port=8019) as client:

        # Step 1: Analyze both videos
        print("\n1. Analyzing videos...")
        analysis = await client.call(
            "video_editor/analyze",
            {
                "video_inputs": [interviewer_video, interviewee_video],
                "analysis_options": {
                    "transcribe": True,
                    "identify_speakers": True,
                    "detect_scenes": False,
                    "extract_highlights": True,
                },
            },
        )

        if "error" in analysis:
            print(f"Error: {analysis['error']}")
            return

        # Step 2: Create edit with speaker-based switching
        print("\n2. Creating edit decision list...")
        edit = await client.call(
            "video_editor/create_edit",
            {
                "video_inputs": [interviewer_video, interviewee_video],
                "editing_rules": {
                    "switch_on_speaker": True,
                    "speaker_switch_delay": 0.8,
                    "picture_in_picture": "auto",
                    "zoom_on_emphasis": True,
                    "remove_silence": True,
                    "silence_threshold": 2.0,
                },
                "speaker_mapping": {"SPEAKER_00": interviewer_video, "SPEAKER_01": interviewee_video},
            },
        )

        print(f"   Created EDL with {len(edit['edit_decision_list'])} decisions")
        print(f"   Estimated duration: {edit['estimated_duration']:.2f} seconds")

        # Step 3: Render the final video
        print("\n3. Rendering final video...")
        result = await client.call(
            "video_editor/render",
            {
                "video_inputs": [interviewer_video, interviewee_video],
                "edit_decision_list": edit["edit_decision_list"],
                "output_settings": {
                    "format": "mp4",
                    "resolution": "1920x1080",
                    "fps": 30,
                    "bitrate": "8M",
                    "output_path": "interview_edited.mp4",
                },
                "render_options": {"hardware_acceleration": True, "add_captions": True, "add_speaker_labels": True},
            },
        )

        print(f"   ✓ Video rendered: {result['output_path']}")
        print(f"   Duration: {result['duration']:.2f} seconds")
        print(f"   File size: {result['file_size'] / (1024*1024):.2f} MB")
        if "transcript_path" in result:
            print(f"   Transcript: {result['transcript_path']}")


async def example_highlight_extraction():
    """Example: Extract highlight clips from a presentation"""

    print("=" * 60)
    print("Example: Highlight Clip Extraction")
    print("=" * 60)

    presentation_video = "conference_presentation.mp4"

    async with MCPClient("video_editor", port=8019) as client:

        # Extract clips based on keywords
        print("\n1. Extracting keyword-based highlights...")
        result = await client.call(
            "video_editor/extract_clips",
            {
                "video_input": presentation_video,
                "extraction_criteria": {
                    "keywords": ["important", "key point", "remember", "conclusion", "summary", "breakthrough"],
                    "min_clip_length": 5.0,
                    "max_clip_length": 30.0,
                    "padding": 1.0,  # Add 1 second before/after
                },
                "output_dir": "highlights/",
            },
        )

        if "error" not in result:
            print(f"   Extracted {result['total_clips']} highlight clips:")
            for clip in result["clips_extracted"]:
                print(f"   - {clip['output_path']}")
                print(f"     Duration: {clip['duration']:.2f}s")
                print(f"     Criteria: {clip['criteria']}")
                if "keyword" in clip:
                    print(f"     Keyword: {clip['keyword']}")
                print()


async def example_multi_language_captions():
    """Example: Add captions in multiple languages"""

    print("=" * 60)
    print("Example: Multi-Language Captioning")
    print("=" * 60)

    video_file = "presentation.mp4"

    async with MCPClient("video_editor", port=8019) as client:

        print("\n1. Adding captions in multiple languages...")
        result = await client.call(
            "video_editor/add_captions",
            {
                "video_input": video_file,
                "caption_style": {
                    "font": "Arial",
                    "size": 48,
                    "color": "#FFFFFF",
                    "background": "#000000",
                    "position": "bottom",
                    "max_chars_per_line": 45,
                    "display_speaker_names": True,
                },
                "languages": ["en", "es", "fr", "de", "ja"],
            },
        )

        if "error" not in result:
            print("   Generated captioned videos:")
            for lang_result in result["languages_processed"]:
                print(f"   - {lang_result['language']}: {lang_result['output_path']}")
                print(f"     Captions: {lang_result['caption_count']}")
                print(f"     SRT file: {lang_result['srt_path']}")
                print()


async def example_podcast_editing():
    """Example: Edit a multi-person podcast with smart switching"""

    print("=" * 60)
    print("Example: Multi-Person Podcast Editing")
    print("=" * 60)

    # Multiple camera feeds
    video_feeds = ["host_camera.mp4", "guest1_camera.mp4", "guest2_camera.mp4", "wide_shot.mp4"]

    async with MCPClient("video_editor", port=8019) as client:

        # Step 1: Analyze all feeds
        print("\n1. Analyzing all camera feeds...")
        analysis = await client.call(
            "video_editor/analyze",
            {
                "video_inputs": video_feeds,
                "analysis_options": {
                    "transcribe": True,
                    "identify_speakers": True,
                    "detect_scenes": True,
                    "extract_highlights": True,
                },
            },
        )

        # Step 2: Create dynamic edit
        print("\n2. Creating podcast edit...")
        edit = await client.call(
            "video_editor/create_edit",
            {
                "video_inputs": video_feeds,
                "editing_rules": {
                    "switch_on_speaker": True,
                    "speaker_switch_delay": 1.5,  # Slower switching for podcast
                    "picture_in_picture": "auto",  # PiP for reactions
                    "zoom_on_emphasis": False,  # No zoom for podcast
                    "remove_silence": True,
                    "silence_threshold": 3.0,
                },
            },
        )

        # Step 3: Render with preview mode first
        print("\n3. Creating preview...")
        preview = await client.call(
            "video_editor/render",
            {
                "video_inputs": video_feeds,
                "edit_decision_list": edit["edit_decision_list"],
                "output_settings": {
                    "format": "mp4",
                    "resolution": "640x360",  # Low res for preview
                    "fps": 15,
                    "bitrate": "2M",
                    "output_path": "podcast_preview.mp4",
                },
                "render_options": {"preview_mode": True, "add_captions": False},
            },
        )

        print(f"   Preview created: {preview['output_path']}")

        # Step 4: If preview looks good, render full quality
        print("\n4. Rendering full quality...")
        final = await client.call(
            "video_editor/render",
            {
                "video_inputs": video_feeds,
                "edit_decision_list": edit["edit_decision_list"],
                "output_settings": {
                    "format": "mp4",
                    "resolution": "1920x1080",
                    "fps": 30,
                    "bitrate": "10M",
                    "output_path": "podcast_final.mp4",
                },
                "render_options": {"hardware_acceleration": True, "add_captions": True, "add_speaker_labels": True},
            },
        )

        print(f"   ✓ Final video: {final['output_path']}")
        print(f"   Duration: {final['duration']:.2f} seconds")


async def example_scene_based_editing():
    """Example: Edit based on scene changes"""

    print("=" * 60)
    print("Example: Scene-Based Automatic Editing")
    print("=" * 60)

    video_files = ["camera1.mp4", "camera2.mp4", "camera3.mp4"]

    async with MCPClient("video_editor", port=8019) as client:

        # Analyze for scene changes
        print("\n1. Detecting scene changes...")
        analysis = await client.call(
            "video_editor/analyze",
            {
                "video_inputs": video_files,
                "analysis_options": {
                    "transcribe": False,
                    "identify_speakers": False,
                    "detect_scenes": True,
                    "extract_highlights": False,
                },
            },
        )

        # Create edit based on scenes
        print("\n2. Creating scene-based edit...")
        edit = await client.call(
            "video_editor/create_edit",
            {
                "video_inputs": video_files,
                "editing_rules": {
                    "switch_on_speaker": False,
                    "picture_in_picture": False,
                    "zoom_on_emphasis": False,
                    "remove_silence": False,
                },
            },
        )

        print(f"   Created {len(edit['edit_decision_list'])} scene-based cuts")


def print_menu():
    """Print the example menu"""
    print("\n" + "=" * 60)
    print("Video Editor MCP Server - Examples")
    print("=" * 60)
    print("1. Two-Camera Interview Editing")
    print("2. Highlight Clip Extraction")
    print("3. Multi-Language Captioning")
    print("4. Multi-Person Podcast Editing")
    print("5. Scene-Based Automatic Editing")
    print("6. Run All Examples")
    print("0. Exit")
    print("=" * 60)


async def main():
    """Main menu for examples"""

    examples = {
        "1": example_interview_editing,
        "2": example_highlight_extraction,
        "3": example_multi_language_captions,
        "4": example_podcast_editing,
        "5": example_scene_based_editing,
    }

    while True:
        print_menu()
        choice = input("Select an example (0-6): ").strip()

        if choice == "0":
            print("Exiting...")
            break
        elif choice == "6":
            # Run all examples
            for name, func in examples.items():
                try:
                    await func()
                except Exception as e:
                    print(f"Error in example: {e}")
                print("\nPress Enter to continue...")
                input()
        elif choice in examples:
            try:
                await examples[choice]()
            except Exception as e:
                print(f"Error: {e}")
            print("\nPress Enter to continue...")
            input()
        else:
            print("Invalid choice. Please try again.")


if __name__ == "__main__":
    print("Video Editor MCP Server - Example Usage")
    print("=" * 60)
    print("Note: These examples assume you have video files available.")
    print("Update the file paths in the examples to match your videos.")
    print("=" * 60)

    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n\nExiting...")
    except Exception as e:
        print(f"Error: {e}")
