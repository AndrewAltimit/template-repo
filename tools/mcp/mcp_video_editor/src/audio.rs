//! Audio processing for video editor.
//!
//! Handles audio extraction, transcription via Whisper, and speaker diarization.
//! All processing is done via external tools (ffmpeg, whisper CLI).

use crate::types::{
    AudioAnalysis, ServerConfig, Speaker, Transcript, TranscriptSegment,
    TranscriptSegmentWithSpeaker, VolumePoint, Word,
};
use anyhow::{Context, Result};
use serde::{Deserialize, Serialize};
use std::path::{Path, PathBuf};
use std::process::Stdio;
use tempfile::NamedTempFile;
use tokio::process::Command;
use tracing::{info, warn};

/// Audio processor for video editing operations
pub struct AudioProcessor {
    pub(crate) config: ServerConfig,
    #[allow(dead_code)]
    cache_dir: PathBuf,
    transcripts_cache: PathBuf,
    diarization_cache: PathBuf,
}

impl AudioProcessor {
    /// Create a new audio processor
    pub fn new(config: ServerConfig) -> Result<Self> {
        let cache_dir = PathBuf::from(&config.cache_dir);
        let transcripts_cache = cache_dir.join("transcripts");
        let diarization_cache = cache_dir.join("diarization");

        // Create cache directories
        std::fs::create_dir_all(&transcripts_cache)?;
        std::fs::create_dir_all(&diarization_cache)?;

        Ok(Self {
            config,
            cache_dir,
            transcripts_cache,
            diarization_cache,
        })
    }

    /// Extract audio from video file to WAV format
    pub async fn extract_audio(&self, video_path: &str) -> Result<PathBuf> {
        info!("Extracting audio from: {}", video_path);

        let temp_file = NamedTempFile::with_suffix(".wav")?;
        let audio_path = temp_file.path().to_path_buf();

        // Keep the temp file from being deleted
        temp_file.keep()?;

        // Use ffmpeg to extract audio
        let audio_path_str = audio_path
            .to_str()
            .ok_or_else(|| anyhow::anyhow!("Audio path contains invalid UTF-8"))?;

        let output = Command::new("ffmpeg")
            .args([
                "-i",
                video_path,
                "-vn", // No video
                "-acodec",
                "pcm_s16le", // PCM 16-bit
                "-ar",
                "16000", // 16kHz sample rate (good for speech)
                "-ac",
                "1",  // Mono
                "-y", // Overwrite
                audio_path_str,
            ])
            .stderr(Stdio::piped())
            .output()
            .await
            .context("Failed to run ffmpeg")?;

        if !output.status.success() {
            let stderr = String::from_utf8_lossy(&output.stderr);
            // Clean up temp file on error
            let _ = std::fs::remove_file(&audio_path);
            anyhow::bail!("ffmpeg failed: {}", stderr);
        }

        info!("Audio extracted to: {:?}", audio_path);
        Ok(audio_path)
    }

