//! Audio processing: extraction, loudness analysis, silence/peak detection,
//! energy-based speaker detection and Whisper transcription.
//!
//! Audio is extracted once per video as 16 kHz mono 16-bit PCM WAV (the format
//! Whisper wants anyway) into the server's temp directory. Loudness analysis
//! then reads that WAV directly in Rust: the per-window RMS levels drive
//! silence detection, the volume profile, peak detection and multi-camera
//! speaker detection, all as pure functions that are unit-tested without
//! ffmpeg.

use std::io::{BufReader, Read};
use std::path::{Path, PathBuf};

use anyhow::{Context, Result, bail};
use serde::Deserialize;
use tempfile::TempPath;
use tokio::process::Command;
use tracing::{info, warn};

use crate::config::ServerConfig;
use crate::ffmpeg::{ffmpeg, media_arg};
use crate::process::run_checked;
use crate::types::{
    AudioAnalysis, Speaker, SpeakerTurn, Transcript, TranscriptSegment, VolumePoint, Word,
};

/// Sample rate used for extracted analysis audio.
pub const ANALYSIS_SAMPLE_RATE: u32 = 16_000;

/// Length of one loudness window, in seconds.
pub const LEVEL_WINDOW_SECS: f64 = 0.1;

/// Upper bound on the number of points in a reported volume profile.
const MAX_PROFILE_POINTS: usize = 600;

/// Maximum number of reported peak moments.
const MAX_PEAKS: usize = 20;

/// Minimum spacing between reported peaks, in seconds.
const MIN_PEAK_SPACING_SECS: f64 = 3.0;

/// dB margin the loudest input needs over the runner-up to claim a window.
const SPEAKER_MARGIN_DB: f64 = 3.0;

/// Floor used when converting silence (RMS 0) to dB.
const DB_FLOOR: f64 = -120.0;

/// Convert linear RMS amplitude to dBFS.
pub fn rms_to_db(rms: f64) -> f64 {
    if rms <= 0.0 {
        DB_FLOOR
    } else {
        (20.0 * rms.log10()).max(DB_FLOOR)
    }
}

// ============================================================================
// Extraction
// ============================================================================

/// Extract a video's audio track to a temporary 16 kHz mono WAV.
///
/// The returned [`TempPath`] deletes the file when dropped, so the WAV is
/// cleaned up on every exit path (including errors and job cancellation).
pub async fn extract_audio(video: &Path, temp_dir: &Path) -> Result<TempPath> {
    std::fs::create_dir_all(temp_dir)
        .with_context(|| format!("Failed to create temp dir {}", temp_dir.display()))?;
    let temp = tempfile::Builder::new()
        .prefix("audio_")
        .suffix(".wav")
        .tempfile_in(temp_dir)
        .context("Failed to create temporary audio file")?
        .into_temp_path();

    info!("Extracting audio from {}", video.display());
    run_checked(
        ffmpeg()
            .arg("-y")
            .arg("-i")
            .arg(media_arg(video))
            .args(["-vn", "-sn", "-dn", "-map", "0:a:0", "-acodec", "pcm_s16le"])
            .args([
                "-ar",
                &ANALYSIS_SAMPLE_RATE.to_string(),
                "-ac",
                "1",
                "-f",
                "wav",
            ])
            .arg(media_arg(&temp)),
        "ffmpeg audio extraction",
    )
    .await
    .with_context(|| {
        format!(
            "Could not extract audio from {} (does it have an audio track?)",
            video.display()
        )
    })?;
    Ok(temp)
}

// ============================================================================
// Loudness analysis
// ============================================================================

/// Per-window RMS loudness of an audio track.
#[derive(Debug, Clone, PartialEq)]
pub struct LevelTrack {
    pub sample_rate: u32,
    /// Window length in seconds.
    pub window: f64,
    /// Linear RMS per window, in [0, 1].
    pub rms: Vec<f64>,
    /// Exact duration in seconds (from the sample count).
    pub duration: f64,
}

impl LevelTrack {
    /// Loudness of window `i` in dBFS.
    pub fn db(&self, i: usize) -> f64 {
        rms_to_db(self.rms[i])
    }
}

/// Compute windowed RMS levels from 16-bit samples.
pub fn levels_from_samples<I: IntoIterator<Item = i16>>(
    samples: I,
    sample_rate: u32,
    window_secs: f64,
) -> LevelTrack {
    let window_len = ((sample_rate as f64 * window_secs).round() as usize).max(1);
    let mut rms = Vec::new();
    let mut acc = 0.0_f64;
    let mut count = 0usize;
    let mut total = 0usize;
    for s in samples {
        let v = s as f64 / 32768.0;
        acc += v * v;
        count += 1;
        total += 1;
        if count == window_len {
            rms.push((acc / count as f64).sqrt());
            acc = 0.0;
            count = 0;
        }
    }
    if count > 0 {
        rms.push((acc / count as f64).sqrt());
    }
    LevelTrack {
        sample_rate,
        window: window_len as f64 / sample_rate as f64,
        rms,
        duration: total as f64 / sample_rate as f64,
    }
}

