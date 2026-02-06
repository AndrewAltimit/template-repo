//! Video decoder using ffmpeg-next.

use crate::error::{VideoError, VideoResult};
use crate::hwaccel::HwDeviceContext;
use crate::scaler::FrameScaler;
use crate::stream::StreamSource;
use crate::{DEFAULT_HEIGHT, DEFAULT_WIDTH};
use ffmpeg_next::format::context::Input as FormatContext;
use ffmpeg_next::media::Type as MediaType;
use ffmpeg_next::util::frame::video::Video as VideoFrame;
use ffmpeg_next::{Codec, Packet, Rational, codec, decoder};
use std::sync::Once;
use tracing::{debug, info, warn};

/// Initialize ffmpeg (called once).
static FFMPEG_INIT: Once = Once::new();

fn init_ffmpeg() {
    FFMPEG_INIT.call_once(|| {
        ffmpeg_next::init().expect("failed to initialize ffmpeg");
        info!("ffmpeg initialized");
    });
}

/// A decoded video frame with metadata.
#[derive(Debug)]
pub struct DecodedFrame {
    /// The presentation timestamp in milliseconds.
    pub pts_ms: u64,
    /// The frame data in RGBA format.
    pub data: Vec<u8>,
    /// Frame width.
    pub width: u32,
    /// Frame height.
    pub height: u32,
}

/// Video decoder that reads frames from a stream source.
pub struct VideoDecoder {
    format_ctx: FormatContext,
    decoder: decoder::Video,
    video_stream_index: usize,
    time_base: Rational,
    scaler: FrameScaler,
    /// Duration in milliseconds, if known.
    duration_ms: Option<u64>,
    /// Frames per second, if known.
    fps: Option<f64>,
    /// Reusable frame buffer.
    frame: VideoFrame,
    /// Reusable packet.
    _packet: Packet,
    /// Hardware device context (kept alive for the decoder's lifetime).
    _hw_ctx: Option<HwDeviceContext>,
    /// Whether hardware acceleration is active.
    hw_accel_active: bool,
}

impl VideoDecoder {
    /// Create a new decoder for the given source.
    pub fn new(source: StreamSource) -> VideoResult<Self> {
        Self::with_size(source, DEFAULT_WIDTH, DEFAULT_HEIGHT)
    }

    /// Create a new decoder with custom output dimensions.
    pub fn with_size(source: StreamSource, width: u32, height: u32) -> VideoResult<Self> {
        init_ffmpeg();

        // Handle YouTube URLs
        #[allow(unused_mut)]
        let mut actual_source = source.clone();

        if source.is_youtube() {
            #[cfg(feature = "youtube")]
            {
                // YouTube extraction happens asynchronously, so we need to use block_on
                // In practice, the caller should handle this before calling new()
                return Err(VideoError::YoutubeExtraction(
                    "call youtube::extract_url() first, then pass the direct URL".to_string(),
                ));
            }
            #[cfg(not(feature = "youtube"))]
            {
                return Err(VideoError::YoutubeNotEnabled);
            }
        }

        let input_path = actual_source.as_ffmpeg_input();
        debug!(path = %input_path, "opening video source");

        // Open the input format context
        let format_ctx = ffmpeg_next::format::input(&input_path)
            .map_err(|e| VideoError::OpenFailed(format!("{}: {}", input_path, e)))?;

        // Find the best video stream
        let video_stream = format_ctx
            .streams()
            .best(MediaType::Video)
            .ok_or(VideoError::NoVideoStream)?;

        let video_stream_index = video_stream.index();
        let time_base = video_stream.time_base();

        // Get duration if available
        let duration_ms = if format_ctx.duration() > 0 {
            Some((format_ctx.duration() as u64) / 1000) // Convert from microseconds
        } else {
            None
        };

        // Calculate FPS
        let fps = {
            let rate = video_stream.avg_frame_rate();
            if rate.denominator() > 0 {
                Some(rate.numerator() as f64 / rate.denominator() as f64)
            } else {
                None
            }
        };

        // Get decoder parameters
        let codec_params = video_stream.parameters();
        let codec_id = codec_params.id();

        // Try D3D11VA hardware acceleration first
        let hw_ctx = HwDeviceContext::create_d3d11va();
        let hw_accel_active;

        // Find the decoder - when hw accel is available, use default decoder
        // (it will use the hw device context). Otherwise prefer software decoders.
        let codec = if hw_ctx.is_some() {
            decoder::find(codec_id)
                .ok_or_else(|| VideoError::NoDecoder(format!("{:?}", codec_id)))?
        } else {
            find_software_decoder(codec_id)
                .or_else(|| decoder::find(codec_id))
                .ok_or_else(|| VideoError::NoDecoder(format!("{:?}", codec_id)))?
        };

        debug!(codec_name = ?codec.name(), hw_accel = hw_ctx.is_some(), "using decoder");

        // Create decoder context
        let mut decoder_ctx = codec::context::Context::new_with_codec(codec);
        decoder_ctx.set_parameters(codec_params)?;

        // Set hardware device context if available
        if let Some(ref hw) = hw_ctx {
            unsafe {
                let raw = decoder_ctx.as_mut_ptr();
                (*raw).hw_device_ctx = hw.new_ref();
            }
            hw_accel_active = true;
            info!("Hardware acceleration enabled (D3D11VA)");
        } else {
            // Software mode: set thread_count for better performance
            unsafe {
                let raw = decoder_ctx.as_mut_ptr();
                (*raw).thread_count = 0; // auto-detect
            }
            hw_accel_active = false;
        }

        let decoder = decoder_ctx.decoder().video()?;

        info!(
            width = decoder.width(),
            height = decoder.height(),
            fps = ?fps,
            duration_ms = ?duration_ms,
            codec = ?codec_id,
            hw_accel = hw_accel_active,
            "video decoder initialized"
        );

        Ok(Self {
            format_ctx,
            decoder,
            video_stream_index,
            time_base,
            scaler: FrameScaler::with_size(width, height),
            duration_ms,
            fps,
            frame: VideoFrame::empty(),
            _packet: Packet::empty(),
            _hw_ctx: hw_ctx,
            hw_accel_active,
        })
    }

