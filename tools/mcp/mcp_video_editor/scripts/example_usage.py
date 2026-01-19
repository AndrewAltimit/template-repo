#!/usr/bin/env python3
"""Example usage of the Video Editor MCP Server"""

import os
from pathlib import Path
import sys

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

from tools.mcp.core.client import MCPClient  # noqa: E402


def example_interview_editing():
    """Example: Edit a two-camera interview with automatic speaker switching"""

    print("=" * 60)
    print("Example: Two-Camera Interview Editing")
    print("=" * 60)

    # Video paths (update with your actual video files)
    interviewer_video = "interviewer_camera.mp4"
    interviewee_video = "interviewee_camera.mp4"

    port = int(os.environ.get("PORT", 8019))
    base_url = f"http://localhost:{port}"
    client = MCPClient(base_url=base_url)

    # Step 1: Analyze both videos
    print("\n1. Analyzing videos...")
    client.execute_tool(
        "video_editor/analyze_video",
        {
            "video_inputs": [interviewer_video, interviewee_video],
            "analysis_options": {
                "transcribe": True,
                "identify_speakers": True,
                "detect_scenes": False,
                "extract_metadata": True,
            },
        },
    )

    # Step 2: Create an intelligent edit based on speaker detection
    print("\n2. Creating automatic speaker-switching edit...")
    edit_result = client.execute_tool(
        "video_editor/create_edit",
        {
            "video_inputs": [interviewer_video, interviewee_video],
            "edit_instructions": {
                "mode": "interview",
                "auto_switch_speakers": True,
                "transitions": ["cut"],  # Quick cuts between speakers
                "audio_mix": "active_speaker",  # Use audio from active speaker
                "output_format": "mp4",
                "resolution": "1920x1080",
                "framerate": 30,
            },
            "use_ai_assistance": True,  # Enable AI for smart cutting decisions
        },
    )

    print(f"\n✓ Edit created: {edit_result.get('output_path')}")
    print(f"  Job ID: {edit_result.get('job_id')}")

    # Step 3: Check job progress
    print("\n3. Monitoring job progress...")
    job_status = client.execute_tool("video_editor/get_job_status", {"job_id": edit_result.get("job_id")})

    print(f"  Status: {job_status.get('status')}")
    print(f"  Progress: {job_status.get('progress', 0)}%")

    # Step 4: Add captions from transcription
    if job_status.get("status") == "completed":
        print("\n4. Adding captions...")
        caption_result = client.execute_tool(
            "video_editor/add_captions",
            {
                "video_input": edit_result.get("output_path"),
                "caption_options": {
                    "source": "transcription",  # Use the transcription from analysis
                    "style": "professional",
                    "position": "bottom",
                    "font_size": "medium",
                },
            },
        )
        print(f"  ✓ Captions added: {caption_result.get('output_path')}")

    print("\n" + "=" * 60)
    print("Interview editing completed!")


def example_highlight_extraction():
    """Example: Extract highlights from a long video based on keywords"""

    print("=" * 60)
    print("Example: Automatic Highlight Extraction")
    print("=" * 60)

    # Input video (update with your actual video file)
    source_video = "conference_recording.mp4"

    port = int(os.environ.get("PORT", 8019))
    base_url = f"http://localhost:{port}"
    client = MCPClient(base_url=base_url)

    # Step 1: Analyze video for keywords
    print("\n1. Analyzing video for key moments...")
    client.execute_tool(
        "video_editor/analyze_video",
        {
            "video_inputs": [source_video],
            "analysis_options": {
                "transcribe": True,
                "detect_scenes": True,
                "extract_metadata": True,
            },
        },
    )

    # Step 2: Extract clips based on keywords and scene detection
    print("\n2. Extracting highlight clips...")
    clips_result = client.execute_tool(
        "video_editor/extract_clips",
        {
            "video_input": source_video,
            "extraction_criteria": {
                "keywords": ["important", "announcement", "breakthrough", "key point", "summary"],
                "scene_changes": True,  # Also extract based on scene changes
                "min_clip_length": 10,  # Minimum 10 seconds
                "max_clip_length": 60,  # Maximum 60 seconds
                "padding": 2,  # Add 2 seconds before/after each keyword
            },
        },
    )

    print(f"  ✓ Extracted {clips_result.get('clips_count', 0)} clips")
    for clip in clips_result.get("clips", []):
        print(f"    - {clip['output_path']}: {clip['duration']}s ({clip['criteria']})")

    print("\n" + "=" * 60)
    print("Highlight extraction completed!")


