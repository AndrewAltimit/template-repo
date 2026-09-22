//! ElevenLabs HTTP API client.
//!
//! All requests carry the API key in the `xi-api-key` header (never in the
//! URL), and every error string produced here passes through [`redact`] so
//! the key cannot leak into logs or tool results even if an upstream error
//! were to echo it back.

use crate::config::Config;
use crate::storage;
use crate::types::{
    ModelInfo, OutputFormat, UserInfo, Voice, VoiceSettings, VoicesResponse, alias_voice_id,
    find_voice_by_name, looks_like_voice_id, validate_path_id,
};
use reqwest::{Client, RequestBuilder, Response};
use serde::Serialize;
use serde::de::DeserializeOwned;
use std::path::{Path, PathBuf};
use std::sync::Arc;
use std::time::{Duration, Instant};
use tokio::sync::Mutex;
use tracing::{debug, info, warn};

/// Maximum audio payload accepted from the API (guards memory use).
pub const MAX_AUDIO_BYTES: usize = 100 * 1024 * 1024;
/// How long a fetched voice list is reused for name resolution.
pub const VOICE_CACHE_TTL: Duration = Duration::from_secs(600);
/// Maximum length of an upstream error message included in a tool result.
const MAX_ERROR_CHARS: usize = 500;

/// Errors from the ElevenLabs client. Messages are already redacted.
#[derive(Debug, thiserror::Error)]
pub enum ApiError {
    #[error(
        "ELEVENLABS_API_KEY is not set. Set it in the server environment to use ElevenLabs API tools."
    )]
    MissingApiKey,
    #[error("{0}")]
    InvalidInput(String),
    #[error("Request to ElevenLabs failed: {0}")]
    Transport(String),
    #[error("ElevenLabs API error (HTTP {status}): {message}")]
    Api { status: u16, message: String },
    #[error("{0}")]
    Io(String),
}

/// Replace every occurrence of `secret` in `text` with `[REDACTED]`.
pub fn redact(text: &str, secret: Option<&str>) -> String {
    match secret {
        Some(s) if s.len() >= 4 => text.replace(s, "[REDACTED]"),
        _ => text.to_string(),
    }
}

/// Extract a human-readable message from an ElevenLabs error body.
///
/// The API returns `{"detail": {"status": "...", "message": "..."}}` or
/// `{"detail": "..."}`; anything else is returned as (truncated) raw text.
pub fn extract_api_message(body: &str) -> String {
    let msg = serde_json::from_str::<serde_json::Value>(body)
        .ok()
        .and_then(|v| {
            let detail = v.get("detail")?;
            if let Some(s) = detail.as_str() {
                return Some(s.to_string());
            }
            let message = detail.get("message").and_then(|m| m.as_str());
            let status = detail.get("status").and_then(|m| m.as_str());
            match (status, message) {
                (Some(s), Some(m)) => Some(format!("{s}: {m}")),
                (None, Some(m)) => Some(m.to_string()),
                _ => Some(detail.to_string()),
            }
        })
        .unwrap_or_else(|| body.trim().to_string());
    let msg = if msg.is_empty() {
        "(empty response body)".to_string()
    } else {
        msg
    };
    truncate_chars(&msg, MAX_ERROR_CHARS)
}

fn truncate_chars(s: &str, max: usize) -> String {
    if s.chars().count() <= max {
        s.to_string()
    } else {
        let mut out: String = s.chars().take(max).collect();
        out.push_str("...");
        out
    }
}

/// Body of `POST /v1/text-to-speech/{voice_id}`.
#[derive(Debug, Clone, Serialize)]
pub struct TtsBody {
    pub text: String,
    pub model_id: String,
    pub voice_settings: VoiceSettings,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub language_code: Option<String>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub seed: Option<u32>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub previous_text: Option<String>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub next_text: Option<String>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub apply_text_normalization: Option<String>,
}

/// Body of `POST /v1/sound-generation`.
#[derive(Debug, Clone, Serialize)]
pub struct SoundBody {
    pub text: String,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub duration_seconds: Option<f32>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub prompt_influence: Option<f32>,
    #[serde(rename = "loop", skip_serializing_if = "std::ops::Not::not")]
    pub looping: bool,
}

