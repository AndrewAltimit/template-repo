//! Template discovery and validation.
//!
//! Every `templates/config/<id>.json` (except `template_schema.json`) is
//! parsed and semantically validated against its image. A template with a hard
//! error (unreadable image, bad color, impossible geometry, ...) is skipped and
//! the reason is recorded in [`TemplateStore::errors`], which the status and
//! list tools surface -- previously such problems only reached the log, and a
//! broken template (e.g. a PNG saved with a `.jpg` extension) failed at
//! generation time with an opaque decoder error.

use std::collections::{BTreeMap, HashSet};
use std::path::{Component, Path, PathBuf};
use tracing::{debug, info, warn};

use crate::render::{FONT_SIZE_RANGE, MAX_STROKE_WIDTH, parse_color};
use crate::types::{TemplateConfig, TemplateSummary};

/// Image extensions a template may reference.
const IMAGE_EXTENSIONS: &[&str] = &["jpg", "jpeg", "png", "webp"];

/// A validated template ready for rendering.
#[derive(Debug, Clone)]
pub struct LoadedTemplate {
    /// Template id (config file stem).
    pub id: String,
    /// Parsed configuration.
    pub config: TemplateConfig,
    /// Absolute-or-relative path to the template image.
    pub image_path: PathBuf,
    /// Image width in px.
    pub width: u32,
    /// Image height in px.
    pub height: u32,
}

impl LoadedTemplate {
    /// Summary used by `list_meme_templates`.
    pub fn summary(&self) -> TemplateSummary {
        TemplateSummary {
            id: self.id.clone(),
            name: self.config.name.clone(),
            description: self.config.description.clone(),
            text_areas: self
                .config
                .text_areas
                .iter()
                .map(|a| a.id.clone())
                .collect(),
            image_size: [self.width, self.height],
        }
    }
}

/// All templates found in a directory, plus any problems encountered.
#[derive(Debug, Default)]
pub struct TemplateStore {
    templates: BTreeMap<String, LoadedTemplate>,
    /// Templates that were rejected, with reasons.
    pub errors: Vec<String>,
    /// Non-fatal issues in accepted templates.
    pub warnings: Vec<String>,
}

/// Template ids become part of output file names, so keep them boring.
pub fn is_valid_template_id(id: &str) -> bool {
    !id.is_empty()
        && id.len() <= 64
        && id
            .bytes()
            .all(|b| b.is_ascii_alphanumeric() || b == b'_' || b == b'-')
}

/// `template_file` must be a single plain file name with an image extension:
/// no directories, no `..`, no absolute paths.
fn check_template_file(name: &str) -> Result<(), String> {
    let path = Path::new(name);
    let mut components = path.components();
    let plain = matches!(
        (components.next(), components.next()),
        (Some(Component::Normal(_)), None)
    );
    if !plain || name.contains(['/', '\\']) {
        return Err(format!(
            "template_file '{name}' must be a plain file name inside the templates directory"
        ));
    }
    let ext = path
        .extension()
        .and_then(|e| e.to_str())
        .map(str::to_ascii_lowercase)
        .unwrap_or_default();
    if !IMAGE_EXTENSIONS.contains(&ext.as_str()) {
        return Err(format!(
            "template_file '{name}' must have one of the extensions {IMAGE_EXTENSIONS:?}"
        ));
    }
    Ok(())
}

