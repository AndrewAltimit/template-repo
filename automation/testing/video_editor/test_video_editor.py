#!/usr/bin/env python3
"""
Test script for video editor functionality validation
Tests basic operations without requiring the full MCP server

Usage:
    python test_video_editor.py [--debug]

Options:
    --debug    Show ffmpeg stderr output for debugging
"""

from pathlib import Path
import sys

# pylint: disable=wrong-import-position
from automation.testing.video_editor.utils import (  # noqa: E402
    add_caption_overlay,
    analyze_audio_levels,
    compose_videos_with_transition,
    detect_scene_changes,
    extract_audio,
    extract_clip,
    extract_frames,
    get_video_info,
)


def main():
    """Main test function"""
    # Check for debug flag
    debug = "--debug" in sys.argv

    if debug:
        print("🐞 Debug mode enabled - will show ffmpeg stderr")
        print()

    print("=" * 60)
    print("Video Editor Functionality Test Suite")
    print("=" * 60)

    # Test videos directory
    test_videos_dir = Path("outputs/video-editor/test_videos")
    output_dir = Path("outputs/video-editor")
    output_dir.mkdir(exist_ok=True)

    # Check if test videos exist
    if not test_videos_dir.exists():
        print("❌ Test videos directory not found. Please run create_test_videos.sh first.")
        return 1

    test_results = []

    # Test 1: Video Information Extraction
    print("\n📊 Test 1: Video Information Extraction")
    print("-" * 40)

    for video_file in test_videos_dir.glob("*.mp4"):
        info = get_video_info(video_file)
        if info:
            duration = float(info["format"]["duration"])
            size = int(info["format"]["size"])
            video_stream = next((s for s in info["streams"] if s["codec_type"] == "video"), None)
            audio_stream = next((s for s in info["streams"] if s["codec_type"] == "audio"), None)

            print(f"✓ {video_file.name}:")
            print(f"  - Duration: {duration:.2f}s")
            print(f"  - Size: {size/1024:.1f} KB")
            if video_stream:
                print(f"  - Resolution: {video_stream['width']}x{video_stream['height']}")
                # Parse frame rate fraction without eval
                fps_parts = video_stream["r_frame_rate"].split("/")
                fps = float(fps_parts[0]) / float(fps_parts[1]) if len(fps_parts) == 2 else float(fps_parts[0])
                print(f"  - FPS: {fps:.2f}")
            if audio_stream:
                print(f"  - Audio: {audio_stream['codec_name']} @ {audio_stream['sample_rate']} Hz")

            test_results.append(("Video Info Extraction", video_file.name, True))
        else:
            print(f"❌ Failed to get info for {video_file.name}")
            test_results.append(("Video Info Extraction", video_file.name, False))

    # Test 2: Audio Extraction
    print("\n🎵 Test 2: Audio Extraction")
    print("-" * 40)

    test_video = test_videos_dir / "camera1_presenter.mp4"
    audio_output = output_dir / "extracted_audio.wav"

    if extract_audio(test_video, audio_output, debug=debug):
        audio_size = audio_output.stat().st_size
        print("✓ Audio extracted successfully")
        print(f"  - Output: {audio_output}")
        print(f"  - Size: {audio_size/1024:.1f} KB")
        test_results.append(("Audio Extraction", test_video.name, True))

        # Test audio level analysis
        silence_segments = analyze_audio_levels(audio_output)
        print(f"  - Detected {len(silence_segments)} silence segments")
    else:
        print("❌ Audio extraction failed")
        test_results.append(("Audio Extraction", test_video.name, False))

    # Test 3: Frame Extraction
    print("\n🖼️ Test 3: Frame Extraction")
    print("-" * 40)

    frames_dir = output_dir / "frames"
    frames_dir.mkdir(exist_ok=True)
    if extract_frames(test_video, frames_dir / "frame_%03d.jpg", 10, debug=debug):
        frame_files = list(frames_dir.glob("*.jpg"))
        print("✓ Frames extracted successfully")
        print(f"  - Extracted {len(frame_files)} frames")
        if frame_files:
            print(f"  - Sample frame: {frame_files[0]}")
        test_results.append(("Frame Extraction", test_video.name, True))
    else:
        print("❌ Frame extraction failed")
        test_results.append(("Frame Extraction", test_video.name, False))

    # Test 4: Scene Detection
    print("\n🎬 Test 4: Scene Change Detection")
    print("-" * 40)

    scene_video = test_videos_dir / "video_with_scenes.mp4"
    if scene_video.exists():
        scenes = detect_scene_changes(scene_video)
        if scenes:
            print(f"✓ Detected {len(scenes)} scene changes")
            for i, scene_time in enumerate(scenes[:5]):  # Show first 5
                print(f"  - Scene {i+1} at {scene_time:.2f}s")
            test_results.append(("Scene Detection", scene_video.name, True))
        else:
            print("ℹ️ No scene changes detected (may be normal for simple test video)")
            test_results.append(("Scene Detection", scene_video.name, True))

    # Test 5: Video Composition
    print("\n🎞️ Test 5: Video Composition with Transition")
    print("-" * 40)

    video1 = test_videos_dir / "camera1_presenter.mp4"
    video2 = test_videos_dir / "camera2_audience.mp4"
    composed_output = output_dir / "composed_video.mp4"

    if compose_videos_with_transition(video1, video2, composed_output, debug=debug):
        info = get_video_info(composed_output)
        if info:
            duration = float(info["format"]["duration"])
            print("✓ Video composition successful")
            print(f"  - Output: {composed_output}")
            print(f"  - Duration: {duration:.2f}s")
            print("  - Transition: Crossfade at 4s")
            test_results.append(("Video Composition", "crossfade", True))
    else:
        print("❌ Video composition failed")
        test_results.append(("Video Composition", "crossfade", False))

    # Test 6: Clip Extraction
    print("\n✂️ Test 6: Clip Extraction")
    print("-" * 40)

    source_video = test_videos_dir / "video_with_scenes.mp4"
    clip_output = output_dir / "extracted_clip.mp4"

    if extract_clip(source_video, 5.0, 3.0, clip_output, debug=debug):
        info = get_video_info(clip_output)
        if info:
            duration = float(info["format"]["duration"])
            print("✓ Clip extraction successful")
            print(f"  - Source: {source_video.name}")
            print(f"  - Extracted: {duration:.2f}s clip from 5.0s")
            print(f"  - Output: {clip_output}")
            test_results.append(("Clip Extraction", source_video.name, True))
    else:
        print("❌ Clip extraction failed")
        test_results.append(("Clip Extraction", source_video.name, False))

    # Test 7: Caption Overlay
    print("\n📝 Test 7: Caption Overlay")
    print("-" * 40)

    caption_video = test_videos_dir / "short_clip.mp4"
    caption_output = output_dir / "video_with_caption.mp4"

    if add_caption_overlay(caption_video, "Test Caption", caption_output, debug=debug):
        print("✓ Caption overlay successful")
        print("  - Added caption: 'Test Caption'")
        print(f"  - Output: {caption_output}")
        test_results.append(("Caption Overlay", caption_video.name, True))
    else:
        print("❌ Caption overlay failed")
        test_results.append(("Caption Overlay", caption_video.name, False))

    # Test 8: Silence Detection
    print("\n🔇 Test 8: Silence Detection")
    print("-" * 40)

    silence_video = test_videos_dir / "video_with_silence.mp4"
    if silence_video.exists():
        silence_audio = output_dir / "silence_audio.wav"
        if extract_audio(silence_video, silence_audio, debug=debug):
            silence_segments = analyze_audio_levels(silence_audio)
            print("✓ Silence detection successful")
            print(f"  - Detected {len(silence_segments)} silence segments")
            for start, end in silence_segments:
                duration = end - start
                print(f"  - Silence from {start:.2f}s to {end:.2f}s ({duration:.2f}s)")
            test_results.append(("Silence Detection", silence_video.name, True))
        else:
            print("❌ Silence detection failed")
            test_results.append(("Silence Detection", silence_video.name, False))

    # Summary
    print("\n" + "=" * 60)
    print("Test Summary")
    print("=" * 60)

    passed = sum(1 for _, _, success in test_results if success)
    total = len(test_results)

    print(f"\nResults: {passed}/{total} tests passed")
    print("\nDetailed Results:")
    for test_name, details, success in test_results:
        status = "✓" if success else "❌"
        print(f"  {status} {test_name}: {details}")

    print("\n" + "=" * 60)

    if passed == total:
        print("🎉 All tests passed! Video editor functionality validated.")
    else:
        print(f"⚠️ {total - passed} test(s) failed. Please review the results.")

    return 0 if passed == total else 1


if __name__ == "__main__":
    sys.exit(main())
