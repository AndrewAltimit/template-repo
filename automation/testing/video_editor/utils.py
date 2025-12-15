#!/usr/bin/env python3
"""
Shared utilities for video editor testing scripts.
Centralizes common functionality to avoid code duplication.
"""

import json
import os
import subprocess
import tempfile
from typing import Any, Dict, List, Optional, Tuple


def run_command_safe(args: List[str], capture_output: bool = True, check: bool = True, debug: bool = False) -> Optional[str]:
    """
    Run a command safely without shell=True.

    Args:
        args: Command and arguments as list
        capture_output: Whether to capture stdout/stderr
        check: Whether to raise exception on non-zero exit
        debug: If True, show stderr output for debugging

    Returns:
        Command stdout if successful, None if failed
    """
    try:
        if capture_output:
            if debug:
                result = subprocess.run(args, capture_output=True, text=True, check=check)
                if result.stderr:
                    print(f"Debug stderr: {result.stderr}")
            else:
                result = subprocess.run(args, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True, check=check)
            return result.stdout
        result = subprocess.run(args, text=True, check=check)
        return ""
    except subprocess.CalledProcessError as e:
        if debug or check:
            print(f"Command failed: {' '.join(args)}")
            if hasattr(e, "stderr") and e.stderr:
                print(f"Error: {e.stderr}")
        return None


def get_video_info(video_path: str) -> Optional[Dict[str, Any]]:
    """
    Get video information using ffprobe.

    Args:
        video_path: Path to video file

    Returns:
        Video metadata as dictionary or None if failed
    """
    args = ["ffprobe", "-v", "quiet", "-print_format", "json", "-show_format", "-show_streams", str(video_path)]

    output = run_command_safe(args)
    if output:
        result: Dict[str, Any] = json.loads(output)
        return result
    return None


def extract_audio(video_path: str, output_path: str, debug: bool = False) -> bool:
    """
    Extract audio from video to WAV format.

    Args:
        video_path: Input video file
        output_path: Output audio file path
        debug: Show ffmpeg stderr for debugging

    Returns:
        True if successful, False otherwise
    """
    args = ["ffmpeg", "-i", str(video_path), "-vn", "-acodec", "pcm_s16le", "-ar", "44100", "-ac", "2", str(output_path), "-y"]

    return run_command_safe(args, capture_output=not debug, debug=debug) is not None


def extract_frames(video_path: str, output_pattern: str, num_frames: int = 5, debug: bool = False) -> bool:
    """
    Extract sample frames from video.

    Args:
        video_path: Input video file
        output_pattern: Output pattern for frame files (e.g., "frame_%03d.jpg")
        num_frames: Extract every Nth frame
        debug: Show ffmpeg stderr for debugging

    Returns:
        True if successful, False otherwise
    """
    args = [
        "ffmpeg",
        "-i",
        str(video_path),
        "-vf",
        f"select=not(mod(n\\,{num_frames}))",
        "-vsync",
        "vfr",
        str(output_pattern),
        "-y",
    ]

    return run_command_safe(args, capture_output=not debug, debug=debug) is not None


def detect_scene_changes(video_path: str, threshold: float = 0.4) -> List[float]:
    """
    Detect scene changes using ffmpeg scene detection filter.

    Args:
        video_path: Input video file
        threshold: Scene change threshold (0.0-1.0)

    Returns:
        List of scene change timestamps
    """
    # pylint: disable=too-many-nested-blocks  # Inherent to ffmpeg output parsing
    # Run ffmpeg without shell=True and process stderr in Python
    args = ["ffmpeg", "-i", str(video_path), "-filter:v", f"select='gt(scene,{threshold})',showinfo", "-f", "null", "-"]

    # Capture stderr where ffmpeg outputs the showinfo data
    result = subprocess.run(args, capture_output=True, text=True, check=False)
    output = result.stderr  # showinfo output goes to stderr

    scenes = []
    if output:
        for line in output.splitlines():
            if "showinfo" in line and "pts_time" in line:
                parts = line.split()
                for part in parts:
                    if part.startswith("pts_time:"):
                        try:
                            time_str = part.split(":")[1]
                            scenes.append(float(time_str))
                        except (ValueError, IndexError):
                            continue

    return scenes


def compose_videos_with_transition(
    video1: str,
    video2: str,
    output_path: str,
    transition_type: str = "fade",
    transition_duration: float = 1.0,
    offset: float = 4.0,
    debug: bool = False,
) -> bool:
    """
    Compose two videos with a transition effect.

    Args:
        video1: First input video
        video2: Second input video
        output_path: Output video path
        transition_type: Type of transition (fade, dissolve, etc.)
        transition_duration: Duration of transition in seconds
        offset: When to start transition
        debug: Show ffmpeg stderr for debugging

    Returns:
        True if successful, False otherwise
    """
    filter_complex = (
        f"[0:v]trim=0:5,setpts=PTS-STARTPTS[v0];"
        f"[1:v]trim=0:5,setpts=PTS-STARTPTS[v1];"
        f"[v0][v1]xfade=transition={transition_type}:duration={transition_duration}:offset={offset}[outv];"
        f"[0:a]atrim=0:5,asetpts=PTS-STARTPTS[a0];"
        f"[1:a]atrim=0:5,asetpts=PTS-STARTPTS[a1];"
        f"[a0][a1]acrossfade=d={transition_duration}[outa]"
    )

    args = [
        "ffmpeg",
        "-i",
        str(video1),
        "-i",
        str(video2),
        "-filter_complex",
        filter_complex,
        "-map",
        "[outv]",
        "-map",
        "[outa]",
        "-c:v",
        "libx264",
        "-preset",
        "fast",
        str(output_path),
        "-y",
    ]

    return run_command_safe(args, capture_output=not debug, debug=debug) is not None