/// Stream a 16-bit PCM WAV file and compute its loudness track.
///
/// Multi-channel audio is down-mixed by averaging. Only 16-bit integer PCM is
/// supported (which is what [`extract_audio`] produces).
pub fn read_wav_levels(path: &Path, window_secs: f64) -> Result<LevelTrack> {
    let file = std::fs::File::open(path)
        .with_context(|| format!("Failed to open WAV {}", path.display()))?;
    read_wav_levels_from(BufReader::with_capacity(1 << 16, file), window_secs)
}

/// [`read_wav_levels`] over any reader (exposed for tests).
pub fn read_wav_levels_from<R: Read>(mut r: R, window_secs: f64) -> Result<LevelTrack> {
    let mut header = [0u8; 12];
    r.read_exact(&mut header).context("WAV file too short")?;
    if &header[0..4] != b"RIFF" || &header[8..12] != b"WAVE" {
        bail!("Not a RIFF/WAVE file");
    }

    let mut channels: u16 = 0;
    let mut sample_rate: u32 = 0;
    let mut bits: u16 = 0;
    loop {
        let mut chunk = [0u8; 8];
        r.read_exact(&mut chunk)
            .context("WAV file has no data chunk")?;
        let id = &chunk[0..4];
        let size = u32::from_le_bytes([chunk[4], chunk[5], chunk[6], chunk[7]]);
        if id == b"fmt " {
            let mut fmt = vec![0u8; size as usize];
            r.read_exact(&mut fmt).context("Truncated WAV fmt chunk")?;
            if fmt.len() < 16 {
                bail!("Invalid WAV fmt chunk");
            }
            let format_tag = u16::from_le_bytes([fmt[0], fmt[1]]);
            channels = u16::from_le_bytes([fmt[2], fmt[3]]);
            sample_rate = u32::from_le_bytes([fmt[4], fmt[5], fmt[6], fmt[7]]);
            bits = u16::from_le_bytes([fmt[14], fmt[15]]);
            if !(format_tag == 1 || format_tag == 0xFFFE) || bits != 16 {
                bail!(
                    "Unsupported WAV encoding (need 16-bit PCM, got tag {format_tag}, {bits} bits)"
                );
            }
            if size % 2 == 1 {
                let mut pad = [0u8; 1];
                r.read_exact(&mut pad)?;
            }
        } else if id == b"data" {
            if channels == 0 || sample_rate == 0 || bits == 0 {
                bail!("WAV data chunk before fmt chunk");
            }
            // ffmpeg may write 0 / 0xFFFFFFFF when the size is unknown: read to EOF.
            let limit = if size == 0 || size == u32::MAX {
                u64::MAX
            } else {
                size as u64
            };
            let samples = PcmSamples::new(r.take(limit), channels as usize);
            return Ok(levels_from_samples(samples, sample_rate, window_secs));
        } else {
            let skip = size as u64 + (size as u64 % 2);
            std::io::copy(&mut (&mut r).take(skip), &mut std::io::sink())?;
        }
    }
}

/// Iterator over down-mixed 16-bit samples of an interleaved PCM stream.
struct PcmSamples<R: Read> {
    reader: R,
    channels: usize,
    buf: Vec<u8>,
    pos: usize,
    len: usize,
}

impl<R: Read> PcmSamples<R> {
    fn new(reader: R, channels: usize) -> Self {
        Self {
            reader,
            channels: channels.max(1),
            buf: vec![0u8; 1 << 16],
            pos: 0,
            len: 0,
        }
    }

    fn next_i16(&mut self) -> Option<i16> {
        if self.len - self.pos < 2 {
            // Move any leftover byte to the front and refill.
            let leftover = self.len - self.pos;
            self.buf.copy_within(self.pos..self.len, 0);
            self.pos = 0;
            self.len = leftover;
            loop {
                match self.reader.read(&mut self.buf[self.len..]) {
                    Ok(0) => break,
                    Ok(n) => {
                        self.len += n;
                        if self.len >= 2 {
                            break;
                        }
                    },
                    Err(e) if e.kind() == std::io::ErrorKind::Interrupted => continue,
                    Err(_) => break,
                }
            }
            if self.len < 2 {
                return None;
            }
        }
        let v = i16::from_le_bytes([self.buf[self.pos], self.buf[self.pos + 1]]);
        self.pos += 2;
        Some(v)
    }
}

