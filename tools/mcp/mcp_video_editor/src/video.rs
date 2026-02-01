//! Video processing for video editor.
//!
//! Handles video editing, composition, effects, and rendering via ffmpeg.

use crate::types::{EditDecision, OutputSettings, RenderOptions, ServerConfig};
use anyhow::{Context, Result};
use std::path::{Path, PathBuf};
use std::process::Stdio;
use tempfile::TempDir;
use tokio::process::Command;
use tracing::info;

/// Video processor for editing operations
pub struct VideoProcessor {
    config: ServerConfig,
    temp_dir: PathBuf,
}

impl VideoProcessor {
    /// Create a new video processor
    pub fn new(config: ServerConfig) -> Result<Self> {
        let temp_dir = PathBuf::from(&config.temp_dir);
        std::fs::create_dir_all(&temp_dir)?;

        Ok(Self { config, temp_dir })
    }

    /// Get video information using ffprobe
    #[allow(dead_code)]
    pub async fn get_video_info(&self, video_path: &str) -> Result<VideoInfo> {
        let output = Command::new("ffprobe")
            .args([
                "-v",
                "error",
                "-show_entries",
                "format=duration,size,bit_rate:stream=width,height,r_frame_rate,codec_name",
                "-of",
                "json",
                video_path,
            ])
            .output()
            .await
            .context("Failed to run ffprobe")?;

        if !output.status.success() {
            anyhow::bail!(
                "ffprobe failed: {}",
                String::from_utf8_lossy(&output.stderr)
            );
        }

        #[derive(serde::Deserialize)]
        struct FfprobeOutput {
            format: Option<FfprobeFormat>,
            streams: Option<Vec<FfprobeStream>>,
        }

        #[derive(serde::Deserialize)]
        struct FfprobeFormat {
            duration: Option<String>,
            size: Option<String>,
            bit_rate: Option<String>,
        }

        #[derive(serde::Deserialize)]
        struct FfprobeStream {
            width: Option<u32>,
            height: Option<u32>,
            r_frame_rate: Option<String>,
            codec_name: Option<String>,
        }

        let probe: FfprobeOutput = serde_json::from_slice(&output.stdout)?;

        let format = probe.format.unwrap_or(FfprobeFormat {
            duration: None,
            size: None,
            bit_rate: None,
        });

        let video_stream = probe
            .streams
            .and_then(|s| s.into_iter().find(|s| s.width.is_some()));

        let (width, height, fps, codec) = if let Some(stream) = video_stream {
            let fps = stream.r_frame_rate.and_then(|r| {
                let parts: Vec<&str> = r.split('/').collect();
                if parts.len() == 2 {
                    let num: f64 = parts[0].parse().ok()?;
                    let den: f64 = parts[1].parse().ok()?;
                    Some(num / den)
                } else {
                    r.parse().ok()
                }
            });
            (
                stream.width.unwrap_or(0),
                stream.height.unwrap_or(0),
                fps.unwrap_or(30.0),
                stream.codec_name.unwrap_or_default(),
            )
        } else {
            (0, 0, 30.0, String::new())
        };

        Ok(VideoInfo {
            duration: format.duration.and_then(|d| d.parse().ok()).unwrap_or(0.0),
            width,
            height,
            fps,
            codec,
            file_size: format.size.and_then(|s| s.parse().ok()).unwrap_or(0),
            bitrate: format.bit_rate.and_then(|b| b.parse().ok()).unwrap_or(0),
        })
    }

    /// Detect scene changes in video
    pub async fn detect_scene_changes(&self, video_path: &str) -> Result<Vec<f64>> {
        info!("Detecting scene changes in: {}", video_path);

        // Use ffmpeg with scene detection filter
        let output = Command::new("ffmpeg")
            .args([
                "-i",
                video_path,
                "-vf",
                "select='gt(scene,0.3)',metadata=print:file=-",
                "-f",
                "null",
                "-",
            ])
            .stderr(Stdio::piped())
            .stdout(Stdio::piped())
            .output()
            .await
            .context("Failed to run ffmpeg for scene detection")?;

        let stdout = String::from_utf8_lossy(&output.stdout);
        let stderr = String::from_utf8_lossy(&output.stderr);

        let mut scene_changes = Vec::new();

        // Parse pts_time from output
        for line in stdout.lines().chain(stderr.lines()) {
            if let Some(pts_idx) = line.find("pts_time:")
                && let Some(time_str) = line[pts_idx + 9..].split_whitespace().next()
                && let Ok(time) = time_str.parse::<f64>()
            {
                scene_changes.push(time);
            }
        }

        info!("Detected {} scene changes", scene_changes.len());
        Ok(scene_changes)
    }

