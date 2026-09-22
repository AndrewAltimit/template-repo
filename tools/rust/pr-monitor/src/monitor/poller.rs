//! Polling loop for PR comment monitoring
//!
//! Each poll is a single GraphQL request (see [`crate::github::GhClient`]).
//! New items are detected by node ID rather than by comment count, so deleted
//! comments, edits and comments/reviews arriving in the same poll are all
//! handled correctly.

use std::collections::HashSet;
use std::io::IsTerminal;
use std::sync::Arc;
use std::sync::atomic::{AtomicBool, Ordering};
use std::thread;
use std::time::{Duration, Instant};

use chrono::{DateTime, Utc};

use crate::analysis::{Classification, Decision, ResponseType, has_prior_response};
use crate::error::{Error, Result};
use crate::github::{Comment, CommentKind, PrSnapshot, PrSource};
use crate::monitor::Filter;

/// Consecutive transient poll failures tolerated before giving up
const MAX_CONSECUTIVE_FAILURES: u32 = 5;

/// Upper bound for the retry back-off
const MAX_BACKOFF: Duration = Duration::from_secs(60);

/// Minimum wait after GitHub reports a rate limit
const RATE_LIMIT_BACKOFF: Duration = Duration::from_secs(60);

/// Maximum number of older pages fetched per connection for `--since-commit`
const MAX_BACKFILL_PAGES: usize = 10;

/// Granularity of interruptible sleeps
const SLEEP_SLICE: Duration = Duration::from_millis(100);

/// How often a progress line is printed when stderr is not a terminal
const PLAIN_PROGRESS_EVERY: Duration = Duration::from_secs(60);

/// Poller settings
#[derive(Debug, Clone)]
pub struct PollerConfig {
    pub pr_number: u32,
    pub poll_interval: Duration,
    pub timeout: Duration,
    /// Only consider comments created strictly after this time
    pub since_time: Option<DateTime<Utc>>,
    pub filter: Filter,
    /// Suppress progress output on stderr (warnings are still printed)
    pub quiet: bool,
}

/// A relevant comment or review that ended monitoring
#[derive(Debug, Clone)]
pub struct Found {
    pub comment: Comment,
    pub classification: Classification,
    /// PR head SHA at detection time
    pub head_sha: String,
}

impl Found {
    /// Build the JSON decision for this result
    pub fn into_decision(self, pr_number: u32) -> Decision {
        let mut decision = self.classification.into_decision(&self.comment);
        decision.pr_number = Some(pr_number);
        if !self.head_sha.is_empty() {
            decision.head_sha = Some(self.head_sha);
        }
        decision
    }
}

/// PR comment poller
pub struct Poller<S: PrSource> {
    source: S,
    config: PollerConfig,
    running: Arc<AtomicBool>,
}

/// Items already present when live monitoring started
struct Baseline {
    seen: HashSet<String>,
    /// Oldest comment in a truncated baseline window: older unseen comments
    /// sliding into the window (after a deletion) are not new.
    comment_floor: Option<DateTime<Utc>>,
    review_floor: Option<DateTime<Utc>>,
}

impl Baseline {
    fn new(snapshot: &PrSnapshot) -> Self {
        let floor = |kind: CommentKind, truncated: bool| {
            truncated
                .then(|| {
                    snapshot
                        .events
                        .iter()
                        .filter(|e| e.kind == kind)
                        .map(|e| e.created_at)
                        .min()
                })
                .flatten()
        };
        Self {
            seen: snapshot.events.iter().map(|e| e.id.clone()).collect(),
            comment_floor: floor(
                CommentKind::IssueComment,
                snapshot.older_comments_cursor.is_some(),
            ),
            review_floor: floor(CommentKind::Review, snapshot.older_reviews_cursor.is_some()),
        }
    }

    /// Record `event`; returns true if it is genuinely new
    fn observe(&mut self, event: &Comment) -> bool {
        if !self.seen.insert(event.id.clone()) {
            return false;
        }
        let floor = match event.kind {
            CommentKind::Review => self.review_floor,
            _ => self.comment_floor,
        };
        floor.is_none_or(|f| event.created_at >= f)
    }
}

impl<S: PrSource> Poller<S> {
    /// Create a new poller
    pub fn new(source: S, config: PollerConfig, running: Arc<AtomicBool>) -> Self {
        Self {
            source,
            config,
            running,
        }
    }