def example_multi_language_captions():
    """Example: Add multi-language captions to a video"""

    print("=" * 60)
    print("Example: Multi-Language Caption Generation")
    print("=" * 60)

    # Input video
    source_video = "presentation.mp4"

    port = int(os.environ.get("PORT", 8019))
    base_url = f"http://localhost:{port}"
    client = MCPClient(base_url=base_url)

    # Step 1: Transcribe the video
    print("\n1. Transcribing video...")
    analysis = client.execute_tool(
        "video_editor/analyze_video",
        {
            "video_inputs": [source_video],
            "analysis_options": {"transcribe": True, "language": "auto"},  # Auto-detect language
        },
    )

    transcript = analysis.get("analysis", {}).get(source_video, {}).get("transcript", {})
    print("  ✓ Transcription completed")
    print(f"    Language detected: {transcript.get('language', 'unknown')}")
    print(f"    Duration: {transcript.get('duration', 0):.1f}s")

    # Step 2: Generate captions in multiple languages
    languages = ["en", "es", "fr", "de", "ja"]  # English, Spanish, French, German, Japanese

    for lang in languages:
        print(f"\n2. Adding {lang.upper()} captions...")
        caption_result = client.execute_tool(
            "video_editor/add_captions",
            {
                "video_input": source_video,
                "caption_options": {
                    "language": lang,
                    "translate": lang != transcript.get("language", "en"),
                    "style": "minimal",
                    "burn_in": False,  # Create separate subtitle files
                },
            },
        )
        print(f"  ✓ {lang.upper()} captions: {caption_result.get('subtitle_file')}")

    print("\n" + "=" * 60)
    print("Multi-language captions completed!")


