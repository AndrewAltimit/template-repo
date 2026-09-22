//! Training log reading and progress parsing.
//!
//! AI Toolkit reports progress through tqdm, which redraws a single line with
//! carriage returns (`\r`) rather than newlines, e.g.
//!
//! ```text
//! my_lora:  12%|#2        | 250/2000 [05:00<35:00,  1.20s/it, lr: 1.0e-04 loss: 3.215e-01]
//! ```
//!
//! Logs are therefore split on both `\r` and `\n`, and only the tail of the
//! file is read so status polling stays cheap for multi-hour runs.

use regex::Regex;
use serde::Serialize;
use std::path::Path;
use std::sync::LazyLock;
use tokio::io::{AsyncReadExt, AsyncSeekExt};

/// Default number of trailing bytes inspected for progress.
pub const PROGRESS_TAIL_BYTES: u64 = 256 * 1024;

/// Upper bound on bytes read for `get_training_logs`.
pub const LOG_TAIL_BYTES: u64 = 4 * 1024 * 1024;

static TQDM_RE: LazyLock<Regex> = LazyLock::new(|| {
    Regex::new(r"(\d+)/(\d+)\s*\[([^\]]*)\]").expect("static tqdm regex is valid")
});
static STEP_RE: LazyLock<Regex> = LazyLock::new(|| {
    Regex::new(r"(?i)\bstep\b\s*:?\s*(\d+)\s*/\s*(\d+)").expect("static step regex is valid")
});
static LOSS_RE: LazyLock<Regex> = LazyLock::new(|| {
    Regex::new(r"loss:\s*([-+]?[0-9]*\.?[0-9]+(?:[eE][-+]?[0-9]+)?)")
        .expect("static loss regex is valid")
});
static LR_RE: LazyLock<Regex> = LazyLock::new(|| {
    Regex::new(r"\blr:\s*([-+]?[0-9]*\.?[0-9]+(?:[eE][-+]?[0-9]+)?)")
        .expect("static lr regex is valid")
});
static ERROR_RE: LazyLock<Regex> = LazyLock::new(|| {
    Regex::new(r"^\s*([A-Za-z_][\w.]*(?:Error|Exception)|RuntimeError|KeyboardInterrupt)\b.*")
        .expect("static error regex is valid")
});

/// Training progress extracted from a log.
#[derive(Debug, Clone, PartialEq, Serialize)]
pub struct Progress {
    pub current_step: u32,
    pub total_steps: u32,
    /// Integer percentage 0-100.
    pub percent: u32,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub loss: Option<f64>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub lr: Option<f64>,
    /// tqdm remaining-time estimate, e.g. `35:00`.
    #[serde(skip_serializing_if = "Option::is_none")]
    pub eta: Option<String>,
}

/// Split log text into display lines, keeping only the final redraw of each
/// carriage-return-updated line.
pub fn display_lines(text: &str) -> Vec<String> {
    text.split('\n')
        .map(|line| {
            line.split('\r')
                .rfind(|seg| !seg.trim().is_empty())
                .unwrap_or("")
                .trim_end()
                .to_string()
        })
        .filter(|l| !l.is_empty())
        .collect()
}

/// Parse the most recent training progress from log text.
///
/// If `expected_total` is known (from the config's `train.steps`), progress
/// bars with a different total (latent caching, sample generation) are ignored.
pub fn parse_progress(text: &str, expected_total: Option<u32>) -> Option<Progress> {
    for seg in text.rsplit(['\r', '\n']) {
        if seg.trim().is_empty() {
            continue;
        }
        let (step, total, bracket) = if let Some(c) = TQDM_RE.captures(seg) {
            (c[1].parse::<u32>().ok(), c[2].parse::<u32>().ok(), c.get(3))
        } else if let Some(c) = STEP_RE.captures(seg) {
            (c[1].parse::<u32>().ok(), c[2].parse::<u32>().ok(), None)
        } else {
            continue;
        };
        let (Some(step), Some(total)) = (step, total) else {
            continue;
        };
        if total == 0 || expected_total.is_some_and(|t| t != total) {
            continue;
        }
        let eta = bracket.and_then(|b| {
            let s = b.as_str();
            let after = s.split_once('<')?.1;
            Some(after.split(',').next()?.trim().to_string()).filter(|e| !e.is_empty())
        });
        let num = |re: &Regex| {
            re.captures(seg)
                .and_then(|c| c.get(1))
                .and_then(|m| m.as_str().parse::<f64>().ok())
        };
        return Some(Progress {
            current_step: step,
            total_steps: total,
            percent: ((u64::from(step.min(total)) * 100) / u64::from(total)) as u32,
            loss: num(&LOSS_RE),
            lr: num(&LR_RE),
            eta,
        });
    }
    None
}

