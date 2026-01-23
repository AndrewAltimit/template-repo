//! Audio player using ffmpeg for decoding and cpal for output.
//!
//! Opens the same source as the video decoder, finds the audio stream,
//! decodes + resamples to the output device format, and plays through cpal.

use cpal::traits::{DeviceTrait, HostTrait, StreamTrait};
use cpal::{Device, SampleRate, Stream, StreamConfig};
use ffmpeg_next::media::Type as MediaType;
use ffmpeg_next::software::resampling::Context as Resampler;
use ffmpeg_next::util::frame::audio::Audio as AudioFrame;
use ffmpeg_next::{codec, decoder, format, ChannelLayout};
use ringbuf::traits::{Consumer, Observer, Producer, Split};
use ringbuf::HeapRb;
use std::sync::atomic::{AtomicBool, AtomicU32, Ordering};
use std::sync::mpsc::{self, Receiver, Sender};
use std::sync::Arc;
use std::thread::{self, JoinHandle};
use std::time::Duration;
use tracing::{debug, error, info, warn};

/// Commands for the audio decode thread.
#[derive(Debug)]
pub enum AudioCommand {
    Play,
    Pause,
    Seek { position_ms: u64 },
    SetVolume { volume: f32 },
    Stop,
}

/// Ring buffer size: ~500ms of stereo f32 audio at 48kHz.
const RING_BUFFER_SIZE: usize = 48000 * 2 * 2; // samples * channels * 0.5s worth

/// Audio player that decodes audio from a source and plays through system audio.
pub struct AudioPlayer {
    command_tx: Sender<AudioCommand>,
    decode_thread: Option<JoinHandle<()>>,
    _stream: Stream,
}

impl AudioPlayer {
    /// Create a new audio player for the given source.
    ///
    /// Opens the source with ffmpeg, finds the audio stream, and starts playback.
    /// Returns None if no audio stream is found or audio output is unavailable.
    pub fn new(source: &str, volume: f32, autoplay: bool) -> Option<Self> {
        // Initialize cpal output device
        let host = cpal::default_host();
        let device = match host.default_output_device() {
            Some(d) => d,
            None => {
                warn!("No audio output device available");
                return None;
            }
        };

        let device_name = device.name().unwrap_or_else(|_| "unknown".to_string());
        info!(device = %device_name, "Using audio output device");

        // Get output config - prefer 48kHz stereo f32
        let config = match get_output_config(&device) {
            Some(c) => c,
            None => {
                warn!("No suitable audio output configuration");
                return None;
            }
        };

        let sample_rate = config.sample_rate.0;
        let channels = config.channels as u32;
        info!(sample_rate, channels, "Audio output config");

        // Create ring buffer
        let rb = HeapRb::<f32>::new(RING_BUFFER_SIZE);
        let (producer, mut consumer) = rb.split();

        // Volume control shared with output callback
        let volume_atomic = Arc::new(AtomicU32::new(volume.to_bits()));
        let paused = Arc::new(AtomicBool::new(!autoplay));
        // Flush flag: when set, consumer discards samples (used during seek)
        let flush_flag = Arc::new(AtomicBool::new(false));

        // Create cpal output stream
        let vol_clone = Arc::clone(&volume_atomic);
        let paused_clone = Arc::clone(&paused);
        let flush_clone = Arc::clone(&flush_flag);
        let stream = device
            .build_output_stream(
                &config,
                move |data: &mut [f32], _: &cpal::OutputCallbackInfo| {
                    let vol = f32::from_bits(vol_clone.load(Ordering::Relaxed));
                    let is_paused = paused_clone.load(Ordering::Relaxed);

                    // If flush requested, discard buffered samples
                    if flush_clone.load(Ordering::Relaxed) {
                        consumer.skip(consumer.occupied_len());
                        flush_clone.store(false, Ordering::Relaxed);
                        data.fill(0.0);
                        return;
                    }

                    if is_paused {
                        data.fill(0.0);
                        return;
                    }

                    let available = consumer.occupied_len();
                    let to_read = data.len().min(available);

                    // Read from ring buffer
                    if to_read > 0 {
                        consumer.pop_slice(&mut data[..to_read]);
                        // Apply volume
                        for sample in &mut data[..to_read] {
                            *sample *= vol;
                        }
                    }

                    // Fill remainder with silence
                    if to_read < data.len() {
                        data[to_read..].fill(0.0);
                    }
                },
                |err| {
                    error!(?err, "Audio output stream error");
                },
                None,
            )
            .ok()?;

        stream.play().ok()?;

        // Create command channel
        let (command_tx, command_rx) = mpsc::channel();

        // Spawn audio decode thread
        let source_owned = source.to_string();
        let vol_for_thread = Arc::clone(&volume_atomic);
        let paused_for_thread = Arc::clone(&paused);
        let flush_for_thread = Arc::clone(&flush_flag);
        let decode_thread = thread::spawn(move || {
            audio_decode_loop(
                &source_owned,
                sample_rate,
                channels,
                producer,
                command_rx,
                vol_for_thread,
                paused_for_thread,
                flush_for_thread,
                autoplay,
            );
        });

        Some(Self {
            command_tx,
            decode_thread: Some(decode_thread),
            _stream: stream,
        })
    }