impl<R: Read> Iterator for PcmSamples<R> {
    type Item = i16;

    fn next(&mut self) -> Option<i16> {
        if self.channels == 1 {
            return self.next_i16();
        }
        let mut sum = 0i32;
        for _ in 0..self.channels {
            sum += self.next_i16()? as i32;
        }
        Some((sum / self.channels as i32) as i16)
    }
}

/// Find silent intervals: runs of windows below `silence_db` lasting at least
/// `min_duration` seconds.
pub fn detect_silence(track: &LevelTrack, silence_db: f64, min_duration: f64) -> Vec<(f64, f64)> {
    let mut out = Vec::new();
    let mut run_start: Option<usize> = None;
    let n = track.rms.len();
    for i in 0..=n {
        let silent = i < n && track.db(i) < silence_db;
        match (silent, run_start) {
            (true, None) => run_start = Some(i),
            (false, Some(s)) => {
                let start = s as f64 * track.window;
                let end = (i as f64 * track.window).min(track.duration);
                if end - start >= min_duration {
                    out.push((round3(start), round3(end)));
                }
                run_start = None;
            },
            _ => {},
        }
    }
    out
}

/// Downsample the loudness track into at most `max_points` profile points.
pub fn volume_profile(track: &LevelTrack, max_points: usize) -> Vec<VolumePoint> {
    if track.rms.is_empty() || max_points == 0 {
        return Vec::new();
    }
    // Group at least 0.5 s per point, more for long media.
    let min_group = (0.5 / track.window).round().max(1.0) as usize;
    let group = min_group.max(track.rms.len().div_ceil(max_points));
    track
        .rms
        .chunks(group)
        .enumerate()
        .map(|(i, chunk)| {
            let mean_sq = chunk.iter().map(|r| r * r).sum::<f64>() / chunk.len() as f64;
            let rms = mean_sq.sqrt();
            VolumePoint {
                time: round3(i as f64 * group as f64 * track.window),
                rms: (rms * 1e4).round() / 1e4,
                db: (rms_to_db(rms) * 10.0).round() / 10.0,
            }
        })
        .collect()
}

/// Pick the loudest moments: local maxima of the profile above the 90th
/// percentile (and above the silence floor), at least
/// [`MIN_PEAK_SPACING_SECS`] apart, capped at [`MAX_PEAKS`].
pub fn detect_peaks(profile: &[VolumePoint], silence_db: f64) -> Vec<f64> {
    if profile.len() < 3 {
        return Vec::new();
    }
    let dbs: Vec<f64> = profile.iter().map(|p| p.db).collect();
    let threshold = percentile(&dbs, 90.0).max(silence_db);
    let mut candidates: Vec<(f64, f64)> = Vec::new();
    for i in 0..profile.len() {
        let v = profile[i].db;
        let left = if i > 0 { profile[i - 1].db } else { f64::MIN };
        let right = profile.get(i + 1).map(|p| p.db).unwrap_or(f64::MIN);
        if v > threshold && v >= left && v >= right {
            candidates.push((profile[i].time, v));
        }
    }
    // Loudest first, enforce spacing, then report chronologically.
    candidates.sort_by(|a, b| b.1.total_cmp(&a.1));
    let mut chosen: Vec<f64> = Vec::new();
    for (t, _) in candidates {
        if chosen
            .iter()
            .all(|c| (c - t).abs() >= MIN_PEAK_SPACING_SECS)
        {
            chosen.push(t);
            if chosen.len() == MAX_PEAKS {
                break;
            }
        }
    }
    chosen.sort_by(f64::total_cmp);
    chosen
}

/// Build the full [`AudioAnalysis`] for a loudness track.
pub fn analyze_levels(track: &LevelTrack, silence_db: f64, min_silence: f64) -> AudioAnalysis {
    let profile = volume_profile(track, MAX_PROFILE_POINTS);
    let peaks = detect_peaks(&profile, silence_db);
    let mean_sq = if track.rms.is_empty() {
        0.0
    } else {
        track.rms.iter().map(|r| r * r).sum::<f64>() / track.rms.len() as f64
    };
    let max_rms = track.rms.iter().copied().fold(0.0, f64::max);
    AudioAnalysis {
        duration: round3(track.duration),
        sample_rate: track.sample_rate,
        silence_segments: detect_silence(track, silence_db, min_silence),
        volume_profile: profile,
        peak_moments: peaks,
        mean_db: (rms_to_db(mean_sq.sqrt()) * 10.0).round() / 10.0,
        max_db: (rms_to_db(max_rms) * 10.0).round() / 10.0,
    }
}

