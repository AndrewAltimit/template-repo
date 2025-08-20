"""Audio processing module for video editor - Whisper transcription and speaker diarization"""

import hashlib
import json
import os
import subprocess
import tempfile
from typing import TYPE_CHECKING, Any, Dict, List, Optional, Tuple

if TYPE_CHECKING:
    import numpy as np
else:
    try:
        import numpy as np
    except ImportError:
        np = None  # Handle missing numpy gracefully for testing


class AudioProcessor:
    """Handles audio extraction, transcription, and speaker diarization"""

    def __init__(self, config: Dict[str, Any], cache_dir: str, logger):
        self.config = config
        self.cache_dir = cache_dir
        self.logger = logger

        # Lazy-loaded models
        self._whisper_model = None
        self._diart_pipeline = None

        # Create cache subdirectories
        self.transcripts_cache = os.path.join(cache_dir, "transcripts")
        self.diarization_cache = os.path.join(cache_dir, "diarization")
        os.makedirs(self.transcripts_cache, exist_ok=True)
        os.makedirs(self.diarization_cache, exist_ok=True)

    @property
    def whisper_model(self):
        """Lazy-load Whisper model"""
        if self._whisper_model is None:
            try:
                import whisper

                model_name = self.config["models"]["whisper_model"]
                device = self.config["models"]["whisper_device"]
                self.logger.info(f"Loading Whisper model: {model_name} on {device}")
                self._whisper_model = whisper.load_model(model_name, device=device)
            except ImportError:
                self.logger.error("Whisper not installed. Install with: pip install openai-whisper")
                raise ImportError("Whisper is required for transcription")
            except Exception as e:
                self.logger.error(f"Failed to load Whisper model: {e}")
                raise
        return self._whisper_model

    @property
    def diart_pipeline(self):
        """Lazy-load diart pipeline for speaker diarization"""
        if self._diart_pipeline is None:
            try:
                from pyannote.audio import Pipeline

                # Check for Hugging Face token
                token = os.environ.get("HUGGINGFACE_TOKEN")
                if not token:
                    self.logger.warning("HUGGINGFACE_TOKEN not set. Speaker diarization will be unavailable.")
                    self.logger.warning("To enable speaker diarization, set the HUGGINGFACE_TOKEN environment variable.")
                    return None

                self.logger.info("Loading diart/pyannote speaker diarization pipeline")
                # Use pretrained pipeline
                self._diart_pipeline = Pipeline.from_pretrained("pyannote/speaker-diarization@2.1", use_auth_token=token)

                # Set device
                import torch

                device = self.config["models"]["diart_device"]
                if device == "cuda" and torch.cuda.is_available():
                    self._diart_pipeline.to(torch.device("cuda"))

            except ImportError:
                self.logger.warning("pyannote.audio not installed. Speaker diarization unavailable.")
                self.logger.warning("Install with: pip install pyannote.audio")
            except Exception as e:
                self.logger.warning(f"Failed to load diarization pipeline: {e}")
        return self._diart_pipeline

    def extract_audio(self, video_path: str) -> str:
        """Extract audio from video file"""
        self.logger.info(f"Extracting audio from: {video_path}")

        # Create temporary audio file
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as temp_audio:
            audio_path = temp_audio.name

        try:
            # Use ffmpeg to extract audio
            command = [
                "ffmpeg",
                "-i",
                video_path,
                "-vn",  # No video
                "-acodec",
                "pcm_s16le",  # PCM 16-bit
                "-ar",
                "16000",  # 16kHz sample rate (good for speech)
                "-ac",
                "1",  # Mono
                "-y",  # Overwrite
                audio_path,
            ]

            subprocess.run(command, capture_output=True, text=True, check=True)

            self.logger.info(f"Audio extracted to: {audio_path}")
            return audio_path

        except subprocess.CalledProcessError as e:
            self.logger.error(f"Failed to extract audio: {e.stderr}")
            if os.path.exists(audio_path):
                os.unlink(audio_path)
            raise RuntimeError(f"Audio extraction failed: {e.stderr}")
        except Exception:
            if os.path.exists(audio_path):
                os.unlink(audio_path)
            raise

    def transcribe(self, audio_path: str, language: Optional[str] = None) -> Dict[str, Any]:
        """Transcribe audio using Whisper with word-level timestamps"""

        # Check cache first
        cache_key = self._get_cache_key(audio_path, "transcript", language)
        cached_result = self._load_from_cache(cache_key, self.transcripts_cache)
        if cached_result:
            self.logger.info("Using cached transcript")
            return cached_result

        self.logger.info(f"Transcribing audio: {audio_path}")

        try:
            # Transcribe with word timestamps
            result = self.whisper_model.transcribe(audio_path, language=language, word_timestamps=True, verbose=False)

            # Process the result to extract structured data
            transcript_data = {"text": result["text"], "language": result["language"], "segments": [], "words": []}

            for segment in result.get("segments", []):
                segment_data = {
                    "id": segment["id"],
                    "start": segment["start"],
                    "end": segment["end"],
                    "text": segment["text"],
                    "words": [],
                }

                # Extract word-level timestamps if available
                if "words" in segment:
                    for word in segment["words"]:
                        word_data = {
                            "word": word["word"],
                            "start": word["start"],
                            "end": word["end"],
                            "probability": word.get("probability", 1.0),
                        }
                        segment_data["words"].append(word_data)
                        transcript_data["words"].append(word_data)

                transcript_data["segments"].append(segment_data)

            # Save to cache
            self._save_to_cache(cache_key, transcript_data, self.transcripts_cache)

            return transcript_data

        except Exception as e:
            self.logger.error(f"Transcription failed: {e}")
            raise RuntimeError(f"Transcription failed: {e}")

    def diarize_speakers(self, audio_path: str) -> Dict[str, Any]:
        """Perform speaker diarization to identify different speakers"""

        # Check cache first
        cache_key = self._get_cache_key(audio_path, "diarization")
        cached_result = self._load_from_cache(cache_key, self.diarization_cache)
        if cached_result:
            self.logger.info("Using cached diarization")
            return cached_result

        if self.diart_pipeline is None:
            self.logger.warning("Speaker diarization not available")
            return {"speakers": [], "segments": []}

        self.logger.info(f"Performing speaker diarization: {audio_path}")

        try:
            # Run diarization
            diarization = self.diart_pipeline(audio_path)  # pylint: disable=not-callable

            # Process results
            speakers_data = {"speakers": [], "segments": [], "timeline": []}

            # Extract unique speakers
            speakers = set()
            for turn, _, speaker in diarization.itertracks(yield_label=True):
                speakers.add(speaker)
                segment = {"speaker": speaker, "start": turn.start, "end": turn.end, "duration": turn.end - turn.start}
                speakers_data["segments"].append(segment)

            # Calculate per-speaker statistics
            speaker_stats = {}
            for speaker in speakers:
                speaker_segments = [s for s in speakers_data["segments"] if s["speaker"] == speaker]
                total_time = sum(s["duration"] for s in speaker_segments)
                speaker_stats[speaker] = {
                    "id": speaker,
                    "total_speaking_time": total_time,
                    "segment_count": len(speaker_segments),
                    "segments": [[s["start"], s["end"]] for s in speaker_segments],
                }

            speakers_data["speakers"] = list(speaker_stats.values())

            # Save to cache
            self._save_to_cache(cache_key, speakers_data, self.diarization_cache)

            return speakers_data

        except Exception as e:
            self.logger.error(f"Speaker diarization failed: {e}")
            # Return empty result on failure
            return {"speakers": [], "segments": []}

    def analyze_audio_levels(self, audio_path: str) -> Dict[str, Any]:
        """Analyze audio levels for volume, silence detection, etc."""
        self.logger.info(f"Analyzing audio levels: {audio_path}")

        try:
            import librosa

            # Load audio
            y, sr = librosa.load(audio_path, sr=None)

            # Calculate various audio features
            analysis = {
                "duration": len(y) / sr,
                "sample_rate": sr,
                "silence_segments": [],
                "volume_profile": [],
                "peak_moments": [],
            }

            # Detect silence segments
            silence_threshold = self.config["defaults"]["silence_threshold"]
            analysis["silence_segments"] = self._detect_silence(y, sr, silence_threshold)

            # Sample volume levels at regular intervals
            window_size = int(sr * 0.5)  # 0.5 second windows
            for i in range(0, len(y), window_size):
                window = y[i : i + window_size]
                if len(window) > 0:
                    rms = np.sqrt(np.mean(window**2))
                    analysis["volume_profile"].append(
                        {"time": i / sr, "rms": float(rms), "db": float(20 * np.log10(rms + 1e-10))}
                    )

            # Detect peak moments (for emphasis detection)
            analysis["peak_moments"] = self._detect_peaks(analysis["volume_profile"])

            return analysis

        except ImportError:
            self.logger.warning("librosa not installed. Audio analysis limited.")
            return {"duration": 0, "silence_segments": [], "volume_profile": [], "peak_moments": []}
        except Exception as e:
            self.logger.error(f"Audio analysis failed: {e}")
            raise

    def _detect_silence(self, audio: "np.ndarray", sr: int, threshold_seconds: float) -> List[Tuple[float, float]]:
        """Detect silence segments in audio"""
        import librosa

        # Convert to dB
        audio_db = librosa.amplitude_to_db(np.abs(audio))

        # Define silence threshold (e.g., -40 dB)
        silence_threshold_db = -40

        # Find silent samples
        silent_samples = audio_db < silence_threshold_db

        # Convert to time segments
        silence_segments = []
        in_silence = False
        start_time = 0

        # min_silence_samples = int(threshold_seconds * sr)  # Not used currently

        for i in range(0, len(silent_samples), sr // 10):  # Check every 0.1 seconds
            window = silent_samples[i : i + sr // 10]
            is_silent = np.mean(window) > 0.8  # 80% of window is silent

            if is_silent and not in_silence:
                in_silence = True
                start_time = i / sr
            elif not is_silent and in_silence:
                in_silence = False
                duration = (i / sr) - start_time
                if duration >= threshold_seconds:
                    silence_segments.append((start_time, i / sr))

        return silence_segments

    def _detect_peaks(self, volume_profile: List[Dict[str, float]], percentile: float = 90) -> List[float]:
        """Detect peak moments in volume profile"""
        if not volume_profile:
            return []

        # Extract RMS values
        rms_values = [v["rms"] for v in volume_profile]

        # Calculate threshold for peaks
        threshold = np.percentile(rms_values, percentile)

        # Find peaks above threshold
        peaks = []
        for i, v in enumerate(volume_profile):
            if v["rms"] > threshold:
                # Check if it's a local maximum
                is_peak = True
                if i > 0 and volume_profile[i - 1]["rms"] > v["rms"]:
                    is_peak = False
                if i < len(volume_profile) - 1 and volume_profile[i + 1]["rms"] > v["rms"]:
                    is_peak = False

                if is_peak:
                    peaks.append(v["time"])

        return peaks

    def combine_transcript_with_speakers(self, transcript: Dict[str, Any], diarization: Dict[str, Any]) -> Dict[str, Any]:
        """Combine transcript with speaker identification"""

        if not diarization.get("segments"):
            # No speaker data, return transcript as-is
            return transcript

        combined = {
            "text": transcript["text"],
            "language": transcript["language"],
            "speakers": diarization["speakers"],
            "segments_with_speakers": [],
        }

        # Match transcript segments with speakers
        for segment in transcript["segments"]:
            segment_start = segment["start"]
            segment_end = segment["end"]

            # Find the speaker for this segment
            speaker = None
            max_overlap = 0

            for speaker_segment in diarization["segments"]:
                # Calculate overlap
                overlap_start = max(segment_start, speaker_segment["start"])
                overlap_end = min(segment_end, speaker_segment["end"])
                overlap = max(0, overlap_end - overlap_start)

                if overlap > max_overlap:
                    max_overlap = overlap
                    speaker = speaker_segment["speaker"]

            # Add speaker info to segment
            segment_with_speaker = segment.copy()
            segment_with_speaker["speaker"] = speaker
            combined["segments_with_speakers"].append(segment_with_speaker)

        return combined

    def _get_cache_key(self, file_path: str, operation: str, *args) -> str:
        """Generate cache key for a file and operation"""
        # Get file modification time and size
        stat = os.stat(file_path)
        file_info = f"{file_path}:{stat.st_mtime}:{stat.st_size}"

        # Add operation and arguments
        key_parts = [file_info, operation] + [str(arg) for arg in args if arg]
        key_string = ":".join(key_parts)

        # Generate hash
        return hashlib.sha256(key_string.encode()).hexdigest()

    def _load_from_cache(self, cache_key: str, cache_dir: str) -> Optional[Dict[str, Any]]:
        """Load cached result if available"""
        cache_file = os.path.join(cache_dir, f"{cache_key}.json")

        if os.path.exists(cache_file):
            try:
                with open(cache_file, "r") as f:
                    return json.load(f)
            except Exception as e:
                self.logger.warning(f"Failed to load cache: {e}")

        return None

    def _save_to_cache(self, cache_key: str, data: Dict[str, Any], cache_dir: str):
        """Save result to cache"""
        cache_file = os.path.join(cache_dir, f"{cache_key}.json")

        try:
            with open(cache_file, "w") as f:
                json.dump(data, f, indent=2)
        except Exception as e:
            self.logger.warning(f"Failed to save cache: {e}")
