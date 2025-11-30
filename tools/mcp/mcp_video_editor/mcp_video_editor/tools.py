"""Video editor tools for MCP"""

import hashlib
import json
import os
from pathlib import Path
from typing import Any, Dict, List, Optional, cast

# Tool registry
TOOLS = {}


def register_tool(name: str):
    """Decorator to register a tool"""

    def decorator(func):
        TOOLS[name] = func
        return func

    return decorator


@register_tool("video_editor/analyze")
async def analyze_video(
    video_inputs: List[str], analysis_options: Optional[Dict[str, bool]] = None, _server=None, **_kwargs
) -> Dict[str, Any]:
    """Analyze video content without rendering, returns metadata and suggested edits"""
    # pylint: disable=too-many-nested-blocks  # Video analysis requires nested processing

    if not _server:
        return {"error": "Server context not provided"}

    if not video_inputs:
        return {"error": "No video inputs provided"}

    # Default analysis options
    if analysis_options is None:
        analysis_options = {"transcribe": True, "identify_speakers": True, "detect_scenes": True, "extract_highlights": True}

    _server.logger.info("Analyzing %s video(s)", len(video_inputs))

    try:
        results: Dict[str, Any] = {"video_inputs": video_inputs, "analysis": {}}

        for video_path in video_inputs:
            if not os.path.exists(video_path):
                return {"error": f"Video file not found: {video_path}"}

            video_analysis = {"file": video_path, "file_size": os.path.getsize(video_path)}

            # Extract audio for analysis
            audio_path = _server.audio_processor.extract_audio(video_path)

            try:
                # Transcription
                if analysis_options.get("transcribe", True):
                    _server.logger.info("Performing transcription...")
                    transcript = _server.audio_processor.transcribe(audio_path)
                    video_analysis["transcript"] = transcript

                # Speaker identification
                if analysis_options.get("identify_speakers", True):
                    _server.logger.info("Identifying speakers...")
                    diarization = _server.audio_processor.diarize_speakers(audio_path)
                    video_analysis["speakers"] = diarization["speakers"]

                    # Combine transcript with speakers if both available
                    if "transcript" in video_analysis:
                        combined = _server.audio_processor.combine_transcript_with_speakers(transcript, diarization)
                        video_analysis["segments_with_speakers"] = combined["segments_with_speakers"]

                # Audio analysis
                _server.logger.info("Analyzing audio levels...")
                audio_analysis = _server.audio_processor.analyze_audio_levels(audio_path)
                video_analysis["audio_analysis"] = audio_analysis

                # Scene detection
                if analysis_options.get("detect_scenes", True):
                    _server.logger.info("Detecting scene changes...")
                    scene_changes = _server.video_processor.detect_scene_changes(video_path)
                    video_analysis["scene_changes"] = scene_changes

                # Extract highlights based on audio peaks and keywords
                if analysis_options.get("extract_highlights", True):
                    highlights = []

                    # Audio-based highlights
                    if "audio_analysis" in video_analysis:
                        for peak_time in audio_analysis.get("peak_moments", []):
                            highlights.append({"time": peak_time, "type": "audio_peak", "confidence": 0.8})

                    # Keyword-based highlights (if transcript available)
                    if "transcript" in video_analysis:
                        highlight_keywords = ["important", "key point", "summary", "conclusion", "remember"]
                        transcript = cast(Dict[str, Any], video_analysis["transcript"])
                        for segment in transcript.get("segments", []):
                            text_lower = segment["text"].lower()
                            for keyword in highlight_keywords:
                                if keyword in text_lower:
                                    highlights.append(
                                        {
                                            "time": segment["start"],
                                            "type": "keyword",
                                            "keyword": keyword,
                                            "text": segment["text"],
                                            "confidence": 0.9,
                                        }
                                    )

                    video_analysis["highlights"] = highlights

                # Generate editing suggestions
                video_analysis["suggested_edits"] = _generate_edit_suggestions(video_analysis)

            finally:
                # Clean up temp audio file
                if os.path.exists(audio_path):
                    os.unlink(audio_path)

            results["analysis"][video_path] = video_analysis

        return results

    except Exception as e:
        _server.logger.error("Analysis failed: %s", e)
        return {"error": str(e)}