/// Combine several tracks into one by taking the loudest input per window
/// (used to find silence common to all cameras).
pub fn combine_tracks_max(tracks: &[LevelTrack]) -> Option<LevelTrack> {
    let first = tracks.first()?;
    let n = tracks.iter().map(|t| t.rms.len()).min().unwrap_or(0);
    let rms = (0..n)
        .map(|i| tracks.iter().map(|t| t.rms[i]).fold(0.0, f64::max))
        .collect();
    Some(LevelTrack {
        sample_rate: first.sample_rate,
        window: first.window,
        rms,
        duration: tracks.iter().map(|t| t.duration).fold(f64::MAX, f64::min),
    })
}

/// Speaker ID for input index `i` (`SPEAKER_00`, `SPEAKER_01`, ...).
pub fn speaker_id(i: usize) -> String {
    format!("SPEAKER_{i:02}")
}

/// Energy-based speaker detection across time-synchronised inputs.
///
/// Assumes one camera/microphone per speaker. For each window the loudest
/// input (by at least [`SPEAKER_MARGIN_DB`], and above `silence_db`) is the
/// active speaker; ambiguous or silent windows keep the previous speaker.
/// Turns shorter than `min_turn` seconds are merged into the preceding turn so
/// the edit does not flicker between cameras.
pub fn detect_speaker_turns(
    tracks: &[LevelTrack],
    silence_db: f64,
    min_turn: f64,
) -> Vec<SpeakerTurn> {
    if tracks.len() < 2 {
        return Vec::new();
    }
    let window = tracks[0].window;
    let n = tracks.iter().map(|t| t.rms.len()).min().unwrap_or(0);
    if n == 0 {
        return Vec::new();
    }

    // Raw per-window labels.
    let mut labels: Vec<Option<usize>> = Vec::with_capacity(n);
    let mut current: Option<usize> = None;
    for i in 0..n {
        let mut dbs: Vec<(usize, f64)> = tracks
            .iter()
            .enumerate()
            .map(|(k, t)| (k, t.db(i)))
            .collect();
        dbs.sort_by(|a, b| b.1.total_cmp(&a.1));
        let (best, best_db) = dbs[0];
        let second_db = dbs.get(1).map(|d| d.1).unwrap_or(DB_FLOOR);
        if best_db >= silence_db && best_db - second_db >= SPEAKER_MARGIN_DB {
            current = Some(best);
        }
        labels.push(current);
    }
    // Leading windows before anyone speaks belong to the first speaker.
    let first_speaker = labels.iter().flatten().next().copied().unwrap_or(0);

    // Runs of identical labels.
    let mut runs: Vec<(usize, usize, usize)> = Vec::new(); // (speaker, start_idx, end_idx)
    for (i, label) in labels.iter().enumerate() {
        let spk = label.unwrap_or(first_speaker);
        match runs.last_mut() {
            Some(last) if last.0 == spk => last.2 = i + 1,
            _ => runs.push((spk, i, i + 1)),
        }
    }

    // Merge short runs into the previous turn.
    let mut turns: Vec<SpeakerTurn> = Vec::new();
    for (spk, s, e) in runs {
        let start = s as f64 * window;
        let end = e as f64 * window;
        match turns.last_mut() {
            Some(last) if last.speaker == speaker_id(spk) || end - start < min_turn => {
                last.end = end;
            },
            _ => turns.push(SpeakerTurn {
                speaker: speaker_id(spk),
                start,
                end,
            }),
        }
    }
    // A second pass collapses neighbours that became identical after merging.
    let mut merged: Vec<SpeakerTurn> = Vec::new();
    for t in turns {
        match merged.last_mut() {
            Some(last) if last.speaker == t.speaker => last.end = t.end,
            _ => merged.push(t),
        }
    }
    for t in &mut merged {
        t.start = round3(t.start);
        t.end = round3(t.end);
    }
    merged
}

/// Summarise speaker turns per speaker, attaching each speaker's source video.
pub fn summarize_speakers(turns: &[SpeakerTurn], sources: &[String]) -> Vec<Speaker> {
    sources
        .iter()
        .enumerate()
        .map(|(i, src)| {
            let id = speaker_id(i);
            let segs: Vec<(f64, f64)> = turns
                .iter()
                .filter(|t| t.speaker == id)
                .map(|t| (t.start, t.end))
                .collect();
            Speaker {
                total_speaking_time: round3(segs.iter().map(|(s, e)| e - s).sum()),
                segment_count: segs.len() as u32,
                segments: segs,
                id,
                source: Some(src.clone()),
            }
        })
        .collect()
}