/// Audio saved to disk after a successful generation request.
#[derive(Debug, Clone)]
pub struct SavedAudio {
    pub path: PathBuf,
    pub size_bytes: u64,
    pub request_id: Option<String>,
}

/// Outcome of resolving a voice name/ID.
#[derive(Debug, Clone, PartialEq, Eq)]
pub struct ResolvedVoice {
    pub voice_id: String,
    pub warning: Option<String>,
}

/// ElevenLabs API client.
pub struct ElevenLabsClient {
    http: Client,
    api_key: Option<String>,
    base_url: String,
    output_dir: PathBuf,
    voice_cache: Mutex<Option<(Instant, Arc<Vec<Voice>>)>>,
}

impl ElevenLabsClient {
    /// Create a client from configuration. Does no I/O.
    pub fn new(config: &Config) -> Self {
        Self {
            http: mcp_core::http::build_client_or_default(config.timeout),
            api_key: config.api_key.clone(),
            base_url: config.base_url.clone(),
            output_dir: config.output_dir.clone(),
            voice_cache: Mutex::new(None),
        }
    }

    /// Whether an API key is configured.
    pub fn has_api_key(&self) -> bool {
        self.api_key.is_some()
    }

    /// Directory generated audio is written to.
    pub fn output_dir(&self) -> &Path {
        &self.output_dir
    }

    fn url(&self, path: &str) -> String {
        format!("{}/v1/{}", self.base_url, path.trim_start_matches('/'))
    }

    fn redact(&self, s: &str) -> String {
        redact(s, self.api_key.as_deref())
    }

    fn authed(&self, rb: RequestBuilder) -> Result<RequestBuilder, ApiError> {
        let key = self.api_key.as_deref().ok_or(ApiError::MissingApiKey)?;
        Ok(rb.header("xi-api-key", key))
    }

    /// Send a request and map transport errors / non-2xx statuses.
    async fn send(&self, rb: RequestBuilder) -> Result<Response, ApiError> {
        let resp = self
            .authed(rb)?
            .send()
            .await
            .map_err(|e| ApiError::Transport(self.redact(&e.without_url().to_string())))?;
        let status = resp.status();
        if status.is_success() {
            return Ok(resp);
        }
        let body = resp.text().await.unwrap_or_default();
        let message = self.redact(&extract_api_message(&body));
        warn!("ElevenLabs API error {}: {}", status.as_u16(), message);
        Err(ApiError::Api {
            status: status.as_u16(),
            message,
        })
    }

    async fn get_json<T: DeserializeOwned>(&self, path: &str) -> Result<T, ApiError> {
        let resp = self.send(self.http.get(self.url(path))).await?;
        resp.json::<T>().await.map_err(|e| {
            ApiError::Transport(self.redact(&format!(
                "unexpected response from {path}: {}",
                e.without_url()
            )))
        })
    }

    /// Read an audio response body (bounded by [`MAX_AUDIO_BYTES`]) and save it.
    async fn save_audio_response(
        &self,
        mut resp: Response,
        prefix: &str,
        format: OutputFormat,
    ) -> Result<SavedAudio, ApiError> {
        let request_id = resp
            .headers()
            .get("request-id")
            .and_then(|v| v.to_str().ok())
            .map(str::to_string);

        let mut data = Vec::with_capacity(resp.content_length().unwrap_or(0).min(8 << 20) as usize);
        while let Some(chunk) = resp
            .chunk()
            .await
            .map_err(|e| ApiError::Transport(self.redact(&e.without_url().to_string())))?
        {
            if data.len() + chunk.len() > MAX_AUDIO_BYTES {
                return Err(ApiError::Transport(format!(
                    "audio response exceeded {} MB limit",
                    MAX_AUDIO_BYTES / (1024 * 1024)
                )));
            }
            data.extend_from_slice(&chunk);
        }
        if data.is_empty() {
            return Err(ApiError::Transport(
                "ElevenLabs returned an empty audio response".to_string(),
            ));
        }

        let path = storage::save_audio(&self.output_dir, prefix, format.extension(), &data)
            .await
            .map_err(|e| {
                ApiError::Io(format!(
                    "Failed to save audio under {}: {e}",
                    self.output_dir.display()
                ))
            })?;
        info!("Saved {} bytes of audio to {}", data.len(), path.display());
        Ok(SavedAudio {
            path,
            size_bytes: data.len() as u64,
            request_id,
        })
    }

