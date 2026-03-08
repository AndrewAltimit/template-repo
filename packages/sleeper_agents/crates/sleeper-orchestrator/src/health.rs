use std::time::Duration;

use anyhow::{Result, bail};

use crate::output;

/// Wait for the API server inside the container to become healthy.
///
/// Polls the /health endpoint with exponential backoff up to `timeout`.
pub async fn wait_for_api(base_url: &str, timeout: Duration) -> Result<()> {
    let client = sleeper_api_client::SleeperClient::new(base_url, None);
    let start = std::time::Instant::now();
    let mut delay = Duration::from_millis(500);
    let max_delay = Duration::from_secs(5);

    output::info(&format!("Waiting for API at {base_url}..."));

    loop {
        match client.health().await {
            Ok(resp)
                if resp.status.eq_ignore_ascii_case("healthy")
                    || resp.status.eq_ignore_ascii_case("ok") =>
            {
                output::success(&format!("API healthy at {base_url}"));
                return Ok(());
            },
            Ok(resp) => {
                output::detail(&format!("API responded with status: {}", resp.status));
            },
            Err(_) if start.elapsed() < timeout => {
                // Not ready yet, keep waiting
            },
            Err(e) => {
                bail!(
                    "API not reachable at {base_url} after {}s: {e}",
                    timeout.as_secs()
                );
            },
        }

        if start.elapsed() >= timeout {
            bail!(
                "API did not become healthy at {base_url} within {}s",
                timeout.as_secs()
            );
        }

        tokio::time::sleep(delay).await;
        delay = (delay * 2).min(max_delay);
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[tokio::test]
    async fn timeout_on_unreachable() {
        let result = wait_for_api("http://127.0.0.1:19999", Duration::from_millis(500)).await;
        assert!(result.is_err());
    }
}