/// Percentile (nearest-rank on sorted values).
pub fn percentile(values: &[f64], p: f64) -> f64 {
    if values.is_empty() {
        return 0.0;
    }
    let mut sorted = values.to_vec();
    sorted.sort_by(f64::total_cmp);
    let idx = ((p / 100.0) * (sorted.len() - 1) as f64).round() as usize;
    sorted[idx.min(sorted.len() - 1)]
}

fn round3(v: f64) -> f64 {
    (v * 1000.0).round() / 1000.0
}

// ============================================================================
// Transcription
// ============================================================================

/// Validate a Whisper language argument (ISO code or language name).
pub fn validate_language(lang: &str) -> Result<()> {
    let ok = !lang.is_empty()
        && lang.len() <= 32
        && lang.chars().next().is_some_and(|c| c.is_ascii_alphabetic())
        && lang
            .chars()
            .all(|c| c.is_ascii_alphabetic() || c == ' ' || c == '-' || c == '_');
    if !ok {
        bail!("Invalid language '{lang}' (expected an ISO code such as 'en' or a language name)");
    }
    Ok(())
}

/// Whisper CLI wrapper with an on-disk transcript cache.
pub struct Transcriber {
    whisper_bin: String,
    model: String,
    device: String,
    cache_dir: PathBuf,
    temp_dir: PathBuf,
}

impl Transcriber {
    /// Create a transcriber from the server configuration.
    pub fn new(config: &ServerConfig) -> Self {
        Self {
            whisper_bin: config.whisper_bin.clone(),
            model: config.whisper_model.clone(),
            device: config.whisper_device.clone(),
            cache_dir: config.cache_dir.join("transcripts"),
            temp_dir: config.temp_dir.clone(),
        }
    }

    /// Resolve the Whisper executable, or explain how to install it.
    pub fn whisper_path(&self) -> Result<PathBuf> {
        which::which(&self.whisper_bin).map_err(|_| {
            anyhow::anyhow!(
                "Whisper CLI '{}' not found in PATH. Install openai-whisper (pip install \
                 openai-whisper) or set WHISPER_BIN to a compatible executable.",
                self.whisper_bin
            )
        })
    }

    /// Cache key for a source media file + transcription parameters.
    ///
    /// Keyed on the *source video* (canonical path, size, mtime) rather than
    /// the temporary WAV, so repeated calls on the same video hit the cache.
    pub fn cache_key(&self, source: &Path, language: Option<&str>) -> Result<String> {
        let meta = std::fs::metadata(source)
            .with_context(|| format!("Cannot stat {}", source.display()))?;
        let mtime = meta
            .modified()
            .ok()
            .and_then(|m| m.duration_since(std::time::UNIX_EPOCH).ok())
            .map(|d| d.as_nanos())
            .unwrap_or(0);
        let canonical = source
            .canonicalize()
            .unwrap_or_else(|_| source.to_path_buf());
        let material = format!(
            "v2|{}|{}|{}|{}|{}",
            canonical.to_string_lossy(),
            meta.len(),
            mtime,
            self.model,
            language.unwrap_or("auto")
        );
        Ok(format!("{:016x}", fnv1a64(material.as_bytes())))
    }

    fn load_cached(&self, key: &str) -> Option<Transcript> {
        let path = self.cache_dir.join(format!("{key}.json"));
        let content = std::fs::read_to_string(&path).ok()?;
        match serde_json::from_str(&content) {
            Ok(t) => Some(t),
            Err(e) => {
                warn!(
                    "Ignoring corrupt transcript cache {}: {}",
                    path.display(),
                    e
                );
                let _ = std::fs::remove_file(&path);
                None
            },
        }
    }

    fn store_cached(&self, key: &str, transcript: &Transcript) {
        let result = (|| -> Result<()> {
            std::fs::create_dir_all(&self.cache_dir)?;
            let final_path = self.cache_dir.join(format!("{key}.json"));
            let tmp = tempfile::NamedTempFile::new_in(&self.cache_dir)?;
            std::fs::write(tmp.path(), serde_json::to_vec(transcript)?)?;
            tmp.persist(&final_path)?;
            Ok(())
        })();
        if let Err(e) = result {
            warn!("Failed to cache transcript: {:#}", e);
        }
    }