# Default editing rules for create_edit
DEFAULT_EDITING_RULES: Dict[str, Any] = {
    "switch_on_speaker": True,
    "speaker_switch_delay": 0.5,
    "picture_in_picture": "auto",
    "zoom_on_emphasis": True,
    "remove_silence": True,
    "silence_threshold": 2.0,
}


def _determine_source_video(
    speaker: Optional[str],
    speaker_mapping: Optional[Dict[str, str]],
    video_inputs: List[str],
    primary_video: str,
    logger: Any,
) -> str:
    """Determine which video to use for a speaker."""
    if speaker_mapping and speaker and speaker in speaker_mapping:
        return speaker_mapping[speaker]
    if speaker and len(video_inputs) > 1:
        speaker_hash = hashlib.md5(speaker.encode()).hexdigest()
        speaker_idx = int(speaker_hash, 16) % len(video_inputs)
        logger.warning(
            "No explicit mapping for speaker '%s'. "
            "Auto-mapping to video %s (%s) using deterministic hash. "
            "For predictable results, provide explicit speaker_mapping.",
            speaker,
            speaker_idx,
            video_inputs[speaker_idx],
        )
        return video_inputs[speaker_idx]
    return primary_video


def _check_highlight_overlap(start_time: float, end_time: float, highlights: List[Dict]) -> bool:
    """Check if a segment contains any highlights."""
    return any(start_time <= h["time"] <= end_time for h in highlights)


def _check_overlapping_speakers(
    segment: Dict, segments: List[Dict], start_time: float, end_time: float, speaker: Optional[str]
) -> bool:
    """Check for overlapping speakers in other segments."""
    for other in segments:
        if other == segment:
            continue
        if other["start"] < end_time and other["end"] > start_time and other.get("speaker") != speaker:
            return True
    return False


def _process_speaker_segments(
    segments: List[Dict],
    editing_rules: Dict[str, Any],
    speaker_mapping: Optional[Dict[str, str]],
    video_inputs: List[str],
    primary_video: str,
    primary_analysis: Dict[str, Any],
    logger: Any,
) -> List[Dict[str, Any]]:
    """Process segments with speakers into edit decisions."""
    edit_list: List[Dict[str, Any]] = []
    speaker_switch_delay = editing_rules.get("speaker_switch_delay", 0.5)
    last_speaker: Optional[str] = None
    last_switch_time: float = 0
    current_time: float = 0.0

    for segment in segments:
        speaker = segment.get("speaker")
        start_time = segment["start"]
        end_time = segment["end"]
        duration = end_time - start_time

        source_video = _determine_source_video(speaker, speaker_mapping, video_inputs, primary_video, logger)

        should_switch = speaker != last_speaker and (current_time - last_switch_time) > speaker_switch_delay

        decision: Dict[str, Any] = {
            "timestamp": start_time,
            "duration": duration,
            "source": source_video,
            "action": "transition" if should_switch else "show",
            "effects": [],
        }

        if should_switch:
            decision["transition_type"] = "cross_dissolve"
            last_speaker = speaker
            last_switch_time = current_time

        if editing_rules.get("zoom_on_emphasis"):
            if _check_highlight_overlap(start_time, end_time, primary_analysis.get("highlights", [])):
                decision["effects"].append("zoom_in")

        if editing_rules.get("picture_in_picture") == "auto" and len(video_inputs) > 1:
            if _check_overlapping_speakers(segment, segments, start_time, end_time, speaker):
                decision["effects"].append("picture_in_picture")
                decision["pip_size"] = editing_rules.get("pip_size", 0.25)

        edit_list.append(decision)
        current_time = end_time

    return edit_list


def _process_scene_changes(scene_changes: List[float], video_inputs: List[str]) -> List[Dict[str, Any]]:
    """Create edit decisions based on scene changes."""
    edit_list: List[Dict[str, Any]] = []
    last_time = 0.0
    for i, scene_time in enumerate(scene_changes):
        duration = scene_time - last_time
        if duration > 0.5:
            source_idx = i % len(video_inputs)
            edit_list.append(
                {
                    "timestamp": last_time,
                    "duration": duration,
                    "source": video_inputs[source_idx],
                    "action": "show" if i == 0 else "transition",
                    "transition_type": "cross_dissolve" if i > 0 else None,
                    "effects": [],
                }
            )
            last_time = scene_time
    return edit_list