    /// Send a command to the audio player.
    pub fn send_command(&self, cmd: AudioCommand) {
        let _ = self.command_tx.send(cmd);
    }

    /// Resume audio playback.
    pub fn play(&self) {
        self.send_command(AudioCommand::Play);
    }

    /// Pause audio playback.
    pub fn pause(&self) {
        self.send_command(AudioCommand::Pause);
    }

    /// Seek audio to a position.
    pub fn seek(&self, position_ms: u64) {
        self.send_command(AudioCommand::Seek { position_ms });
    }

    /// Set audio volume (0.0 - 1.0).
    pub fn set_volume(&self, volume: f32) {
        self.send_command(AudioCommand::SetVolume { volume });
    }
}

impl Drop for AudioPlayer {
    fn drop(&mut self) {
        let _ = self.command_tx.send(AudioCommand::Stop);
        if let Some(handle) = self.decode_thread.take() {
            let _ = handle.join();
        }
    }
}

/// Find a suitable output config for the device.
fn get_output_config(device: &Device) -> Option<StreamConfig> {
    if let Ok(configs) = device.supported_output_configs() {
        let configs: Vec<_> = configs.collect();

        // Prefer stereo f32 at 48kHz
        for cfg in &configs {
            if cfg.channels() == 2 && cfg.sample_format() == cpal::SampleFormat::F32 {
                let rate = SampleRate(48000);
                if cfg.min_sample_rate() <= rate && cfg.max_sample_rate() >= rate {
                    return Some(cfg.with_sample_rate(rate).into());
                }
            }
        }

        // Fall back to any stereo config
        for cfg in &configs {
            if cfg.channels() == 2 {
                let rate = SampleRate(48000).clamp(cfg.min_sample_rate(), cfg.max_sample_rate());
                return Some(cfg.with_sample_rate(rate).into());
            }
        }

        // Fall back to default config
        device.default_output_config().ok().map(|c| c.into())
    } else {
        device.default_output_config().ok().map(|c| c.into())
    }
}

/// Type alias for the ring buffer producer.
type AudioProducer = ringbuf::HeapProd<f32>;