    /// Run until a relevant comment is found, the timeout expires or the user
    /// interrupts.
    ///
    /// With `since_time` set, comments already on the PR after that time that
    /// need a response are reported immediately. Otherwise only items posted
    /// after monitoring starts are considered.
    pub fn run(&self) -> Result<Found> {
        let cfg = &self.config;
        let start = Instant::now();
        let deadline = start + cfg.timeout;

        let snapshot = self.source.snapshot(cfg.pr_number)?;
        if !snapshot.state.is_empty() && !snapshot.state.eq_ignore_ascii_case("OPEN") {
            eprintln!(
                "WARNING: PR #{} is {}; new feedback is unlikely.",
                cfg.pr_number, snapshot.state
            );
        }

        if let Some(found) = self.check_existing(&snapshot)? {
            return Ok(found);
        }

        let mut baseline = Baseline::new(&snapshot);
        let mut head_sha = snapshot.head_sha.clone();
        let mut event_count = snapshot.events.len();

        if !cfg.quiet {
            eprintln!(
                "Starting monitoring (poll interval: {}s, timeout: {}s)",
                cfg.poll_interval.as_secs(),
                cfg.timeout.as_secs()
            );
            eprintln!(
                "Initial state: {} comments, {} reviews",
                snapshot.comment_count, snapshot.review_count
            );
            eprintln!();
        }

        let fancy_progress = std::io::stderr().is_terminal();
        let mut last_plain_progress = start;
        let mut checks: u64 = 0;
        let mut failures: u32 = 0;
        let mut delay = cfg.poll_interval;

        loop {
            let remaining = deadline.saturating_duration_since(Instant::now());
            if remaining.is_zero() {
                if !cfg.quiet && fancy_progress {
                    eprintln!();
                }
                return Err(Error::Timeout {
                    seconds: cfg.timeout.as_secs(),
                });
            }

            self.sleep(delay.min(remaining))?;
            checks += 1;

            let snapshot = match self.source.snapshot(cfg.pr_number) {
                Ok(s) => {
                    failures = 0;
                    delay = cfg.poll_interval;
                    s
                },
                Err(e) if e.is_transient() && failures < MAX_CONSECUTIVE_FAILURES => {
                    failures += 1;
                    delay = retry_delay(cfg.poll_interval, failures, &e);
                    if fancy_progress && !cfg.quiet {
                        eprintln!();
                    }
                    eprintln!(
                        "WARNING: poll failed ({failures}/{MAX_CONSECUTIVE_FAILURES}): {e}; \
                         retrying in {}s",
                        delay.as_secs()
                    );
                    continue;
                },
                Err(e) => return Err(e),
            };

            if snapshot.head_sha != head_sha && !snapshot.head_sha.is_empty() {
                if !cfg.quiet {
                    if fancy_progress {
                        eprintln!();
                    }
                    eprintln!(
                        "PR head moved: {} -> {}",
                        short_sha(&head_sha),
                        short_sha(&snapshot.head_sha)
                    );
                }
                head_sha.clone_from(&snapshot.head_sha);
            }

            if !cfg.quiet {
                let elapsed = start.elapsed();
                let remaining = cfg.timeout.saturating_sub(elapsed).as_secs();
                let line = format!(
                    "[{:02}:{:02}] Check #{}: {} comments, {} reviews ({}s remaining)",
                    elapsed.as_secs() / 60,
                    elapsed.as_secs() % 60,
                    checks,
                    snapshot.comment_count,
                    snapshot.review_count,
                    remaining
                );
                if fancy_progress {
                    eprint!("\r{line}    ");
                } else if last_plain_progress.elapsed() >= PLAIN_PROGRESS_EVERY {
                    eprintln!("{line}");
                    last_plain_progress = Instant::now();
                }
            }

            let new_events: Vec<&Comment> = snapshot
                .events
                .iter()
                .filter(|e| baseline.observe(e))
                .collect();
            if new_events.is_empty() {
                continue;
            }

            if !cfg.quiet {
                if fancy_progress {
                    eprintln!();
                }
                eprintln!(
                    "New activity detected! ({} new item(s), {} -> {} total)",
                    new_events.len(),
                    event_count,
                    snapshot.events.len()
                );
            }
            event_count = snapshot.events.len();

            let candidates = new_events
                .into_iter()
                .filter(|e| self.passes_time_filter(e))
                .filter_map(|e| cfg.filter.evaluate(e).map(|c| (e, c)));

            if let Some(found) = self.pick(candidates, &snapshot) {
                if !cfg.quiet {
                    eprintln!(
                        "Found relevant comment from {} (type: {:?})",
                        found.comment.author.login, found.classification.response_type
                    );
                }
                return Ok(found);
            }

            if !cfg.quiet {
                eprintln!("New comments were not relevant, continuing...");
                eprintln!();
            }
        }
    }