def _process_fixed_intervals(duration: float, video_inputs: List[str], interval: float = 10.0) -> List[Dict[str, Any]]:
    """Create edit decisions based on fixed time intervals."""
    edit_list: List[Dict[str, Any]] = []
    for i in range(int(duration / interval)):
        source_idx = i % len(video_inputs)
        edit_list.append(
            {
                "timestamp": i * interval,
                "duration": interval,
                "source": video_inputs[source_idx],
                "action": "show" if i == 0 else "transition",
                "transition_type": "cross_dissolve" if i > 0 else None,
                "effects": [],
            }
        )
    return edit_list


def _filter_silence(
    edit_list: List[Dict[str, Any]],
    silence_segments: List[tuple],
    silence_threshold: float,
) -> List[Dict[str, Any]]:
    """Filter out decisions that fall within silence segments."""
    filtered = []
    for decision in edit_list:
        start = decision["timestamp"]
        end = start + decision["duration"]
        is_silent = any(
            silence_end - silence_start >= silence_threshold and start >= silence_start and end <= silence_end
            for silence_start, silence_end in silence_segments
        )
        if not is_silent:
            filtered.append(decision)
    return filtered


@register_tool("video_editor/create_edit")
async def create_edit(
    video_inputs: List[str],
    editing_rules: Optional[Dict[str, Any]] = None,
    speaker_mapping: Optional[Dict[str, str]] = None,
    _server=None,
    **_kwargs,
) -> Dict[str, Any]:
    """Generate an edit decision list (EDL) based on rules without rendering"""
    if not _server:
        return {"error": "Server context not provided"}

    if not video_inputs:
        return {"error": "No video inputs provided"}

    # Use default rules if not provided
    if editing_rules is None:
        editing_rules = DEFAULT_EDITING_RULES.copy()

    _server.logger.info("Creating edit for %s video(s)", len(video_inputs))

    try:
        # First analyze the videos
        analysis_result = await analyze_video(
            video_inputs=video_inputs,
            analysis_options={
                "transcribe": True,
                "identify_speakers": editing_rules.get("switch_on_speaker", False),
                "detect_scenes": True,
                "extract_highlights": editing_rules.get("zoom_on_emphasis", False),
            },
            _server=_server,
        )

        if "error" in analysis_result:
            return analysis_result  # type: ignore[no-any-return]

        # Process based on primary video
        primary_video = video_inputs[0]
        primary_analysis = analysis_result["analysis"][primary_video]

        # Generate edit decision list based on available data
        has_speakers = "segments_with_speakers" in primary_analysis and editing_rules.get("switch_on_speaker")

        if has_speakers:
            edit_decision_list = _process_speaker_segments(
                segments=primary_analysis["segments_with_speakers"],
                editing_rules=editing_rules,
                speaker_mapping=speaker_mapping,
                video_inputs=video_inputs,
                primary_video=primary_video,
                primary_analysis=primary_analysis,
                logger=_server.logger,
            )
        else:
            # Fallback: scene changes or fixed intervals
            scene_changes = primary_analysis.get("scene_changes", [])
            if scene_changes:
                edit_decision_list = _process_scene_changes(scene_changes, video_inputs)
            else:
                duration = primary_analysis.get("audio_analysis", {}).get("duration", 60)
                edit_decision_list = _process_fixed_intervals(duration, video_inputs)

        # Remove silence if requested
        if editing_rules.get("remove_silence"):
            silence_segments = primary_analysis.get("audio_analysis", {}).get("silence_segments", [])
            edit_decision_list = _filter_silence(
                edit_decision_list,
                silence_segments,
                editing_rules.get("silence_threshold", 2.0),
            )

        # Calculate estimated duration
        estimated_duration = sum(d["duration"] for d in edit_decision_list)

        # Save EDL to file
        edl_filename = f"edit_{_server.job_counter}.json"
        edl_path = os.path.join(_server.edl_dir, edl_filename)

        with open(edl_path, "w", encoding="utf-8") as f:
            json.dump(edit_decision_list, f, indent=2)

        return {
            "edit_decision_list": edit_decision_list,
            "estimated_duration": estimated_duration,
            "edl_file": edl_path,
            "video_inputs": video_inputs,
            "editing_rules": editing_rules,
        }

    except Exception as e:
        _server.logger.error("Edit creation failed: %s", e)
        return {"error": str(e)}