/// Validate a config against its image size.
///
/// Returns `(errors, warnings)`; any error means the template is unusable.
pub fn validate_config(
    config: &TemplateConfig,
    width: u32,
    height: u32,
) -> (Vec<String>, Vec<String>) {
    let mut errors = Vec::new();
    let mut warnings = Vec::new();
    let (w, h) = (i64::from(width), i64::from(height));

    if config.name.trim().is_empty() {
        errors.push("name is empty".to_string());
    }
    if config.text_areas.is_empty() {
        errors.push("no text_areas defined".to_string());
    }

    let mut seen = HashSet::new();
    for area in &config.text_areas {
        let id = &area.id;
        if id.trim().is_empty() {
            errors.push("a text area has an empty id".to_string());
        } else if !seen.insert(id.as_str()) {
            errors.push(format!("duplicate text area id '{id}'"));
        }
        if area.width <= 0 || area.height <= 0 {
            errors.push(format!(
                "area '{id}': width and height must be positive (got {}x{})",
                area.width, area.height
            ));
        }
        for (label, size) in [
            ("min_font_size", area.min_font_size),
            ("max_font_size", area.max_font_size),
            ("default_font_size", area.default_font_size),
        ] {
            if !FONT_SIZE_RANGE.contains(&size) {
                errors.push(format!(
                    "area '{id}': {label} {size} outside {}..={}",
                    FONT_SIZE_RANGE.start(),
                    FONT_SIZE_RANGE.end()
                ));
            }
        }
        if area.min_font_size > area.max_font_size {
            errors.push(format!(
                "area '{id}': min_font_size {} > max_font_size {}",
                area.min_font_size, area.max_font_size
            ));
        } else if !(area.min_font_size..=area.max_font_size).contains(&area.default_font_size) {
            warnings.push(format!(
                "area '{id}': default_font_size {} outside min/max {}..={}",
                area.default_font_size, area.min_font_size, area.max_font_size
            ));
        }
        if !(0..=MAX_STROKE_WIDTH).contains(&area.stroke_width) {
            errors.push(format!(
                "area '{id}': stroke_width {} outside 0..={MAX_STROKE_WIDTH}",
                area.stroke_width
            ));
        }
        for (label, color) in [
            ("text_color", &area.text_color),
            ("stroke_color", &area.stroke_color),
        ] {
            if parse_color(color).is_none() {
                errors.push(format!("area '{id}': invalid {label} '{color}'"));
            }
        }
        let (cx, cy) = (i64::from(area.position.x), i64::from(area.position.y));
        if !(0..w).contains(&cx) || !(0..h).contains(&cy) {
            errors.push(format!(
                "area '{id}': center ({cx}, {cy}) lies outside the {width}x{height} image"
            ));
        } else {
            let (hw, hh) = (i64::from(area.width) / 2, i64::from(area.height) / 2);
            if cx - hw < 0 || cy - hh < 0 || cx + hw > w || cy + hh > h {
                warnings.push(format!(
                    "area '{id}': box {}x{} at ({cx}, {cy}) extends past the image edge; text may be clipped",
                    area.width, area.height
                ));
            }
        }
        if area.max_chars.is_some_and(|m| m <= 0) {
            warnings.push(format!("area '{id}': max_chars should be positive"));
        }
    }

    for (i, example) in config.examples.iter().enumerate() {
        for key in example.texts.keys() {
            if !seen.contains(key.as_str()) {
                warnings.push(format!("example {i} uses unknown area '{key}'"));
            }
        }
    }

    (errors, warnings)
}

/// Read only the image header to get its dimensions. The format is sniffed
/// from content, not the extension (some shipped files have the wrong one).
fn image_dimensions(path: &Path) -> Result<(u32, u32), String> {
    image::ImageReader::open(path)
        .map_err(|e| format!("cannot open image {}: {e}", path.display()))?
        .with_guessed_format()
        .map_err(|e| format!("cannot read image {}: {e}", path.display()))?
        .into_dimensions()
        .map_err(|e| format!("cannot decode image {}: {e}", path.display()))
}

