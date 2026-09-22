//! Meme rendering, encoding, and saving.
//!
//! Everything here is synchronous and CPU/disk bound; the MCP tools call it
//! from `tokio::task::spawn_blocking` so it never stalls the async runtime.

use image::{ImageFormat, RgbImage, imageops::FilterType};
use serde::{Deserialize, Serialize};
use std::collections::BTreeMap;
use std::fs::OpenOptions;
use std::io::{Cursor, Write};
use std::path::{Path, PathBuf};
use std::sync::atomic::{AtomicU64, Ordering};

use crate::fonts::LoadedFont;
use crate::render::{
    self, AreaRect, FONT_SIZE_RANGE, Layout, MAX_TEXT_CHARS, TextStyle, fit_text, layout_at_size,
    parse_color, sanitize_text, unsupported_chars,
};
use crate::templates::{LoadedTemplate, TemplateStore};

/// Longest side of the preview image returned to the client.
pub const PREVIEW_MAX_SIDE: u32 = 512;

/// JPEG quality for full-size JPEG output.
const JPEG_QUALITY: u8 = 90;
/// JPEG quality for previews.
const PREVIEW_JPEG_QUALITY: u8 = 80;

/// Errors surfaced to the caller as tool errors.
#[derive(Debug, thiserror::Error)]
pub enum MemeError {
    /// Unknown template id.
    #[error("Template '{id}' not found. Available templates: {}", available.join(", "))]
    TemplateNotFound {
        /// Requested id.
        id: String,
        /// Valid ids.
        available: Vec<String>,
    },
    /// Caller-supplied arguments are invalid.
    #[error("{0}")]
    InvalidArgument(String),
    /// Template image could not be decoded.
    #[error("Failed to load template image {path}: {message}")]
    TemplateImage {
        /// Image path.
        path: String,
        /// Decoder error.
        message: String,
    },
    /// Encoding failed.
    #[error("Failed to encode image: {0}")]
    Encode(String),
    /// Writing the output failed.
    #[error("Failed to save meme to {path}: {message}")]
    Save {
        /// Target path.
        path: String,
        /// I/O error.
        message: String,
    },
}

/// Output image format.
#[derive(Debug, Clone, Copy, Default, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "lowercase")]
pub enum OutputFormat {
    /// Lossless PNG (default).
    #[default]
    Png,
    /// JPEG (much smaller; better for uploads of photo templates).
    #[serde(alias = "jpg")]
    Jpeg,
}

impl OutputFormat {
    /// File extension.
    pub fn extension(self) -> &'static str {
        match self {
            Self::Png => "png",
            Self::Jpeg => "jpg",
        }
    }

    /// MIME type.
    pub fn mime(self) -> &'static str {
        match self {
            Self::Png => "image/png",
            Self::Jpeg => "image/jpeg",
        }
    }
}

/// A validated-at-render-time meme request.
#[derive(Debug, Clone, Default)]
pub struct MemeRequest {
    /// Template id.
    pub template: String,
    /// Area id -> caption.
    pub texts: BTreeMap<String, String>,
    /// Area id -> fixed font size (skips auto-fit for that area).
    pub font_size_override: BTreeMap<String, i32>,
    /// Shrink text to fit each area (otherwise use `default_font_size`).
    pub auto_resize: bool,
}

/// How one area was rendered.
#[derive(Debug, Clone, Serialize, PartialEq)]
pub struct AreaReport {
    /// Area id.
    pub id: String,
    /// Font size used (px).
    pub font_size: f32,
    /// Number of wrapped lines.
    pub lines: usize,
    /// Whether the text fit inside the area.
    pub fits: bool,
}

/// A rendered (not yet encoded) meme.
pub struct RenderedMeme {
    /// Template id.
    pub template: String,
    /// Final pixels.
    pub image: RgbImage,
    /// Per-area layout report.
    pub areas: Vec<AreaReport>,
    /// Non-fatal issues (overflow, missing glyphs, over max_chars, ...).
    pub warnings: Vec<String>,
}

/// An encoded image.
pub struct EncodedImage {
    /// File bytes.
    pub bytes: Vec<u8>,
    /// Format.
    pub format: OutputFormat,
    /// Width in px.
    pub width: u32,
    /// Height in px.
    pub height: u32,
}

