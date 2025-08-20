"""Video processing module for video editor - MoviePy integration for editing and effects"""

import os
from typing import Any, Dict, List, Optional, Tuple

try:
    import numpy as np
except ImportError:
    np = None  # Handle missing numpy gracefully for testing


class VideoProcessor:
    """Handles video editing, composition, effects, and rendering"""

    def __init__(self, config: Dict[str, Any], temp_dir: str, logger):
        self.config = config
        self.temp_dir = temp_dir
        self.logger = logger

        # Lazy-loaded MoviePy
        self._moviepy = None

        # Video cache for loaded clips
        self._video_cache = {}
        self._cache_size = 0
        self._max_cache_size = self._parse_cache_size(config["performance"]["video_cache_size"])

    def _parse_cache_size(self, size_str: str) -> int:
        """Parse cache size string to bytes"""
        size_str = size_str.upper()
        if size_str.endswith("GB"):
            return int(size_str[:-2]) * 1024 * 1024 * 1024
        elif size_str.endswith("MB"):
            return int(size_str[:-2]) * 1024 * 1024
        elif size_str.endswith("KB"):
            return int(size_str[:-2]) * 1024
        else:
            return int(size_str)

    @property
    def moviepy(self):
        """Lazy-load MoviePy"""
        if self._moviepy is None:
            try:
                import moviepy.editor as mpy

                self._moviepy = mpy
                self.logger.info("MoviePy loaded successfully")
            except ImportError:
                self.logger.error("MoviePy not installed. Install with: pip install moviepy")
                raise ImportError("MoviePy is required for video editing")
        return self._moviepy

    def load_video(self, video_path: str, audio: bool = True) -> Any:
        """Load a video file into memory"""
        # Check cache first
        if video_path in self._video_cache:
            self.logger.info(f"Using cached video: {video_path}")
            return self._video_cache[video_path]

        self.logger.info(f"Loading video: {video_path}")

        try:
            clip = self.moviepy.VideoFileClip(video_path, audio=audio)

            # Estimate memory usage (rough approximation)
            estimated_size = clip.w * clip.h * clip.duration * 3 * 30  # w*h*duration*channels*fps

            # Check if we need to clear cache
            if self._cache_size + estimated_size > self._max_cache_size:
                self._clear_cache()

            # Add to cache
            self._video_cache[video_path] = clip
            self._cache_size += estimated_size

            return clip

        except Exception as e:
            self.logger.error(f"Failed to load video {video_path}: {e}")
            raise RuntimeError(f"Failed to load video: {e}")

    def _clear_cache(self):
        """Clear video cache to free memory"""
        self.logger.info("Clearing video cache")
        for path, clip in self._video_cache.items():
            try:
                clip.close()
            except Exception:
                pass
        self._video_cache.clear()
        self._cache_size = 0

    def create_edit_from_edl(
        self, video_inputs: List[str], edit_decision_list: List[Dict[str, Any]], output_settings: Dict[str, Any]
    ) -> Any:
        """Create a composed video from an edit decision list"""

        self.logger.info(f"Creating edit from EDL with {len(edit_decision_list)} decisions")

        # Load all video inputs
        clips = {}
        for video_path in video_inputs:
            clips[video_path] = self.load_video(video_path)

        # Process EDL to create final composition
        composed_clips = []

        for decision in edit_decision_list:
            timestamp = decision["timestamp"]
            duration = decision["duration"]
            action = decision["action"]
            source = decision["source"]
            effects = decision.get("effects", [])

            if source not in clips:
                self.logger.warning(f"Source not found: {source}")
                continue

            # Extract the segment
            clip = clips[source]
            segment = clip.subclip(timestamp, timestamp + duration)

            # Apply effects
            segment = self._apply_effects(segment, effects, decision)

            # Handle transitions
            if action == "transition":
                transition_type = decision.get("transition_type", "cross_dissolve")
                segment = self._apply_transition(segment, transition_type, composed_clips)

            composed_clips.append(segment)

        if not composed_clips:
            raise ValueError("No valid clips to compose")

        # Concatenate all clips
        final_video = self.moviepy.concatenate_videoclips(composed_clips, method="compose")

        return final_video

    def _apply_effects(self, clip: Any, effects: List[str], decision: Dict[str, Any]) -> Any:
        """Apply effects to a video clip"""

        for effect in effects:
            if effect == "zoom_in":
                clip = self._apply_zoom(clip, self.config["defaults"]["zoom_factor"])
            elif effect == "zoom_out":
                clip = self._apply_zoom(clip, 1.0 / self.config["defaults"]["zoom_factor"])
            elif effect == "fade_in":
                clip = clip.fadein(0.5)
            elif effect == "fade_out":
                clip = clip.fadeout(0.5)
            elif effect == "picture_in_picture":
                pip_size = decision.get("pip_size", self.config["defaults"]["pip_size"])
                pip_position = decision.get("pip_position", "bottom_right")
                clip = self._apply_pip(clip, pip_size, pip_position)

        return clip

    def _apply_zoom(self, clip: Any, zoom_factor: float) -> Any:
        """Apply zoom effect to a clip"""

        def zoom_effect(get_frame, t):
            frame = get_frame(t)
            h, w = frame.shape[:2]

            # Calculate zoom based on time
            current_zoom = 1 + (zoom_factor - 1) * (t / clip.duration)

            # Calculate new dimensions
            new_h = int(h / current_zoom)
            new_w = int(w / current_zoom)

            # Calculate crop positions (center crop)
            y1 = (h - new_h) // 2
            x1 = (w - new_w) // 2

            # Crop and resize
            cropped = frame[y1 : y1 + new_h, x1 : x1 + new_w]

            # Resize back to original dimensions
            import cv2

            resized = cv2.resize(cropped, (w, h))

            return resized

        return clip.fl(zoom_effect)

    def _apply_pip(self, clip: Any, size: float, position: str) -> Any:
        """Apply picture-in-picture effect"""
        # Resize the clip
        pip_clip = clip.resize(size)

        # Calculate position
        if position == "top_left":
            pip_clip = pip_clip.set_position(("left", "top"))
        elif position == "top_right":
            pip_clip = pip_clip.set_position(("right", "top"))
        elif position == "bottom_left":
            pip_clip = pip_clip.set_position(("left", "bottom"))
        else:  # bottom_right
            pip_clip = pip_clip.set_position(("right", "bottom"))

        return pip_clip

    def _apply_transition(self, clip: Any, transition_type: str, previous_clips: List[Any]) -> Any:
        """Apply transition between clips"""

        duration = self.config["defaults"]["transition_duration"]

        if transition_type == "cross_dissolve" and previous_clips:
            # Cross dissolve with previous clip
            clip = clip.crossfadein(duration)
        elif transition_type == "fade":
            clip = clip.fadein(duration)
        elif transition_type == "slide":
            # Slide transition
            clip = clip.fx(self.moviepy.vfx.slide_in, duration, "left")
        elif transition_type == "wipe":
            # Wipe transition (custom implementation needed)
            pass

        return clip

    def render_video(
        self, video_clip: Any, output_path: str, output_settings: Dict[str, Any], progress_callback: Optional[callable] = None
    ) -> Dict[str, Any]:
        """Render the final video to file

        Note: progress_callback is accepted for API compatibility but MoviePy
        doesn't support real-time progress callbacks. Progress bar will be
        shown in logs if logger is enabled.
        """

        self.logger.info(f"Rendering video to: {output_path}")

        # Extract settings
        fps = output_settings.get("fps", 30)
        resolution = output_settings.get("resolution", "1920x1080")
        bitrate = output_settings.get("bitrate", "8M")
        codec = output_settings.get("codec", "libx264")
        audio_codec = output_settings.get("audio_codec", "aac")

        # Parse resolution
        if isinstance(resolution, str):
            width, height = map(int, resolution.split("x"))
            video_clip = video_clip.resize((width, height))

        # Set up ffmpeg parameters
        ffmpeg_params = [
            "-c:v",
            codec,
            "-b:v",
            bitrate,
            "-c:a",
            audio_codec,
        ]

        # Add hardware acceleration if available
        if self.config["performance"]["enable_gpu"]:
            if codec == "h264_nvenc":
                ffmpeg_params.extend(["-preset", "fast"])
            elif codec == "h264_qsv":
                ffmpeg_params.extend(["-preset", "faster"])

        try:
            # Write the video file
            # Note: MoviePy doesn't support custom progress callbacks
            # It will show a progress bar in the logs if logger is enabled
            video_clip.write_videofile(
                output_path,
                fps=fps,
                codec=codec,
                audio_codec=audio_codec,
                bitrate=bitrate,
                ffmpeg_params=ffmpeg_params,
                logger=None if not self.logger else "bar",
                threads=4,
                write_logfile=False,
            )

            # Get file info
            file_stats = os.stat(output_path)

            result = {
                "success": True,
                "output_path": output_path,
                "duration": video_clip.duration,
                "fps": fps,
                "resolution": resolution,
                "file_size": file_stats.st_size,
                "codec": codec,
            }

            return result

        except Exception as e:
            self.logger.error(f"Rendering failed: {e}")
            raise RuntimeError(f"Video rendering failed: {e}")
        finally:
            # Clean up
            try:
                video_clip.close()
            except Exception:
                pass

    def extract_clip(self, video_path: str, start_time: float, end_time: float, output_path: Optional[str] = None) -> Any:
        """Extract a clip from a video"""

        self.logger.info(f"Extracting clip from {start_time} to {end_time}")

        # Load video
        video = self.load_video(video_path)

        # Extract clip
        clip = video.subclip(start_time, end_time)

        # Save if output path provided
        if output_path:
            clip.write_videofile(output_path, logger=None)

        return clip

    def create_split_screen(self, clips: List[Any], layout: str = "side_by_side") -> Any:
        """Create split screen composition"""

        self.logger.info(f"Creating split screen with {len(clips)} clips")

        if layout == "side_by_side" and len(clips) == 2:
            # Resize clips to half width
            clip1 = clips[0].resize(width=clips[0].w // 2)
            clip2 = clips[1].resize(width=clips[1].w // 2)

            # Position clips
            clip1 = clip1.set_position(("left", "center"))
            clip2 = clip2.set_position(("right", "center"))

            # Composite
            final = self.moviepy.CompositeVideoClip([clip1, clip2])

        elif layout == "grid" and len(clips) == 4:
            # Create 2x2 grid
            resized = [clip.resize(0.5) for clip in clips]

            resized[0] = resized[0].set_position(("left", "top"))
            resized[1] = resized[1].set_position(("right", "top"))
            resized[2] = resized[2].set_position(("left", "bottom"))
            resized[3] = resized[3].set_position(("right", "bottom"))

            final = self.moviepy.CompositeVideoClip(resized)

        else:
            # Default: stack vertically
            final = self.moviepy.concatenate_videoclips(clips, method="compose")

        return final

    def add_text_overlay(
        self,
        clip: Any,
        text: str,
        position: Tuple[str, str] = ("center", "bottom"),
        fontsize: int = 50,
        color: str = "white",
        font: str = "Arial",
        duration: Optional[float] = None,
    ) -> Any:
        """Add text overlay to a video clip"""

        # Create text clip
        txt_clip = self.moviepy.TextClip(text, fontsize=fontsize, color=color, font=font)

        # Set position
        txt_clip = txt_clip.set_position(position)

        # Set duration
        if duration:
            txt_clip = txt_clip.set_duration(duration)
        else:
            txt_clip = txt_clip.set_duration(clip.duration)

        # Composite with video
        final = self.moviepy.CompositeVideoClip([clip, txt_clip])

        return final

    def add_captions_to_video(self, video_clip: Any, captions: List[Dict[str, Any]], style: Dict[str, Any]) -> Any:
        """Add styled captions to video"""

        self.logger.info(f"Adding {len(captions)} captions to video")

        caption_clips = []

        for caption in captions:
            text = caption["text"]
            start = caption["start"]
            end = caption["end"]

            # Apply line wrapping
            max_chars = style.get("max_chars_per_line", 40)
            wrapped_text = self._wrap_text(text, max_chars)

            # Create text clip
            txt_clip = self.moviepy.TextClip(
                wrapped_text,
                fontsize=style.get("size", 42),
                color=style.get("color", "white"),
                font=style.get("font", "Arial"),
                stroke_color=style.get("stroke_color", "black"),
                stroke_width=style.get("stroke_width", 2),
                method="caption",
            )

            # Set position and duration
            position = style.get("position", "bottom")
            if position == "bottom":
                txt_clip = txt_clip.set_position(("center", "bottom"))
            elif position == "top":
                txt_clip = txt_clip.set_position(("center", "top"))
            else:
                txt_clip = txt_clip.set_position("center")

            txt_clip = txt_clip.set_start(start).set_end(end)

            # Add speaker name if requested
            if style.get("display_speaker_names") and "speaker" in caption:
                speaker_text = f"[{caption['speaker']}]"
                speaker_clip = self.moviepy.TextClip(
                    speaker_text,
                    fontsize=style.get("size", 42) - 10,
                    color=style.get("speaker_color", "yellow"),
                    font=style.get("font", "Arial"),
                )
                speaker_clip = speaker_clip.set_position(("left", "bottom"))
                speaker_clip = speaker_clip.set_start(start).set_end(end)
                caption_clips.append(speaker_clip)

            caption_clips.append(txt_clip)

        # Composite all captions with video
        final = self.moviepy.CompositeVideoClip([video_clip] + caption_clips)

        return final

    def _wrap_text(self, text: str, max_chars: int) -> str:
        """Wrap text to specified line length"""
        words = text.split()
        lines = []
        current_line = []
        current_length = 0

        for word in words:
            if current_length + len(word) + 1 > max_chars:
                lines.append(" ".join(current_line))
                current_line = [word]
                current_length = len(word)
            else:
                current_line.append(word)
                current_length += len(word) + 1

        if current_line:
            lines.append(" ".join(current_line))

        return "\n".join(lines)

    def detect_scene_changes(self, video_path: str) -> List[float]:
        """Detect scene changes in video"""

        self.logger.info(f"Detecting scene changes in: {video_path}")

        try:
            import cv2

            cap = cv2.VideoCapture(video_path)
            fps = cap.get(cv2.CAP_PROP_FPS)

            scene_changes = []
            prev_frame = None
            frame_count = 0
            threshold = 30.0  # Adjust based on needs

            while True:
                ret, frame = cap.read()
                if not ret:
                    break

                if prev_frame is not None:
                    # Calculate frame difference
                    diff = cv2.absdiff(frame, prev_frame)
                    mean_diff = np.mean(diff)

                    if mean_diff > threshold:
                        timestamp = frame_count / fps
                        scene_changes.append(timestamp)

                prev_frame = frame
                frame_count += 1

            cap.release()

            self.logger.info(f"Detected {len(scene_changes)} scene changes")
            return scene_changes

        except ImportError:
            self.logger.warning("OpenCV not installed. Scene detection unavailable.")
            return []
        except Exception as e:
            self.logger.error(f"Scene detection failed: {e}")
            return []

    def cleanup(self):
        """Clean up resources"""
        self._clear_cache()

        # Clean up temp files
        if os.path.exists(self.temp_dir):
            for file in os.listdir(self.temp_dir):
                try:
                    os.unlink(os.path.join(self.temp_dir, file))
                except Exception:
                    pass