    /// Transcribe `audio` (extracted from `source`) with Whisper.
    ///
    /// Returns an error if Whisper is unavailable or fails; a failure is never
    /// disguised as an empty transcript, and failures are never cached.
    pub async fn transcribe(
        &self,
        source: &Path,
        audio: &Path,
        language: Option<&str>,
    ) -> Result<Transcript> {
        if let Some(lang) = language {
            validate_language(lang)?;
        }
        let key = self.cache_key(source, language)?;
        if let Some(cached) = self.load_cached(&key) {
            info!("Using cached transcript for {}", source.display());
            return Ok(cached);
        }

        let whisper = self.whisper_path()?;
        std::fs::create_dir_all(&self.temp_dir)?;
        let out_dir = tempfile::Builder::new()
            .prefix("whisper_")
            .tempdir_in(&self.temp_dir)
            .context("Failed to create whisper output dir")?;

        info!(
            "Transcribing {} with whisper model '{}'",
            source.display(),
            self.model
        );
        let mut cmd = Command::new(&whisper);
        cmd.arg(audio)
            .args(["--model", &self.model])
            .args(["--device", &self.device])
            .args([
                "--output_format",
                "json",
                "--word_timestamps",
                "True",
                "--verbose",
                "False",
            ])
            .arg("--output_dir")
            .arg(out_dir.path());
        if self.device == "cpu" {
            cmd.args(["--fp16", "False"]);
        }
        if let Some(lang) = language {
            cmd.args(["--language", lang]);
        }
        run_checked(&mut cmd, "whisper transcription").await?;

        let stem = audio
            .file_stem()
            .ok_or_else(|| anyhow::anyhow!("Audio path has no file name"))?
            .to_string_lossy()
            .to_string();
        let json_path = out_dir.path().join(format!("{stem}.json"));
        let content = std::fs::read_to_string(&json_path).with_context(|| {
            format!(
                "Whisper finished but produced no JSON output at {}",
                json_path.display()
            )
        })?;
        let transcript = parse_whisper_json(&content, language)?;
        self.store_cached(&key, &transcript);
        Ok(transcript)
    }
}

/// Parse Whisper's JSON output format.
pub fn parse_whisper_json(content: &str, language_hint: Option<&str>) -> Result<Transcript> {
    #[derive(Deserialize)]
    struct WhisperOutput {
        #[serde(default)]
        text: String,
        language: Option<String>,
        #[serde(default)]
        segments: Vec<WhisperSegment>,
    }
    #[derive(Deserialize)]
    struct WhisperSegment {
        #[serde(default)]
        id: Option<u32>,
        start: f64,
        end: f64,
        #[serde(default)]
        text: String,
        #[serde(default)]
        words: Vec<WhisperWord>,
    }
    #[derive(Deserialize)]
    struct WhisperWord {
        word: String,
        start: f64,
        end: f64,
        probability: Option<f64>,
    }

    let out: WhisperOutput =
        serde_json::from_str(content).context("Failed to parse Whisper JSON output")?;
    let segments = out
        .segments
        .into_iter()
        .enumerate()
        .map(|(i, s)| TranscriptSegment {
            id: s.id.unwrap_or(i as u32),
            start: s.start,
            end: s.end.max(s.start),
            text: s.text.trim().to_string(),
            words: s
                .words
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
        text: out.text.trim().to_string(),
        language: out
            .language
            .or_else(|| language_hint.map(str::to_string))
            .unwrap_or_else(|| "unknown".to_string()),
        segments,
    })
}

/// 64-bit FNV-1a hash (stable across Rust versions, unlike `DefaultHasher`).
fn fnv1a64(bytes: &[u8]) -> u64 {
    let mut hash: u64 = 0xcbf2_9ce4_8422_2325;
    for b in bytes {
        hash ^= *b as u64;
        hash = hash.wrapping_mul(0x0100_0000_01b3);
    }
    hash
}

#[cfg(test)]
mod tests {
    use super::*;

    fn track(db_values: &[f64]) -> LevelTrack {
        LevelTrack {
            sample_rate: 16000,
            window: 0.1,
            rms: db_values.iter().map(|d| 10f64.powf(d / 20.0)).collect(),
            duration: db_values.len() as f64 * 0.1,
        }
    }

    fn wav_bytes(samples: &[i16], sample_rate: u32, channels: u16, extra_chunk: bool) -> Vec<u8> {
        let mut data = Vec::new();
        for s in samples {
            data.extend_from_slice(&s.to_le_bytes());
        }
        let mut out = Vec::new();
        out.extend_from_slice(b"RIFF");
        out.extend_from_slice(&0u32.to_le_bytes());
        out.extend_from_slice(b"WAVE");
        if extra_chunk {
            out.extend_from_slice(b"LIST");
            out.extend_from_slice(&3u32.to_le_bytes());
            out.extend_from_slice(&[1, 2, 3, 0]); // 3 bytes + pad
        }
        out.extend_from_slice(b"fmt ");
        out.extend_from_slice(&16u32.to_le_bytes());
        out.extend_from_slice(&1u16.to_le_bytes());
        out.extend_from_slice(&channels.to_le_bytes());
        out.extend_from_slice(&sample_rate.to_le_bytes());
        out.extend_from_slice(&(sample_rate * 2 * channels as u32).to_le_bytes());
        out.extend_from_slice(&(2 * channels).to_le_bytes());
        out.extend_from_slice(&16u16.to_le_bytes());
        out.extend_from_slice(b"data");
        out.extend_from_slice(&(data.len() as u32).to_le_bytes());
        out.extend_from_slice(&data);
        out
    }

