//! URL validation with SSRF protection
//!
//! Validates reaction image URLs to ensure:
//! 1. Only whitelisted hostnames are allowed (SSRF protection)
//! 2. No direct IP addresses (IPv4/IPv6)
//! 3. Valid image extensions
//! 4. URLs actually exist (HTTP HEAD request with retries)
//! 5. No embedded credentials or explicit ports
//!
//! Redirects are followed manually (at most [`MAX_REDIRECTS`] hops) and every
//! hop must stay on a GitHub-owned host, so an open redirect on an allowed
//! host cannot turn the check into a request to an arbitrary server.

use crate::error::{Error, Result};
use regex::Regex;
use std::sync::LazyLock;
use std::time::Duration;

/// Whitelisted hostnames for reaction images
const ALLOWED_HOSTNAMES: &[&str] = &[
    "raw.githubusercontent.com",
    "github.com",
    "user-images.githubusercontent.com",
    "camo.githubusercontent.com",
];

/// Additional GitHub CDN hosts that allowed URLs may redirect to.
const REDIRECT_HOSTNAMES: &[&str] = &[
    "objects.githubusercontent.com",
    "private-user-images.githubusercontent.com",
    "media.githubusercontent.com",
];

/// Maximum redirect hops followed while validating a URL.
pub const MAX_REDIRECTS: usize = 3;

/// Valid image file extensions
const ALLOWED_EXTENSIONS: &[&str] = &["png", "jpg", "jpeg", "gif", "webp", "svg"];

/// Regex to extract reaction URLs from markdown. Also matches the escaped
/// `\![...](...)` form, since `![` is a suffix of it.
static URL_PATTERN: LazyLock<Regex> = LazyLock::new(|| {
    Regex::new(r"!\[([^\]]*)\]\((https?://[^)\s]+(?:reaction|Media)[^)\s]*)").expect("static regex")
});

