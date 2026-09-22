//! Typed, validated tool-argument specs shared by `send_animation` and
//! sequence events.
//!
//! Tool arguments are deserialized with serde into these structs (type
//! mismatches become clear errors instead of silently-ignored fields) and then
//! converted into the canonical model with range validation.

use serde::Deserialize;
use serde_json::Value;
use std::collections::HashMap;

use crate::audio::{pcm_to_wav, AudioFormat, AudioHandler, AudioValidator};
use crate::types::{
    AudioData, CanonicalAnimationData, EmotionType, EventType, GestureType, SequenceEvent,
};

/// Maximum nesting depth of `parallel_events`.
pub const MAX_PARALLEL_DEPTH: usize = 3;
/// Maximum number of children in one parallel event.
pub const MAX_PARALLEL_CHILDREN: usize = 32;

/// Deserialize tool arguments into `T`, mapping errors to a readable message.
/// A `null` argument object is treated as `{}`.
pub fn parse_args<T: serde::de::DeserializeOwned>(args: Value) -> Result<T, String> {
    let args = if args.is_null() {
        Value::Object(Default::default())
    } else {
        args
    };
    serde_json::from_value(args).map_err(|e| format!("Invalid arguments: {e}"))
}

fn check_unit(name: &str, v: f32) -> Result<f32, String> {
    if v.is_finite() && (0.0..=1.0).contains(&v) {
        Ok(v)
    } else {
        Err(format!("{name} must be between 0 and 1, got {v}"))
    }
}

fn check_non_negative(name: &str, v: f64) -> Result<f64, String> {
    if v.is_finite() && v >= 0.0 {
        Ok(v)
    } else {
        Err(format!("{name} must be a non-negative number, got {v}"))
    }
}

/// Animation parameters (the `send_animation` arguments, and
/// `animation_params` of a sequence event).
#[derive(Debug, Clone, Default, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct AnimationSpec {
    pub emotion: Option<String>,
    pub emotion_intensity: Option<f32>,
    pub gesture: Option<String>,
    pub gesture_intensity: Option<f32>,
    /// Movement / `avatar_params` map (validated by the backend).
    pub parameters: Option<HashMap<String, Value>>,
    /// Blend shape name -> weight (0..1), sent as `BlendShape_<name>`.
    pub blend_shapes: Option<HashMap<String, f32>>,
}

impl AnimationSpec {
    /// True if the spec would not change anything.
    pub fn is_empty(&self) -> bool {
        self.emotion.is_none()
            && self.gesture.is_none()
            && self.parameters.as_ref().is_none_or(|p| p.is_empty())
            && self.blend_shapes.as_ref().is_none_or(|b| b.is_empty())
    }

    /// Convert to canonical animation data, validating names and ranges.
    pub fn to_canonical(&self, timestamp: f64) -> Result<CanonicalAnimationData, String> {
        let mut anim = CanonicalAnimationData::new(timestamp);
        if let Some(e) = &self.emotion {
            anim.emotion = Some(e.parse::<EmotionType>()?);
            anim.emotion_intensity =
                check_unit("emotion_intensity", self.emotion_intensity.unwrap_or(1.0))?;
        }
        if let Some(g) = &self.gesture {
            anim.gesture = Some(g.parse::<GestureType>()?);
            anim.gesture_intensity =
                check_unit("gesture_intensity", self.gesture_intensity.unwrap_or(1.0))?;
        }
        if let Some(p) = &self.parameters {
            anim.parameters = p.clone();
        }
        if let Some(b) = &self.blend_shapes {
            for (name, v) in b {
                check_unit(&format!("blend_shapes.{name}"), *v)?;
            }
            anim.blend_shapes = b.clone();
        }
        Ok(anim)
    }
}