    /// Extract a clip from video
    pub async fn extract_clip(
        &self,
        video_path: &str,
        start_time: f64,
        end_time: f64,
        output_path: &str,
    ) -> Result<()> {
        info!("Extracting clip from {} to {}", start_time, end_time);

        let duration = end_time - start_time;

        let output = Command::new("ffmpeg")
            .args([
                "-i",
                video_path,
                "-ss",
                &start_time.to_string(),
                "-t",
                &duration.to_string(),
                "-c",
                "copy",
                "-y",
                output_path,
            ])
            .stderr(Stdio::piped())
            .output()
            .await
            .context("Failed to run ffmpeg for clip extraction")?;

        if !output.status.success() {
            // Try re-encoding if copy fails
            let output = Command::new("ffmpeg")
                .args([
                    "-i",
                    video_path,
                    "-ss",
                    &start_time.to_string(),
                    "-t",
                    &duration.to_string(),
                    "-c:v",
                    "libx264",
                    "-c:a",
                    "aac",
                    "-y",
                    output_path,
                ])
                .stderr(Stdio::piped())
                .output()
                .await?;

            if !output.status.success() {
                anyhow::bail!(
                    "ffmpeg clip extraction failed: {}",
                    String::from_utf8_lossy(&output.stderr)
                );
            }
        }

        Ok(())
    }

    /// Render video from edit decision list
    pub async fn render_from_edl(
        &self,
        _video_inputs: &[String],
        edit_decision_list: &[EditDecision],
        output_settings: &OutputSettings,
        render_options: &RenderOptions,
    ) -> Result<RenderResult> {
        info!(
            "Rendering video from {} edit decisions",
            edit_decision_list.len()
        );

        // Determine output path
        let output_path = output_settings.output_path.clone().unwrap_or_else(|| {
            self.temp_dir
                .join(format!("rendered_{}.mp4", uuid::Uuid::new_v4()))
                .to_string_lossy()
                .to_string()
        });

        // For complex EDL, we need to use ffmpeg's concat demuxer or filter_complex
        // For now, implement a simplified version using concat

        // Create a concat file
        let concat_dir = TempDir::new()?;
        let mut segment_files = Vec::new();

        for (i, decision) in edit_decision_list.iter().enumerate() {
            let segment_path = concat_dir.path().join(format!("segment_{:04}.mp4", i));

            // Extract the segment
            self.extract_clip(
                &decision.source,
                decision.timestamp,
                decision.timestamp + decision.duration,
                segment_path.to_str().unwrap(),
            )
            .await?;

            segment_files.push(segment_path);
        }

        // Create concat file
        let concat_file = concat_dir.path().join("concat.txt");
        let concat_content: String = segment_files
            .iter()
            .map(|p| format!("file '{}'\n", p.to_string_lossy()))
            .collect();
        std::fs::write(&concat_file, concat_content)?;

        // Determine codec
        let codec = self.determine_codec(render_options);

        // Parse resolution
        let (width, height) = self.parse_resolution(&output_settings.resolution)?;

        // Build ffmpeg command for concatenation
        let mut cmd = Command::new("ffmpeg");
        cmd.args([
            "-f",
            "concat",
            "-safe",
            "0",
            "-i",
            concat_file.to_str().unwrap(),
        ]);

        // Add video filters for resolution
        cmd.args(["-vf", &format!("scale={}:{}", width, height)]);

        // Add codec settings
        cmd.args([
            "-c:v",
            &codec,
            "-b:v",
            &output_settings.bitrate,
            "-c:a",
            "aac",
            "-r",
            &output_settings.fps.to_string(),
            "-y",
            &output_path,
        ]);

        let output = cmd.stderr(Stdio::piped()).output().await?;

        if !output.status.success() {
            anyhow::bail!(
                "ffmpeg render failed: {}",
                String::from_utf8_lossy(&output.stderr)
            );
        }

        // Get output file info
        let file_stats = std::fs::metadata(&output_path)?;

        Ok(RenderResult {
            success: true,
            output_path,
            duration: edit_decision_list.iter().map(|d| d.duration).sum(),
            fps: output_settings.fps,
            resolution: output_settings.resolution.clone(),
            file_size: file_stats.len(),
            codec,
        })
    }