    #[test]
    fn db_conversion() {
        assert_eq!(rms_to_db(0.0), DB_FLOOR);
        assert!((rms_to_db(1.0)).abs() < 1e-9);
        assert!((rms_to_db(0.1) + 20.0).abs() < 1e-9);
    }

    #[test]
    fn levels_from_constant_samples() {
        let t = levels_from_samples(vec![16384i16; 3200], 16000, 0.1);
        assert_eq!(t.rms.len(), 2);
        assert!((t.rms[0] - 0.5).abs() < 1e-6);
        assert!((t.duration - 0.2).abs() < 1e-9);
    }

    #[test]
    fn wav_parsing_mono_with_extra_chunk() {
        let mut samples = vec![0i16; 1600];
        samples.extend(vec![8192i16; 1600]);
        let bytes = wav_bytes(&samples, 16000, 1, true);
        let t = read_wav_levels_from(&bytes[..], 0.1).unwrap();
        assert_eq!(t.rms.len(), 2);
        assert_eq!(t.rms[0], 0.0);
        assert!((t.rms[1] - 0.25).abs() < 1e-6);
    }

    #[test]
    fn wav_parsing_stereo_downmix() {
        // L=16384, R=0 -> mono 8192
        let samples: Vec<i16> = (0..3200)
            .map(|i| if i % 2 == 0 { 16384 } else { 0 })
            .collect();
        let bytes = wav_bytes(&samples, 16000, 2, false);
        let t = read_wav_levels_from(&bytes[..], 0.1).unwrap();
        assert_eq!(t.rms.len(), 1);
        assert!((t.rms[0] - 0.25).abs() < 1e-6);
    }

    #[test]
    fn wav_rejects_garbage() {
        assert!(read_wav_levels_from(&b"not a wav file at all"[..], 0.1).is_err());
    }

    #[test]
    fn silence_detection_respects_min_duration() {
        // 1s loud, 2.5s silent, 1s loud, 0.5s silent
        let mut v = vec![-10.0; 10];
        v.extend(vec![-60.0; 25]);
        v.extend(vec![-10.0; 10]);
        v.extend(vec![-60.0; 5]);
        let s = detect_silence(&track(&v), -40.0, 2.0);
        assert_eq!(s, vec![(1.0, 3.5)]);
        let s = detect_silence(&track(&v), -40.0, 0.4);
        assert_eq!(s.len(), 2);
        assert_eq!(s[1], (4.5, 5.0));
    }

    #[test]
    fn profile_is_capped() {
        let t = track(&vec![-20.0; 100_000]);
        let p = volume_profile(&t, 600);
        assert!(p.len() <= 600);
        assert!((p[0].db + 20.0).abs() < 0.2);
    }

    #[test]
    fn peaks_found_and_spaced() {
        let mut v = vec![-30.0; 200];
        v[50] = -5.0;
        v[52] = -6.0; // too close to 50 once grouped
        v[150] = -4.0;
        let t = track(&v);
        let profile = volume_profile(&t, 600);
        let peaks = detect_peaks(&profile, -40.0);
        assert_eq!(peaks.len(), 2, "{peaks:?}");
        assert!(peaks[0] < peaks[1]);
    }

    #[test]
    fn flat_audio_has_no_peaks() {
        let t = track(&vec![-20.0; 200]);
        assert!(detect_peaks(&volume_profile(&t, 600), -40.0).is_empty());
    }

    #[test]
    fn speaker_turns_follow_loudest_input() {
        // Speaker 0 talks for 3s, then speaker 1 for 3s, with a 0.2s blip of 0.
        let mut a = vec![-10.0; 30];
        a.extend(vec![-50.0; 30]);
        let mut b = vec![-50.0; 30];
        b.extend(vec![-10.0; 30]);
        a[45] = -5.0;
        a[46] = -5.0;
        let turns = detect_speaker_turns(&[track(&a), track(&b)], -40.0, 0.5);
        assert_eq!(turns.len(), 2, "{turns:?}");
        assert_eq!(turns[0].speaker, "SPEAKER_00");
        assert_eq!(turns[0].start, 0.0);
        assert_eq!(turns[1].speaker, "SPEAKER_01");
        assert!((turns[1].start - 3.0).abs() < 1e-9);
        assert!((turns[1].end - 6.0).abs() < 1e-9);
    }