    /// Check comments already on the PR after `since_time` that need a response
    fn check_existing(&self, snapshot: &PrSnapshot) -> Result<Option<Found>> {
        let cfg = &self.config;
        let Some(since) = cfg.since_time else {
            return Ok(None);
        };

        if !cfg.quiet {
            eprintln!("Checking existing comments after since-commit timestamp...");
        }

        let backlog = self.backfill(snapshot, since)?;
        let full = PrSnapshot {
            events: backlog,
            ..snapshot.clone()
        };

        let candidates = full
            .events
            .iter()
            .filter(|e| self.passes_time_filter(e))
            .filter_map(|e| cfg.filter.evaluate(e).map(|c| (e, c)))
            .filter(|(_, c)| c.needs_response);

        let found = self.pick(candidates, &full);
        if !cfg.quiet {
            match &found {
                Some(f) => eprintln!(
                    "Found existing relevant comment from {} at {}",
                    f.comment.author.login,
                    f.comment.created_at.format("%Y-%m-%d %H:%M:%S")
                ),
                None => {
                    eprintln!("No relevant existing comments found after the commit timestamp.");
                    eprintln!();
                },
            }
        }
        Ok(found)
    }

    /// Snapshot events plus older pages reaching back to `since`
    fn backfill(&self, snapshot: &PrSnapshot, since: DateTime<Utc>) -> Result<Vec<Comment>> {
        let pr = self.config.pr_number;
        let mut events = snapshot.events.clone();

        let needs_more = |events: &[Comment], kind: CommentKind| {
            events
                .iter()
                .filter(|e| e.kind == kind)
                .map(|e| e.created_at)
                .min()
                .is_some_and(|oldest| oldest > since)
        };

        let mut cursor = snapshot.older_comments_cursor.clone();
        let mut pages = 0;
        while let Some(before) = cursor.take() {
            if pages >= MAX_BACKFILL_PAGES || !needs_more(&events, CommentKind::IssueComment) {
                break;
            }
            let page = self.source.older_comments(pr, &before)?;
            events.extend(page.events);
            cursor = page.cursor;
            pages += 1;
        }

        let mut cursor = snapshot.older_reviews_cursor.clone();
        let mut pages = 0;
        while let Some(before) = cursor.take() {
            if pages >= MAX_BACKFILL_PAGES || !needs_more(&events, CommentKind::Review) {
                break;
            }
            let page = self.source.older_reviews(pr, &before)?;
            events.extend(page.events);
            cursor = page.cursor;
            pages += 1;
        }

        Ok(events)
    }

    /// Choose the most urgent candidate (ties: oldest first) and enrich it
    fn pick<'a>(
        &self,
        candidates: impl Iterator<Item = (&'a Comment, Classification)>,
        snapshot: &PrSnapshot,
    ) -> Option<Found> {
        let (comment, mut classification) = candidates
            .min_by_key(|(c, class)| (class.priority.rank(), c.created_at))
            .map(|(c, class)| (c.clone(), class))?;

        if classification.response_type == Some(ResponseType::AiAgentReview)
            && let Some(meta) = classification.review_metadata.as_mut()
        {
            if let Some(review_id) = meta.review_id.clone() {
                meta.already_responded = has_prior_response(&comment, &review_id, &snapshot.events);
            }
            if let Some(sha) = meta.commit_sha.as_deref().or(comment.commit_sha.as_deref()) {
                meta.outdated =
                    !snapshot.head_sha.is_empty() && !sha_matches(sha, &snapshot.head_sha);
            }
        }

        Some(Found {
            comment,
            classification,
            head_sha: snapshot.head_sha.clone(),
        })
    }

    fn passes_time_filter(&self, comment: &Comment) -> bool {
        self.config
            .since_time
            .is_none_or(|since| comment.created_at > since)
    }