/// Find the most relevant error line (e.g. `torch.OutOfMemoryError: ...`)
/// near the end of a log.
pub fn find_error_hint(text: &str) -> Option<String> {
    display_lines(text)
        .into_iter()
        .rev()
        .take(200)
        .find(|l| ERROR_RE.is_match(l))
        .map(|l| {
            let l = l.trim();
            if l.len() > 500 {
                let mut end = 500;
                while !l.is_char_boundary(end) {
                    end -= 1;
                }
                format!("{}...", &l[..end])
            } else {
                l.to_string()
            }
        })
}

/// Read at most `max_bytes` from the end of a file.
///
/// Returns the text (lossy UTF-8, first partial line dropped when truncated),
/// the file size, and whether the read was truncated.
pub async fn read_tail(path: &Path, max_bytes: u64) -> std::io::Result<(String, u64, bool)> {
    let mut file = tokio::fs::File::open(path).await?;
    let size = file.metadata().await?.len();
    let start = size.saturating_sub(max_bytes);
    file.seek(std::io::SeekFrom::Start(start)).await?;
    let mut buf = Vec::with_capacity((size - start) as usize);
    file.take(max_bytes).read_to_end(&mut buf).await?;
    let mut text = String::from_utf8_lossy(&buf).into_owned();
    let truncated = start > 0;
    if truncated && let Some(idx) = text.find('\n') {
        text.drain(..=idx);
    }
    Ok((text, size, truncated))
}

#[cfg(test)]
mod tests {
    use super::*;

    const TQDM_LOG: &str = "Loading model\nCaching latents: 100%|##########| 20/20 [00:05<00:00, 4.0it/s]\n\
my_lora:   0%|          | 0/2000 [00:00<?, ?it/s]\r\
my_lora:   5%|5         | 100/2000 [02:00<38:00,  1.20s/it, lr: 1.0e-04 loss: 4.500e-01]\r\
my_lora:  12%|#2        | 250/2000 [05:00<35:00,  1.20s/it, lr: 1.0e-04 loss: 3.215e-01]\r\
Generating Images: 50%|#####  | 1/2 [00:01<00:01]";

    #[test]
    fn parses_last_training_bar() {
        let p = parse_progress(TQDM_LOG, Some(2000)).unwrap();
        assert_eq!(p.current_step, 250);
        assert_eq!(p.total_steps, 2000);
        assert_eq!(p.percent, 12);
        assert_eq!(p.loss, Some(0.3215));
        assert_eq!(p.lr, Some(1e-4));
        assert_eq!(p.eta.as_deref(), Some("35:00"));
    }

    #[test]
    fn without_expected_total_uses_latest_bar() {
        let p = parse_progress(TQDM_LOG, None).unwrap();
        assert_eq!((p.current_step, p.total_steps), (1, 2));
    }

    #[test]
    fn step_fallback_and_none() {
        let p = parse_progress("foo\nStep 30/60 done\n", None).unwrap();
        assert_eq!(p.percent, 50);
        assert_eq!(p.loss, None);
        assert!(parse_progress("nothing here\n1999/2000 years\n", None).is_none());
        assert!(parse_progress("", Some(10)).is_none());
        // total 0 must not divide by zero
        assert!(parse_progress("x | 0/0 [00:00<?]", None).is_none());
    }

    #[test]
    fn display_lines_collapses_redraws() {
        let lines = display_lines("a\r\nb\rc\n\n  \r\nd\r");
        assert_eq!(lines, vec!["a", "c", "d"]);
    }

    #[test]
    fn error_hint() {
        let log = "Traceback (most recent call last):\n  File \"run.py\"\n\
torch.OutOfMemoryError: CUDA out of memory. Tried to allocate 2.00 GiB\n";
        assert_eq!(
            find_error_hint(log).unwrap(),
            "torch.OutOfMemoryError: CUDA out of memory. Tried to allocate 2.00 GiB"
        );
        assert!(find_error_hint("all good\n").is_none());
    }

    #[tokio::test]
    async fn tail_read() {
        let tmp = tempfile::tempdir().unwrap();
        let f = tmp.path().join("log.txt");
        std::fs::write(&f, "line1\nline2\nline3\n").unwrap();
        let (t, size, trunc) = read_tail(&f, 1024).await.unwrap();
        assert_eq!(
            (t.as_str(), size, trunc),
            ("line1\nline2\nline3\n", 18, false)
        );
        let (t, _, trunc) = read_tail(&f, 8).await.unwrap();
        assert!(trunc);
        assert_eq!(t, "line3\n");
    }
}