/// Meme generator: loaded templates + font + output directory.
pub struct MemeGenerator {
    store: TemplateStore,
    font: LoadedFont,
    output_dir: PathBuf,
}

/// Distinguishes files saved within the same millisecond.
static SAVE_COUNTER: AtomicU64 = AtomicU64::new(0);

impl MemeGenerator {
    /// Build a generator from already-loaded parts.
    pub fn new(store: TemplateStore, font: LoadedFont, output_dir: PathBuf) -> Self {
        Self {
            store,
            font,
            output_dir,
        }
    }

    /// Loaded templates.
    pub fn store(&self) -> &TemplateStore {
        &self.store
    }

    /// Where the font came from.
    pub fn font_source(&self) -> &str {
        &self.font.source
    }

    fn template(&self, id: &str) -> Result<&LoadedTemplate, MemeError> {
        self.store
            .get(id)
            .ok_or_else(|| MemeError::TemplateNotFound {
                id: id.to_string(),
                available: self.store.ids(),
            })
    }

    /// Validate `req` against the template and render it.
    pub fn render(&self, req: &MemeRequest) -> Result<RenderedMeme, MemeError> {
        let template = self.template(&req.template)?;
        let areas = &template.config.text_areas;
        let valid_ids = || {
            areas
                .iter()
                .map(|a| a.id.as_str())
                .collect::<Vec<_>>()
                .join(", ")
        };

        // Reject unknown keys instead of silently producing a blank meme.
        for key in req.texts.keys().chain(req.font_size_override.keys()) {
            if !areas.iter().any(|a| &a.id == key) {
                return Err(MemeError::InvalidArgument(format!(
                    "Unknown text area '{key}' for template '{}'. Valid areas: {}",
                    template.id,
                    valid_ids()
                )));
            }
        }
        for (key, text) in &req.texts {
            let n = text.chars().count();
            if n > MAX_TEXT_CHARS {
                return Err(MemeError::InvalidArgument(format!(
                    "Text for area '{key}' is {n} characters; the limit is {MAX_TEXT_CHARS}"
                )));
            }
        }
        for (key, size) in &req.font_size_override {
            if !FONT_SIZE_RANGE.contains(size) {
                return Err(MemeError::InvalidArgument(format!(
                    "font_size_override for '{key}' is {size}; must be within {}..={}",
                    FONT_SIZE_RANGE.start(),
                    FONT_SIZE_RANGE.end()
                )));
            }
        }

        let mut image = load_template_image(template)?;
        let font = &self.font.font;
        let mut reports = Vec::new();
        let mut warnings = Vec::new();

        for area in areas {
            let Some(raw) = req.texts.get(&area.id) else {
                continue;
            };
            let text = sanitize_text(raw);
            if text.trim().is_empty() {
                continue;
            }

            if let Some(max) = area.max_chars
                && max > 0
                && text.chars().count() > max as usize
            {
                warnings.push(format!(
                    "Text for '{}' is {} characters; this template recommends at most {max}",
                    area.id,
                    text.chars().count()
                ));
            }
            let missing = unsupported_chars(font, &text);
            if !missing.is_empty() {
                warnings.push(format!(
                    "The caption font has no glyphs for {:?} in '{}'; they render as boxes",
                    missing.iter().collect::<String>(),
                    area.id
                ));
            }

            let stroke = area.stroke_width.max(0) as f32;
            let (bw, bh) = (area.width as f32, area.height as f32);
            let layout: Layout = if let Some(&size) = req.font_size_override.get(&area.id) {
                layout_at_size(font, &text, size as f32, bw, bh, stroke)
            } else if req.auto_resize {
                fit_text(
                    font,
                    &text,
                    bw,
                    bh,
                    area.min_font_size,
                    area.max_font_size,
                    stroke,
                )
            } else {
                layout_at_size(font, &text, area.default_font_size as f32, bw, bh, stroke)
            };

            if !layout.fits {
                warnings.push(format!(
                    "Text for '{}' does not fit its {}x{} area at {}px; it may overlap the image. Shorten it{}",
                    area.id,
                    area.width,
                    area.height,
                    layout.font_size,
                    if req.auto_resize && !req.font_size_override.contains_key(&area.id) {
                        ""
                    } else {
                        " or enable auto_resize"
                    }
                ));
            }

            let style = TextStyle {
                // Colors were validated when the template loaded.
                fill: parse_color(&area.text_color).unwrap_or(render::Color::opaque(255, 255, 255)),
                stroke: parse_color(&area.stroke_color).unwrap_or(render::Color::opaque(0, 0, 0)),
                stroke_width: stroke,
                align: area.text_align,
            };
            let rect = AreaRect {
                cx: area.position.x as f32,
                cy: area.position.y as f32,
                width: bw,
            };
            render::draw_block(&mut image, font, &layout, rect, &style);

            reports.push(AreaReport {
                id: area.id.clone(),
                font_size: layout.font_size,
                lines: layout.lines.len(),
                fits: layout.fits,
            });
        }

        if reports.is_empty() {
            warnings.push(format!(
                "No captions were drawn; provide text for at least one of: {}",
                valid_ids()
            ));
        }

        Ok(RenderedMeme {
            template: template.id.clone(),
            image,
            areas: reports,
            warnings,
        })
    }

