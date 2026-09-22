//! Byte-signature patterns with wildcards (`48 8B 05 ?? ?? ?? ??`).

/// Maximum pattern length in bytes (keeps scans and chunk overlaps bounded).
pub const MAX_PATTERN_LEN: usize = 1024;

/// A parsed byte pattern. `None` entries are wildcards.
#[derive(Debug, Clone, PartialEq, Eq)]
pub struct Pattern {
    bytes: Vec<Option<u8>>,
    /// Index of the first non-wildcard byte, used as the `memchr` anchor.
    anchor: usize,
}

impl Pattern {
    /// Parse a pattern string.
    ///
    /// Accepted token forms (whitespace separated, case-insensitive):
    /// - `8B` a literal byte
    /// - `??`, `?`, `**` a wildcard byte
    /// - `488B05` several literal bytes without spaces (even number of hex digits)
    ///
    /// The pattern must contain at least one literal byte: an all-wildcard (or
    /// empty) pattern would match every address.
    pub fn parse(s: &str) -> Result<Self, String> {
        let mut bytes = Vec::new();
        for token in s.split_whitespace() {
            match token {
                "?" | "??" | "*" | "**" => bytes.push(None),
                _ => {
                    if token.len() % 2 != 0 || !token.chars().all(|c| c.is_ascii_hexdigit()) {
                        return Err(format!(
                            "invalid pattern token '{}': expected hex bytes like '8B' or a '??' wildcard",
                            token
                        ));
                    }
                    for i in (0..token.len()).step_by(2) {
                        let b = u8::from_str_radix(&token[i..i + 2], 16)
                            .map_err(|_| format!("invalid pattern byte '{}'", &token[i..i + 2]))?;
                        bytes.push(Some(b));
                    }
                },
            }
            if bytes.len() > MAX_PATTERN_LEN {
                return Err(format!(
                    "pattern is too long (max {} bytes)",
                    MAX_PATTERN_LEN
                ));
            }
        }
        Self::new(bytes)
    }

    /// Build a pattern that matches `bytes` exactly.
    pub fn exact(bytes: &[u8]) -> Result<Self, String> {
        Self::new(bytes.iter().copied().map(Some).collect())
    }

    fn new(bytes: Vec<Option<u8>>) -> Result<Self, String> {
        if bytes.is_empty() {
            return Err("pattern is empty".into());
        }
        let anchor = bytes
            .iter()
            .position(Option::is_some)
            .ok_or_else(|| "pattern must contain at least one non-wildcard byte".to_string())?;
        Ok(Self { bytes, anchor })
    }

    /// Pattern length in bytes (including wildcards).
    pub fn len(&self) -> usize {
        self.bytes.len()
    }

    /// Whether the pattern matches `data` starting at `pos`.
    pub fn matches_at(&self, data: &[u8], pos: usize) -> bool {
        match data.get(pos..pos.saturating_add(self.bytes.len())) {
            Some(window) => self
                .bytes
                .iter()
                .zip(window)
                .all(|(p, d)| p.is_none_or(|b| b == *d)),
            None => false,
        }
    }

    /// Call `on_match(pos)` for every match that starts before `limit` and lies
    /// fully inside `data`. Stop early when `on_match` returns `false`.
    ///
    /// Uses `memchr` on the first literal byte, so scanning large buffers is
    /// close to memory bandwidth for typical signatures.
    pub fn find_each(&self, data: &[u8], limit: usize, mut on_match: impl FnMut(usize) -> bool) {
        let len = self.bytes.len();
        if data.len() < len {
            return;
        }
        let last_start = (data.len() - len).min(limit.saturating_sub(1));
        if limit == 0 {
            return;
        }
        let anchor_byte = match self.bytes[self.anchor] {
            Some(b) => b,
            None => return, // unreachable: `new` guarantees a literal anchor
        };
        // Candidate starts are at (anchor hit - anchor); search the window of
        // anchor positions that correspond to starts in 0..=last_start.
        let window = &data[self.anchor..=last_start + self.anchor];
        for hit in memchr::memchr_iter(anchor_byte, window) {
            let pos = hit;
            if self.matches_at(data, pos) && !on_match(pos) {
                return;
            }
        }
    }
}

impl std::fmt::Display for Pattern {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        for (i, b) in self.bytes.iter().enumerate() {
            if i > 0 {
                f.write_str(" ")?;
            }
            match b {
                Some(b) => write!(f, "{:02X}", b)?,
                None => f.write_str("??")?,
            }
        }
        Ok(())
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    fn all_matches(p: &Pattern, data: &[u8], limit: usize) -> Vec<usize> {
        let mut v = Vec::new();
        p.find_each(data, limit, |pos| {
            v.push(pos);
            true
        });
        v
    }

    #[test]
    fn parse_forms() {
        let p = Pattern::parse("48 8b 05 ?? ? ** 488B").unwrap();
        assert_eq!(p.len(), 8);
        assert_eq!(p.to_string(), "48 8B 05 ?? ?? ?? 48 8B");
    }

    #[test]
    fn parse_rejects_bad_input() {
        assert!(Pattern::parse("").is_err());
        assert!(Pattern::parse("   ").is_err());
        assert!(
            Pattern::parse("?? ??").is_err(),
            "all-wildcard must be rejected"
        );
        assert!(Pattern::parse("4G").is_err());
        assert!(Pattern::parse("123").is_err());
        assert!(Pattern::parse("0x48").is_err());
        let long = "AA ".repeat(MAX_PATTERN_LEN + 1);
        assert!(Pattern::parse(&long).is_err());
    }

    #[test]
    fn finds_with_wildcards() {
        let data = [
            0x00, 0x48, 0x8B, 0x05, 0x11, 0x22, 0x48, 0x8B, 0x05, 0x33, 0x44,
        ];
        let p = Pattern::parse("48 8B 05 ?? ??").unwrap();
        assert_eq!(all_matches(&p, &data, usize::MAX), vec![1, 6]);
    }

    #[test]
    fn leading_wildcard_uses_later_anchor() {
        let data = [0x01, 0x02, 0xAA, 0x03, 0xAA];
        let p = Pattern::parse("?? AA").unwrap();
        assert_eq!(all_matches(&p, &data, usize::MAX), vec![1, 3]);
    }

    #[test]
    fn respects_limit_and_bounds() {
        let data = [0xAA; 8];
        let p = Pattern::parse("AA AA").unwrap();
        assert_eq!(
            all_matches(&p, &data, usize::MAX),
            vec![0, 1, 2, 3, 4, 5, 6]
        );
        // Only starts < limit are reported.
        assert_eq!(all_matches(&p, &data, 3), vec![0, 1, 2]);
        assert!(all_matches(&p, &data, 0).is_empty());
        // Data shorter than pattern: no matches, no panic.
        assert!(all_matches(&p, &[0xAA], usize::MAX).is_empty());
    }

    #[test]
    fn early_stop() {
        let data = [0xAA; 8];
        let p = Pattern::exact(&[0xAA]).unwrap();
        let mut n = 0;
        p.find_each(&data, usize::MAX, |_| {
            n += 1;
            n < 2
        });
        assert_eq!(n, 2);
    }
}