impl TemplateStore {
    /// Load every template under `templates_dir/config`.
    pub fn load(templates_dir: &Path) -> Self {
        let mut store = Self::default();
        let config_dir = templates_dir.join("config");
        let entries = match std::fs::read_dir(&config_dir) {
            Ok(e) => e,
            Err(e) => {
                store.errors.push(format!(
                    "cannot read template config directory {}: {e}",
                    config_dir.display()
                ));
                warn!("{}", store.errors[0]);
                return store;
            },
        };

        let mut paths: Vec<PathBuf> = entries
            .flatten()
            .map(|e| e.path())
            .filter(|p| p.extension().and_then(|e| e.to_str()) == Some("json"))
            .collect();
        paths.sort();

        for path in paths {
            let Some(id) = path.file_stem().and_then(|s| s.to_str()) else {
                continue;
            };
            if id == "template_schema" {
                continue;
            }
            match load_one(templates_dir, id, &path) {
                Ok((template, warnings)) => {
                    debug!("Loaded template {id}");
                    store
                        .warnings
                        .extend(warnings.into_iter().map(|w| format!("{id}: {w}")));
                    store.templates.insert(id.to_string(), template);
                },
                Err(e) => {
                    warn!("Skipping template {id}: {e}");
                    store.errors.push(format!("{id}: {e}"));
                },
            }
        }

        for w in &store.warnings {
            warn!("Template warning: {w}");
        }
        info!(
            "Loaded {} templates ({} rejected)",
            store.templates.len(),
            store.errors.len()
        );
        store
    }

    /// Look up a template by id.
    pub fn get(&self, id: &str) -> Option<&LoadedTemplate> {
        self.templates.get(id)
    }

    /// Sorted template ids.
    pub fn ids(&self) -> Vec<String> {
        self.templates.keys().cloned().collect()
    }

    /// Sorted summaries.
    pub fn summaries(&self) -> Vec<TemplateSummary> {
        self.templates
            .values()
            .map(LoadedTemplate::summary)
            .collect()
    }

    /// Number of usable templates.
    pub fn len(&self) -> usize {
        self.templates.len()
    }
}

fn load_one(
    templates_dir: &Path,
    id: &str,
    path: &Path,
) -> Result<(LoadedTemplate, Vec<String>), String> {
    if !is_valid_template_id(id) {
        return Err("template id (file name) may only contain letters, digits, '_' and '-'".into());
    }
    let text = std::fs::read_to_string(path).map_err(|e| format!("cannot read config: {e}"))?;
    let config: TemplateConfig =
        serde_json::from_str(&text).map_err(|e| format!("invalid config JSON: {e}"))?;
    check_template_file(&config.template_file)?;
    let image_path = templates_dir.join(&config.template_file);
    let (width, height) = image_dimensions(&image_path)?;
    let (errors, warnings) = validate_config(&config, width, height);
    if !errors.is_empty() {
        return Err(errors.join("; "));
    }
    Ok((
        LoadedTemplate {
            id: id.to_string(),
            config,
            image_path,
            width,
            height,
        },
        warnings,
    ))
}

#[cfg(test)]
pub(crate) mod tests {
    use super::*;
    use serde_json::json;

    /// Path to the templates shipped with the crate.
    pub(crate) fn shipped_templates_dir() -> PathBuf {
        PathBuf::from(env!("CARGO_MANIFEST_DIR")).join("templates")
    }

    fn config(areas: serde_json::Value) -> TemplateConfig {
        serde_json::from_value(json!({
            "name": "Test",
            "template_file": "t.png",
            "text_areas": areas
        }))
        .unwrap()
    }

    fn area(id: &str) -> serde_json::Value {
        json!({
            "id": id,
            "position": {"x": 50, "y": 50},
            "width": 80,
            "height": 40,
            "default_font_size": 20,
            "max_font_size": 30,
            "min_font_size": 10
        })
    }

    #[test]
    fn every_shipped_template_loads_cleanly() {
        let store = TemplateStore::load(&shipped_templates_dir());
        assert!(
            store.errors.is_empty(),
            "template errors: {:?}",
            store.errors
        );
        assert!(
            store.warnings.is_empty(),
            "template warnings: {:?}",
            store.warnings
        );
        assert_eq!(store.len(), 8, "ids: {:?}", store.ids());
        for id in [
            "afraid_to_ask_andy",
            "community_fire",
            "handshake_office",
            "millionaire",
            "npc_wojak",
            "ol_reliable",
            "one_does_not_simply",
            "sweating_jordan_peele",
        ] {
            assert!(store.get(id).is_some(), "missing {id}");
        }
    }