    #[test]
    fn speaker_turns_need_two_inputs() {
        assert!(detect_speaker_turns(&[track(&[-10.0; 10])], -40.0, 0.5).is_empty());
    }

    #[test]
    fn speaker_summary() {
        let turns = vec![
            SpeakerTurn {
                speaker: "SPEAKER_00".into(),
                start: 0.0,
                end: 2.0,
            },
            SpeakerTurn {
                speaker: "SPEAKER_01".into(),
                start: 2.0,
                end: 3.0,
            },
            SpeakerTurn {
                speaker: "SPEAKER_00".into(),
                start: 3.0,
                end: 4.0,
            },
        ];
        let s = summarize_speakers(&turns, &["a.mp4".into(), "b.mp4".into()]);
        assert_eq!(s[0].segment_count, 2);
        assert!((s[0].total_speaking_time - 3.0).abs() < 1e-9);
        assert_eq!(s[1].source.as_deref(), Some("b.mp4"));
    }

    #[test]
    fn combine_tracks_takes_max() {
        let c =
            combine_tracks_max(&[track(&[-10.0, -60.0]), track(&[-60.0, -20.0, -5.0])]).unwrap();
        assert_eq!(c.rms.len(), 2);
        assert!((c.db(0) + 10.0).abs() < 1e-6);
        assert!((c.db(1) + 20.0).abs() < 1e-6);
    }

    #[test]
    fn whisper_json_parsing() {
        let json = r#"{"text": " Hello there. ", "language": "en", "segments": [
            {"id": 0, "start": 0.0, "end": 1.5, "text": " Hello there.",
             "words": [{"word": " Hello", "start": 0.0, "end": 0.5, "probability": 0.9}]},
            {"start": 2.0, "end": 1.0, "text": "x"}
        ]}"#;
        let t = parse_whisper_json(json, None).unwrap();
        assert_eq!(t.text, "Hello there.");
        assert_eq!(t.segments.len(), 2);
        assert_eq!(t.segments[0].text, "Hello there.");
        assert_eq!(t.segments[0].words.len(), 1);
        assert_eq!(t.segments[1].id, 1);
        assert_eq!(t.segments[1].end, 2.0, "end clamped to start");
    }

    #[test]
    fn whisper_json_language_fallback() {
        let t = parse_whisper_json(r#"{"text":"","segments":[]}"#, Some("de")).unwrap();
        assert_eq!(t.language, "de");
        assert!(parse_whisper_json("not json", None).is_err());
    }

    #[test]
    fn language_validation() {
        assert!(validate_language("en").is_ok());
        assert!(validate_language("Brazilian Portuguese").is_ok());
        assert!(validate_language("--model").is_err());
        assert!(validate_language("").is_err());
        assert!(validate_language("en;rm").is_err());
    }

    #[test]
    fn transcript_cache_roundtrip_and_key_stability() {
        let tmp = tempfile::tempdir().unwrap();
        let cfg = ServerConfig::for_root(tmp.path());
        let tr = Transcriber::new(&cfg);
        let src = tmp.path().join("video.mp4");
        std::fs::write(&src, b"fake").unwrap();
        let k1 = tr.cache_key(&src, Some("en")).unwrap();
        assert_eq!(k1, tr.cache_key(&src, Some("en")).unwrap());
        assert_ne!(k1, tr.cache_key(&src, Some("fr")).unwrap());
        assert!(tr.load_cached(&k1).is_none());
        let t = Transcript {
            text: "hi".into(),
            language: "en".into(),
            segments: vec![],
        };
        tr.store_cached(&k1, &t);
        assert_eq!(tr.load_cached(&k1).unwrap().text, "hi");
        // Corrupt cache entries are discarded rather than failing.
        std::fs::write(
            cfg.cache_dir.join("transcripts").join(format!("{k1}.json")),
            "{",
        )
        .unwrap();
        assert!(tr.load_cached(&k1).is_none());
    }

    #[tokio::test]
    async fn transcribe_without_whisper_is_an_error() {
        let tmp = tempfile::tempdir().unwrap();
        let cfg = ServerConfig::for_root(tmp.path());
        let tr = Transcriber::new(&cfg);
        let src = tmp.path().join("video.mp4");
        std::fs::write(&src, b"fake").unwrap();
        let err = tr.transcribe(&src, &src, None).await.unwrap_err();
        assert!(err.to_string().contains("not found"), "{err}");
    }

    #[test]
    fn percentile_basic() {
        assert_eq!(percentile(&[], 90.0), 0.0);
        assert_eq!(percentile(&[1.0, 2.0, 3.0, 4.0, 5.0], 50.0), 3.0);
        assert_eq!(percentile(&[1.0, 2.0, 3.0, 4.0, 5.0], 100.0), 5.0);
    }
}
