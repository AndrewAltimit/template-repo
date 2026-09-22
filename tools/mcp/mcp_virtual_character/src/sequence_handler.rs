//! Event sequence building and playback.
//!
//! A single sequence is built with `create_sequence` / `add_sequence_event`
//! and played on the active backend by a background task. Playback:
//!
//! - fires events at their `timestamp` (seconds from sequence start), in
//!   timestamp order, measured on a pausable clock;
//! - supports pause / resume / stop at any time, including mid-wait;
//! - only holds the backend lock while an event is being sent, so other tools
//!   (e.g. `get_backend_status`, `panic_reset`) stay responsive;
//! - resets the avatar at the start and end of each pass and loops if the
//!   sequence was created with `loop=true`;
//! - records per-event failures instead of aborting the performance.
//!
//! `wait` events are timeline markers: they extend the sequence's total
//! duration (`timestamp + wait_duration`) but do not shift other events,
//! which are absolutely timed.

use serde::Serialize;
use std::sync::atomic::{AtomicU64, Ordering};
use std::sync::{Arc, Mutex as StdMutex, MutexGuard};
use std::time::Instant;
use tokio::sync::{watch, Mutex, RwLock};
use tokio::task::JoinHandle;
use tokio::time::{sleep, Duration};
use tracing::{info, warn};

use crate::backends::{BackendAdapter, SharedBackend};
use crate::types::{CanonicalAnimationData, EventSequence, EventType, SequenceEvent};

/// Maximum number of events in one sequence.
pub const MAX_SEQUENCE_EVENTS: usize = 1000;
/// Minimum length of one pass of a looping sequence (prevents busy loops).
pub const MIN_LOOP_DURATION: f64 = 0.1;

/// Errors from sequence operations.
#[derive(Debug, thiserror::Error, PartialEq)]
pub enum SequenceError {
    #[error("No sequence created. Use create_sequence first.")]
    NoSequence,
    #[error("No sequence is playing")]
    NotPlaying,
    #[error("Sequence is not paused")]
    NotPaused,
    #[error("Sequence is empty; add events with add_sequence_event")]
    Empty,
    #[error("Sequence is full ({MAX_SEQUENCE_EVENTS} events)")]
    Full,
    #[error("Invalid parameter: {0}")]
    InvalidParameter(String),
}

/// Result alias for sequence operations.
pub type SequenceResult<T> = Result<T, SequenceError>;

/// Playback control state.
#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize)]
#[serde(rename_all = "lowercase")]
enum PlayState {
    Playing,
    Paused,
    Stopped,
}

/// Pausable sequence clock (seconds of sequence time).
#[derive(Debug)]
struct SeqClock {
    base: f64,
    running_since: Option<Instant>,
}

impl SeqClock {
    fn new(start: f64) -> Self {
        Self {
            base: start,
            running_since: Some(Instant::now()),
        }
    }
    fn now(&self) -> f64 {
        self.base
            + self
                .running_since
                .map_or(0.0, |t| t.elapsed().as_secs_f64())
    }
    fn pause(&mut self) {
        self.base = self.now();
        self.running_since = None;
    }
    fn resume(&mut self) {
        if self.running_since.is_none() {
            self.running_since = Some(Instant::now());
        }
    }
    fn reset(&mut self, to: f64) {
        self.base = to;
        if self.running_since.is_some() {
            self.running_since = Some(Instant::now());
        }
    }
}

fn lock<T>(m: &StdMutex<T>) -> MutexGuard<'_, T> {
    m.lock().unwrap_or_else(|e| e.into_inner())
}

/// Progress shared between the playback task and status queries.
#[derive(Debug)]
struct Progress {
    clock: StdMutex<SeqClock>,
    events_executed: AtomicU64,
    events_failed: AtomicU64,
    passes_completed: AtomicU64,
    last_error: StdMutex<Option<String>>,
}

struct Playback {
    name: String,
    task: JoinHandle<()>,
    control: watch::Sender<PlayState>,
    progress: Arc<Progress>,
}

/// Snapshot of the sequence and playback state.
#[derive(Debug, Clone, Default, Serialize)]
pub struct SequenceStatus {
    pub has_sequence: bool,
    pub sequence_name: Option<String>,
    pub event_count: usize,
    pub total_duration: Option<f64>,
    #[serde(rename = "loop")]
    pub loop_enabled: bool,
    pub is_playing: bool,
    pub is_paused: bool,
    /// Current position in seconds (sequence time).
    pub current_time: f64,
    pub playing_sequence: Option<String>,
    pub events_executed: u64,
    pub events_failed: u64,
    pub passes_completed: u64,
    pub last_error: Option<String>,
}

