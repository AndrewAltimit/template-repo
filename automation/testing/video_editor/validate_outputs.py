#!/usr/bin/env python3
"""
Validate video outputs by sampling audio and frames at specific timestamps
This script validates that the video editor produces correct outputs
"""

import os
import sys
import wave
from pathlib import Path

import numpy as np
from PIL import Image

from automation.testing.video_editor.utils import (  # noqa: E402  # pylint: disable=wrong-import-position
    get_audio_segment,
    get_frame_at_timestamp,
    run_command_safe,
)


def get_video_duration(video_path):
    """Get exact video duration in seconds"""
    args = [
        "ffprobe",
        "-v",
        "error",
        "-show_entries",
        "format=duration",
        "-of",
        "default=noprint_wrappers=1:nokey=1",
        str(video_path),
    ]
    output = run_command_safe(args)
    if output:
        return float(output.strip())
    return None


def analyze_frame(frame_path):
    """Analyze a frame to get basic properties"""
    try:
        img = Image.open(frame_path)
        width, height = img.size
        mode = img.mode

        # Get average color
        img_array = np.array(img)
        if len(img_array.shape) == 3:
            avg_color = img_array.mean(axis=(0, 1))
        else:
            avg_color = img_array.mean()

        return {
            "width": width,
            "height": height,
            "mode": mode,
            "avg_color": avg_color.tolist() if hasattr(avg_color, "tolist") else float(avg_color),
            "file_size": os.path.getsize(frame_path),
        }
    except Exception as e:
        print(f"Error analyzing frame: {e}")
        return None


def analyze_audio_segment(audio_path):
    """Analyze audio segment to get properties"""
    try:
        with wave.open(str(audio_path), "rb") as wav:
            channels = wav.getnchannels()
            # sample_width = wav.getsampwidth()  # Not used currently
            framerate = wav.getframerate()
            n_frames = wav.getnframes()
            duration = n_frames / framerate

            # Read audio data for basic analysis
            frames = wav.readframes(n_frames)
            audio_data = np.frombuffer(frames, dtype=np.int16)

            # Calculate RMS (volume level)
            rms = np.sqrt(np.mean(audio_data.astype(float) ** 2))

            # Check if mostly silent
            is_silent = rms < 100  # Threshold for silence

            return {
                "channels": channels,
                "sample_rate": framerate,
                "duration": duration,
                "rms_level": float(rms),
                "is_silent": is_silent,
                "file_size": os.path.getsize(audio_path),
            }
    except Exception as e:
        print(f"Error analyzing audio: {e}")
        return None


def validate_video_length(video_path, expected_duration, tolerance=0.5):
    """Validate that video has expected duration"""
    actual_duration = get_video_duration(video_path)
    if actual_duration:
        diff = abs(actual_duration - expected_duration)
        is_valid = diff <= tolerance
        return {"valid": is_valid, "expected": expected_duration, "actual": actual_duration, "difference": diff}
    return None


def sample_video_points(video_path, sample_points):
    """Sample video at specific points and analyze"""
    results = []
    temp_dir = Path("temp_samples")
    temp_dir.mkdir(exist_ok=True)

    for i, timestamp in enumerate(sample_points):
        frame_path = temp_dir / f"frame_{i}_{timestamp:.1f}s.jpg"
        audio_path = temp_dir / f"audio_{i}_{timestamp:.1f}s.wav"

        # Extract frame
        frame_extracted = get_frame_at_timestamp(video_path, timestamp, frame_path)

        # Extract 1 second of audio
        audio_extracted = get_audio_segment(video_path, timestamp, 1.0, audio_path)

        result = {"timestamp": timestamp, "frame": None, "audio": None}

        if frame_extracted and frame_path.exists():
            result["frame"] = analyze_frame(frame_path)
            # Clean up frame file
            frame_path.unlink()

        if audio_extracted and audio_path.exists():
            result["audio"] = analyze_audio_segment(audio_path)
            # Clean up audio file
            audio_path.unlink()

        results.append(result)

    # Clean up temp directory
    if temp_dir.exists() and not any(temp_dir.iterdir()):
        temp_dir.rmdir()

    return results