    /// Add captions/subtitles to video
    pub async fn add_subtitles(
        &self,
        video_path: &str,
        srt_path: &str,
        output_path: &str,
    ) -> Result<()> {
        info!("Adding subtitles to video");

        let output = Command::new("ffmpeg")
            .args([
                "-i",
                video_path,
                "-vf",
                &format!("subtitles={}", srt_path),
                "-c:a",
                "copy",
                "-y",
                output_path,
            ])
            .stderr(Stdio::piped())
            .output()
            .await?;

        if !output.status.success() {
            anyhow::bail!(
                "ffmpeg subtitle addition failed: {}",
                String::from_utf8_lossy(&output.stderr)
            );
        }

        Ok(())
    }

    /// Determine the best codec based on render options
    fn determine_codec(&self, render_options: &RenderOptions) -> String {
        if !render_options.hardware_acceleration || !self.config.performance.enable_gpu {
            return "libx264".to_string();
        }

        // Check for hardware encoders
        // In a full implementation, we'd probe ffmpeg for available encoders
        // For now, default to libx264 as it's most compatible
        "libx264".to_string()
    }

    /// Parse resolution string into width and height
    fn parse_resolution(&self, resolution: &str) -> Result<(u32, u32)> {
        let parts: Vec<&str> = resolution.split('x').collect();
        if parts.len() != 2 {
            anyhow::bail!("Invalid resolution format: {}", resolution);
        }

        let width: u32 = parts[0].parse()?;
        let height: u32 = parts[1].parse()?;

        Ok((width, height))
    }

    /// Generate SRT subtitle file from transcript
    pub fn generate_srt(&self, segments: &[(f64, f64, String)], output_path: &Path) -> Result<()> {
        let mut content = String::new();

        for (i, (start, end, text)) in segments.iter().enumerate() {
            content.push_str(&format!("{}\n", i + 1));
            content.push_str(&format!(
                "{} --> {}\n",
                self.format_srt_timestamp(*start),
                self.format_srt_timestamp(*end)
            ));
            content.push_str(&format!("{}\n\n", text.trim()));
        }

        std::fs::write(output_path, content)?;
        Ok(())
    }

    /// Format timestamp for SRT format
    fn format_srt_timestamp(&self, seconds: f64) -> String {
        let hours = (seconds / 3600.0) as u32;
        let minutes = ((seconds % 3600.0) / 60.0) as u32;
        let secs = seconds % 60.0;

        format!("{:02}:{:02}:{:06.3}", hours, minutes, secs).replace('.', ",")
    }

    /// Get the temp directory path
    #[allow(dead_code)]
    pub fn temp_dir(&self) -> &Path {
        &self.temp_dir
    }
}

/// Video information
#[allow(dead_code)]
#[derive(Debug, Clone, serde::Serialize, serde::Deserialize)]
pub struct VideoInfo {
    pub duration: f64,
    pub width: u32,
    pub height: u32,
    pub fps: f64,
    pub codec: String,
    pub file_size: u64,
    pub bitrate: u64,
}

/// Result of video rendering
#[derive(Debug, Clone, serde::Serialize, serde::Deserialize)]
pub struct RenderResult {
    pub success: bool,
    pub output_path: String,
    pub duration: f64,
    pub fps: u32,
    pub resolution: String,
    pub file_size: u64,
    pub codec: String,
}