/// Builds and plays event sequences.
#[derive(Default)]
pub struct SequenceHandler {
    sequence: RwLock<Option<EventSequence>>,
    playback: Mutex<Option<Playback>>,
}

impl SequenceHandler {
    /// Create a new handler with no sequence.
    pub fn new() -> Self {
        Self::default()
    }

    /// Start a new (empty) sequence, replacing the one being built.
    /// If `interrupt_current` is true, stop any playback first.
    pub async fn create_sequence(
        &self,
        name: String,
        description: Option<String>,
        loop_sequence: bool,
        interrupt_current: bool,
        created_timestamp: f64,
    ) -> SequenceResult<()> {
        let name = name.trim().to_string();
        if name.is_empty() || name.len() > 200 {
            return Err(SequenceError::InvalidParameter(
                "name must be 1-200 characters".to_string(),
            ));
        }
        if interrupt_current {
            self.stop().await;
        }
        let mut seq = EventSequence::new(name);
        seq.description = description;
        seq.loop_sequence = loop_sequence;
        seq.interrupt_current = interrupt_current;
        seq.created_timestamp = Some(created_timestamp);
        *self.sequence.write().await = Some(seq);
        Ok(())
    }

    /// Append an event; returns the new event count.
    pub async fn add_event(&self, event: SequenceEvent) -> SequenceResult<usize> {
        let mut guard = self.sequence.write().await;
        let seq = guard.as_mut().ok_or(SequenceError::NoSequence)?;
        if seq.events.len() >= MAX_SEQUENCE_EVENTS {
            return Err(SequenceError::Full);
        }
        seq.add_event(event);
        Ok(seq.events.len())
    }

    /// Start playing the current sequence from `start_time` seconds,
    /// replacing any playback in progress. Returns the sequence name.
    pub async fn play(&self, backend: SharedBackend, start_time: f64) -> SequenceResult<String> {
        if !start_time.is_finite() || start_time < 0.0 {
            return Err(SequenceError::InvalidParameter(
                "start_time must be a non-negative number".to_string(),
            ));
        }
        // Snapshot so edits during playback do not race the player.
        let seq = self
            .sequence
            .read()
            .await
            .clone()
            .ok_or(SequenceError::NoSequence)?;
        if seq.events.is_empty() {
            return Err(SequenceError::Empty);
        }
        let total = seq.total_duration.unwrap_or(0.0);
        if start_time > total {
            return Err(SequenceError::InvalidParameter(format!(
                "start_time {start_time}s is past the end of the sequence ({total}s)"
            )));
        }

        let mut playback = self.playback.lock().await;
        if let Some(old) = playback.take() {
            Self::shutdown(old).await;
        }

        let progress = Arc::new(Progress {
            clock: StdMutex::new(SeqClock::new(start_time)),
            events_executed: AtomicU64::new(0),
            events_failed: AtomicU64::new(0),
            passes_completed: AtomicU64::new(0),
            last_error: StdMutex::new(None),
        });
        let (tx, rx) = watch::channel(PlayState::Playing);
        let name = seq.name.clone();
        let task = tokio::spawn(run_sequence(seq, backend, progress.clone(), rx, start_time));
        *playback = Some(Playback {
            name: name.clone(),
            task,
            control: tx,
            progress,
        });
        info!("Playing sequence '{}' from {}s", name, start_time);
        Ok(name)
    }

    /// Pause playback (the clock stops; pending waits are suspended).
    pub async fn pause(&self) -> SequenceResult<()> {
        let playback = self.playback.lock().await;
        let pb = playback
            .as_ref()
            .filter(|p| !p.task.is_finished())
            .ok_or(SequenceError::NotPlaying)?;
        if *pb.control.borrow() == PlayState::Playing {
            lock(&pb.progress.clock).pause();
            let _ = pb.control.send(PlayState::Paused);
        }
        Ok(())
    }

    /// Resume paused playback.
    pub async fn resume(&self) -> SequenceResult<()> {
        let playback = self.playback.lock().await;
        let pb = playback
            .as_ref()
            .filter(|p| !p.task.is_finished())
            .ok_or(SequenceError::NotPlaying)?;
        if *pb.control.borrow() != PlayState::Paused {
            return Err(SequenceError::NotPaused);
        }
        lock(&pb.progress.clock).resume();
        let _ = pb.control.send(PlayState::Playing);
        Ok(())
    }

