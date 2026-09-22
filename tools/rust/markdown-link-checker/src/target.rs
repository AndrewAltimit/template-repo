//! Classification of link destinations.

use percent_encoding::percent_decode_str;

/// What a link destination points at.
#[derive(Debug, Clone, PartialEq, Eq)]
pub enum LinkTarget {
    /// `#fragment` (or `?query` only) within the current document.
    SamePage {
        /// Percent-decoded fragment, possibly empty.
        anchor: String,
    },
    /// A path on disk, relative to the document or (with a leading `/`) to
    /// the repository root.
    Local {
        /// Percent-decoded path with query and fragment removed.
        path: String,
        /// Percent-decoded fragment, if any.
        anchor: Option<String>,
    },
    /// An `http(s)` URL (protocol-relative `//host` is upgraded to https).
    External {
        /// URL to request.
        url: String,
    },
    /// Some other scheme (`mailto:`, `data:`, `ssh://`, ...) that cannot be
    /// validated. These are skipped and not counted.
    Unsupported,
}

/// Classify a raw link destination.
pub fn classify(link: &str) -> LinkTarget {
    if let Some(rest) = link.strip_prefix("//") {
        return LinkTarget::External {
            url: format!("https://{rest}"),
        };
    }
    if let Some(scheme) = scheme_of(link) {
        return if scheme.eq_ignore_ascii_case("http") || scheme.eq_ignore_ascii_case("https") {
            LinkTarget::External {
                url: link.to_string(),
            }
        } else {
            LinkTarget::Unsupported
        };
    }

    let (before_fragment, fragment) = match link.split_once('#') {
        Some((p, f)) => (p, Some(decode(f))),
        None => (link, None),
    };
    let path = before_fragment
        .split_once('?')
        .map_or(before_fragment, |(p, _)| p);

    if path.is_empty() {
        return LinkTarget::SamePage {
            anchor: fragment.unwrap_or_default(),
        };
    }
    LinkTarget::Local {
        path: decode(path),
        anchor: fragment,
    }
}

/// Return the URI scheme if `link` starts with one (`scheme:`).
///
/// Single-letter schemes are rejected so Windows drive paths (`C:\...`) are
/// not mistaken for URLs.
fn scheme_of(link: &str) -> Option<&str> {
    let colon = link.find(':')?;
    let scheme = &link[..colon];
    let mut chars = scheme.chars();
    let first = chars.next()?;
    let valid = scheme.len() >= 2
        && first.is_ascii_alphabetic()
        && chars.all(|c| c.is_ascii_alphanumeric() || matches!(c, '+' | '-' | '.'));
    valid.then_some(scheme)
}

/// Remove the fragment from a URL (servers never see it; it only affects
/// deduplication).
pub fn strip_fragment(url: &str) -> &str {
    url.split_once('#').map_or(url, |(u, _)| u)
}

fn decode(s: &str) -> String {
    percent_decode_str(s).decode_utf8_lossy().into_owned()
}

#[cfg(test)]
mod tests {
    use super::*;

    fn local(path: &str, anchor: Option<&str>) -> LinkTarget {
        LinkTarget::Local {
            path: path.into(),
            anchor: anchor.map(Into::into),
        }
    }

    #[test]
    fn classifies() {
        assert_eq!(
            classify("#intro"),
            LinkTarget::SamePage {
                anchor: "intro".into()
            }
        );
        assert_eq!(classify("#"), LinkTarget::SamePage { anchor: "".into() });
        assert_eq!(classify("docs/a.md"), local("docs/a.md", None));
        assert_eq!(classify("a.md#Sec"), local("a.md", Some("Sec")));
        assert_eq!(classify("a.md?plain=1#L5"), local("a.md", Some("L5")));
        assert_eq!(classify("my%20file.md"), local("my file.md", None));
        assert_eq!(classify("a.md#caf%C3%A9"), local("a.md", Some("caf\u{e9}")));
        assert_eq!(classify("/root.md"), local("/root.md", None));
        assert_eq!(
            classify("https://x.test/a#b"),
            LinkTarget::External {
                url: "https://x.test/a#b".into()
            }
        );
        assert_eq!(
            classify("HTTP://x.test"),
            LinkTarget::External {
                url: "HTTP://x.test".into()
            }
        );
        assert_eq!(
            classify("//cdn.test/x.js"),
            LinkTarget::External {
                url: "https://cdn.test/x.js".into()
            }
        );
        for other in [
            "mailto:a@b.test",
            "data:image/png;base64,xx",
            "ssh://git@x",
            "vscode:extension/x",
        ] {
            assert_eq!(classify(other), LinkTarget::Unsupported, "{other}");
        }
        assert_eq!(classify("C:/x.md"), local("C:/x.md", None));
    }

    #[test]
    fn strips_fragment() {
        assert_eq!(strip_fragment("https://a.test/x#y"), "https://a.test/x");
        assert_eq!(strip_fragment("https://a.test/x"), "https://a.test/x");
    }
}