    /// Text-to-speech. `voice_id` must already be resolved to an ID.
    pub async fn text_to_speech(
        &self,
        voice_id: &str,
        body: &TtsBody,
        format: OutputFormat,
    ) -> Result<SavedAudio, ApiError> {
        validate_path_id(voice_id).map_err(ApiError::InvalidInput)?;
        debug!(
            "TTS: {} chars, voice {}, model {}",
            body.text.chars().count(),
            voice_id,
            body.model_id
        );
        let rb = self
            .http
            .post(self.url(&format!("text-to-speech/{voice_id}")))
            .query(&[("output_format", format.as_str())])
            .json(body);
        let resp = self.send(rb).await?;
        self.save_audio_response(resp, storage::SPEECH_PREFIX, format)
            .await
    }

    /// Sound effect generation.
    pub async fn sound_generation(
        &self,
        body: &SoundBody,
        format: OutputFormat,
    ) -> Result<SavedAudio, ApiError> {
        debug!(
            "SFX: {:?}s, {} chars",
            body.duration_seconds,
            body.text.len()
        );
        let rb = self
            .http
            .post(self.url("sound-generation"))
            .query(&[("output_format", format.as_str())])
            .json(body);
        let resp = self.send(rb).await?;
        self.save_audio_response(resp, storage::SFX_PREFIX, format)
            .await
    }

    /// All voices available to the account. Cached for [`VOICE_CACHE_TTL`]
    /// unless `refresh` is set.
    pub async fn voices(&self, refresh: bool) -> Result<Arc<Vec<Voice>>, ApiError> {
        let mut cache = self.voice_cache.lock().await;
        if !refresh
            && let Some((at, voices)) = cache.as_ref()
            && at.elapsed() < VOICE_CACHE_TTL
        {
            return Ok(voices.clone());
        }
        let resp: VoicesResponse = self.get_json("voices").await?;
        let voices = Arc::new(resp.voices);
        *cache = Some((Instant::now(), voices.clone()));
        Ok(voices)
    }

    /// Resolve a voice name or ID to a voice ID.
    ///
    /// Order: ID-shaped input is used verbatim; otherwise the account's voice
    /// list is searched by (short) name; if that list is unavailable, the
    /// built-in alias table is consulted.
    pub async fn resolve_voice(&self, input: &str) -> Result<ResolvedVoice, ApiError> {
        let input = input.trim();
        if input.is_empty() {
            return Err(ApiError::InvalidInput("voice_id must not be empty".into()));
        }
        if looks_like_voice_id(input) {
            return Ok(ResolvedVoice {
                voice_id: input.to_string(),
                warning: None,
            });
        }
        match self.voices(false).await {
            Ok(voices) => {
                if let Some(v) = find_voice_by_name(&voices, input) {
                    return Ok(ResolvedVoice {
                        voice_id: v.voice_id.clone(),
                        warning: None,
                    });
                }
                if let Some(id) = alias_voice_id(input) {
                    return Ok(ResolvedVoice {
                        voice_id: id.to_string(),
                        warning: Some(format!(
                            "Voice '{input}' is not in this account's voice list; used legacy built-in ID {id}. ElevenLabs may remap retired voices - pick one from list_voices."
                        )),
                    });
                }
                let mut names: Vec<&str> = voices.iter().map(|v| v.short_name()).collect();
                names.sort_unstable();
                names.dedup();
                Err(ApiError::InvalidInput(format!(
                    "Unknown voice '{input}'. Available voices: {}",
                    truncate_chars(&names.join(", "), MAX_ERROR_CHARS)
                )))
            },
            Err(ApiError::MissingApiKey) => Err(ApiError::MissingApiKey),
            Err(e) => match alias_voice_id(input) {
                Some(id) => Ok(ResolvedVoice {
                    voice_id: id.to_string(),
                    warning: Some(format!(
                        "Could not fetch voice list ({e}); used built-in ID {id} for '{input}'"
                    )),
                }),
                None => Err(e),
            },
        }
    }