    #[test]
    fn valid_config_has_no_errors() {
        let (errors, warnings) = validate_config(&config(json!([area("top")])), 100, 100);
        assert!(errors.is_empty(), "{errors:?}");
        assert!(warnings.is_empty(), "{warnings:?}");
    }

    #[test]
    fn detects_duplicate_ids_bad_colors_and_geometry() {
        let mut bad = area("top");
        bad["text_color"] = json!("chartreuse-ish");
        bad["min_font_size"] = json!(40);
        bad["position"] = json!({"x": 500, "y": 50});
        let (errors, _) = validate_config(&config(json!([area("top"), bad])), 100, 100);
        let all = errors.join("\n");
        assert!(all.contains("duplicate text area id"), "{all}");
        assert!(all.contains("invalid text_color"), "{all}");
        assert!(all.contains("min_font_size 40 > max_font_size 30"), "{all}");
        assert!(all.contains("outside the 100x100 image"), "{all}");
    }

    #[test]
    fn warns_when_box_extends_past_edge() {
        let mut edge = area("top");
        edge["position"] = json!({"x": 50, "y": 5});
        let (errors, warnings) = validate_config(&config(json!([edge])), 100, 100);
        assert!(errors.is_empty());
        assert!(
            warnings
                .iter()
                .any(|w| w.contains("extends past the image edge"))
        );
    }

    #[test]
    fn rejects_non_plain_template_files() {
        for bad in [
            "../x.png",
            "sub/x.png",
            "/etc/x.png",
            "..\\x.png",
            "x.txt",
            "x",
        ] {
            assert!(
                check_template_file(bad).is_err(),
                "{bad} should be rejected"
            );
        }
        assert!(check_template_file("ok_file.JPG").is_ok());
    }

    #[test]
    fn template_ids_are_restricted() {
        assert!(is_valid_template_id("ol_reliable"));
        assert!(is_valid_template_id("a-b-1"));
        assert!(!is_valid_template_id(""));
        assert!(!is_valid_template_id("has space"));
        assert!(!is_valid_template_id("../x"));
    }

    #[test]
    fn broken_templates_are_reported_not_fatal() {
        let dir = tempfile::tempdir().unwrap();
        let cfg = dir.path().join("config");
        std::fs::create_dir_all(&cfg).unwrap();
        // Valid template with a 100x100 PNG.
        image::RgbImage::new(100, 100)
            .save(dir.path().join("good.png"))
            .unwrap();
        let good =
            json!({"name": "Good", "template_file": "good.png", "text_areas": [area("top")]});
        std::fs::write(cfg.join("good.json"), good.to_string()).unwrap();
        // Traversal attempt.
        let evil =
            json!({"name": "Evil", "template_file": "../good.png", "text_areas": [area("top")]});
        std::fs::write(cfg.join("evil.json"), evil.to_string()).unwrap();
        // Missing image.
        let missing =
            json!({"name": "M", "template_file": "nope.png", "text_areas": [area("top")]});
        std::fs::write(cfg.join("missing.json"), missing.to_string()).unwrap();
        // Malformed JSON.
        std::fs::write(cfg.join("broken.json"), "{not json").unwrap();

        let store = TemplateStore::load(dir.path());
        assert_eq!(store.ids(), vec!["good".to_string()]);
        assert_eq!(store.errors.len(), 3, "{:?}", store.errors);
        assert_eq!(store.get("good").unwrap().width, 100);
    }

    #[test]
    fn missing_config_dir_is_reported() {
        let dir = tempfile::tempdir().unwrap();
        let store = TemplateStore::load(dir.path());
        assert_eq!(store.len(), 0);
        assert!(store.errors[0].contains("cannot read template config directory"));
    }

    #[test]
    fn image_format_is_sniffed_not_trusted_from_extension() {
        let dir = tempfile::tempdir().unwrap();
        let path = dir.path().join("really_png.jpg");
        image::RgbImage::new(7, 5)
            .save_with_format(&path, image::ImageFormat::Png)
            .unwrap();
        assert_eq!(image_dimensions(&path).unwrap(), (7, 5));
    }
}