@register_tool("video_editor/render")
async def render_video(
    video_inputs: List[str],
    edit_decision_list: Optional[List[Dict[str, Any]]] = None,
    output_settings: Optional[Dict[str, Any]] = None,
    render_options: Optional[Dict[str, Any]] = None,
    _server=None,
    **_kwargs,
) -> Dict[str, Any]:
    """Execute the actual video rendering based on EDL or automatic rules"""

    if not _server:
        return {"error": "Server context not provided"}

    if not video_inputs:
        return {"error": "No video inputs provided"}

    # Default output settings
    if output_settings is None:
        output_settings = {
            "format": "mp4",
            "resolution": "1920x1080",
            "fps": 30,
            "bitrate": "8M",
            "output_path": os.path.join(_server.renders_dir, f"rendered_{_server.job_counter}.mp4"),
        }

    # Default render options
    if render_options is None:
        render_options = {
            "hardware_acceleration": True,
            "preview_mode": False,
            "add_captions": False,
            "add_speaker_labels": False,
        }

    # Create a job for tracking
    job_id = _server.create_job("render")

    try:
        _server.update_job(job_id, {"status": "running", "stage": "preparing", "progress": 5})

        # Generate EDL if not provided
        if edit_decision_list is None:
            _server.logger.info("No EDL provided, generating automatically...")
            _server.update_job(job_id, {"stage": "generating_edl", "progress": 10})

            edit_result = await create_edit(video_inputs=video_inputs, _server=_server)

            if "error" in edit_result:
                raise RuntimeError(edit_result["error"])

            edit_decision_list = edit_result["edit_decision_list"]

        _server.update_job(job_id, {"stage": "loading_videos", "progress": 20})

        # Create the composed video from EDL
        composed_video = _server.video_processor.create_edit_from_edl(video_inputs, edit_decision_list, output_settings)

        # Add captions if requested
        if render_options.get("add_captions"):
            _server.update_job(job_id, {"stage": "adding_captions", "progress": 40})

            # Get transcript for captions
            primary_video = video_inputs[0]
            audio_path = _server.audio_processor.extract_audio(primary_video)

            try:
                transcript = _server.audio_processor.transcribe(audio_path)

                # Convert transcript segments to caption format
                captions = []
                for segment in transcript.get("segments", []):
                    caption = {"text": segment["text"], "start": segment["start"], "end": segment["end"]}

                    # Add speaker if available
                    if "speaker" in segment:
                        caption["speaker"] = segment["speaker"]

                    captions.append(caption)

                # Apply captions
                caption_style = {
                    "size": 42,
                    "color": "white",
                    "font": "Arial",
                    "position": "bottom",
                    "display_speaker_names": render_options.get("add_speaker_labels", False),
                }

                composed_video = _server.video_processor.add_captions_to_video(composed_video, captions, caption_style)

            finally:
                if os.path.exists(audio_path):
                    os.unlink(audio_path)

        # Update job status before rendering (MoviePy doesn't support real-time progress)
        _server.update_job(job_id, {"stage": "rendering", "progress": 60})

        # Adjust settings for preview mode
        if render_options.get("preview_mode"):
            output_settings["resolution"] = "640x360"
            output_settings["bitrate"] = "2M"
            output_settings["fps"] = 15

        # Set codec based on hardware acceleration
        if render_options.get("hardware_acceleration") and _server.config["performance"]["enable_gpu"]:
            # Try to use hardware encoder
            import subprocess

            try:
                # Check for NVENC support
                result = subprocess.run(["ffmpeg", "-encoders"], capture_output=True, text=True, check=False)
                if "h264_nvenc" in result.stdout:
                    output_settings["codec"] = "h264_nvenc"
                elif "h264_qsv" in result.stdout:
                    output_settings["codec"] = "h264_qsv"
                else:
                    output_settings["codec"] = "libx264"
            except Exception:
                output_settings["codec"] = "libx264"
        else:
            output_settings["codec"] = "libx264"

        # Render the video
        output_path = output_settings.get("output_path")

        # Note: MoviePy doesn't support real-time progress callbacks
        # The rendering will show a progress bar in the logs
        _server.logger.info("Starting video rendering (progress will be shown in logs)...")
        render_result = _server.video_processor.render_video(composed_video, output_path, output_settings)

        # Update job status after rendering
        _server.update_job(job_id, {"stage": "finalizing", "progress": 95})

        # Generate transcript file if captions were added
        transcript_path = None
        if render_options.get("add_captions"):
            transcript_path = output_path.replace(".mp4", ".srt")  # type: ignore[union-attr]
            _generate_srt_file(transcript, transcript_path)
            render_result["transcript_path"] = transcript_path

        # Update job with result
        _server.update_job(job_id, {"status": "completed", "stage": "done", "progress": 100, "result": render_result})

        return render_result  # type: ignore[no-any-return]

    except Exception as e:
        _server.logger.error("Rendering failed: %s", e)
        _server.update_job(job_id, {"status": "failed", "error": str(e)})
        return {"error": str(e), "job_id": job_id}