    /// Transcribe audio using Whisper CLI
    pub async fn transcribe(
        &self,
        audio_path: &Path,
        language: Option<&str>,
    ) -> Result<Transcript> {
        info!("Transcribing audio: {:?}", audio_path);

        // Check cache first
        let cache_key = self.get_cache_key(audio_path, "transcript", language)?;
        if let Some(cached) =
            self.load_from_cache::<Transcript>(&cache_key, &self.transcripts_cache)?
        {
            info!("Using cached transcript");
            return Ok(cached);
        }

        // Build whisper command
        // We'll use whisper CLI if available, otherwise return a placeholder
        let whisper_path = which::which("whisper").ok();

        if whisper_path.is_none() {
            warn!("Whisper CLI not found. Returning placeholder transcript.");
            return Ok(Transcript {
                text: "[Transcription unavailable - whisper CLI not installed]".to_string(),
                language: language.unwrap_or("unknown").to_string(),
                segments: vec![],
            });
        }

        let audio_path_str = audio_path
            .to_str()
            .ok_or_else(|| anyhow::anyhow!("Audio path contains invalid UTF-8"))?;

        let mut cmd = Command::new("whisper");
        cmd.arg(audio_path_str)
            .arg("--model")
            .arg(&self.config.models.whisper_model)
            .arg("--output_format")
            .arg("json")
            .arg("--word_timestamps")
            .arg("True");

        if let Some(lang) = language {
            cmd.arg("--language").arg(lang);
        }

        // Output to temp directory
        let output_dir = tempfile::tempdir()?;
        cmd.arg("--output_dir").arg(output_dir.path());

        let output = cmd
            .stderr(Stdio::piped())
            .output()
            .await
            .context("Failed to run whisper")?;

        if !output.status.success() {
            let stderr = String::from_utf8_lossy(&output.stderr);
            warn!("Whisper transcription failed: {}", stderr);
            return Ok(Transcript {
                text: "[Transcription failed]".to_string(),
                language: language.unwrap_or("unknown").to_string(),
                segments: vec![],
            });
        }

        // Find and parse the JSON output
        let file_stem = audio_path
            .file_stem()
            .ok_or_else(|| anyhow::anyhow!("Audio path has no file name"))?
            .to_string_lossy();
        let json_path = output_dir.path().join(format!("{}.json", file_stem));

        let transcript = if json_path.exists() {
            let content = std::fs::read_to_string(&json_path)?;
            self.parse_whisper_json(&content)?
        } else {
            warn!("Whisper JSON output not found");
            Transcript {
                text: "[Transcription output not found]".to_string(),
                language: language.unwrap_or("unknown").to_string(),
                segments: vec![],
            }
        };

        // Save to cache
        self.save_to_cache(&cache_key, &transcript, &self.transcripts_cache)?;

        Ok(transcript)
    }

    /// Parse Whisper JSON output
    fn parse_whisper_json(&self, content: &str) -> Result<Transcript> {
        #[derive(Deserialize)]
        struct WhisperOutput {
            text: String,
            language: Option<String>,
            segments: Option<Vec<WhisperSegment>>,
        }

        #[derive(Deserialize)]
        struct WhisperSegment {
            id: u32,
            start: f64,
            end: f64,
            text: String,
            words: Option<Vec<WhisperWord>>,
        }

        #[derive(Deserialize)]
        struct WhisperWord {
            word: String,
            start: f64,
            end: f64,
            probability: Option<f64>,
        }

        let whisper_output: WhisperOutput = serde_json::from_str(content)?;

        let segments = whisper_output
            .segments
            .unwrap_or_default()
            .into_iter()
            .map(|s| TranscriptSegment {
                id: s.id,
                start: s.start,
                end: s.end,
                text: s.text,
                words: s
                    .words
                    .unwrap_or_default()
                    .into_iter()
                    .map(|w| Word {
                        word: w.word,
                        start: w.start,
                        end: w.end,
                        probability: w.probability.unwrap_or(1.0),
                    })
                    .collect(),
            })
            .collect();

        Ok(Transcript {
            text: whisper_output.text,
            language: whisper_output.language.unwrap_or_else(|| "en".to_string()),
            segments,
        })
    }

    /// Perform speaker diarization
    pub async fn diarize_speakers(&self, audio_path: &Path) -> Result<DiarizationResult> {
        info!("Performing speaker diarization: {:?}", audio_path);

        // Check cache first
        let cache_key = self.get_cache_key(audio_path, "diarization", None)?;
        if let Some(cached) =
            self.load_from_cache::<DiarizationResult>(&cache_key, &self.diarization_cache)?
        {
            info!("Using cached diarization");
            return Ok(cached);
        }

        // Speaker diarization requires pyannote.audio which is Python-based
        // For the Rust implementation, we'll return a placeholder
        // In production, this would call out to a Python service or use ONNX models
        warn!("Speaker diarization not available in standalone Rust mode");

        let result = DiarizationResult {
            speakers: vec![],
            segments: vec![],
        };

        Ok(result)
    }

