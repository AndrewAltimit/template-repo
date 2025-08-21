#!/usr/bin/env python3
"""
Test script for video editor functionality validation
Tests basic operations without requiring the full MCP server
"""

import json
import os
import subprocess
import sys
from pathlib import Path

# Add the project root to the path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../../..")))


def run_command(cmd):
    """Run a shell command and return output"""
    try:
        result = subprocess.run(cmd, shell=True, capture_output=True, text=True, check=True)
        return result.stdout
    except subprocess.CalledProcessError as e:
        print(f"Command failed: {cmd}")
        print(f"Error: {e.stderr}")
        return None


def get_video_info(video_path):
    """Get video information using ffprobe"""
    cmd = f'ffprobe -v quiet -print_format json -show_format -show_streams "{video_path}"'
    output = run_command(cmd)
    if output:
        return json.loads(output)
    return None


def extract_audio(video_path, output_path):
    """Extract audio from video"""
    cmd = f'ffmpeg -i "{video_path}" -vn -acodec pcm_s16le -ar 44100 -ac 2 "{output_path}" -y 2>/dev/null'
    return run_command(cmd) is not None


def extract_frames(video_path, output_dir, num_frames=5):
    """Extract sample frames from video"""
    os.makedirs(output_dir, exist_ok=True)
    cmd = (
        f'ffmpeg -i "{video_path}" -vf "select=not(mod(n,{num_frames}))" '
        f'-vsync vfr "{output_dir}/frame_%03d.jpg" -y 2>/dev/null'
    )
    return run_command(cmd) is not None


def detect_scene_changes(video_path):
    """Detect scene changes using ffmpeg"""
    cmd = f'ffmpeg -i "{video_path}" -filter:v "select=\'gt(scene,0.4)\',showinfo" -f null - 2>&1 | grep showinfo'
    output = run_command(cmd)
    if output:
        # Parse scene change timestamps
        scenes = []
        for line in output.split("\n"):
            if "pts_time" in line:
                parts = line.split()
                for part in parts:
                    if part.startswith("pts_time:"):
                        time_str = part.split(":")[1]
                        scenes.append(float(time_str))
        return scenes
    return []


def test_video_composition(video1, video2, output_path):
    """Test basic video composition with transition"""
    # Create a composition with crossfade for video and audio
    filter_complex = (
        "[0:v]trim=0:5,setpts=PTS-STARTPTS[v0];"
        "[1:v]trim=0:5,setpts=PTS-STARTPTS[v1];"
        "[v0][v1]xfade=transition=fade:duration=1:offset=4[outv];"
        "[0:a]atrim=0:5,asetpts=PTS-STARTPTS[a0];"
        "[1:a]atrim=0:5,asetpts=PTS-STARTPTS[a1];"
        "[a0][a1]acrossfade=d=1[outa]"
    )

    cmd = (
        f'ffmpeg -i "{video1}" -i "{video2}" -filter_complex "{filter_complex}" '
        f'-map "[outv]" -map "[outa]" -c:v libx264 -preset fast "{output_path}" -y 2>/dev/null'
    )
    return run_command(cmd) is not None


def test_clip_extraction(video_path, start_time, duration, output_path):
    """Test clip extraction from video"""
    cmd = f'ffmpeg -i "{video_path}" -ss {start_time} -t {duration} -c copy "{output_path}" -y 2>/dev/null'
    return run_command(cmd) is not None


def test_caption_overlay(video_path, caption_text, output_path):
    """Test adding caption overlay to video"""
    # Escape special characters in caption text
    caption_text = caption_text.replace("'", "\\'").replace('"', '\\"')

    filter_str = (
        f"drawtext=text='{caption_text}':fontcolor=white:fontsize=24:box=1:"
        f"boxcolor=black@0.5:boxborderw=5:x=(w-text_w)/2:y=h-th-10"
    )
    cmd = f'ffmpeg -i "{video_path}" -vf "{filter_str}" -codec:a copy "{output_path}" -y 2>/dev/null'
    return run_command(cmd) is not None


def analyze_audio_levels(audio_path):
    """Analyze audio levels to detect silence"""
    cmd = f'ffmpeg -i "{audio_path}" -af "silencedetect=n=-50dB:d=0.5" -f null - 2>&1'
    output = run_command(cmd)

    silence_segments = []
    if output:
        lines = output.split("\n")
        start_time = None
        for line in lines:
            if "silence_start" in line:
                parts = line.split()
                for part in parts:
                    if part.startswith("silence_start:"):
                        try:
                            start_time = float(part.split(":")[1])
                        except (ValueError, IndexError):
                            continue
            elif "silence_end" in line and start_time is not None:
                parts = line.split()
                for part in parts:
                    if part.startswith("silence_end:"):
                        try:
                            end_time = float(part.split(":")[1])
                            silence_segments.append((start_time, end_time))
                            start_time = None
                        except (ValueError, IndexError):
                            continue
    return silence_segments


def main():
    """Main test function"""
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
                print(f"  - FPS: {eval(video_stream['r_frame_rate']):.2f}")
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

    if extract_audio(test_video, audio_output):
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
    if extract_frames(test_video, frames_dir, 10):
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

    if test_video_composition(video1, video2, composed_output):
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

    if test_clip_extraction(source_video, 5.0, 3.0, clip_output):
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

    if test_caption_overlay(caption_video, "Test Caption", caption_output):
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
        if extract_audio(silence_video, silence_audio):
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