/// Audio decode loop - runs in a separate thread.
fn audio_decode_loop(
    source: &str,
    target_sample_rate: u32,
    target_channels: u32,
    mut producer: AudioProducer,
    command_rx: Receiver<AudioCommand>,
    volume_atomic: Arc<AtomicU32>,
    paused: Arc<AtomicBool>,
    flush_flag: Arc<AtomicBool>,
    autoplay: bool,
) {
    // Open the source
    let mut format_ctx = match format::input(&source) {
        Ok(ctx) => ctx,
        Err(e) => {
            error!(?e, "Failed to open audio source");
            return;
        }
    };

    // Find audio stream
    let audio_stream = match format_ctx.streams().best(MediaType::Audio) {
        Some(s) => s,
        None => {
            info!("No audio stream found in source");
            return;
        }
    };

    let audio_stream_index = audio_stream.index();

    // Create audio decoder
    let codec_params = audio_stream.parameters();
    let codec_id = codec_params.id();
    let codec = match decoder::find(codec_id) {
        Some(c) => c,
        None => {
            error!(?codec_id, "No audio decoder found");
            return;
        }
    };

    let mut decoder_ctx = codec::context::Context::new_with_codec(codec);
    if let Err(e) = decoder_ctx.set_parameters(codec_params) {
        error!(?e, "Failed to set audio decoder parameters");
        return;
    }

    let mut audio_decoder = match decoder_ctx.decoder().audio() {
        Ok(d) => d,
        Err(e) => {
            error!(?e, "Failed to open audio decoder");
            return;
        }
    };

    info!(
        sample_rate = audio_decoder.rate(),
        channels = audio_decoder.channels(),
        format = ?audio_decoder.format(),
        "Audio decoder initialized"
    );

    // We'll create the resampler lazily after the first frame is decoded,
    // since some codecs don't report format info until then.
    let mut resampler: Option<Resampler> = None;
    let mut audio_frame = AudioFrame::empty();
    let mut resampled_frame = AudioFrame::empty();

    // Set initial state
    if !autoplay {
        paused.store(true, Ordering::Relaxed);
    }

    let mut running = true;

    while running {
        // Check for commands (non-blocking)
        while let Ok(cmd) = command_rx.try_recv() {
            match cmd {
                AudioCommand::Play => {
                    debug!("Audio: play");
                    paused.store(false, Ordering::Relaxed);
                }
                AudioCommand::Pause => {
                    debug!("Audio: pause");
                    paused.store(true, Ordering::Relaxed);
                }
                AudioCommand::Seek { position_ms } => {
                    debug!(position_ms, "Audio: seek");
                    let timestamp_us = (position_ms as i64) * 1000;
                    if let Err(e) = format_ctx.seek(timestamp_us, ..timestamp_us) {
                        warn!(?e, "Audio seek failed");
                    }
                    audio_decoder.flush();
                    // Signal consumer to discard buffered samples
                    flush_flag.store(true, Ordering::Release);
                }
                AudioCommand::SetVolume { volume } => {
                    volume_atomic.store(volume.to_bits(), Ordering::Relaxed);
                }
                AudioCommand::Stop => {
                    debug!("Audio: stop");
                    running = false;
                }
            }
        }

        if !running {
            break;
        }

        // If paused, just sleep and poll commands
        if paused.load(Ordering::Relaxed) {
            thread::sleep(Duration::from_millis(50));
            continue;
        }

        // If ring buffer is nearly full, wait a bit
        if producer.vacant_len() < 4096 {
            thread::sleep(Duration::from_millis(5));
            continue;
        }

        // Try to receive a decoded frame
        match audio_decoder.receive_frame(&mut audio_frame) {
            Ok(()) => {
                // Create resampler if needed
                if resampler.is_none() {
                    let target_layout = if target_channels == 1 {
                        ChannelLayout::MONO
                    } else {
                        ChannelLayout::STEREO
                    };

                    match Resampler::get(
                        audio_frame.format(),
                        audio_frame.channel_layout(),
                        audio_frame.rate(),
                        ffmpeg_next::format::Sample::F32(ffmpeg_next::format::sample::Type::Packed),
                        target_layout,
                        target_sample_rate,
                    ) {
                        Ok(r) => {
                            info!(
                                src_rate = audio_frame.rate(),
                                dst_rate = target_sample_rate,
                                src_channels = audio_frame.channels(),
                                dst_channels = target_channels,
                                "Audio resampler created"
                            );
                            resampler = Some(r);
                        }
                        Err(e) => {
                            error!(?e, "Failed to create audio resampler");
                            running = false;
                            continue;
                        }
                    }
                }

                // Resample the frame
                if let Some(ref mut ctx) = resampler {
                    match ctx.run(&audio_frame, &mut resampled_frame) {
                        Ok(_delay) => {
                            // Extract f32 samples from resampled frame
                            let data = resampled_frame.data(0);
                            let sample_count =
                                resampled_frame.samples() * target_channels as usize;
                            let samples: &[f32] = unsafe {
                                std::slice::from_raw_parts(
                                    data.as_ptr() as *const f32,
                                    sample_count,
                                )
                            };

                            // Write to ring buffer (drop samples if full)
                            let written = producer.push_slice(samples);
                            if written < samples.len() {
                                debug!(
                                    "Audio ring buffer full, dropped {} samples",
                                    samples.len() - written
                                );
                            }
                        }
                        Err(e) => {
                            warn!(?e, "Audio resample failed");
                        }
                    }
                }
            }
            Err(ffmpeg_next::Error::Other { errno }) if errno == ffmpeg_next::error::EAGAIN => {
                // Need more input packets - fall through to read next packet
            }
            Err(ffmpeg_next::Error::Eof) => {
                info!("Audio stream ended");
                running = false;
                continue;
            }
            Err(e) => {
                warn!(?e, "Audio decode error");
                running = false;
                continue;
            }
        }

        // Read the next packet
        match format_ctx.packets().next() {
            Some((stream, packet)) => {
                if stream.index() == audio_stream_index {
                    if let Err(e) = audio_decoder.send_packet(&packet) {
                        warn!(?e, "Failed to send audio packet");
                    }
                }
            }
            None => {
                // End of stream - flush decoder
                let _ = audio_decoder.send_eof();
            }
        }
    }

    info!("Audio decode thread exiting");
}