/// One sequence event as accepted by `add_sequence_event` (and nested in
/// `parallel_events`).
#[derive(Debug, Clone, Default, Deserialize)]
pub struct EventSpec {
    pub event_type: String,
    /// Seconds from sequence start (children of a parallel event inherit the
    /// parent's timestamp).
    #[serde(default)]
    pub timestamp: Option<f64>,
    pub duration: Option<f64>,
    pub animation_params: Option<AnimationSpec>,
    pub audio_data: Option<String>,
    pub audio_format: Option<String>,
    /// Sample rate for `audio_format="pcm"` (default 44100).
    pub sample_rate: Option<u32>,
    /// Transcript for audio events (tags drive expression).
    pub text: Option<String>,
    pub expression_tags: Option<Vec<String>>,
    pub wait_duration: Option<f64>,
    pub expression: Option<String>,
    pub expression_intensity: Option<f32>,
    pub movement_params: Option<HashMap<String, Value>>,
    pub parallel_events: Option<Vec<EventSpec>>,
    /// Accepted for compatibility; audio events always extend their duration
    /// to the clip length when no explicit duration is given.
    #[serde(default)]
    pub sync_with_audio: bool,
}

/// Decode audio for playback: resolve the input, wrap PCM, detect the
/// container and estimate the duration.
pub async fn prepare_audio(
    handler: &AudioHandler,
    audio_data: &str,
    audio_format: Option<&str>,
    sample_rate: Option<u32>,
) -> Result<AudioData, String> {
    let requested = match audio_format {
        Some(f) => Some(AudioFormat::from_name(f).ok_or_else(|| {
            format!("Unsupported audio_format '{f}' (use mp3, wav, opus, ogg, flac or pcm)")
        })?),
        None => None,
    };
    let mut bytes = handler.load(audio_data).await?;
    let detected = AudioValidator::detect_format(&bytes);

    let format = if requested == Some(AudioFormat::Pcm) && detected == AudioFormat::Unknown {
        let rate = sample_rate.unwrap_or(44_100);
        if !(8_000..=192_000).contains(&rate) {
            return Err(format!("sample_rate must be 8000-192000, got {rate}"));
        }
        bytes = pcm_to_wav(&bytes, rate, 1);
        AudioFormat::Wav
    } else if detected != AudioFormat::Unknown {
        // Magic bytes win over a (possibly wrong) declared format.
        detected
    } else {
        requested.unwrap_or(AudioFormat::Mp3)
    };

    let duration = AudioValidator::estimate_duration(&bytes, format).unwrap_or(0.0);
    Ok(AudioData {
        data: bytes,
        format: format.to_string(),
        duration: duration as f32,
        sample_rate: sample_rate.unwrap_or(44_100),
        ..Default::default()
    })
}