    /// `GET /v1/user`.
    pub async fn user_info(&self) -> Result<UserInfo, ApiError> {
        self.get_json("user").await
    }

    /// `GET /v1/models`.
    pub async fn models(&self) -> Result<Vec<ModelInfo>, ApiError> {
        self.get_json("models").await
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::types::VoiceSettings;
    use wiremock::matchers::{body_partial_json, header, method, path, query_param};
    use wiremock::{Mock, MockServer, ResponseTemplate};

    const KEY: &str = "sk_test_secret_key_123";

    fn config(base: &str, out: &Path, key: Option<&str>) -> Config {
        Config {
            api_key: key.map(str::to_string),
            base_url: base.to_string(),
            output_dir: out.to_path_buf(),
            default_model: "eleven_v3".into(),
            default_voice: "george".into(),
            timeout: Duration::from_secs(5),
        }
    }

    fn voices_json() -> serde_json::Value {
        serde_json::json!({"voices": [
            {"voice_id": "JBFqnCBsd6RMkjVDRZzb", "name": "George - Warm, Captivating Storyteller", "category": "premade"},
            {"voice_id": "CustomVoiceId0000001", "name": "My Clone", "category": "cloned"}
        ]})
    }

    fn tts_body() -> TtsBody {
        TtsBody {
            text: "hello".into(),
            model_id: "eleven_v3".into(),
            voice_settings: VoiceSettings::default(),
            language_code: Some("en".into()),
            seed: None,
            previous_text: None,
            next_text: None,
            apply_text_normalization: None,
        }
    }

    #[test]
    fn redaction() {
        assert_eq!(
            redact("key=sk_abc123 bad", Some("sk_abc123")),
            "key=[REDACTED] bad"
        );
        assert_eq!(redact("nothing", None), "nothing");
    }

    #[test]
    fn api_message_extraction() {
        assert_eq!(
            extract_api_message(
                r#"{"detail":{"status":"quota_exceeded","message":"Out of credits"}}"#
            ),
            "quota_exceeded: Out of credits"
        );
        assert_eq!(
            extract_api_message(r#"{"detail":"Not found"}"#),
            "Not found"
        );
        assert_eq!(extract_api_message("  plain  "), "plain");
        assert_eq!(extract_api_message(""), "(empty response body)");
        assert!(extract_api_message(&"x".repeat(2000)).len() < 600);
    }

    #[tokio::test]
    async fn tts_success_writes_file_and_sends_expected_request() {
        let server = MockServer::start().await;
        let tmp = tempfile::tempdir().unwrap();
        Mock::given(method("POST"))
            .and(path("/v1/text-to-speech/JBFqnCBsd6RMkjVDRZzb"))
            .and(header("xi-api-key", KEY))
            .and(query_param("output_format", "wav_24000"))
            .and(body_partial_json(serde_json::json!({
                "text": "hello", "model_id": "eleven_v3", "language_code": "en"
            })))
            .respond_with(
                ResponseTemplate::new(200)
                    .insert_header("request-id", "req-42")
                    .set_body_bytes(b"RIFFfakewav".to_vec()),
            )
            .expect(1)
            .mount(&server)
            .await;

        let client = ElevenLabsClient::new(&config(&server.uri(), tmp.path(), Some(KEY)));
        let saved = client
            .text_to_speech(
                "JBFqnCBsd6RMkjVDRZzb",
                &tts_body(),
                OutputFormat::parse("wav_24000").unwrap(),
            )
            .await
            .unwrap();
        assert_eq!(saved.size_bytes, 11);
        assert_eq!(saved.request_id.as_deref(), Some("req-42"));
        assert_eq!(saved.path.extension().unwrap(), "wav");
        assert_eq!(std::fs::read(&saved.path).unwrap(), b"RIFFfakewav");
    }

    #[tokio::test]
    async fn api_error_is_surfaced_and_key_redacted() {
        let server = MockServer::start().await;
        let tmp = tempfile::tempdir().unwrap();
        Mock::given(method("POST"))
            .respond_with(ResponseTemplate::new(401).set_body_string(format!(
                r#"{{"detail":{{"status":"invalid_api_key","message":"bad key {KEY}"}}}}"#
            )))
            .mount(&server)
            .await;
        let client = ElevenLabsClient::new(&config(&server.uri(), tmp.path(), Some(KEY)));
        let err = client
            .text_to_speech("JBFqnCBsd6RMkjVDRZzb", &tts_body(), OutputFormat::default())
            .await
            .unwrap_err();
        let msg = err.to_string();
        assert!(msg.contains("HTTP 401"), "{msg}");
        assert!(msg.contains("invalid_api_key"), "{msg}");
        assert!(!msg.contains(KEY), "key leaked: {msg}");
        assert!(msg.contains("[REDACTED]"));
    }

    #[tokio::test]
    async fn empty_audio_is_an_error() {
        let server = MockServer::start().await;
        let tmp = tempfile::tempdir().unwrap();
        Mock::given(method("POST"))
            .respond_with(ResponseTemplate::new(200))
            .mount(&server)
            .await;
        let client = ElevenLabsClient::new(&config(&server.uri(), tmp.path(), Some(KEY)));
        let err = client
            .text_to_speech("JBFqnCBsd6RMkjVDRZzb", &tts_body(), OutputFormat::default())
            .await
            .unwrap_err();
        assert!(err.to_string().contains("empty audio"));
    }

    #[tokio::test]
    async fn path_injection_rejected_before_request() {
        let server = MockServer::start().await;
        let tmp = tempfile::tempdir().unwrap();
        Mock::given(method("POST"))
            .respond_with(ResponseTemplate::new(200).set_body_bytes(b"x".to_vec()))
            .expect(0)
            .mount(&server)
            .await;
        let client = ElevenLabsClient::new(&config(&server.uri(), tmp.path(), Some(KEY)));
        let err = client
            .text_to_speech("../user", &tts_body(), OutputFormat::default())
            .await
            .unwrap_err();
        assert!(matches!(err, ApiError::InvalidInput(_)));
    }

    #[tokio::test]
    async fn missing_key_short_circuits() {
        let tmp = tempfile::tempdir().unwrap();
        // Unroutable base URL: must never be contacted.
        let client = ElevenLabsClient::new(&config("http://127.0.0.1:9", tmp.path(), None));
        assert!(!client.has_api_key());
        assert!(matches!(
            client.user_info().await,
            Err(ApiError::MissingApiKey)
        ));
        assert!(matches!(
            client.resolve_voice("george").await,
            Err(ApiError::MissingApiKey)
        ));
    }

    #[tokio::test]
    async fn sound_generation_request_shape() {
        let server = MockServer::start().await;
        let tmp = tempfile::tempdir().unwrap();
        Mock::given(method("POST"))
            .and(path("/v1/sound-generation"))
            .and(query_param("output_format", "mp3_44100_128"))
            .and(body_partial_json(serde_json::json!({
                "text": "rain", "duration_seconds": 3.0, "loop": true, "prompt_influence": 0.5
            })))
            .respond_with(ResponseTemplate::new(200).set_body_bytes(b"ID3".to_vec()))
            .expect(1)
            .mount(&server)
            .await;
        let client = ElevenLabsClient::new(&config(&server.uri(), tmp.path(), Some(KEY)));
        let saved = client
            .sound_generation(
                &SoundBody {
                    text: "rain".into(),
                    duration_seconds: Some(3.0),
                    prompt_influence: Some(0.5),
                    looping: true,
                },
                OutputFormat::default(),
            )
            .await
            .unwrap();
        let name = saved
            .path
            .file_name()
            .unwrap()
            .to_string_lossy()
            .to_string();
        assert!(name.starts_with("sfx_"));
    }

    #[tokio::test]
    async fn voice_resolution_uses_account_list_and_cache() {
        let server = MockServer::start().await;
        let tmp = tempfile::tempdir().unwrap();
        Mock::given(method("GET"))
            .and(path("/v1/voices"))
            .respond_with(ResponseTemplate::new(200).set_body_json(voices_json()))
            .expect(1) // second lookup must hit the cache
            .mount(&server)
            .await;
        let client = ElevenLabsClient::new(&config(&server.uri(), tmp.path(), Some(KEY)));

        let r = client.resolve_voice("my clone").await.unwrap();
        assert_eq!(r.voice_id, "CustomVoiceId0000001");
        assert!(r.warning.is_none());

        let r = client.resolve_voice("George").await.unwrap();
        assert_eq!(r.voice_id, "JBFqnCBsd6RMkjVDRZzb");

        // Legacy alias not in the account: allowed but flagged.
        let r = client.resolve_voice("rachel").await.unwrap();
        assert_eq!(r.voice_id, "21m00Tcm4TlvDq8ikWAM");
        assert!(r.warning.is_some());

        let err = client.resolve_voice("nobody").await.unwrap_err();
        assert!(err.to_string().contains("Available voices"));
        assert!(err.to_string().contains("George"));

        // ID-shaped input needs no lookup at all.
        let r = client.resolve_voice("AbCdEfGhIjKlMnOpQrSt").await.unwrap();
        assert_eq!(r.voice_id, "AbCdEfGhIjKlMnOpQrSt");
    }

    #[tokio::test]
    async fn voice_resolution_falls_back_to_alias_on_api_failure() {
        let server = MockServer::start().await;
        let tmp = tempfile::tempdir().unwrap();
        Mock::given(method("GET"))
            .and(path("/v1/voices"))
            .respond_with(ResponseTemplate::new(500).set_body_string("boom"))
            .mount(&server)
            .await;
        let client = ElevenLabsClient::new(&config(&server.uri(), tmp.path(), Some(KEY)));
        let r = client.resolve_voice("sarah").await.unwrap();
        assert_eq!(r.voice_id, "EXAVITQu4vr4xnSDxMaL");
        assert!(r.warning.unwrap().contains("Could not fetch"));
        assert!(client.resolve_voice("nobody").await.is_err());
    }

    #[tokio::test]
    async fn user_and_models_parse() {
        let server = MockServer::start().await;
        let tmp = tempfile::tempdir().unwrap();
        Mock::given(method("GET"))
            .and(path("/v1/user"))
            .respond_with(ResponseTemplate::new(200).set_body_json(serde_json::json!({
                "subscription": {"tier": "creator", "character_count": 10, "character_limit": 100},
                "is_new_user": false
            })))
            .mount(&server)
            .await;
        Mock::given(method("GET"))
            .and(path("/v1/models"))
            .respond_with(ResponseTemplate::new(200).set_body_json(serde_json::json!([
                {"model_id": "eleven_v3", "name": "Eleven v3", "can_do_text_to_speech": true,
                 "languages": [{"language_id": "en", "name": "English"}]}
            ])))
            .mount(&server)
            .await;
        let client = ElevenLabsClient::new(&config(&server.uri(), tmp.path(), Some(KEY)));
        let u = client.user_info().await.unwrap();
        assert_eq!(u.subscription.characters_remaining(), Some(90));
        let m = client.models().await.unwrap();
        assert_eq!(m[0].model_id, "eleven_v3");
    }

    #[tokio::test]
    async fn malformed_json_is_clean_error() {
        let server = MockServer::start().await;
        let tmp = tempfile::tempdir().unwrap();
        Mock::given(method("GET"))
            .respond_with(ResponseTemplate::new(200).set_body_string("not json"))
            .mount(&server)
            .await;
        let client = ElevenLabsClient::new(&config(&server.uri(), tmp.path(), Some(KEY)));
        let err = client.models().await.unwrap_err();
        assert!(err.to_string().contains("unexpected response"));
    }
}
