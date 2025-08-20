"""Video editor tools for MCP"""

import asyncio
import json
import os
from pathlib import Path
from typing import Any, Dict, List, Optional

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
    video_inputs: List[str], analysis_options: Optional[Dict[str, bool]] = None, _server=None, **kwargs
) -> Dict[str, Any]:
    """Analyze video content without rendering, returns metadata and suggested edits"""

    if not _server:
        return {"error": "Server context not provided"}

    if not video_inputs:
        return {"error": "No video inputs provided"}

    # Default analysis options
    if analysis_options is None:
        analysis_options = {"transcribe": True, "identify_speakers": True, "detect_scenes": True, "extract_highlights": True}

    _server.logger.info(f"Analyzing {len(video_inputs)} video(s)")

    try:
        results = {"video_inputs": video_inputs, "analysis": {}}

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
                        for segment in video_analysis["transcript"].get("segments", []):
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
        _server.logger.error(f"Analysis failed: {e}")
        return {"error": str(e)}


@register_tool("video_editor/create_edit")
async def create_edit(
    video_inputs: List[str],
    editing_rules: Optional[Dict[str, Any]] = None,
    speaker_mapping: Optional[Dict[str, str]] = None,
    _server=None,
    **kwargs,
) -> Dict[str, Any]:
    """Generate an edit decision list (EDL) based on rules without rendering"""

    if not _server:
        return {"error": "Server context not provided"}

    if not video_inputs:
        return {"error": "No video inputs provided"}

    # Default editing rules
    if editing_rules is None:
        editing_rules = {
            "switch_on_speaker": True,
            "speaker_switch_delay": 0.5,
            "picture_in_picture": "auto",
            "zoom_on_emphasis": True,
            "remove_silence": True,
            "silence_threshold": 2.0,
        }

    _server.logger.info(f"Creating edit for {len(video_inputs)} video(s)")

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
            return analysis_result

        # Generate EDL based on analysis and rules
        edit_decision_list = []
        current_time = 0.0

        # Process based on primary video (first input)
        primary_video = video_inputs[0]
        primary_analysis = analysis_result["analysis"][primary_video]

        # If we have speaker segments, use them for editing
        if "segments_with_speakers" in primary_analysis and editing_rules.get("switch_on_speaker"):

            segments = primary_analysis["segments_with_speakers"]
            speaker_switch_delay = editing_rules.get("speaker_switch_delay", 0.5)
            last_speaker = None
            last_switch_time = 0

            for segment in segments:
                speaker = segment.get("speaker")
                start_time = segment["start"]
                end_time = segment["end"]
                duration = end_time - start_time

                # Determine which video to use
                if speaker_mapping and speaker in speaker_mapping:
                    source_video = speaker_mapping[speaker]
                elif speaker and len(video_inputs) > 1:
                    # Auto-map speakers to videos
                    speaker_idx = hash(speaker) % len(video_inputs)
                    source_video = video_inputs[speaker_idx]
                    # Log warning about ambiguous mapping
                    _server.logger.warning(
                        f"No explicit mapping for speaker '{speaker}'. "
                        f"Auto-mapping to video {speaker_idx} ({source_video}). "
                        "Consider providing explicit speaker_mapping for better control."
                    )
                else:
                    source_video = primary_video

                # Check if we should switch
                should_switch = speaker != last_speaker and (current_time - last_switch_time) > speaker_switch_delay

                # Create edit decision
                decision = {
                    "timestamp": start_time,
                    "duration": duration,
                    "source": source_video,
                    "action": "transition" if should_switch else "show",
                    "effects": [],
                }

                # Add transition if switching
                if should_switch:
                    decision["transition_type"] = "cross_dissolve"
                    last_speaker = speaker
                    last_switch_time = current_time

                # Add zoom on emphasis
                if editing_rules.get("zoom_on_emphasis"):
                    # Check if this segment contains a highlight
                    for highlight in primary_analysis.get("highlights", []):
                        if start_time <= highlight["time"] <= end_time:
                            decision["effects"].append("zoom_in")
                            break

                # Add picture-in-picture for multi-speaker segments
                if editing_rules.get("picture_in_picture") == "auto":
                    # Check for overlapping speakers
                    overlapping = False
                    for other_segment in segments:
                        if other_segment != segment:
                            if (
                                other_segment["start"] < end_time
                                and other_segment["end"] > start_time
                                and other_segment.get("speaker") != speaker
                            ):
                                overlapping = True
                                break

                    if overlapping and len(video_inputs) > 1:
                        decision["effects"].append("picture_in_picture")
                        decision["pip_size"] = editing_rules.get("pip_size", 0.25)

                edit_decision_list.append(decision)
                current_time = end_time

        else:
            # Fallback: create simple cuts based on scene changes or fixed intervals
            scene_changes = primary_analysis.get("scene_changes", [])

            if scene_changes:
                # Use scene changes for cuts
                last_time = 0
                for i, scene_time in enumerate(scene_changes):
                    duration = scene_time - last_time
                    if duration > 0.5:  # Minimum segment duration
                        source_idx = i % len(video_inputs)
                        decision = {
                            "timestamp": last_time,
                            "duration": duration,
                            "source": video_inputs[source_idx],
                            "action": "show" if i == 0 else "transition",
                            "transition_type": "cross_dissolve" if i > 0 else None,
                            "effects": [],
                        }
                        edit_decision_list.append(decision)
                        last_time = scene_time

            else:
                # Fixed interval cuts (every 10 seconds)
                duration = primary_analysis.get("audio_analysis", {}).get("duration", 60)
                interval = 10.0

                for i in range(int(duration / interval)):
                    source_idx = i % len(video_inputs)
                    decision = {
                        "timestamp": i * interval,
                        "duration": interval,
                        "source": video_inputs[source_idx],
                        "action": "show" if i == 0 else "transition",
                        "transition_type": "cross_dissolve" if i > 0 else None,
                        "effects": [],
                    }
                    edit_decision_list.append(decision)

        # Remove silence if requested
        if editing_rules.get("remove_silence"):
            silence_threshold = editing_rules.get("silence_threshold", 2.0)
            silence_segments = primary_analysis.get("audio_analysis", {}).get("silence_segments", [])

            # Filter out decisions that fall within silence segments
            filtered_edl = []
            for decision in edit_decision_list:
                start = decision["timestamp"]
                end = start + decision["duration"]

                # Check if this segment overlaps with silence
                is_silent = False
                for silence_start, silence_end in silence_segments:
                    if silence_end - silence_start >= silence_threshold:
                        if start >= silence_start and end <= silence_end:
                            is_silent = True
                            break

                if not is_silent:
                    filtered_edl.append(decision)

            edit_decision_list = filtered_edl

        # Calculate estimated duration
        estimated_duration = sum(d["duration"] for d in edit_decision_list)

        # Save EDL to file
        edl_filename = f"edit_{_server.job_counter}.json"
        edl_path = os.path.join(_server.edl_dir, edl_filename)

        with open(edl_path, "w") as f:
            json.dump(edit_decision_list, f, indent=2)

        return {
            "edit_decision_list": edit_decision_list,
            "estimated_duration": estimated_duration,
            "edl_file": edl_path,
            "video_inputs": video_inputs,
            "editing_rules": editing_rules,
        }

    except Exception as e:
        _server.logger.error(f"Edit creation failed: {e}")
        return {"error": str(e)}