def _extract_time_range_clips(
    video_input: str,
    extraction_criteria: Dict[str, Any],
    output_dir: str,
    clips_extracted: List[Dict[str, Any]],
    _server,
) -> None:
    """Extract clips based on time ranges.

    Args:
        video_input: Path to input video
        extraction_criteria: Extraction configuration
        output_dir: Output directory for clips
        clips_extracted: List to append extracted clips to
        _server: Server context
    """
    for time_range in extraction_criteria.get("time_ranges", []):
        start_time = time_range[0] - extraction_criteria.get("padding", 0)
        end_time = time_range[1] + extraction_criteria.get("padding", 0)

        duration = end_time - start_time
        if duration < extraction_criteria.get("min_clip_length", 0):
            continue
        if duration > extraction_criteria.get("max_clip_length", float("inf")):
            end_time = start_time + extraction_criteria["max_clip_length"]

        output_path = os.path.join(output_dir, f"clip_{len(clips_extracted)+1}_time_{start_time:.1f}-{end_time:.1f}.mp4")
        _server.video_processor.extract_clip(video_input, max(0, start_time), end_time, output_path)

        clips_extracted.append(
            {
                "output_path": output_path,
                "start_time": start_time,
                "end_time": end_time,
                "duration": end_time - start_time,
                "criteria": "time_range",
            }
        )


def _extract_keyword_clips(
    video_input: str,
    extraction_criteria: Dict[str, Any],
    video_analysis: Dict[str, Any],
    output_dir: str,
    clips_extracted: List[Dict[str, Any]],
    _server,
) -> None:
    """Extract clips based on keywords in transcript.

    Args:
        video_input: Path to input video
        extraction_criteria: Extraction configuration
        video_analysis: Video analysis results
        output_dir: Output directory for clips
        clips_extracted: List to append extracted clips to
        _server: Server context
    """
    keywords = [k.lower() for k in extraction_criteria["keywords"]]

    for segment in video_analysis.get("transcript", {}).get("segments", []):
        text_lower = segment["text"].lower()

        for keyword in keywords:
            if keyword in text_lower:
                start_time = segment["start"] - extraction_criteria.get("padding", 0)
                end_time = segment["end"] + extraction_criteria.get("padding", 0)

                duration = end_time - start_time
                if duration < extraction_criteria.get("min_clip_length", 0):
                    center = (start_time + end_time) / 2
                    half_min = extraction_criteria["min_clip_length"] / 2
                    start_time = center - half_min
                    end_time = center + half_min

                if duration > extraction_criteria.get("max_clip_length", float("inf")):
                    end_time = start_time + extraction_criteria["max_clip_length"]

                output_path = os.path.join(
                    output_dir, f"clip_{len(clips_extracted)+1}_keyword_{keyword.replace(' ', '_')}.mp4"
                )
                _server.video_processor.extract_clip(video_input, max(0, start_time), end_time, output_path)

                clips_extracted.append(
                    {
                        "output_path": output_path,
                        "start_time": start_time,
                        "end_time": end_time,
                        "duration": end_time - start_time,
                        "criteria": "keyword",
                        "keyword": keyword,
                        "text": segment["text"],
                    }
                )
                break  # Only extract once per segment


