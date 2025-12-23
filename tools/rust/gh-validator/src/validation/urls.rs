//! URL validation with SSRF protection
//!
//! Validates reaction image URLs to ensure:
//! 1. Only whitelisted hostnames are allowed (SSRF protection)
//! 2. No direct IP addresses (IPv4/IPv6)
//! 3. Valid image extensions
//! 4. URLs actually exist (HTTP HEAD request with retries)

use crate::error::{Error, Result};
use once_cell::sync::Lazy;
use regex::Regex;
use std::time::Duration;

/// Whitelisted hostnames for reaction images
const ALLOWED_HOSTNAMES: &[&str] = &[
    "raw.githubusercontent.com",
    "github.com",
    "user-images.githubusercontent.com",
    "camo.githubusercontent.com",
];

/// Valid image file extensions
const ALLOWED_EXTENSIONS: &[&str] = &["png", "jpg", "jpeg", "gif", "webp", "svg"];

/// Regex to extract reaction URLs from markdown
static URL_PATTERN: Lazy<Regex> = Lazy::new(|| {
    Regex::new(r"!\[([^\]]*)\]\((https?://[^)]+(?:reaction|Media)[^)]+)\)").unwrap()
});

/// Regex for escaped reaction URLs
static ESCAPED_URL_PATTERN: Lazy<Regex> = Lazy::new(|| {
    Regex::new(r"\\!\[([^\]]*)\]\((https?://[^)]+(?:reaction|Media)[^)]+)\)").unwrap()
});

/// IPv4 address pattern
static IPV4_PATTERN: Lazy<Regex> =
    Lazy::new(|| Regex::new(r"^\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}$").unwrap());

/// URL validator with SSRF protection
pub struct UrlValidator {
    timeout: Duration,
    max_retries: u32,
}

impl Default for UrlValidator {
    fn default() -> Self {
        Self::new(5, 3)
    }
}

impl UrlValidator {
    /// Create a new URL validator
    ///
    /// # Arguments
    /// * `timeout_secs` - Timeout for HTTP requests in seconds
    /// * `max_retries` - Maximum number of retry attempts
    pub fn new(timeout_secs: u64, max_retries: u32) -> Self {
        Self {
            timeout: Duration::from_secs(timeout_secs),
            max_retries,
        }
    }

    /// Extract reaction image URLs from text
    ///
    /// Looks for markdown image syntax with "reaction" or "Media" in the URL.
    pub fn extract_reaction_urls(text: &str) -> Vec<String> {
        let mut urls = Vec::new();

        // Extract from regular markdown images
        for cap in URL_PATTERN.captures_iter(text) {
            if let Some(url) = cap.get(2) {
                urls.push(url.as_str().to_string());
            }
        }

        // Extract from escaped markdown images
        for cap in ESCAPED_URL_PATTERN.captures_iter(text) {
            if let Some(url) = cap.get(2) {
                let url_str = url.as_str().to_string();
                if !urls.contains(&url_str) {
                    urls.push(url_str);
                }
            }
        }

        urls
    }

    /// Validate URL for SSRF protection (no network request)
    pub fn validate_ssrf(&self, url: &str) -> Result<()> {
        let parsed = url::Url::parse(url).map_err(|_| Error::InvalidUrl {
            url: url.to_string(),
            reason: "Failed to parse URL".to_string(),
        })?;

        // Only allow HTTPS
        if parsed.scheme() != "https" {
            return Err(Error::InvalidUrl {
                url: url.to_string(),
                reason: format!("Only HTTPS allowed, got: {}", parsed.scheme()),
            });
        }

        let hostname = parsed.host_str().ok_or_else(|| Error::InvalidUrl {
            url: url.to_string(),
            reason: "No hostname in URL".to_string(),
        })?;

        // Check whitelist (case-insensitive)
        if !ALLOWED_HOSTNAMES
            .iter()
            .any(|h| hostname.eq_ignore_ascii_case(h))
        {
            return Err(Error::InvalidUrl {
                url: url.to_string(),
                reason: format!("Hostname not in whitelist: {}", hostname),
            });
        }

        // Block direct IP addresses (IPv4)
        if IPV4_PATTERN.is_match(hostname) {
            return Err(Error::InvalidUrl {
                url: url.to_string(),
                reason: "Direct IP addresses not allowed".to_string(),
            });
        }

        // Block IPv6 addresses (contain colons)
        if hostname.contains(':') || hostname.starts_with('[') {
            return Err(Error::InvalidUrl {
                url: url.to_string(),
                reason: "IPv6 addresses not allowed".to_string(),
            });
        }

        // Validate extension for GitHub raw URLs
        if hostname.eq_ignore_ascii_case("raw.githubusercontent.com") {
            let path = parsed.path();
            let ext = path.rsplit('.').next().unwrap_or("");

            if !ALLOWED_EXTENSIONS
                .iter()
                .any(|e| ext.eq_ignore_ascii_case(e))
            {
                return Err(Error::InvalidUrl {
                    url: url.to_string(),
                    reason: format!("Invalid image extension: {}", ext),
                });
            }
        }

        Ok(())
    }