    /// Analyze audio levels
    pub async fn analyze_audio_levels(&self, audio_path: &Path) -> Result<AudioAnalysis> {
        info!("Analyzing audio levels: {:?}", audio_path);

        let audio_path_str = audio_path
            .to_str()
            .ok_or_else(|| anyhow::anyhow!("Audio path contains invalid UTF-8"))?;

        // Use ffprobe to get audio info
        let probe_output = Command::new("ffprobe")
            .args([
                "-v",
                "error",
                "-show_entries",
                "format=duration:stream=sample_rate",
                "-of",
                "json",
                audio_path_str,
            ])
            .output()
            .await
            .context("Failed to run ffprobe")?;

        let duration: f64;
        let sample_rate: u32;

        if probe_output.status.success() {
            #[derive(Deserialize)]
            struct FfprobeOutput {
                format: Option<FfprobeFormat>,
                streams: Option<Vec<FfprobeStream>>,
            }

            #[derive(Deserialize)]
            struct FfprobeFormat {
                duration: Option<String>,
            }

            #[derive(Deserialize, Clone)]
            struct FfprobeStream {
                sample_rate: Option<String>,
            }

            let output: FfprobeOutput = serde_json::from_slice(&probe_output.stdout)?;
            duration = output
                .format
                .and_then(|f| f.duration)
                .and_then(|d| d.parse().ok())
                .unwrap_or(0.0);
            sample_rate = output
                .streams
                .and_then(|s| s.first().cloned())
                .and_then(|s| s.sample_rate)
                .and_then(|r| r.parse().ok())
                .unwrap_or(16000);
        } else {
            duration = 0.0;
            sample_rate = 16000;
        }

        // Use ffmpeg to detect silence
        let silence_output = Command::new("ffmpeg")
            .args([
                "-i",
                audio_path_str,
                "-af",
                "silencedetect=n=-40dB:d=2",
                "-f",
                "null",
                "-",
            ])
            .stderr(Stdio::piped())
            .output()
            .await?;

        let silence_segments =
            self.parse_silence_detect(&String::from_utf8_lossy(&silence_output.stderr));

        // Volume analysis using ffmpeg volumedetect
        let volume_profile = self.analyze_volume(audio_path, duration).await?;
        let peak_moments = self.detect_peaks(&volume_profile);

        Ok(AudioAnalysis {
            duration,
            sample_rate,
            silence_segments,
            volume_profile,
            peak_moments,
        })
    }

    /// Parse ffmpeg silencedetect output
    fn parse_silence_detect(&self, output: &str) -> Vec<(f64, f64)> {
        let mut segments = Vec::new();
        let mut current_start: Option<f64> = None;

        for line in output.lines() {
            if let Some(start_idx) = line.find("silence_start: ")
                && let Ok(start) = line[start_idx + 15..]
                    .split_whitespace()
                    .next()
                    .unwrap_or("0")
                    .parse::<f64>()
            {
                current_start = Some(start);
            } else if let Some(end_idx) = line.find("silence_end: ")
                && let Ok(end) = line[end_idx + 13..]
                    .split_whitespace()
                    .next()
                    .unwrap_or("0")
                    .parse::<f64>()
                && let Some(start) = current_start.take()
            {
                segments.push((start, end));
            }
        }

        segments
    }

    /// Analyze volume levels at regular intervals
    async fn analyze_volume(&self, _audio_path: &Path, duration: f64) -> Result<Vec<VolumePoint>> {
        // For a full implementation, we'd use ffmpeg to extract volume at intervals
        // For now, return a simplified profile
        let mut profile = Vec::new();
        let interval = 0.5; // 0.5 second intervals
        let mut time = 0.0;

        while time < duration {
            profile.push(VolumePoint {
                time,
                rms: 0.1,  // Placeholder
                db: -20.0, // Placeholder
            });
            time += interval;
        }

        Ok(profile)
    }

    /// Detect peak moments in volume profile
    fn detect_peaks(&self, volume_profile: &[VolumePoint]) -> Vec<f64> {
        if volume_profile.is_empty() {
            return vec![];
        }

        let rms_values: Vec<f64> = volume_profile.iter().map(|v| v.rms).collect();
        let threshold = percentile(&rms_values, 90.0);

        let mut peaks = Vec::new();
        for (i, v) in volume_profile.iter().enumerate() {
            if v.rms > threshold {
                // Check if it's a local maximum
                let is_peak = (i == 0 || volume_profile[i - 1].rms <= v.rms)
                    && (i == volume_profile.len() - 1 || volume_profile[i + 1].rms <= v.rms);

                if is_peak {
                    peaks.push(v.time);
                }
            }
        }

        peaks
    }