def _extract_speaker_clips(
    video_input: str,
    extraction_criteria: Dict[str, Any],
    video_analysis: Dict[str, Any],
    output_dir: str,
    clips_extracted: List[Dict[str, Any]],
    _server,
) -> None:
    """Extract clips based on speaker segments.

    Args:
        video_input: Path to input video
        extraction_criteria: Extraction configuration
        video_analysis: Video analysis results
        output_dir: Output directory for clips
        clips_extracted: List to append extracted clips to
        _server: Server context
    """
    target_speakers = extraction_criteria["speakers"]

    for segment in video_analysis.get("segments_with_speakers", []):
        if segment.get("speaker") in target_speakers:
            start_time = segment["start"] - extraction_criteria.get("padding", 0)
            end_time = segment["end"] + extraction_criteria.get("padding", 0)

            output_path = os.path.join(output_dir, f"clip_{len(clips_extracted)+1}_speaker_{segment['speaker']}.mp4")
            _server.video_processor.extract_clip(video_input, max(0, start_time), end_time, output_path)

            clips_extracted.append(
                {
                    "output_path": output_path,
                    "start_time": start_time,
                    "end_time": end_time,
                    "duration": end_time - start_time,
                    "criteria": "speaker",
                    "speaker": segment["speaker"],
                    "text": segment.get("text", ""),
                }
            )


@register_tool("video_editor/extract_clips")
async def extract_clips(
    video_input: str,
    extraction_criteria: Optional[Dict[str, Any]] = None,
    output_dir: Optional[str] = None,
    _server=None,
    **_kwargs,
) -> Dict[str, Any]:
    """Create short clips based on transcript keywords or timestamps"""
    if not _server:
        return {"error": "Server context not provided"}

    if not os.path.exists(video_input):
        return {"error": f"Video file not found: {video_input}"}

    if extraction_criteria is None:
        extraction_criteria = {
            "keywords": [],
            "speakers": [],
            "time_ranges": [],
            "min_clip_length": 3.0,
            "max_clip_length": 60.0,
            "padding": 0.5,
        }

    if output_dir is None:
        output_dir = _server.clips_dir

    _server.logger.info("Extracting clips from: %s", video_input)

    try:
        clips_extracted: List[Dict[str, Any]] = []
        video_analysis: Dict[str, Any] = {}

        need_analysis = extraction_criteria.get("keywords") or extraction_criteria.get("speakers")

        if need_analysis:
            analysis_result = await analyze_video(
                video_inputs=[video_input],
                analysis_options={
                    "transcribe": bool(extraction_criteria.get("keywords")),
                    "identify_speakers": bool(extraction_criteria.get("speakers")),
                },
                _server=_server,
            )
            if "error" in analysis_result:
                return analysis_result  # type: ignore[no-any-return]
            video_analysis = analysis_result["analysis"][video_input]

        _extract_time_range_clips(video_input, extraction_criteria, output_dir, clips_extracted, _server)

        if extraction_criteria.get("keywords") and need_analysis:
            _extract_keyword_clips(video_input, extraction_criteria, video_analysis, output_dir, clips_extracted, _server)

        if extraction_criteria.get("speakers") and need_analysis:
            _extract_speaker_clips(video_input, extraction_criteria, video_analysis, output_dir, clips_extracted, _server)

        return {
            "video_input": video_input,
            "clips_extracted": clips_extracted,
            "total_clips": len(clips_extracted),
            "output_directory": output_dir,
        }

    except Exception as e:
        _server.logger.error("Clip extraction failed: %s", e)
        return {"error": str(e)}


