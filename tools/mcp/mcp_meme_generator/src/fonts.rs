//! Caption font selection.
//!
//! Resolution order:
//! 1. An explicit font file (`--font` / `MCP_MEME_FONT`). If it is given but
//!    cannot be loaded, that is an error rather than a silent fallback.
//! 2. Liberation Sans Bold from the system (installed in the Docker image via
//!    `fonts-liberation`).
//! 3. The DejaVu Sans Bold font embedded in the binary, so rendering always
//!    works even on a bare system.

use ab_glyph::FontArc;
use std::path::Path;
use tracing::{info, warn};

/// DejaVu Sans Bold (full font, ~700 KB) compiled into the binary.
pub const EMBEDDED_FONT: &[u8] = include_bytes!("../assets/DejaVuSans-Bold.ttf");

/// System fonts tried (in order) when no explicit font is configured.
pub const SYSTEM_FONT_CANDIDATES: &[&str] =
    &["/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf"];

/// A parsed font plus a human-readable description of where it came from.
#[derive(Clone)]
pub struct LoadedFont {
    /// Parsed font (cheaply cloneable).
    pub font: FontArc,
    /// Path or `"embedded:DejaVuSans-Bold"`.
    pub source: String,
}

fn load_file(path: &Path) -> Result<FontArc, String> {
    let bytes =
        std::fs::read(path).map_err(|e| format!("cannot read font {}: {e}", path.display()))?;
    FontArc::try_from_vec(bytes).map_err(|e| format!("cannot parse font {}: {e}", path.display()))
}

/// Load the caption font. Only fails when an explicit font path is unusable.
pub fn load_font(explicit: Option<&Path>) -> Result<LoadedFont, String> {
    if let Some(path) = explicit {
        let font = load_file(path)?;
        info!("Using configured font: {}", path.display());
        return Ok(LoadedFont {
            font,
            source: path.display().to_string(),
        });
    }

    for candidate in SYSTEM_FONT_CANDIDATES {
        let path = Path::new(candidate);
        if !path.is_file() {
            continue;
        }
        match load_file(path) {
            Ok(font) => {
                info!("Using system font: {candidate}");
                return Ok(LoadedFont {
                    font,
                    source: (*candidate).to_string(),
                });
            },
            Err(e) => warn!("{e}; trying next font"),
        }
    }

    info!("Using embedded DejaVu Sans Bold font");
    Ok(embedded())
}

/// The embedded fallback font.
pub fn embedded() -> LoadedFont {
    LoadedFont {
        // The embedded bytes are a known-good TTF (covered by tests); if they
        // ever failed to parse that would be a build defect, not user input.
        font: FontArc::try_from_slice(EMBEDDED_FONT)
            .unwrap_or_else(|e| panic!("embedded font is corrupt: {e}")),
        source: "embedded:DejaVuSans-Bold".to_string(),
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn embedded_font_parses() {
        let f = embedded();
        assert_eq!(f.source, "embedded:DejaVuSans-Bold");
    }

    #[test]
    fn explicit_missing_font_is_an_error() {
        let err = match load_font(Some(Path::new("/definitely/not/here.ttf"))) {
            Err(e) => e,
            Ok(_) => panic!("expected error"),
        };
        assert!(err.contains("cannot read font"));
    }

    #[test]
    fn explicit_non_font_file_is_an_error() {
        let dir = tempfile::tempdir().unwrap();
        let path = dir.path().join("bad.ttf");
        std::fs::write(&path, b"not a font").unwrap();
        let err = match load_font(Some(&path)) {
            Err(e) => e,
            Ok(_) => panic!("expected error"),
        };
        assert!(err.contains("cannot parse font"));
    }

    #[test]
    fn default_resolution_always_succeeds() {
        assert!(load_font(None).is_ok());
    }
}