    /// Combine transcript with speaker diarization
    pub fn combine_transcript_with_speakers(
        &self,
        transcript: &Transcript,
        diarization: &DiarizationResult,
    ) -> CombinedTranscript {
        if diarization.segments.is_empty() {
            return CombinedTranscript {
                text: transcript.text.clone(),
                language: transcript.language.clone(),
                speakers: vec![],
                segments_with_speakers: transcript
                    .segments
                    .iter()
                    .map(|s| TranscriptSegmentWithSpeaker {
                        id: s.id,
                        start: s.start,
                        end: s.end,
                        text: s.text.clone(),
                        speaker: None,
                    })
                    .collect(),
            };
        }

        let segments_with_speakers = transcript
            .segments
            .iter()
            .map(|segment| {
                // Find the speaker with maximum overlap
                let mut best_speaker = None;
                let mut max_overlap = 0.0;

                for diar_seg in &diarization.segments {
                    let overlap_start = segment.start.max(diar_seg.start);
                    let overlap_end = segment.end.min(diar_seg.end);
                    let overlap = (overlap_end - overlap_start).max(0.0);

                    if overlap > max_overlap {
                        max_overlap = overlap;
                        best_speaker = Some(diar_seg.speaker.clone());
                    }
                }

                TranscriptSegmentWithSpeaker {
                    id: segment.id,
                    start: segment.start,
                    end: segment.end,
                    text: segment.text.clone(),
                    speaker: best_speaker,
                }
            })
            .collect();

        CombinedTranscript {
            text: transcript.text.clone(),
            language: transcript.language.clone(),
            speakers: diarization.speakers.clone(),
            segments_with_speakers,
        }
    }

    /// Generate cache key for a file and operation
    fn get_cache_key(
        &self,
        file_path: &Path,
        operation: &str,
        extra: Option<&str>,
    ) -> Result<String> {
        use std::collections::hash_map::DefaultHasher;
        use std::hash::{Hash, Hasher};

        let metadata = std::fs::metadata(file_path)?;
        let mtime = metadata
            .modified()?
            .duration_since(std::time::UNIX_EPOCH)?
            .as_secs();
        let size = metadata.len();

        let mut hasher = DefaultHasher::new();
        file_path.to_string_lossy().hash(&mut hasher);
        mtime.hash(&mut hasher);
        size.hash(&mut hasher);
        operation.hash(&mut hasher);
        if let Some(e) = extra {
            e.hash(&mut hasher);
        }

        Ok(format!("{:016x}", hasher.finish()))
    }

    /// Load from cache
    fn load_from_cache<T: for<'de> Deserialize<'de>>(
        &self,
        cache_key: &str,
        cache_dir: &Path,
    ) -> Result<Option<T>> {
        let cache_file = cache_dir.join(format!("{}.json", cache_key));

        if cache_file.exists() {
            let content = std::fs::read_to_string(&cache_file)?;
            let value: T = serde_json::from_str(&content)?;
            return Ok(Some(value));
        }

        Ok(None)
    }

    /// Save to cache
    fn save_to_cache<T: Serialize>(
        &self,
        cache_key: &str,
        data: &T,
        cache_dir: &Path,
    ) -> Result<()> {
        let cache_file = cache_dir.join(format!("{}.json", cache_key));
        let content = serde_json::to_string_pretty(data)?;
        std::fs::write(&cache_file, content)?;
        Ok(())
    }
}

/// Result of speaker diarization
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct DiarizationResult {
    pub speakers: Vec<Speaker>,
    pub segments: Vec<DiarizationSegment>,
}

/// A segment from diarization
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct DiarizationSegment {
    pub speaker: String,
    pub start: f64,
    pub end: f64,
    pub duration: f64,
}

/// Combined transcript with speakers
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct CombinedTranscript {
    pub text: String,
    pub language: String,
    pub speakers: Vec<Speaker>,
    pub segments_with_speakers: Vec<TranscriptSegmentWithSpeaker>,
}

/// Calculate percentile of values
fn percentile(values: &[f64], p: f64) -> f64 {
    if values.is_empty() {
        return 0.0;
    }

    let mut sorted = values.to_vec();
    sorted.sort_by(|a, b| a.partial_cmp(b).unwrap_or(std::cmp::Ordering::Equal));

    let idx = ((p / 100.0) * (sorted.len() - 1) as f64) as usize;
    sorted[idx.min(sorted.len() - 1)]
}