@register_tool("video_editor/render")
async def render_video(
    video_inputs: List[str],
    edit_decision_list: Optional[List[Dict[str, Any]]] = None,
    output_settings: Optional[Dict[str, Any]] = None,
    render_options: Optional[Dict[str, Any]] = None,
    _server=None,
    **kwargs,
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
                result = subprocess.run(["ffmpeg", "-encoders"], capture_output=True, text=True)
                if "h264_nvenc" in result.stdout:
                    output_settings["codec"] = "h264_nvenc"
                elif "h264_qsv" in result.stdout:
                    output_settings["codec"] = "h264_qsv"
                else:
                    output_settings["codec"] = "libx264"
            except:
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
            transcript_path = output_path.replace(".mp4", ".srt")
            _generate_srt_file(transcript, transcript_path)
            render_result["transcript_path"] = transcript_path

        # Update job with result
        _server.update_job(job_id, {"status": "completed", "stage": "done", "progress": 100, "result": render_result})

        return render_result

    except Exception as e:
        _server.logger.error(f"Rendering failed: {e}")
        _server.update_job(job_id, {"status": "failed", "error": str(e)})
        return {"error": str(e), "job_id": job_id}


@register_tool("video_editor/extract_clips")
async def extract_clips(
    video_input: str,
    extraction_criteria: Optional[Dict[str, Any]] = None,
    output_dir: Optional[str] = None,
    _server=None,
    **kwargs,
) -> Dict[str, Any]:
    """Create short clips based on transcript keywords or timestamps"""

    if not _server:
        return {"error": "Server context not provided"}

    if not os.path.exists(video_input):
        return {"error": f"Video file not found: {video_input}"}

    # Default extraction criteria
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

    _server.logger.info(f"Extracting clips from: {video_input}")

    try:
        clips_extracted = []

        # Analyze video if we need transcript or speaker info
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
                return analysis_result

            video_analysis = analysis_result["analysis"][video_input]

        # Extract based on time ranges
        for time_range in extraction_criteria.get("time_ranges", []):
            start_time = time_range[0] - extraction_criteria.get("padding", 0)
            end_time = time_range[1] + extraction_criteria.get("padding", 0)

            # Enforce clip length limits
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

        # Extract based on keywords
        if extraction_criteria.get("keywords") and need_analysis:
            keywords = [k.lower() for k in extraction_criteria["keywords"]]

            for segment in video_analysis.get("transcript", {}).get("segments", []):
                text_lower = segment["text"].lower()

                for keyword in keywords:
                    if keyword in text_lower:
                        start_time = segment["start"] - extraction_criteria.get("padding", 0)
                        end_time = segment["end"] + extraction_criteria.get("padding", 0)

                        # Enforce clip length limits
                        duration = end_time - start_time
                        if duration < extraction_criteria.get("min_clip_length", 0):
                            # Extend clip to minimum length
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

        # Extract based on speakers
        if extraction_criteria.get("speakers") and need_analysis:
            target_speakers = extraction_criteria["speakers"]

            for segment in video_analysis.get("segments_with_speakers", []):
                if segment.get("speaker") in target_speakers:
                    start_time = segment["start"] - extraction_criteria.get("padding", 0)
                    end_time = segment["end"] + extraction_criteria.get("padding", 0)

                    # Merge consecutive segments from same speaker
                    # (This is simplified - could be more sophisticated)

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

        return {
            "video_input": video_input,
            "clips_extracted": clips_extracted,
            "total_clips": len(clips_extracted),
            "output_directory": output_dir,
        }

    except Exception as e:
        _server.logger.error(f"Clip extraction failed: {e}")
        return {"error": str(e)}


@register_tool("video_editor/add_captions")
async def add_captions(
    video_input: str,
    caption_style: Optional[Dict[str, Any]] = None,
    languages: Optional[List[str]] = None,
    output_path: Optional[str] = None,
    _server=None,
    **kwargs,
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

    _server.logger.info(f"Adding captions to: {video_input}")

    try:
        # Load the video
        video_clip = _server.video_processor.load_video(video_input)

        results = {"video_input": video_input, "languages_processed": []}

        for language in languages:
            _server.logger.info(f"Processing captions for language: {language}")

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
                render_result = _server.video_processor.render_video(
                    video_with_captions,
                    lang_output_path,
                    {"fps": video_clip.fps, "resolution": f"{video_clip.w}x{video_clip.h}", "bitrate": "8M"},
                )

                # Generate SRT subtitle file
                srt_path = lang_output_path.replace(".mp4", ".srt")
                _generate_srt_file(transcript, srt_path)

                results["languages_processed"].append(
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
        _server.logger.error(f"Caption addition failed: {e}")
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
async def get_job_status(job_id: str, _server=None, **kwargs) -> Dict[str, Any]:
    """Get the status of a rendering job"""

    if not _server:
        return {"error": "Server context not provided"}

    return _server.get_job_status(job_id)