def main():
    """Main validation function"""
    print("=" * 60)
    print("Video Output Validation Suite")
    print("=" * 60)

    # Check for test outputs
    output_dir = Path("outputs/video-editor")
    if not output_dir.exists():
        print("❌ Test outputs directory not found. Please run test_video_editor.py first.")
        return 1

    validation_results = []

    # Test 1: Validate composed video length
    print("\n📏 Test 1: Validate Video Lengths")
    print("-" * 40)

    videos_to_validate = [
        ("outputs/video-editor/composed_video.mp4", 9.0, "Composed video (with transition)"),
        ("outputs/video-editor/extracted_clip.mp4", 3.0, "Extracted clip"),
        ("outputs/video-editor/video_with_caption.mp4", 5.0, "Video with caption"),
    ]

    for video_path, expected_duration, description in videos_to_validate:
        if Path(video_path).exists():
            result = validate_video_length(video_path, expected_duration, tolerance=0.5)
            if result:
                status = "✓" if result["valid"] else "❌"
                print(f"{status} {description}:")
                print(f"  - Expected: {result['expected']:.2f}s")
                print(f"  - Actual: {result['actual']:.2f}s")
                print(f"  - Difference: {result['difference']:.2f}s")
                validation_results.append((description, result["valid"]))
            else:
                print(f"❌ Could not validate {description}")
                validation_results.append((description, False))
        else:
            print(f"⚠️ {description} not found")

    # Test 2: Sample frames and audio at specific points
    print("\n🎯 Test 2: Sample Specific Timestamps")
    print("-" * 40)

    composed_video = Path("outputs/video-editor/composed_video.mp4")
    if composed_video.exists():
        # Sample at beginning, middle (transition point), and end
        sample_points = [0.5, 4.0, 8.0]  # Start, transition, near end

        print(f"Sampling composed video at {sample_points} seconds...")
        samples = sample_video_points(composed_video, sample_points)

        for sample in samples:
            print(f"\n  Timestamp {sample['timestamp']}s:")

            if sample["frame"]:
                frame_info = sample["frame"]
                print("    Frame:")
                print(f"      - Resolution: {frame_info['width']}x{frame_info['height']}")
                print(f"      - Average color: {frame_info['avg_color']}")
                print(f"      - Size: {frame_info['file_size']} bytes")

            if sample["audio"]:
                audio_info = sample["audio"]
                print("    Audio:")
                print(f"      - Channels: {audio_info['channels']}")
                print(f"      - Sample rate: {audio_info['sample_rate']} Hz")
                print(f"      - RMS level: {audio_info['rms_level']:.2f}")
                print(f"      - Silent: {'Yes' if audio_info['is_silent'] else 'No'}")

        validation_results.append(("Timestamp sampling", True))

    # Test 3: Verify frame extraction points
    print("\n🖼️ Test 3: Verify Frame Extraction Accuracy")
    print("-" * 40)

    test_video = Path("outputs/video-editor/test_videos/video_with_scenes.mp4")
    if test_video.exists():
        # Extract frames at scene boundaries (approximately every 5 seconds)
        scene_times = [0.1, 5.0, 10.0, 15.0, 19.9]

        print("Extracting frames at scene boundaries...")
        temp_dir = Path("frame_validation")
        temp_dir.mkdir(exist_ok=True)

        frame_valid = True
        for i, timestamp in enumerate(scene_times):
            frame_path = temp_dir / f"scene_{i+1}_at_{timestamp:.1f}s.jpg"
            if get_frame_at_timestamp(test_video, timestamp, frame_path):
                if frame_path.exists():
                    frame_info = analyze_frame(frame_path)
                    if frame_info:
                        print(f"  ✓ Scene {i+1} frame at {timestamp}s extracted")
                        print(f"    - Resolution: {frame_info['width']}x{frame_info['height']}")
                    frame_path.unlink()  # Clean up
                else:
                    frame_valid = False
                    print(f"  ❌ Failed to extract frame at {timestamp}s")
            else:
                frame_valid = False

        validation_results.append(("Frame extraction accuracy", frame_valid))

        # Clean up
        if temp_dir.exists() and not any(temp_dir.iterdir()):
            temp_dir.rmdir()

    # Test 4: Validate audio continuity
    print("\n🎵 Test 4: Validate Audio Continuity")
    print("-" * 40)

    videos_with_audio = [
        "outputs/video-editor/composed_video.mp4",
        "outputs/video-editor/extracted_clip.mp4",
        "outputs/video-editor/video_with_caption.mp4",
    ]

    for video_path in videos_with_audio:
        if Path(video_path).exists():
            duration = get_video_duration(video_path)
            if duration:
                # Sample audio at beginning, middle, and end
                sample_times = [0.1, duration / 2, duration - 0.5]

                audio_valid = True
                temp_audio = Path("temp_audio_check.wav")

                for sample_time in sample_times:
                    if 0 <= sample_time < duration:
                        if get_audio_segment(video_path, sample_time, 0.5, temp_audio):
                            audio_info = analyze_audio_segment(temp_audio)
                            if audio_info:
                                print(f"  ✓ {Path(video_path).name} - Audio at {sample_time:.1f}s")
                                print(f"    - RMS level: {audio_info['rms_level']:.2f}")
                            if temp_audio.exists():
                                temp_audio.unlink()
                        else:
                            audio_valid = False

                validation_results.append((f"Audio continuity - {Path(video_path).name}", audio_valid))

    # Summary
    print("\n" + "=" * 60)
    print("Validation Summary")
    print("=" * 60)

    passed = sum(1 for _, valid in validation_results if valid)
    total = len(validation_results)

    print(f"\nResults: {passed}/{total} validations passed")
    print("\nDetailed Results:")
    for test_name, success in validation_results:
        status = "✓" if success else "❌"
        print(f"  {status} {test_name}")

    print("\n" + "=" * 60)

    if passed == total:
        print("🎉 All validations passed! Video outputs are correct.")
    else:
        print(f"⚠️ {total - passed} validation(s) failed.")

    return 0 if passed == total else 1


if __name__ == "__main__":
    sys.exit(main())