    /// Save encoded bytes to a new, uniquely named file in the output dir.
    pub fn save(&self, template: &str, encoded: &EncodedImage) -> Result<PathBuf, MemeError> {
        let save_err = |path: &Path, e: std::io::Error| MemeError::Save {
            path: path.display().to_string(),
            message: e.to_string(),
        };
        std::fs::create_dir_all(&self.output_dir).map_err(|e| save_err(&self.output_dir, e))?;

        let stamp = chrono::Utc::now().format("%Y%m%d_%H%M%S_%3f");
        loop {
            let n = SAVE_COUNTER.fetch_add(1, Ordering::Relaxed);
            let name = format!("meme_{template}_{stamp}_{n}.{}", encoded.format.extension());
            let path = self.output_dir.join(name);
            // create_new: never clobber an existing file.
            match OpenOptions::new().write(true).create_new(true).open(&path) {
                Ok(mut file) => {
                    file.write_all(&encoded.bytes)
                        .map_err(|e| save_err(&path, e))?;
                    return Ok(std::path::absolute(&path).unwrap_or(path));
                },
                Err(e) if e.kind() == std::io::ErrorKind::AlreadyExists => continue,
                Err(e) => return Err(save_err(&path, e)),
            }
        }
    }
}

/// Decode the template image, sniffing the real format from its bytes.
fn load_template_image(template: &LoadedTemplate) -> Result<RgbImage, MemeError> {
    let err = |message: String| MemeError::TemplateImage {
        path: template.image_path.display().to_string(),
        message,
    };
    let img = image::ImageReader::open(&template.image_path)
        .map_err(|e| err(e.to_string()))?
        .with_guessed_format()
        .map_err(|e| err(e.to_string()))?
        .decode()
        .map_err(|e| err(e.to_string()))?;
    Ok(img.to_rgb8())
}

/// Encode an image in the requested format.
pub fn encode(image: &RgbImage, format: OutputFormat) -> Result<EncodedImage, MemeError> {
    let mut buf = Cursor::new(Vec::new());
    match format {
        OutputFormat::Png => image
            .write_to(&mut buf, ImageFormat::Png)
            .map_err(|e| MemeError::Encode(e.to_string()))?,
        OutputFormat::Jpeg => {
            image::codecs::jpeg::JpegEncoder::new_with_quality(&mut buf, JPEG_QUALITY)
                .encode_image(image)
                .map_err(|e| MemeError::Encode(e.to_string()))?
        },
    }
    Ok(EncodedImage {
        bytes: buf.into_inner(),
        format,
        width: image.width(),
        height: image.height(),
    })
}

/// Downscale (if needed) to at most [`PREVIEW_MAX_SIDE`] and encode as JPEG,
/// which keeps the inline preview small while the text stays legible.
pub fn preview(image: &RgbImage) -> Result<EncodedImage, MemeError> {
    let (w, h) = image.dimensions();
    let longest = w.max(h);
    let mut buf = Cursor::new(Vec::new());
    let scaled;
    let target: &RgbImage = if longest > PREVIEW_MAX_SIDE {
        let ratio = PREVIEW_MAX_SIDE as f32 / longest as f32;
        let nw = ((w as f32 * ratio).round() as u32).max(1);
        let nh = ((h as f32 * ratio).round() as u32).max(1);
        scaled = image::imageops::resize(image, nw, nh, FilterType::Triangle);
        &scaled
    } else {
        image
    };
    image::codecs::jpeg::JpegEncoder::new_with_quality(&mut buf, PREVIEW_JPEG_QUALITY)
        .encode_image(target)
        .map_err(|e| MemeError::Encode(e.to_string()))?;
    Ok(EncodedImage {
        bytes: buf.into_inner(),
        format: OutputFormat::Jpeg,
        width: target.width(),
        height: target.height(),
    })
}