/// Build a validated [`SequenceEvent`] from a spec. Audio is loaded (and
/// validated) now, so errors surface when the event is added rather than
/// in the middle of playback.
pub async fn build_event(
    spec: &EventSpec,
    audio: &AudioHandler,
    parent_timestamp: Option<f64>,
    depth: usize,
) -> Result<SequenceEvent, String> {
    let event_type: EventType = spec.event_type.parse()?;
    let timestamp = check_non_negative(
        "timestamp",
        spec.timestamp.or(parent_timestamp).unwrap_or(0.0),
    )?;
    let mut event = SequenceEvent::new(event_type, timestamp);
    if let Some(d) = spec.duration {
        event.duration = Some(check_non_negative("duration", d)?);
    }

    match event_type {
        EventType::Animation => {
            let mut anim_spec = spec.animation_params.clone().unwrap_or_default();
            // Convenience: a top-level expression fills in a missing emotion.
            if anim_spec.emotion.is_none() {
                anim_spec.emotion = spec.expression.clone();
                anim_spec.emotion_intensity = spec.expression_intensity;
            }
            if anim_spec.is_empty() {
                return Err("animation events need animation_params (emotion, gesture, parameters or blend_shapes)".into());
            }
            event.animation_data = Some(anim_spec.to_canonical(timestamp)?);
        },
        EventType::Expression => {
            let expr = spec
                .expression
                .as_deref()
                .ok_or("expression events need 'expression'")?;
            event.expression = Some(expr.parse::<EmotionType>()?);
            event.expression_intensity = Some(check_unit(
                "expression_intensity",
                spec.expression_intensity.unwrap_or(1.0),
            )?);
        },
        EventType::Movement => {
            let params = spec
                .movement_params
                .clone()
                .filter(|p| !p.is_empty())
                .ok_or("movement events need non-empty 'movement_params'")?;
            // Validate now (same rules the backend applies).
            crate::backends::movement::parse_movement(&params).map_err(|e| e.to_string())?;
            event.movement_params = Some(params);
        },
        EventType::Audio => {
            let data = spec
                .audio_data
                .as_deref()
                .ok_or("audio events need 'audio_data'")?;
            let mut clip =
                prepare_audio(audio, data, spec.audio_format.as_deref(), spec.sample_rate).await?;
            clip.text = spec.text.clone();
            clip.expression_tags = spec.expression_tags.clone();
            if event.duration.is_none() && clip.duration > 0.0 {
                event.duration = Some(clip.duration as f64);
            }
            if let Some(d) = event.duration {
                clip.duration = d as f32;
            }
            event.audio_data = Some(clip);
        },
        EventType::Wait => {
            let w = spec
                .wait_duration
                .or(spec.duration)
                .ok_or("wait events need 'wait_duration' (seconds)")?;
            event.wait_duration = Some(check_non_negative("wait_duration", w)?);
        },
        EventType::Parallel => {
            if depth >= MAX_PARALLEL_DEPTH {
                return Err(format!(
                    "parallel_events nested deeper than {MAX_PARALLEL_DEPTH}"
                ));
            }
            let children = spec
                .parallel_events
                .as_ref()
                .filter(|c| !c.is_empty())
                .ok_or("parallel events need non-empty 'parallel_events'")?;
            if children.len() > MAX_PARALLEL_CHILDREN {
                return Err(format!(
                    "too many parallel_events ({} > {MAX_PARALLEL_CHILDREN})",
                    children.len()
                ));
            }
            let mut built = Vec::with_capacity(children.len());
            let mut span = event.duration.unwrap_or(0.0);
            for child in children {
                let c = Box::pin(build_event(child, audio, Some(timestamp), depth + 1)).await?;
                let child_end =
                    c.timestamp - timestamp + c.duration.or(c.wait_duration).unwrap_or(0.0);
                span = span.max(child_end);
                built.push(c);
            }
            if span > 0.0 {
                event.duration = Some(span);
            }
            event.parallel_events = Some(built);
        },
        EventType::LoopStart | EventType::LoopEnd => {
            return Err(
                "loop_start/loop_end markers are not supported; use create_sequence(loop=true)"
                    .into(),
            );
        },
    }
    Ok(event)
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::audio::{AudioDownloader, AudioPathValidator};
    use base64::Engine;
    use serde_json::json;

    fn handler() -> AudioHandler {
        AudioHandler {
            path_validator: AudioPathValidator::with_paths(vec![]),
            downloader: AudioDownloader::new(),
        }
    }

    fn spec(v: Value) -> EventSpec {
        parse_args(v).unwrap()
    }

    #[test]
    fn animation_spec_validation() {
        let ok: AnimationSpec =
            parse_args(json!({"emotion": "happy", "gesture": "wave", "emotion_intensity": 0.5}))
                .unwrap();
        let anim = ok.to_canonical(1.0).unwrap();
        assert_eq!(anim.emotion, Some(EmotionType::Happy));
        assert_eq!(anim.gesture, Some(GestureType::Wave));
        assert_eq!(anim.emotion_intensity, 0.5);

        let bad: AnimationSpec = parse_args(json!({"emotion": "gleeful"})).unwrap();
        assert!(bad
            .to_canonical(0.0)
            .unwrap_err()
            .contains("Valid emotions"));
        let bad: AnimationSpec =
            parse_args(json!({"emotion": "sad", "emotion_intensity": 3})).unwrap();
        assert!(bad.to_canonical(0.0).is_err());
        // Typos in field names are rejected rather than ignored.
        assert!(parse_args::<AnimationSpec>(json!({"emotions": "sad"})).is_err());
        // Wrong types are rejected.
        assert!(parse_args::<AnimationSpec>(json!({"emotion": 5})).is_err());
    }

    #[tokio::test]
    async fn build_basic_events() {
        let h = handler();
        let e = build_event(
            &spec(json!({"event_type": "expression", "timestamp": 1.5, "expression": "sad"})),
            &h,
            None,
            0,
        )
        .await
        .unwrap();
        assert_eq!(e.expression, Some(EmotionType::Sad));
        assert_eq!(e.timestamp, 1.5);

        let e = build_event(&spec(json!({"event_type": "animation", "timestamp": 0, "animation_params": {"gesture": "wave"}})), &h, None, 0)
            .await
            .unwrap();
        assert_eq!(e.animation_data.unwrap().gesture, Some(GestureType::Wave));

        let e = build_event(
            &spec(json!({"event_type": "wait", "timestamp": 2, "wait_duration": 1.0})),
            &h,
            None,
            0,
        )
        .await
        .unwrap();
        assert_eq!(e.wait_duration, Some(1.0));

        let e = build_event(&spec(json!({"event_type": "movement", "timestamp": 0, "movement_params": {"move_forward": 0.5}})), &h, None, 0)
            .await
            .unwrap();
        assert!(e.movement_params.is_some());
    }

    #[tokio::test]
    async fn build_rejects_incomplete_events() {
        let h = handler();
        for v in [
            json!({"event_type": "expression", "timestamp": 0}),
            json!({"event_type": "expression", "timestamp": 0, "expression": "meh"}),
            json!({"event_type": "animation", "timestamp": 0}),
            json!({"event_type": "movement", "timestamp": 0, "movement_params": {"move_forward": "x"}}),
            json!({"event_type": "audio", "timestamp": 0}),
            json!({"event_type": "wait", "timestamp": 0}),
            json!({"event_type": "parallel", "timestamp": 0, "parallel_events": []}),
            json!({"event_type": "loop_start", "timestamp": 0}),
            json!({"event_type": "dance", "timestamp": 0}),
            json!({"event_type": "wait", "timestamp": -1, "wait_duration": 1}),
        ] {
            assert!(
                build_event(&spec(v.clone()), &h, None, 0).await.is_err(),
                "{v}"
            );
        }
    }

    #[tokio::test]
    async fn build_audio_and_parallel_events() {
        let h = handler();
        let wav = pcm_to_wav(&vec![0u8; 44_100 * 2], 44_100, 1); // 1 second
        let b64 = base64::engine::general_purpose::STANDARD.encode(&wav);
        let e = build_event(
            &spec(json!({
                "event_type": "parallel",
                "timestamp": 2.0,
                "parallel_events": [
                    {"event_type": "audio", "audio_data": b64, "text": "[laughs] hi"},
                    {"event_type": "expression", "expression": "happy"}
                ]
            })),
            &h,
            None,
            0,
        )
        .await
        .unwrap();
        let children = e.parallel_events.as_ref().unwrap();
        assert_eq!(children.len(), 2);
        assert_eq!(children[0].timestamp, 2.0);
        let clip = children[0].audio_data.as_ref().unwrap();
        assert_eq!(clip.format, "wav");
        assert!((clip.duration - 1.0).abs() < 0.01);
        // Parallel duration covers the audio clip.
        assert!((e.duration.unwrap() - 1.0).abs() < 0.01);
    }

    #[tokio::test]
    async fn prepare_audio_pcm_and_format_detection() {
        let h = handler();
        let pcm = vec![0u8; 22_050]; // 11025 samples = 0.5 s mono at 22.05 kHz
        let b64 = base64::engine::general_purpose::STANDARD.encode(&pcm);
        let clip = prepare_audio(&h, &b64, Some("pcm"), Some(22_050))
            .await
            .unwrap();
        assert_eq!(clip.format, "wav");
        assert!((clip.duration - 0.5).abs() < 0.01);

        // A WAV declared as mp3 is detected as WAV.
        let wav = pcm_to_wav(&vec![0u8; 4000], 44_100, 1);
        let b64 = base64::engine::general_purpose::STANDARD.encode(&wav);
        let clip = prepare_audio(&h, &b64, Some("mp3"), None).await.unwrap();
        assert_eq!(clip.format, "wav");

        assert!(prepare_audio(&h, &b64, Some("aac"), None).await.is_err());
        assert!(prepare_audio(&h, &b64, Some("pcm"), Some(10)).await.is_ok()); // WAV detected, rate unused
    }
}