def extract_clip(video_path: str, start_time: float, duration: float, output_path: str, debug: bool = False) -> bool:
    """
    Extract a clip from video.

    Args:
        video_path: Input video file
        start_time: Start time in seconds
        duration: Duration in seconds
        output_path: Output clip path
        debug: Show ffmpeg stderr for debugging

    Returns:
        True if successful, False otherwise
    """
    args = ["ffmpeg", "-i", str(video_path), "-ss", str(start_time), "-t", str(duration), "-c", "copy", str(output_path), "-y"]

    return run_command_safe(args, capture_output=not debug, debug=debug) is not None


def add_caption_overlay(video_path: str, caption_text: str, output_path: str, debug: bool = False) -> bool:
    """
    Add caption overlay to video.

    Args:
        video_path: Input video file
        caption_text: Text to overlay
        output_path: Output video path
        debug: Show ffmpeg stderr for debugging

    Returns:
        True if successful, False otherwise
    """
    # Use a temporary file for the text to avoid injection risks
    with tempfile.NamedTemporaryFile(mode="w", delete=False, suffix=".txt") as tmp:
        tmp.write(caption_text)
        text_filepath = tmp.name

    try:
        filter_str = (
            f"drawtext=textfile='{text_filepath}':fontcolor=white:fontsize=24:box=1:"
            f"boxcolor=black@0.5:boxborderw=5:x=(w-text_w)/2:y=h-th-10"
        )

        args = ["ffmpeg", "-i", str(video_path), "-vf", filter_str, "-codec:a", "copy", str(output_path), "-y"]

        result = run_command_safe(args, capture_output=not debug, debug=debug) is not None
    finally:
        # Clean up the temporary file
        if os.path.exists(text_filepath):
            os.remove(text_filepath)

    return result


def analyze_audio_levels(audio_path: str, noise_level: str = "-50dB", min_duration: float = 0.5) -> List[Tuple[float, float]]:
    """
    Analyze audio levels to detect silence segments.

    Args:
        audio_path: Input audio file
        noise_level: Noise threshold for silence detection
        min_duration: Minimum duration for silence segment

    Returns:
        List of (start, end) tuples for silence segments
    """
    # pylint: disable=too-many-nested-blocks  # Inherent to ffmpeg output parsing
    # Run ffmpeg without shell=True and process stderr in Python
    args = ["ffmpeg", "-i", str(audio_path), "-af", f"silencedetect=n={noise_level}:d={min_duration}", "-f", "null", "-"]

    # Capture stderr where ffmpeg outputs the silence detection info
    result = subprocess.run(args, capture_output=True, text=True, check=False)
    output = result.stderr  # silencedetect output goes to stderr

    silence_segments = []
    if output:
        lines = output.splitlines()
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
                # Capture start_time before any modifications in this block
                current_start: float = start_time
                parts = line.split()
                for part in parts:
                    if part.startswith("silence_end:"):
                        try:
                            end_time = float(part.split(":")[1])
                            silence_segments.append((current_start, end_time))
                            start_time = None
                        except (ValueError, IndexError):
                            continue

    return silence_segments


def get_frame_at_timestamp(video_path: str, timestamp: float, output_path: str, debug: bool = False) -> bool:
    """
    Extract a single frame at specific timestamp.

    Args:
        video_path: Input video file
        timestamp: Timestamp in seconds
        output_path: Output image path
        debug: Show ffmpeg stderr for debugging

    Returns:
        True if successful, False otherwise
    """
    args = ["ffmpeg", "-ss", str(timestamp), "-i", str(video_path), "-frames:v", "1", str(output_path), "-y"]

    return run_command_safe(args, capture_output=not debug, debug=debug) is not None


def get_audio_segment(audio_path: str, start_time: float, duration: float, output_path: str, debug: bool = False) -> bool:
    """
    Extract audio segment from file.

    Args:
        audio_path: Input audio file
        start_time: Start time in seconds
        duration: Duration in seconds
        output_path: Output audio path
        debug: Show ffmpeg stderr for debugging

    Returns:
        True if successful, False otherwise
    """
    args = ["ffmpeg", "-i", str(audio_path), "-ss", str(start_time), "-t", str(duration), "-c", "copy", str(output_path), "-y"]

    return run_command_safe(args, capture_output=not debug, debug=debug) is not None
