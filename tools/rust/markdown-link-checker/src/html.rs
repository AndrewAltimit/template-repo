//! Scanning of raw HTML embedded in markdown.
//!
//! GitHub renders raw HTML, so `<a href>`, `<img src>` and friends are real
//! links, and `id`/`name` attributes are valid fragment targets. HTML comments
//! are never rendered: their contents are skipped, except for the
//! `md-link-checker-*` control markers.

use std::sync::OnceLock;

use regex::Regex;

/// Inline control marker found inside an HTML comment.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum Marker {
    /// `<!-- md-link-checker-disable -->`: skip links until `enable`.
    Disable,
    /// `<!-- md-link-checker-enable -->`: resume checking.
    Enable,
    /// `<!-- md-link-checker-disable-next-line -->`: skip the next line.
    DisableNextLine,
}

/// Everything of interest found in a run of HTML.
#[derive(Debug, Default)]
pub struct HtmlFindings {
    /// `(destination, source byte offset)` for each `href`/`src` attribute.
    pub links: Vec<(String, usize)>,
    /// Values of `id` and `name` attributes (valid fragment targets).
    pub anchors: Vec<String>,
    /// Control markers with their source byte offsets.
    pub markers: Vec<(Marker, usize)>,
}

/// A piece of HTML text and the byte offset in the markdown source where it
/// starts. HTML blocks arrive from the parser as one chunk per line.
pub type Chunk = (String, usize);

fn link_attr_re() -> &'static Regex {
    static RE: OnceLock<Regex> = OnceLock::new();
    RE.get_or_init(|| {
        Regex::new(r#"(?i)(?:^|[\s"'])(?:href|src)\s*=\s*(?:"([^"]*)"|'([^']*)'|([^\s"'<>`]+))"#)
            .expect("valid regex")
    })
}

fn anchor_attr_re() -> &'static Regex {
    static RE: OnceLock<Regex> = OnceLock::new();
    RE.get_or_init(|| {
        Regex::new(r#"(?i)(?:^|[\s"'])(?:id|name)\s*=\s*(?:"([^"]*)"|'([^']*)'|([^\s"'<>`]+))"#)
            .expect("valid regex")
    })
}

/// Scan a contiguous run of HTML chunks (one HTML block, or a single inline
/// HTML fragment).
pub fn scan(chunks: &[Chunk]) -> HtmlFindings {
    let mut findings = HtmlFindings::default();
    if chunks.is_empty() {
        return findings;
    }

    // Concatenate, remembering where each chunk starts in both coordinate
    // systems so matches can be mapped back to source offsets.
    let mut text = String::new();
    let mut starts: Vec<(usize, usize)> = Vec::with_capacity(chunks.len());
    for (chunk, src_offset) in chunks {
        starts.push((text.len(), *src_offset));
        text.push_str(chunk);
    }
    let to_source = |pos: usize| -> usize {
        let idx = starts
            .partition_point(|&(start, _)| start <= pos)
            .saturating_sub(1);
        let (start, src) = starts[idx];
        src + (pos - start)
    };

    let visible = blank_comments(&text, |body, pos| {
        if let Some(marker) = parse_marker(body) {
            findings.markers.push((marker, to_source(pos)));
        }
    });

    for caps in link_attr_re().captures_iter(&visible) {
        if let Some(m) = caps.get(1).or_else(|| caps.get(2)).or_else(|| caps.get(3)) {
            let value = decode_entities(m.as_str().trim());
            if !value.is_empty() {
                findings.links.push((value, to_source(m.start())));
            }
        }
    }
    for caps in anchor_attr_re().captures_iter(&visible) {
        if let Some(m) = caps.get(1).or_else(|| caps.get(2)).or_else(|| caps.get(3)) {
            let value = decode_entities(m.as_str().trim());
            if !value.is_empty() {
                findings.anchors.push(value);
            }
        }
    }
    findings
}

/// Replace every `<!-- ... -->` comment with spaces (preserving byte offsets)
/// and report each comment body with its start position.
fn blank_comments(text: &str, mut on_comment: impl FnMut(&str, usize)) -> String {
    let mut out = String::with_capacity(text.len());
    let mut rest = 0;
    while let Some(open) = text[rest..].find("<!--") {
        let open = rest + open;
        out.push_str(&text[rest..open]);
        let body_start = open + 4;
        let (body_end, close_end) = match text[body_start..].find("-->") {
            Some(i) => (body_start + i, body_start + i + 3),
            None => (text.len(), text.len()),
        };
        on_comment(&text[body_start..body_end], open);
        out.extend(std::iter::repeat_n(' ', close_end - open));
        rest = close_end;
    }
    out.push_str(&text[rest..]);
    out
}

fn parse_marker(comment_body: &str) -> Option<Marker> {
    match comment_body.trim() {
        "md-link-checker-disable-next-line" => Some(Marker::DisableNextLine),
        "md-link-checker-disable" => Some(Marker::Disable),
        "md-link-checker-enable" => Some(Marker::Enable),
        _ => None,
    }
}

/// Decode the handful of HTML entities that plausibly appear in URLs.
fn decode_entities(value: &str) -> String {
    if !value.contains('&') {
        return value.to_string();
    }
    value
        .replace("&amp;", "&")
        .replace("&quot;", "\"")
        .replace("&#39;", "'")
        .replace("&lt;", "<")
        .replace("&gt;", ">")
}

#[cfg(test)]
mod tests {
    use super::*;

    fn one(s: &str) -> HtmlFindings {
        scan(&[(s.to_string(), 100)])
    }

    #[test]
    fn finds_href_and_src_with_offsets() {
        let f = one(r#"<a href="docs/a.md">x</a> <img alt='y' src='img.png'>"#);
        let urls: Vec<_> = f.links.iter().map(|(u, _)| u.as_str()).collect();
        assert_eq!(urls, ["docs/a.md", "img.png"]);
        assert_eq!(f.links[0].1, 100 + 9);
    }

    #[test]
    fn unquoted_and_entity_values() {
        let f = one("<a href=https://x.test/?a=1&amp;b=2>x</a>");
        assert_eq!(f.links[0].0, "https://x.test/?a=1&b=2");
    }

    #[test]
    fn ignores_lookalike_attributes() {
        let f = one(r#"<img data-src="lazy.png" srcset="a.png 2x">"#);
        assert!(f.links.is_empty(), "{:?}", f.links);
    }

    #[test]
    fn collects_id_and_name_anchors() {
        let f = one(r#"<a name="legacy-anchor"></a><div id='custom'>"#);
        assert_eq!(f.anchors, ["legacy-anchor", "custom"]);
    }

    #[test]
    fn skips_comments_and_reads_markers() {
        let chunks = vec![
            ("<!-- md-link-checker-disable -->\n".to_string(), 0),
            ("<!--\n".to_string(), 40),
            ("<a href=\"hidden.md\">\n".to_string(), 45),
            ("-->\n".to_string(), 70),
            ("<a href=\"shown.md\">\n".to_string(), 74),
        ];
        let f = scan(&chunks);
        assert_eq!(f.markers, [(Marker::Disable, 0)]);
        assert_eq!(f.links, [("shown.md".to_string(), 74 + 9)]);
    }

    #[test]
    fn unterminated_comment_hides_rest() {
        let f = one("<!-- <a href=\"x.md\">");
        assert!(f.links.is_empty());
    }
}