    /// Stop playback. Returns true if something was playing.
    pub async fn stop(&self) -> bool {
        let old = self.playback.lock().await.take();
        match old {
            Some(pb) => {
                let was_running = !pb.task.is_finished();
                Self::shutdown(pb).await;
                was_running
            },
            None => false,
        }
    }

    /// Stop playback and discard the sequence.
    pub async fn clear(&self) {
        self.stop().await;
        *self.sequence.write().await = None;
    }

    async fn shutdown(pb: Playback) {
        let _ = pb.control.send(PlayState::Stopped);
        pb.task.abort();
        let _ = pb.task.await;
    }

    /// Current status.
    pub async fn status(&self) -> SequenceStatus {
        let mut status = SequenceStatus::default();
        if let Some(seq) = self.sequence.read().await.as_ref() {
            status.has_sequence = true;
            status.sequence_name = Some(seq.name.clone());
            status.event_count = seq.events.len();
            status.total_duration = seq.total_duration;
            status.loop_enabled = seq.loop_sequence;
        }
        if let Some(pb) = self.playback.lock().await.as_ref() {
            let running = !pb.task.is_finished();
            status.is_playing = running;
            status.is_paused = running && *pb.control.borrow() == PlayState::Paused;
            status.current_time = (lock(&pb.progress.clock).now() * 1000.0).round() / 1000.0;
            status.playing_sequence = Some(pb.name.clone());
            status.events_executed = pb.progress.events_executed.load(Ordering::Relaxed);
            status.events_failed = pb.progress.events_failed.load(Ordering::Relaxed);
            status.passes_completed = pb.progress.passes_completed.load(Ordering::Relaxed);
            status.last_error = lock(&pb.progress.last_error).clone();
        }
        status
    }
}

/// Wait until the sequence clock reaches `target`. Returns false if stopped.
async fn wait_until(target: f64, progress: &Progress, rx: &mut watch::Receiver<PlayState>) -> bool {
    loop {
        let state = *rx.borrow_and_update();
        match state {
            PlayState::Stopped => return false,
            PlayState::Paused => {
                if rx.changed().await.is_err() {
                    return false;
                }
            },
            PlayState::Playing => {
                let remaining = target - lock(&progress.clock).now();
                if remaining <= 0.0 {
                    return true;
                }
                tokio::select! {
                    _ = sleep(Duration::from_secs_f64(remaining)) => {},
                    changed = rx.changed() => {
                        if changed.is_err() {
                            return false;
                        }
                    },
                }
            },
        }
    }
}

async fn run_sequence(
    seq: EventSequence,
    backend: SharedBackend,
    progress: Arc<Progress>,
    mut rx: watch::Receiver<PlayState>,
    start_time: f64,
) {
    let mut events = seq.events.clone();
    events.sort_by(|a, b| a.timestamp.total_cmp(&b.timestamp));
    let total = seq.total_duration.unwrap_or(0.0);
    let pass_len = if seq.loop_sequence {
        total.max(MIN_LOOP_DURATION)
    } else {
        total
    };
    let mut first_pass = true;

    loop {
        let offset = if first_pass { start_time } else { 0.0 };
        lock(&progress.clock).reset(offset);
        reset_backend(&backend, &progress).await;

        for event in events.iter().filter(|e| e.timestamp >= offset) {
            if !wait_until(event.timestamp, &progress, &mut rx).await {
                return;
            }
            let result = {
                let mut guard = backend.write().await;
                match guard.as_mut() {
                    Some(b) if b.is_connected() => execute_event(event, b.as_mut()).await,
                    _ => Err("backend disconnected".to_string()),
                }
            };
            match result {
                Ok(()) => {
                    progress.events_executed.fetch_add(1, Ordering::Relaxed);
                },
                Err(e) => {
                    warn!(
                        "Sequence '{}': {:?} event at {}s failed: {}",
                        seq.name, event.event_type, event.timestamp, e
                    );
                    progress.events_failed.fetch_add(1, Ordering::Relaxed);
                    *lock(&progress.last_error) = Some(format!(
                        "{:?} at {}s: {}",
                        event.event_type, event.timestamp, e
                    ));
                },
            }
        }

        if !wait_until(pass_len, &progress, &mut rx).await {
            return;
        }
        reset_backend(&backend, &progress).await;
        progress.passes_completed.fetch_add(1, Ordering::Relaxed);
        first_pass = false;
        if !seq.loop_sequence {
            info!("Sequence '{}' finished", seq.name);
            return;
        }
    }
}