    /// Sleep for `duration`, waking early (with an error) on Ctrl+C
    fn sleep(&self, duration: Duration) -> Result<()> {
        let end = Instant::now() + duration;
        loop {
            if !self.running.load(Ordering::SeqCst) {
                return Err(Error::Interrupted);
            }
            let left = end.saturating_duration_since(Instant::now());
            if left.is_zero() {
                return Ok(());
            }
            thread::sleep(left.min(SLEEP_SLICE));
        }
    }
}

/// Back-off after `failures` consecutive transient failures
fn retry_delay(poll_interval: Duration, failures: u32, error: &Error) -> Duration {
    let exp = poll_interval.saturating_mul(1 << failures.min(6));
    let delay = exp.min(MAX_BACKOFF);
    if matches!(error, Error::RateLimited { .. }) {
        delay.max(RATE_LIMIT_BACKOFF)
    } else {
        delay
    }
}

/// Whether two (possibly abbreviated) SHAs refer to the same commit
fn sha_matches(a: &str, b: &str) -> bool {
    let (a, b) = (a.to_ascii_lowercase(), b.to_ascii_lowercase());
    a.len() >= 4 && b.len() >= 4 && (a.starts_with(&b) || b.starts_with(&a))
}

fn short_sha(sha: &str) -> &str {
    sha.get(..8).unwrap_or(sha)
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::analysis::Priority;
    use crate::github::OlderPage;
    use chrono::TimeZone;
    use std::cell::RefCell;
    use std::collections::VecDeque;

    /// Scripted source: returns queued results in order, then repeats the last
    /// successful snapshot forever.
    struct FakeSource {
        queue: RefCell<VecDeque<Result<PrSnapshot>>>,
        last: RefCell<PrSnapshot>,
        calls: RefCell<usize>,
        older_comments: RefCell<VecDeque<OlderPage>>,
    }

    impl FakeSource {
        fn new(results: Vec<Result<PrSnapshot>>) -> Self {
            Self {
                queue: RefCell::new(results.into()),
                last: RefCell::new(PrSnapshot::default()),
                calls: RefCell::new(0),
                older_comments: RefCell::new(VecDeque::new()),
            }
        }
    }

    impl PrSource for &FakeSource {
        fn snapshot(&self, _pr: u32) -> Result<PrSnapshot> {
            *self.calls.borrow_mut() += 1;
            match self.queue.borrow_mut().pop_front() {
                Some(Ok(s)) => {
                    *self.last.borrow_mut() = s.clone();
                    Ok(s)
                },
                Some(Err(e)) => Err(e),
                None => Ok(self.last.borrow().clone()),
            }
        }

        fn older_comments(&self, _pr: u32, _before: &str) -> Result<OlderPage> {
            Ok(self
                .older_comments
                .borrow_mut()
                .pop_front()
                .unwrap_or_default())
        }

        fn older_reviews(&self, _pr: u32, _before: &str) -> Result<OlderPage> {
            Ok(OlderPage::default())
        }
    }

    fn t(minute: u32) -> DateTime<Utc> {
        Utc.with_ymd_and_hms(2026, 1, 1, 12, minute, 0).unwrap()
    }

    fn event(id: &str, author: &str, body: &str, at: DateTime<Utc>) -> Comment {
        Comment {
            id: id.to_string(),
            ..Comment::new(author, body, at)
        }
    }

    fn snapshot(events: Vec<Comment>) -> PrSnapshot {
        let comment_count = events
            .iter()
            .filter(|e| e.kind == CommentKind::IssueComment)
            .count();
        let review_count = events.len() - comment_count;
        PrSnapshot {
            state: "OPEN".to_string(),
            head_sha: "abcdef12".to_string(),
            events,
            comment_count,
            review_count,
            older_comments_cursor: None,
            older_reviews_cursor: None,
        }
    }

    fn config(timeout_ms: u64, since: Option<DateTime<Utc>>) -> PollerConfig {
        PollerConfig {
            pr_number: 1,
            poll_interval: Duration::from_millis(5),
            timeout: Duration::from_millis(timeout_ms),
            since_time: since,
            filter: Filter::new("admin"),
            quiet: true,
        }
    }

    fn run(source: &FakeSource, cfg: PollerConfig) -> Result<Found> {
        Poller::new(source, cfg, Arc::new(AtomicBool::new(true))).run()
    }

    const REVIEW: &str = "## Claude AI Code Review\n<!-- claude-review-marker:commit:abcdef12 -->";

    #[test]
    fn test_detects_new_comment_by_id() {
        let old = event("A", "admin", "old feedback", t(0));
        let new = event("B", "admin", "new feedback", t(5));
        let source = FakeSource::new(vec![
            Ok(snapshot(vec![old.clone()])),
            Ok(snapshot(vec![old.clone()])),
            Ok(snapshot(vec![old, new])),
        ]);
        let found = run(&source, config(5_000, None)).unwrap();
        assert_eq!(found.comment.id, "B");
        assert_eq!(found.head_sha, "abcdef12");
    }

    #[test]
    fn test_deleted_plus_added_comment_is_detected() {
        // Count stays the same (1 deleted, 1 added); ID tracking still sees it.
        let a = event("A", "admin", "first", t(0));
        let b = event("B", "admin", "second", t(1));
        let c = event("C", "admin", "third", t(2));
        let source = FakeSource::new(vec![
            Ok(snapshot(vec![a.clone(), b])),
            Ok(snapshot(vec![a, c])),
        ]);
        let found = run(&source, config(5_000, None)).unwrap();
        assert_eq!(found.comment.id, "C");
    }

    #[test]
    fn test_irrelevant_new_comments_are_ignored_until_timeout() {
        let source = FakeSource::new(vec![
            Ok(snapshot(vec![])),
            Ok(snapshot(vec![event("X", "stranger", "hi", t(1))])),
            Ok(snapshot(vec![
                event("X", "stranger", "hi", t(1)),
                event("Y", "github-actions[bot]", "Deployed preview", t(2)),
            ])),
        ]);
        let err = run(&source, config(60, None)).unwrap_err();
        assert!(matches!(err, Error::Timeout { .. }));
    }

    #[test]
    fn test_prefers_higher_priority_in_same_poll() {
        let review = event("R", "github-actions[bot]", REVIEW, t(1));
        let command = event("C", "admin", "[Approved][Claude]", t(2));
        let source = FakeSource::new(vec![
            Ok(snapshot(vec![])),
            Ok(snapshot(vec![review, command])),
        ]);
        let found = run(&source, config(5_000, None)).unwrap();
        assert_eq!(found.comment.id, "C");
        assert_eq!(found.classification.priority, Priority::High);
    }

    #[test]
    fn test_since_commit_returns_existing_comment() {
        let before = event("A", "admin", "stale feedback", t(0));
        let after = event("B", "github-actions[bot]", REVIEW, t(10));
        let source = FakeSource::new(vec![Ok(snapshot(vec![before, after]))]);
        let found = run(&source, config(5_000, Some(t(5)))).unwrap();
        assert_eq!(found.comment.id, "B");
        let meta = found.classification.review_metadata.unwrap();
        assert!(!meta.outdated);
        assert!(!meta.already_responded);
        assert_eq!(*source.calls.borrow(), 1);
    }

    #[test]
    fn test_since_commit_skips_existing_informational_comments() {
        let ci = event(
            "CI",
            "github-actions[bot]",
            "## PR Validation Results\nAll checks passed",
            t(10),
        );
        let source = FakeSource::new(vec![Ok(snapshot(vec![ci]))]);
        assert!(matches!(
            run(&source, config(30, Some(t(5)))),
            Err(Error::Timeout { .. })
        ));
    }

    #[test]
    fn test_since_commit_marks_outdated_and_responded_reviews() {
        let review = event(
            "R",
            "github-actions[bot]",
            "## Claude AI Code Review\n<!-- claude-review-marker:commit:0ddc0de1 -->",
            t(10),
        );
        let response = event(
            "F",
            "admin",
            "<!-- agent-metadata:type=review-fix:iteration=1 -->",
            t(12),
        );
        let source = FakeSource::new(vec![Ok(snapshot(vec![review, response]))]);
        let found = run(&source, config(5_000, Some(t(5)))).unwrap();
        let meta = found.classification.review_metadata.unwrap();
        assert!(meta.already_responded);
        // "0ddc0de1" is not a prefix of the head; treated as outdated
        assert!(meta.outdated);
    }

    #[test]
    fn test_since_commit_backfills_older_pages() {
        let mut first = snapshot(vec![event("N", "stranger", "noise", t(20))]);
        first.older_comments_cursor = Some("cursor".to_string());
        let source = FakeSource::new(vec![Ok(first)]);
        source.older_comments.borrow_mut().push_back(OlderPage {
            events: vec![event("O", "admin", "please fix", t(10))],
            cursor: None,
        });
        let found = run(&source, config(5_000, Some(t(5)))).unwrap();
        assert_eq!(found.comment.id, "O");
    }

    #[test]
    fn test_window_slide_after_deletion_is_not_new() {
        // Baseline window is truncated; after a deletion an older comment
        // slides into the window. It must not be reported as new.
        let mut first = snapshot(vec![
            event("B", "admin", "b", t(10)),
            event("C", "admin", "c", t(11)),
        ]);
        first.older_comments_cursor = Some("cursor".to_string());
        let mut second = snapshot(vec![
            event("A", "admin", "old, slid into window", t(1)),
            event("B", "admin", "b", t(10)),
        ]);
        second.older_comments_cursor = Some("cursor".to_string());
        let source = FakeSource::new(vec![Ok(first), Ok(second)]);
        assert!(matches!(
            run(&source, config(40, None)),
            Err(Error::Timeout { .. })
        ));
    }

    #[test]
    fn test_transient_errors_are_retried() {
        let new = event("B", "admin", "feedback", t(5));
        let source = FakeSource::new(vec![
            Ok(snapshot(vec![])),
            Err(Error::GhFailed {
                code: 1,
                stderr: "HTTP 502".to_string(),
            }),
            Ok(snapshot(vec![new])),
        ]);
        let found = run(&source, config(5_000, None)).unwrap();
        assert_eq!(found.comment.id, "B");
    }

    #[test]
    fn test_fatal_errors_abort() {
        let source = FakeSource::new(vec![
            Ok(snapshot(vec![])),
            Err(Error::GhFailed {
                code: 4,
                stderr: "HTTP 401: Bad credentials".to_string(),
            }),
        ]);
        assert!(matches!(
            run(&source, config(5_000, None)),
            Err(Error::GhFailed { code: 4, .. })
        ));
    }

    #[test]
    fn test_initial_error_is_fatal() {
        let source = FakeSource::new(vec![Err(Error::PrNotFound { pr_number: 1 })]);
        assert!(matches!(
            run(&source, config(5_000, None)),
            Err(Error::PrNotFound { .. })
        ));
    }

    #[test]
    fn test_interrupt() {
        let source = FakeSource::new(vec![Ok(snapshot(vec![]))]);
        let running = Arc::new(AtomicBool::new(false));
        let result = Poller::new(&source, config(5_000, None), running).run();
        assert!(matches!(result, Err(Error::Interrupted)));
    }

    #[test]
    fn test_zero_timeout_only_checks_existing() {
        let source = FakeSource::new(vec![Ok(snapshot(vec![]))]);
        assert!(matches!(
            run(&source, config(0, None)),
            Err(Error::Timeout { .. })
        ));
        assert_eq!(*source.calls.borrow(), 1);
    }

    #[test]
    fn test_live_poll_respects_since_filter() {
        // A comment created before since_time that shows up late (e.g. from a
        // previously pending review) is ignored.
        let late_old = event("L", "admin", "old", t(1));
        let source = FakeSource::new(vec![Ok(snapshot(vec![])), Ok(snapshot(vec![late_old]))]);
        assert!(matches!(
            run(&source, config(40, Some(t(5)))),
            Err(Error::Timeout { .. })
        ));
    }

    #[test]
    fn test_retry_delay() {
        let base = Duration::from_secs(5);
        let blip = Error::GraphQl("x".into());
        assert_eq!(retry_delay(base, 1, &blip), Duration::from_secs(10));
        assert_eq!(retry_delay(base, 2, &blip), Duration::from_secs(20));
        assert_eq!(retry_delay(base, 5, &blip), MAX_BACKOFF);
        let limited = Error::RateLimited {
            message: "x".into(),
        };
        assert_eq!(retry_delay(base, 1, &limited), RATE_LIMIT_BACKOFF);
    }

    #[test]
    fn test_sha_matches() {
        assert!(sha_matches("abc1234", "abc1234def"));
        assert!(sha_matches("ABC1234DEF", "abc1234"));
        assert!(!sha_matches("abc1234", "abd1234"));
        assert!(!sha_matches("", "abc"));
    }
}