#[cfg(test)]
pub(crate) mod tests {
    use super::*;
    use crate::fonts;
    use crate::templates::tests::shipped_templates_dir;

    pub(crate) fn generator(output_dir: PathBuf) -> MemeGenerator {
        MemeGenerator::new(
            TemplateStore::load(&shipped_templates_dir()),
            fonts::embedded(),
            output_dir,
        )
    }

    fn request(template: &str, texts: &[(&str, &str)]) -> MemeRequest {
        MemeRequest {
            template: template.to_string(),
            texts: texts
                .iter()
                .map(|(k, v)| (k.to_string(), v.to_string()))
                .collect(),
            font_size_override: BTreeMap::new(),
            auto_resize: true,
        }
    }

    #[test]
    fn renders_every_shipped_template_example() {
        let g = generator(PathBuf::from("unused"));
        for summary in g.store().summaries() {
            let t = g.store().get(&summary.id).unwrap();
            let example = t
                .config
                .examples
                .first()
                .unwrap_or_else(|| panic!("{} has no examples", summary.id));
            let req = MemeRequest {
                template: summary.id.clone(),
                texts: example.texts.clone(),
                font_size_override: BTreeMap::new(),
                auto_resize: true,
            };
            let meme = g.render(&req).unwrap();
            assert_eq!(meme.image.dimensions(), (t.width, t.height));
            assert_eq!(meme.areas.len(), example.texts.len(), "{}", summary.id);
            assert!(
                meme.areas.iter().all(|a| a.fits),
                "{}: {:?} {:?}",
                summary.id,
                meme.areas,
                meme.warnings
            );
        }
    }

    /// Template-authoring aid: render every example of every template to
    /// `$MEME_EXAMPLES_OUT` for visual review. Run with
    /// `MEME_EXAMPLES_OUT=/tmp/ex cargo test -- --ignored render_examples`.
    #[test]
    #[ignore = "writes images for manual review; needs MEME_EXAMPLES_OUT"]
    fn render_examples_to_dir() {
        let Some(out) = std::env::var_os("MEME_EXAMPLES_OUT") else {
            return;
        };
        let out = PathBuf::from(out);
        std::fs::create_dir_all(&out).unwrap();
        let g = generator(out.clone());
        for summary in g.store().summaries() {
            let t = g.store().get(&summary.id).unwrap();
            for (i, example) in t.config.examples.iter().enumerate() {
                let req = MemeRequest {
                    template: summary.id.clone(),
                    texts: example.texts.clone(),
                    font_size_override: BTreeMap::new(),
                    auto_resize: true,
                };
                let meme = g.render(&req).unwrap();
                let enc = encode(&meme.image, OutputFormat::Jpeg).unwrap();
                std::fs::write(out.join(format!("{}_{i}.jpg", summary.id)), &enc.bytes).unwrap();
            }
        }
    }

    #[test]
    fn rendering_changes_pixels() {
        let g = generator(PathBuf::from("unused"));
        let blank = g.render(&request("ol_reliable", &[])).unwrap();
        assert!(blank.warnings.iter().any(|w| w.contains("No captions")));
        let meme = g
            .render(&request("ol_reliable", &[("top", "When it breaks")]))
            .unwrap();
        assert_ne!(blank.image, meme.image);
        assert!(meme.warnings.is_empty(), "{:?}", meme.warnings);
    }

    #[test]
    fn png_saved_with_jpg_extension_renders() {
        // community_fire.jpg is actually PNG data; the old decoder trusted
        // the extension and failed on it.
        let g = generator(PathBuf::from("unused"));
        let meme = g
            .render(&request("community_fire", &[("expectation", "ME")]))
            .unwrap();
        assert_eq!(meme.image.dimensions(), (843, 957));
    }