    /// Validate URL exists with HTTP HEAD request and retries
    ///
    /// Fails closed: if URL cannot be verified after retries, it's rejected.
    pub fn validate_exists(&self, url: &str) -> Result<()> {
        // First validate SSRF
        self.validate_ssrf(url)?;

        let mut last_error = None;

        for attempt in 0..self.max_retries {
            match ureq::head(url)
                .timeout(self.timeout)
                .set("User-Agent", "gh-validator/1.0")
                .call()
            {
                Ok(response) => {
                    if response.status() == 200 {
                        return Ok(());
                    }
                    return Err(Error::InvalidUrl {
                        url: url.to_string(),
                        reason: format!("HTTP status {}", response.status()),
                    });
                }
                Err(ureq::Error::Status(404, _)) => {
                    // 404 is definitive - no retry
                    return Err(Error::InvalidUrl {
                        url: url.to_string(),
                        reason: "Image not found (404)".to_string(),
                    });
                }
                Err(ureq::Error::Status(code, _)) if (400..500).contains(&code) => {
                    // Other 4xx errors are definitive
                    return Err(Error::InvalidUrl {
                        url: url.to_string(),
                        reason: format!("HTTP error {}", code),
                    });
                }
                Err(e) => {
                    // 5xx or network errors - retry
                    last_error = Some(e.to_string());
                    if attempt < self.max_retries - 1 {
                        std::thread::sleep(Duration::from_millis(500));
                    }
                }
            }
        }

        // FAIL CLOSED: Could not verify URL after retries
        Err(Error::NetworkError {
            url: url.to_string(),
            details: last_error.unwrap_or_else(|| "Unknown error".to_string()),
        })
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_extract_reaction_urls() {
        let text = r#"
            Check out this ![Reaction](https://raw.githubusercontent.com/AndrewAltimit/Media/main/reaction/miku.png)
            And this ![alt](https://example.com/Media/image.gif)
        "#;

        let urls = UrlValidator::extract_reaction_urls(text);
        assert_eq!(urls.len(), 2);
        assert!(urls[0].contains("raw.githubusercontent.com"));
    }

    #[test]
    fn test_ssrf_blocks_non_https() {
        let validator = UrlValidator::default();
        let result = validator.validate_ssrf("http://raw.githubusercontent.com/test.png");
        assert!(result.is_err());
        assert!(result.unwrap_err().to_string().contains("HTTPS"));
    }

    #[test]
    fn test_ssrf_blocks_non_whitelisted_host() {
        let validator = UrlValidator::default();
        let result = validator.validate_ssrf("https://evil.com/image.png");
        assert!(result.is_err());
        assert!(result.unwrap_err().to_string().contains("whitelist"));
    }

    #[test]
    fn test_ssrf_blocks_ip_address() {
        let validator = UrlValidator::default();
        let result = validator.validate_ssrf("https://192.168.1.1/image.png");
        assert!(result.is_err());
        assert!(result.unwrap_err().to_string().contains("IP address"));
    }

    #[test]
    fn test_ssrf_blocks_ipv6() {
        let validator = UrlValidator::default();
        let result = validator.validate_ssrf("https://[::1]/image.png");
        assert!(result.is_err());
        assert!(result.unwrap_err().to_string().contains("IPv6"));
    }

    #[test]
    fn test_ssrf_allows_valid_url() {
        let validator = UrlValidator::default();
        let result = validator.validate_ssrf(
            "https://raw.githubusercontent.com/AndrewAltimit/Media/main/reaction/test.png",
        );
        assert!(result.is_ok());
    }

    #[test]
    fn test_ssrf_blocks_invalid_extension() {
        let validator = UrlValidator::default();
        let result = validator.validate_ssrf(
            "https://raw.githubusercontent.com/user/repo/main/file.exe",
        );
        assert!(result.is_err());
        assert!(result.unwrap_err().to_string().contains("extension"));
    }

    #[test]
    fn test_extract_no_urls() {
        let text = "Plain text without any reaction images";
        let urls = UrlValidator::extract_reaction_urls(text);
        assert!(urls.is_empty());
    }

    #[test]
    fn test_extract_non_reaction_url() {
        let text = "![Image](https://example.com/normal/image.png)";
        let urls = UrlValidator::extract_reaction_urls(text);
        assert!(urls.is_empty()); // "reaction" or "Media" not in URL
    }
}