@register_tool("video_editor/add_captions")
async def add_captions(
    video_input: str,
    caption_style: Optional[Dict[str, Any]] = None,
    languages: Optional[List[str]] = None,
    output_path: Optional[str] = None,
    _server=None,
    **_kwargs,
) -> Dict[str, Any]:
    """Add styled captions to existing video using transcript"""

    if not _server:
        return {"error": "Server context not provided"}

    if not os.path.exists(video_input):
        return {"error": f"Video file not found: {video_input}"}

    # Default caption style
    if caption_style is None:
        caption_style = {
            "font": "Arial",
            "size": 42,
            "color": "#FFFFFF",
            "background": "#000000",
            "position": "bottom",
            "max_chars_per_line": 40,
            "display_speaker_names": True,
        }

    if languages is None:
        languages = ["en"]  # Default to English

    if output_path is None:
        output_path = os.path.join(_server.renders_dir, f"captioned_{Path(video_input).stem}.mp4")

    _server.logger.info("Adding captions to: %s", video_input)

    try:
        # Load the video
        video_clip = _server.video_processor.load_video(video_input)

        results = {"video_input": video_input, "languages_processed": []}

        for language in languages:
            _server.logger.info("Processing captions for language: %s", language)

            # Extract audio and transcribe
            audio_path = _server.audio_processor.extract_audio(video_input)

            try:
                # Transcribe with specific language
                transcript = _server.audio_processor.transcribe(audio_path, language=None if language == "auto" else language)

                # Also get speaker diarization if requested
                captions = []
                if caption_style.get("display_speaker_names"):
                    diarization = _server.audio_processor.diarize_speakers(audio_path)
                    combined = _server.audio_processor.combine_transcript_with_speakers(transcript, diarization)

                    for segment in combined.get("segments_with_speakers", []):
                        caption = {
                            "text": segment["text"],
                            "start": segment["start"],
                            "end": segment["end"],
                            "speaker": segment.get("speaker", "Unknown"),
                        }
                        captions.append(caption)
                else:
                    for segment in transcript.get("segments", []):
                        caption = {"text": segment["text"], "start": segment["start"], "end": segment["end"]}
                        captions.append(caption)

                # Add captions to video
                video_with_captions = _server.video_processor.add_captions_to_video(video_clip, captions, caption_style)

                # Save video with language suffix if multiple languages
                if len(languages) > 1:
                    lang_output_path = output_path.replace(".mp4", f"_{language}.mp4")
                else:
                    lang_output_path = output_path

                # Render the video
                _server.video_processor.render_video(
                    video_with_captions,
                    lang_output_path,
                    {"fps": video_clip.fps, "resolution": f"{video_clip.w}x{video_clip.h}", "bitrate": "8M"},
                )

                # Generate SRT subtitle file
                srt_path = lang_output_path.replace(".mp4", ".srt")
                _generate_srt_file(transcript, srt_path)

                results["languages_processed"].append(  # type: ignore[attr-defined]
                    {
                        "language": transcript.get("language", language),
                        "output_path": lang_output_path,
                        "srt_path": srt_path,
                        "caption_count": len(captions),
                    }
                )

            finally:
                if os.path.exists(audio_path):
                    os.unlink(audio_path)

        return results

    except Exception as e:
        _server.logger.error("Caption addition failed: %s", e)
        return {"error": str(e)}


# Helper functions


def _generate_edit_suggestions(analysis: Dict[str, Any]) -> List[Dict[str, str]]:
    """Generate editing suggestions based on video analysis"""
    suggestions = []

    # Suggest removing long silences
    silence_segments = analysis.get("audio_analysis", {}).get("silence_segments", [])
    for start, end in silence_segments:
        if end - start > 3.0:  # Silence longer than 3 seconds
            suggestions.append(
                {
                    "type": "remove_silence",
                    "start": start,
                    "end": end,
                    "reason": f"Long silence detected ({end-start:.1f} seconds)",
                }
            )

    # Suggest emphasis on highlights
    for highlight in analysis.get("highlights", []):
        suggestions.append(
            {
                "type": "add_emphasis",
                "time": highlight["time"],
                "effect": "zoom_in",
                "reason": f"Highlight detected: {highlight['type']}",
            }
        )

    # Suggest cuts at scene changes
    for scene_time in analysis.get("scene_changes", [])[:10]:  # Limit to first 10
        suggestions.append(
            {"type": "scene_cut", "time": scene_time, "transition": "cross_dissolve", "reason": "Scene change detected"}
        )

    return suggestions


def _generate_srt_file(transcript: Dict[str, Any], output_path: str):
    """Generate SRT subtitle file from transcript"""

    def format_timestamp(seconds: float) -> str:
        """Convert seconds to SRT timestamp format"""
        hours = int(seconds // 3600)
        minutes = int((seconds % 3600) // 60)
        secs = seconds % 60
        return f"{hours:02d}:{minutes:02d}:{secs:06.3f}".replace(".", ",")

    with open(output_path, "w", encoding="utf-8") as f:
        for i, segment in enumerate(transcript.get("segments", []), 1):
            f.write(f"{i}\n")
            f.write(f"{format_timestamp(segment['start'])} --> {format_timestamp(segment['end'])}\n")
            f.write(f"{segment['text'].strip()}\n")
            f.write("\n")


@register_tool("video_editor/get_job_status")
async def get_job_status(job_id: str, _server=None, **_kwargs) -> Dict[str, Any]:
    """Get the status of a rendering job"""

    if not _server:
        return {"error": "Server context not provided"}

    return _server.get_job_status(job_id)  # type: ignore[no-any-return]