def example_podcast_editing():
    """Example: Edit a podcast with intro, outro, and chapter markers"""

    print("=" * 60)
    print("Example: Podcast Production Pipeline")
    print("=" * 60)

    # Input files
    main_recording = "podcast_raw.mp4"
    intro_clip = "intro.mp4"
    outro_clip = "outro.mp4"
    background_music = "background_music.mp3"

    port = int(os.environ.get("PORT", 8019))
    base_url = f"http://localhost:{port}"
    client = MCPClient(base_url=base_url)

    # Step 1: Analyze main recording for content
    print("\n1. Analyzing podcast content...")
    analysis = client.execute_tool(
        "video_editor/analyze_video",
        {
            "video_inputs": [main_recording],
            "analysis_options": {
                "transcribe": True,
                "identify_speakers": True,
                "detect_silence": True,  # Detect long silences for removal
            },
        },
    )

    # Step 2: Create the podcast edit
    print("\n2. Creating podcast edit...")
    edit_result = client.execute_tool(
        "video_editor/create_edit",
        {
            "video_inputs": [intro_clip, main_recording, outro_clip],
            "edit_instructions": {
                "timeline": [
                    {"clip": 0, "start": 0, "end": None},  # Full intro
                    {"clip": 1, "start": 0, "end": None, "remove_silence": True},  # Main content
                    {"clip": 2, "start": 0, "end": None},  # Full outro
                ],
                "audio_tracks": [{"file": background_music, "volume": 0.1, "fade_in": 5, "fade_out": 5}],
                "chapters": [  # Add chapter markers based on topics
                    {"time": 0, "title": "Introduction"},
                    {"time": 30, "title": "Topic 1: Getting Started"},
                    {"time": 600, "title": "Topic 2: Deep Dive"},
                    {"time": 1200, "title": "Topic 3: Best Practices"},
                    {"time": 1800, "title": "Conclusion"},
                ],
                "normalize_audio": True,  # Normalize audio levels
                "output_format": "mp4",
                "audio_format": "aac",
                "audio_bitrate": "192k",
            },
        },
    )

    print(f"  ✓ Podcast edit created: {edit_result.get('output_path')}")

    # Step 3: Generate podcast description with timestamps
    print("\n3. Generating show notes with timestamps...")
    transcript = analysis.get("analysis", {}).get(main_recording, {}).get("transcript", {})

    if transcript:
        segments = transcript.get("segments", [])
        print("\n  📝 Show Notes:")
        print("  " + "-" * 40)

        for segment in segments:
            # Simple topic detection based on pauses or keywords
            if segment.get("duration", 0) > 2 or "topic" in segment.get("text", "").lower():
                timestamp = segment.get("start", 0)
                minutes = int(timestamp // 60)
                seconds = int(timestamp % 60)
                text_preview = segment.get("text", "")[:100]
                print(f"  [{minutes:02d}:{seconds:02d}] {text_preview}...")

    print("\n" + "=" * 60)
    print("Podcast production completed!")


def example_scene_based_editing():
    """Example: Create a dynamic edit based on scene detection"""

    print("=" * 60)
    print("Example: AI-Powered Scene-Based Editing")
    print("=" * 60)

    # Input video
    source_video = "raw_footage.mp4"

    port = int(os.environ.get("PORT", 8019))
    base_url = f"http://localhost:{port}"
    client = MCPClient(base_url=base_url)

    # Step 1: Analyze video for scenes and content
    print("\n1. Analyzing video scenes and content...")
    analysis = client.execute_tool(
        "video_editor/analyze_video",
        {
            "video_inputs": [source_video],
            "analysis_options": {
                "detect_scenes": True,
                "analyze_motion": True,  # Detect high-motion scenes
                "detect_faces": True,  # Detect scenes with faces
                "extract_colors": True,  # Extract dominant colors per scene
            },
        },
    )

    scenes = analysis.get("analysis", {}).get(source_video, {}).get("scenes", [])
    print(f"  ✓ Detected {len(scenes)} scenes")

    # Step 2: Create a dynamic edit based on scene characteristics
    print("\n2. Creating AI-powered edit...")

    # Build edit instructions based on scene analysis
    timeline = []
    for i, scene in enumerate(scenes):
        # Include scenes based on certain criteria
        include = False
        transition = "cut"

        # Include scenes with faces
        if scene.get("has_faces", False):
            include = True
            transition = "fade"

        # Include high-motion scenes
        if scene.get("motion_score", 0) > 0.7:
            include = True
            transition = "wipe"

        # Include scenes with specific colors (e.g., warm colors)
        dominant_color = scene.get("dominant_color", {})
        if dominant_color.get("hue", 0) < 60:  # Warm colors (red/orange/yellow)
            include = True

        if include:
            timeline.append(
                {
                    "scene_index": i,
                    "start": scene.get("start", 0),
                    "end": scene.get("end", 0),
                    "transition": transition,
                    "effect": "color_grade" if dominant_color else None,
                }
            )

    edit_result = client.execute_tool(
        "video_editor/create_edit",
        {
            "video_inputs": [source_video],
            "edit_instructions": {
                "timeline": timeline,
                "auto_pace": True,  # Automatically adjust pacing
                "music_sync": True,  # Sync cuts to music beat if audio present
                "color_correction": "auto",  # Auto color correction
                "stabilization": True,  # Apply stabilization to shaky footage
                "output_format": "mp4",
                "resolution": "1920x1080",
                "quality": "high",
            },
        },
    )

    print(f"  ✓ Dynamic edit created: {edit_result.get('output_path')}")
    print(f"    Included {len(timeline)} scenes from {len(scenes)} total")

    # Step 3: Generate a preview/trailer
    print("\n3. Generating 30-second trailer...")
    trailer_result = client.execute_tool(
        "video_editor/create_trailer",
        {
            "video_input": edit_result.get("output_path"),
            "trailer_options": {
                "duration": 30,
                "style": "dynamic",  # fast-paced, energetic
                "include_text": True,  # Add text overlays
                "music": "epic",  # Add epic trailer music
            },
        },
    )

    print(f"  ✓ Trailer created: {trailer_result.get('output_path')}")

    print("\n" + "=" * 60)
    print("Scene-based editing completed!")


def main():
    """Run examples based on command-line argument"""
    examples = {
        "interview": example_interview_editing,
        "highlights": example_highlight_extraction,
        "captions": example_multi_language_captions,
        "podcast": example_podcast_editing,
        "scenes": example_scene_based_editing,
    }

    if len(sys.argv) > 1:
        example_name = sys.argv[1].lower()
        if example_name in examples:
            print(f"\n🎬 Running '{example_name}' example...")
            print("=" * 60)
            examples[example_name]()
        else:
            print(f"❌ Unknown example: {example_name}")
            print(f"Available examples: {', '.join(examples.keys())}")
            sys.exit(1)
    else:
        # Run all examples
        print("\n🎬 Video Editor MCP Server - Example Usage")
        print("=" * 60)
        print("Running all examples...")
        print("(To run a specific example, use: python example_usage.py <example_name>)")
        print()

        for name, func in examples.items():
            print(f"\n{'=' * 60}")
            print(f"Running: {name}")
            print("=" * 60)
            try:
                func()
            except Exception as e:
                print(f"❌ Example '{name}' failed: {e}")
                continue

            # Add a break between examples
            if name != list(examples.keys())[-1]:
                print("\nPress Enter to continue to next example...")
                input()

        print("\n" + "=" * 60)
        print("✅ All examples completed!")
        print("=" * 60)


if __name__ == "__main__":
    main()