/// Collapses blank-line runs left behind by stripped images.
static BLANK_RUNS: LazyLock<Regex> =
    LazyLock::new(|| Regex::new(r"\n\s*\n\s*\n").expect("static regex"));

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
        let mut urls: Vec<String> = Vec::new();
        for cap in URL_PATTERN.captures_iter(text) {
            if let Some(url) = cap.get(2) {
                let url = url.as_str().to_string();
                if !urls.contains(&url) {
                    urls.push(url);
                }
            }
        }
        urls
    }

    /// Validate URL for SSRF protection (no network request).
    pub fn validate_ssrf(&self, url: &str) -> Result<()> {
        Self::check_url(url, ALLOWED_HOSTNAMES)
    }

    fn check_url(url: &str, hosts: &[&str]) -> Result<()> {
        let invalid = |reason: String| Error::InvalidUrl {
            url: url.to_string(),
            reason,
        };
        let parsed =
            url::Url::parse(url).map_err(|e| invalid(format!("Failed to parse URL: {e}")))?;

        if parsed.scheme() != "https" {
            return Err(invalid(format!(
                "Only HTTPS allowed, got: {}",
                parsed.scheme()
            )));
        }
        if !parsed.username().is_empty() || parsed.password().is_some() {
            return Err(invalid("Credentials in URLs are not allowed".to_string()));
        }
        // Only DNS names are accepted: IP literals never match the list.
        let hostname = match parsed.host() {
            Some(url::Host::Domain(d)) => d,
            Some(_) => {
                return Err(invalid("Hostname not in whitelist: IP address".to_string()));
            },
            None => return Err(invalid("No hostname in URL".to_string())),
        };
        if !hosts.iter().any(|h| hostname.eq_ignore_ascii_case(h)) {
            return Err(invalid(format!("Hostname not in whitelist: {hostname}")));
        }
        if parsed.port().is_some() {
            return Err(invalid("Explicit ports are not allowed".to_string()));
        }
        if hostname.eq_ignore_ascii_case("raw.githubusercontent.com") {
            let ext = parsed.path().rsplit('.').next().unwrap_or("");
            if !ALLOWED_EXTENSIONS
                .iter()
                .any(|e| ext.eq_ignore_ascii_case(e))
            {
                return Err(invalid(format!("Invalid image extension: {ext}")));
            }
        }
        Ok(())
    }

    /// Validate that the URL exists (HTTP HEAD, retries on network/5xx
    /// errors, redirects followed within GitHub hosts only).
    ///
    /// Fails closed: if the URL cannot be verified it is rejected.
    pub fn validate_exists(&self, url: &str) -> Result<()> {
        self.validate_ssrf(url)?;
        let agent = ureq::AgentBuilder::new()
            .redirects(0)
            .timeout(self.timeout)
            .user_agent("gh-validator/0.2")
            .build();

        let mut current = url.to_string();
        for _ in 0..=MAX_REDIRECTS {
            let Some(location) = self.head(&agent, &current)? else {
                return Ok(());
            };
            let next = url::Url::parse(&current)
                .and_then(|base| base.join(&location))
                .map_err(|e| Error::InvalidUrl {
                    url: url.to_string(),
                    reason: format!("Bad redirect location '{location}': {e}"),
                })?;
            let hosts: Vec<&str> = ALLOWED_HOSTNAMES
                .iter()
                .chain(REDIRECT_HOSTNAMES)
                .copied()
                .collect();
            Self::check_url(next.as_str(), &hosts).map_err(|e| Error::InvalidUrl {
                url: url.to_string(),
                reason: format!("Redirect rejected: {e}"),
            })?;
            current = next.to_string();
        }
        Err(Error::InvalidUrl {
            url: url.to_string(),
            reason: format!("More than {MAX_REDIRECTS} redirects"),
        })
    }

    /// One HEAD request with retries. `Ok(None)` means 200, `Ok(Some(loc))`
    /// a redirect to `loc`.
    fn head(&self, agent: &ureq::Agent, url: &str) -> Result<Option<String>> {
        let mut last_error = String::from("Unknown error");
        let attempts = self.max_retries.max(1);
        for attempt in 0..attempts {
            match agent.head(url).call() {
                Ok(response) => {
                    let status = response.status();
                    if status == 200 {
                        return Ok(None);
                    }
                    if (300..400).contains(&status) {
                        return match response.header("location") {
                            Some(loc) => Ok(Some(loc.to_string())),
                            None => Err(Error::InvalidUrl {
                                url: url.to_string(),
                                reason: format!("HTTP {status} without Location"),
                            }),
                        };
                    }
                    return Err(Error::InvalidUrl {
                        url: url.to_string(),
                        reason: format!("HTTP status {status}"),
                    });
                },
                Err(ureq::Error::Status(404, _)) => {
                    return Err(Error::InvalidUrl {
                        url: url.to_string(),
                        reason: "Image not found (404)".to_string(),
                    });
                },
                Err(ureq::Error::Status(code, _)) if (400..500).contains(&code) => {
                    return Err(Error::InvalidUrl {
                        url: url.to_string(),
                        reason: format!("HTTP error {code}"),
                    });
                },
                Err(e) => {
                    last_error = e.to_string();
                    if attempt + 1 < attempts {
                        std::thread::sleep(Duration::from_millis(500));
                    }
                },
            }
        }
        Err(Error::NetworkError {
            url: url.to_string(),
            details: last_error,
        })
    }

    /// Find invalid URLs in content and return them with their error reasons
    ///
    /// Returns a vector of (url, reason) tuples for invalid URLs.
    pub fn find_invalid_urls(&self, content: &str) -> Vec<(String, String)> {
        let urls = Self::extract_reaction_urls(content);
        let mut invalid = Vec::new();
        let mut seen = std::collections::HashSet::new();

        for url in urls {
            // Skip duplicate URLs to avoid redundant network requests
            if !seen.insert(url.clone()) {
                continue;
            }
            if let Err(e) = self.validate_exists(&url) {
                invalid.push((url, e.to_string()));
            }
        }

        invalid
    }

    /// Strip invalid reaction image URLs from content
    ///
    /// Returns the modified content with invalid images removed, plus a list
    /// of (url, reason) tuples for the removed images.
    pub fn strip_invalid_images(&self, content: &str) -> (String, Vec<(String, String)>) {
        let invalid_urls = self.find_invalid_urls(content);

        if invalid_urls.is_empty() {
            return (content.to_string(), vec![]);
        }

        let mut result = content.to_string();

        for (url, _) in &invalid_urls {
            // Remove the full markdown image syntax: ![...](url)
            // Need to escape special regex chars in URL
            let escaped_url = regex::escape(url);

            // Pattern for ![alt text](url) or ![alt text](url "title") - captures the whole thing
            // Optional title can be quoted with " or '
            let pattern = format!(r#"!\[[^\]]*\]\({}\s*(?:["'][^"']*["'])?\)"#, escaped_url);
            if let Ok(re) = Regex::new(&pattern) {
                result = re.replace_all(&result, "").to_string();
            }

            // Also handle escaped variant \![alt text](url) or \![alt text](url "title")
            let escaped_pattern =
                format!(r#"\\!\[[^\]]*\]\({}\s*(?:["'][^"']*["'])?\)"#, escaped_url);
            if let Ok(re) = Regex::new(&escaped_pattern) {
                result = re.replace_all(&result, "").to_string();
            }
        }

        // Clean up blank-line runs left by removed images
        result = BLANK_RUNS.replace_all(&result, "\n\n").into_owned();

        // Trim trailing whitespace
        result = result.trim_end().to_string();

        (result, invalid_urls)
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
        // IP addresses are blocked by the whitelist check (no IPs in whitelist)
        assert!(result.unwrap_err().to_string().contains("whitelist"));
    }

    #[test]
    fn test_ssrf_blocks_ipv6() {
        let validator = UrlValidator::default();
        let result = validator.validate_ssrf("https://[::1]/image.png");
        assert!(result.is_err());
        // IPv6 addresses are blocked by the whitelist check (no IPs in whitelist)
        assert!(result.unwrap_err().to_string().contains("whitelist"));
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
    fn test_ssrf_blocks_credentials_and_ports() {
        let validator = UrlValidator::default();
        let err = validator
            .validate_ssrf("https://user:pw@raw.githubusercontent.com/a/b/c.png")
            .unwrap_err();
        assert!(err.to_string().contains("Credentials"));
        // Userinfo trick: the real host is evil.com.
        assert!(
            validator
                .validate_ssrf("https://raw.githubusercontent.com@evil.com/a.png")
                .is_err()
        );
        assert!(
            validator
                .validate_ssrf("https://raw.githubusercontent.com:8443/a/b/c.png")
                .is_err()
        );
    }

    #[test]
    fn test_escaped_and_duplicate_urls_extracted_once() {
        let url = "https://raw.githubusercontent.com/AndrewAltimit/Media/main/reaction/a.png";
        let text = format!("![Reaction]({url}) and \\![Reaction]({url})");
        assert_eq!(
            UrlValidator::extract_reaction_urls(&text),
            vec![url.to_string()]
        );
    }

    #[test]
    fn test_ssrf_blocks_invalid_extension() {
        let validator = UrlValidator::default();
        let result =
            validator.validate_ssrf("https://raw.githubusercontent.com/user/repo/main/file.exe");
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

    #[test]
    fn test_strip_invalid_images_with_title() {
        let validator = UrlValidator::default();

        // Test stripping image with title attribute - use a non-whitelisted host
        // to trigger validation failure
        let content = r#"Some text
![Reaction](https://invalid.example.com/reaction/test.png "My title")
More text"#;

        let (result, invalid_urls) = validator.strip_invalid_images(content);

        // The invalid URL should be stripped along with its title
        assert!(!result.contains("invalid.example.com"));
        assert!(!result.contains("My title"));
        assert!(result.contains("Some text"));
        assert!(result.contains("More text"));
        assert_eq!(invalid_urls.len(), 1);
    }
}