async fn reset_backend(backend: &SharedBackend, progress: &Progress) {
    let mut guard = backend.write().await;
    if let Some(b) = guard.as_mut().filter(|b| b.is_connected()) {
        if let Err(e) = b.reset_all().await {
            warn!("Sequence reset failed: {}", e);
            *lock(&progress.last_error) = Some(format!("reset: {e}"));
        }
    }
}

/// Execute a single event (and parallel children) against the backend.
async fn execute_event(
    event: &SequenceEvent,
    backend: &mut dyn BackendAdapter,
) -> Result<(), String> {
    match event.event_type {
        EventType::Animation => {
            if let Some(anim) = &event.animation_data {
                backend
                    .send_animation_data(anim.clone())
                    .await
                    .map_err(|e| e.to_string())?;
            }
        },
        EventType::Audio => {
            if let Some(audio) = &event.audio_data {
                backend
                    .send_audio_data(audio.clone())
                    .await
                    .map_err(|e| e.to_string())?;
            }
        },
        EventType::Expression => {
            if let Some(emotion) = event.expression {
                let anim = CanonicalAnimationData::new(event.timestamp)
                    .with_emotion(emotion, event.expression_intensity.unwrap_or(1.0));
                backend
                    .send_animation_data(anim)
                    .await
                    .map_err(|e| e.to_string())?;
            }
        },
        EventType::Movement => {
            if let Some(params) = &event.movement_params {
                let anim =
                    CanonicalAnimationData::new(event.timestamp).with_parameters(params.clone());
                backend
                    .send_animation_data(anim)
                    .await
                    .map_err(|e| e.to_string())?;
            }
        },
        EventType::Parallel => {
            // Backend sends are near-instant (audio playback is started in the
            // background), so children are dispatched back-to-back.
            let mut errors = Vec::new();
            for child in event.parallel_events.iter().flatten() {
                if let Err(e) = Box::pin(execute_event(child, backend)).await {
                    errors.push(e);
                }
            }
            if !errors.is_empty() {
                return Err(errors.join("; "));
            }
        },
        EventType::Wait | EventType::LoopStart | EventType::LoopEnd => {},
    }
    Ok(())
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::backends::{create_backend, SharedBackend};
    use crate::types::EmotionType;
    use std::collections::HashMap;

    async fn mock_backend() -> SharedBackend {
        let mut b = create_backend("mock").unwrap();
        b.connect(HashMap::new()).await.unwrap();
        Arc::new(RwLock::new(Some(b)))
    }

    fn expr(ts: f64, e: EmotionType) -> SequenceEvent {
        let mut ev = SequenceEvent::new(EventType::Expression, ts);
        ev.expression = Some(e);
        ev
    }

    async fn frames(backend: &SharedBackend) -> u64 {
        let guard = backend.read().await;
        let stats = guard.as_ref().unwrap().get_statistics().await.unwrap();
        stats["frames_sent"].as_u64().unwrap()
    }

    #[tokio::test]
    async fn create_and_add() {
        let h = SequenceHandler::new();
        assert!(!h.status().await.has_sequence);
        assert_eq!(
            h.add_event(expr(0.0, EmotionType::Happy)).await,
            Err(SequenceError::NoSequence)
        );
        h.create_sequence("greet".into(), None, false, true, 0.0)
            .await
            .unwrap();
        assert_eq!(h.add_event(expr(1.0, EmotionType::Happy)).await, Ok(1));
        let s = h.status().await;
        assert_eq!(s.sequence_name.as_deref(), Some("greet"));
        assert_eq!(s.event_count, 1);
        assert!(h
            .create_sequence("  ".into(), None, false, true, 0.0)
            .await
            .is_err());
    }

    #[tokio::test]
    async fn play_requires_events_and_valid_start() {
        let h = SequenceHandler::new();
        let backend = mock_backend().await;
        assert_eq!(
            h.play(backend.clone(), 0.0).await,
            Err(SequenceError::NoSequence)
        );
        h.create_sequence("s".into(), None, false, true, 0.0)
            .await
            .unwrap();
        assert_eq!(
            h.play(backend.clone(), 0.0).await,
            Err(SequenceError::Empty)
        );
        h.add_event(expr(0.1, EmotionType::Sad)).await.unwrap();
        assert!(h.play(backend.clone(), -1.0).await.is_err());
        assert!(h.play(backend.clone(), 50.0).await.is_err());
        assert_eq!(
            h.pause().await.map_err(|e| e.to_string()),
            Err("No sequence is playing".into())
        );
    }

    #[tokio::test]
    async fn plays_events_in_order_and_finishes() {
        let h = SequenceHandler::new();
        let backend = mock_backend().await;
        h.create_sequence("s".into(), None, false, true, 0.0)
            .await
            .unwrap();
        h.add_event(expr(0.1, EmotionType::Sad)).await.unwrap();
        h.add_event(expr(0.0, EmotionType::Happy)).await.unwrap();
        h.play(backend.clone(), 0.0).await.unwrap();
        assert!(h.status().await.is_playing);
        sleep(Duration::from_millis(400)).await;
        let s = h.status().await;
        assert!(!s.is_playing, "{s:?}");
        assert_eq!(s.events_executed, 2);
        assert_eq!(s.events_failed, 0);
        assert_eq!(s.passes_completed, 1);
        assert_eq!(frames(&backend).await, 2);
    }

    #[tokio::test]
    async fn pause_resume_and_stop() {
        let h = SequenceHandler::new();
        let backend = mock_backend().await;
        h.create_sequence("s".into(), None, false, true, 0.0)
            .await
            .unwrap();
        h.add_event(expr(0.3, EmotionType::Happy)).await.unwrap();
        h.play(backend.clone(), 0.0).await.unwrap();
        sleep(Duration::from_millis(50)).await;
        h.pause().await.unwrap();
        let paused_at = h.status().await.current_time;
        sleep(Duration::from_millis(400)).await;
        let s = h.status().await;
        assert!(s.is_paused && s.is_playing);
        assert_eq!(s.events_executed, 0, "event fired while paused");
        assert!((s.current_time - paused_at).abs() < 0.01);
        assert_eq!(h.pause().await, Ok(())); // idempotent

        h.resume().await.unwrap();
        assert_eq!(h.resume().await, Err(SequenceError::NotPaused));
        sleep(Duration::from_millis(400)).await;
        assert_eq!(h.status().await.events_executed, 1);

        // Stop mid-loop.
        h.create_sequence("l".into(), None, true, true, 0.0)
            .await
            .unwrap();
        h.add_event(expr(0.0, EmotionType::Sad)).await.unwrap();
        h.play(backend.clone(), 0.0).await.unwrap();
        sleep(Duration::from_millis(350)).await;
        assert!(h.status().await.passes_completed >= 2);
        assert!(h.stop().await);
        assert!(!h.status().await.is_playing);
        assert!(!h.stop().await);
    }

    #[tokio::test]
    async fn failures_are_recorded_not_fatal() {
        let h = SequenceHandler::new();
        let backend = mock_backend().await;
        h.create_sequence("s".into(), None, false, true, 0.0)
            .await
            .unwrap();
        let mut bad = SequenceEvent::new(EventType::Movement, 0.0);
        let mut p = HashMap::new();
        p.insert("move_forward".to_string(), serde_json::json!("oops"));
        bad.movement_params = Some(p);
        h.add_event(bad).await.unwrap();
        h.add_event(expr(0.05, EmotionType::Happy)).await.unwrap();
        h.play(backend.clone(), 0.0).await.unwrap();
        sleep(Duration::from_millis(300)).await;
        let s = h.status().await;
        assert_eq!(s.events_failed, 1);
        assert_eq!(s.events_executed, 1);
        assert!(s.last_error.unwrap().contains("move_forward"));
    }

    #[tokio::test]
    async fn start_time_skips_earlier_events() {
        let h = SequenceHandler::new();
        let backend = mock_backend().await;
        h.create_sequence("s".into(), None, false, true, 0.0)
            .await
            .unwrap();
        h.add_event(expr(0.0, EmotionType::Happy)).await.unwrap();
        h.add_event(expr(0.2, EmotionType::Sad)).await.unwrap();
        h.play(backend.clone(), 0.1).await.unwrap();
        sleep(Duration::from_millis(300)).await;
        assert_eq!(h.status().await.events_executed, 1);
    }

    #[test]
    fn clock_pause_resume() {
        let mut c = SeqClock::new(1.0);
        c.pause();
        let t = c.now();
        std::thread::sleep(std::time::Duration::from_millis(20));
        assert_eq!(c.now(), t);
        c.resume();
        std::thread::sleep(std::time::Duration::from_millis(20));
        assert!(c.now() > t);
        c.reset(0.0);
        assert!(c.now() < 0.01);
    }
}