    #[test]
    fn unknown_template_lists_available() {
        let g = generator(PathBuf::from("unused"));
        let err = g.render(&request("drake", &[("top", "x")])).err().unwrap();
        let msg = err.to_string();
        assert!(msg.contains("Template 'drake' not found"));
        assert!(msg.contains("ol_reliable"));
    }

    #[test]
    fn unknown_area_is_rejected_with_valid_list() {
        let g = generator(PathBuf::from("unused"));
        let err = g
            .render(&request("ol_reliable", &[("reject", "x")]))
            .err()
            .unwrap();
        let msg = err.to_string();
        assert!(msg.contains("Unknown text area 'reject'"), "{msg}");
        assert!(msg.contains("top, bottom"), "{msg}");
    }

    #[test]
    fn font_override_is_validated_and_applied() {
        let g = generator(PathBuf::from("unused"));
        let mut req = request("ol_reliable", &[("top", "x")]);
        req.font_size_override.insert("top".into(), 10_000);
        assert!(g.render(&req).is_err());
        req.font_size_override.insert("top".into(), 0);
        assert!(g.render(&req).is_err());
        req.font_size_override.insert("top".into(), 22);
        let meme = g.render(&req).unwrap();
        assert_eq!(meme.areas[0].font_size, 22.0);
    }

    #[test]
    fn overlong_text_is_rejected() {
        let g = generator(PathBuf::from("unused"));
        let long = "x".repeat(MAX_TEXT_CHARS + 1);
        assert!(
            g.render(&request("ol_reliable", &[("top", &long)]))
                .is_err()
        );
    }

    #[test]
    fn overflow_and_max_chars_produce_warnings() {
        let g = generator(PathBuf::from("unused"));
        let text = "this caption is far too long for the tiny answer box ".repeat(4);
        let meme = g.render(&request("millionaire", &[("a", &text)])).unwrap();
        assert!(!meme.areas[0].fits);
        assert!(meme.warnings.iter().any(|w| w.contains("does not fit")));
        assert!(
            meme.warnings
                .iter()
                .any(|w| w.contains("recommends at most"))
        );
    }

    #[test]
    fn no_auto_resize_uses_default_size() {
        let g = generator(PathBuf::from("unused"));
        let mut req = request("ol_reliable", &[("top", "hi")]);
        req.auto_resize = false;
        let meme = g.render(&req).unwrap();
        assert_eq!(meme.areas[0].font_size, 40.0);
    }

    #[test]
    fn encode_and_preview_roundtrip() {
        let g = generator(PathBuf::from("unused"));
        let meme = g
            .render(&request("ol_reliable", &[("top", "hello")]))
            .unwrap();
        for format in [OutputFormat::Png, OutputFormat::Jpeg] {
            let enc = encode(&meme.image, format).unwrap();
            let decoded = image::load_from_memory(&enc.bytes).unwrap();
            assert_eq!((decoded.width(), decoded.height()), (960, 1444));
        }
        let p = preview(&meme.image).unwrap();
        assert_eq!(p.height, PREVIEW_MAX_SIDE);
        assert!(p.width < PREVIEW_MAX_SIDE);
        assert!(p.bytes.len() < 200 * 1024);
    }

    #[test]
    fn save_creates_unique_files() {
        let dir = tempfile::tempdir().unwrap();
        let g = generator(dir.path().join("nested/out"));
        let enc = EncodedImage {
            bytes: vec![1, 2, 3],
            format: OutputFormat::Png,
            width: 1,
            height: 1,
        };
        let a = g.save("ol_reliable", &enc).unwrap();
        let b = g.save("ol_reliable", &enc).unwrap();
        assert_ne!(a, b);
        assert!(a.is_absolute());
        assert_eq!(std::fs::read(&a).unwrap(), vec![1, 2, 3]);
        assert!(
            a.file_name()
                .unwrap()
                .to_string_lossy()
                .starts_with("meme_ol_reliable_")
        );
    }

    #[test]
    fn output_format_parses_aliases() {
        let f: OutputFormat = serde_json::from_value(serde_json::json!("jpg")).unwrap();
        assert_eq!(f, OutputFormat::Jpeg);
        let f: OutputFormat = serde_json::from_value(serde_json::json!("png")).unwrap();
        assert_eq!(f, OutputFormat::Png);
        assert!(serde_json::from_value::<OutputFormat>(serde_json::json!("gif")).is_err());
    }
}