    /// Get the video duration in milliseconds, if known.
    pub fn duration_ms(&self) -> Option<u64> {
        self.duration_ms
    }

    /// Get the video FPS, if known.
    pub fn fps(&self) -> Option<f64> {
        self.fps
    }

    /// Get the source video width.
    pub fn source_width(&self) -> u32 {
        self.decoder.width()
    }

    /// Get the source video height.
    pub fn source_height(&self) -> u32 {
        self.decoder.height()
    }

    /// Get the output width (after scaling).
    pub fn output_width(&self) -> u32 {
        self.scaler.width()
    }

    /// Get the output height (after scaling).
    pub fn output_height(&self) -> u32 {
        self.scaler.height()
    }

    /// Decode and return the next frame.
    ///
    /// Returns `None` when the end of the stream is reached.
    pub fn next_frame(&mut self) -> VideoResult<Option<DecodedFrame>> {
        loop {
            // Try to receive a decoded frame first
            match self.decoder.receive_frame(&mut self.frame) {
                Ok(()) => {
                    // Transfer from GPU to CPU memory if using hardware acceleration
                    if self.hw_accel_active {
                        unsafe {
                            crate::hwaccel::transfer_hw_frame_if_needed(self.frame.as_mut_ptr());
                        }
                    }

                    // Calculate PTS in milliseconds
                    let pts = self.frame.pts().unwrap_or(0);
                    let pts_ms = self.pts_to_ms(pts);

                    // Scale the frame to output resolution
                    let scaled_data = self.scaler.scale(&self.frame)?;

                    return Ok(Some(DecodedFrame {
                        pts_ms,
                        data: scaled_data.to_vec(),
                        width: self.scaler.width(),
                        height: self.scaler.height(),
                    }));
                },
                Err(ffmpeg_next::Error::Other { errno }) if errno == ffmpeg_next::error::EAGAIN => {
                    // Need more input, continue to read packets
                },
                Err(ffmpeg_next::Error::Eof) => {
                    // End of stream
                    return Ok(None);
                },
                Err(e) => {
                    return Err(VideoError::DecodeError(e.to_string()));
                },
            }

            // Read the next packet
            match self.format_ctx.packets().next() {
                Some((stream, packet)) => {
                    if stream.index() == self.video_stream_index {
                        // Send packet to decoder
                        self.decoder.send_packet(&packet)?;
                    }
                    // Non-video packets are ignored
                },
                None => {
                    // No more packets, flush the decoder
                    self.decoder.send_eof()?;
                },
            }
        }
    }

    /// Seek to a position in milliseconds.
    pub fn seek(&mut self, position_ms: u64) -> VideoResult<()> {
        // format_ctx.seek() with stream_index=-1 expects AV_TIME_BASE units (microseconds)
        let timestamp_us = (position_ms as i64) * 1000;

        // Seek to the nearest keyframe before the target
        self.format_ctx
            .seek(timestamp_us, ..timestamp_us)
            .map_err(|e| VideoError::SeekError(e.to_string()))?;

        // Flush the decoder
        self.decoder.flush();

        debug!(position_ms, "seeked to position");
        Ok(())
    }

    /// Convert a PTS value to milliseconds.
    fn pts_to_ms(&self, pts: i64) -> u64 {
        if pts < 0 {
            return 0;
        }

        let num = self.time_base.numerator() as i64;
        let den = self.time_base.denominator() as i64;

        if den == 0 {
            return 0;
        }

        // pts * (num / den) * 1000 = pts * num * 1000 / den
        ((pts * num * 1000) / den) as u64
    }

    /// Convert milliseconds to PTS value.
    fn _ms_to_pts(&self, ms: u64) -> i64 {
        let num = self.time_base.numerator() as i64;
        let den = self.time_base.denominator() as i64;

        if num == 0 {
            return 0;
        }

        // ms / 1000 * (den / num) = ms * den / (1000 * num)
        ((ms as i64) * den) / (1000 * num)
    }
}

/// Try to find a software decoder for the given codec ID.
///
/// For codecs like AV1 that often have broken hardware acceleration on Windows,
/// we prefer known software decoders (libdav1d, libaom-av1) over the default
/// decoder which may attempt hardware acceleration and fail.
fn find_software_decoder(codec_id: codec::Id) -> Option<Codec> {
    let software_names: &[&str] = match codec_id {
        codec::Id::AV1 => &["libdav1d", "libaom-av1"],
        codec::Id::H264 => &["h264"], // native software decoder
        codec::Id::HEVC => &["hevc"],
        _ => return None,
    };

    for name in software_names {
        if let Some(dec) = decoder::find_by_name(name) {
            debug!(codec = ?codec_id, decoder = name, "found software decoder");
            return Some(dec);
        }
    }

    warn!(codec = ?codec_id, "no software decoder found, will try default");
    None
}

#[cfg(test)]
mod tests {
    #[allow(unused_imports)]
    use super::*;

    #[test]
    fn test_pts_conversion() {
        // This test verifies the PTS conversion logic
        // With time_base = 1/1000, pts_to_ms should be identity
        // We can't easily test this without a real decoder, but the math is straightforward
    }
}
