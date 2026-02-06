//! Meme generation engine with text overlay support.

use ab_glyph::{Font, FontRef, PxScale, ScaleFont};
use base64::{Engine as _, engine::general_purpose::STANDARD as BASE64};
use image::{DynamicImage, ImageFormat, Rgb, RgbImage};
use imageproc::drawing::draw_text_mut;
use std::collections::HashMap;
use std::fs;
use std::io::Cursor;
use std::path::{Path, PathBuf};
use tracing::{debug, error, info, warn};

use crate::types::{MemeResult, TemplateConfig, TemplateSummary, TextArea, VisualFeedback};
use crate::upload::MemeUploader;

/// Default font path for Linux systems
const DEFAULT_FONT_PATH: &str = "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf";

/// Fallback font embedded in binary (DejaVu Sans Bold subset)
/// This is just the basic ASCII subset for fallback
const FALLBACK_FONT_BYTES: &[u8] = include_bytes!("../assets/DejaVuSans-Bold.ttf");

/// Meme generator engine
pub struct MemeGenerator {
    templates_dir: PathBuf,
    output_dir: PathBuf,
    templates: HashMap<String, TemplateConfig>,
    font_data: Vec<u8>,
}

impl MemeGenerator {
    /// Create a new meme generator
    pub fn new(templates_dir: PathBuf, output_dir: PathBuf) -> Self {
        let mut generator = Self {
            templates_dir,
            output_dir,
            templates: HashMap::new(),
            font_data: Vec::new(),
        };
        generator.load_font();
        generator.load_templates();
        generator
    }

    /// Load font data
    fn load_font(&mut self) {
        // Try system font first
        if Path::new(DEFAULT_FONT_PATH).exists() {
            match fs::read(DEFAULT_FONT_PATH) {
                Ok(data) => {
                    info!("Loaded system font: {}", DEFAULT_FONT_PATH);
                    self.font_data = data;
                    return;
                },
                Err(e) => {
                    warn!("Failed to load system font: {}", e);
                },
            }
        }

        // Fall back to embedded font
        info!("Using embedded fallback font");
        self.font_data = FALLBACK_FONT_BYTES.to_vec();
    }

    /// Load all template configurations
    fn load_templates(&mut self) {
        let config_dir = self.templates_dir.join("config");
        if !config_dir.exists() {
            warn!("Config directory not found: {}", config_dir.display());
            return;
        }

        let entries = match fs::read_dir(&config_dir) {
            Ok(e) => e,
            Err(e) => {
                error!("Failed to read config directory: {}", e);
                return;
            },
        };

        for entry in entries.flatten() {
            let path = entry.path();
            if path.extension().and_then(|e| e.to_str()) == Some("json") {
                let filename = path.file_stem().and_then(|s| s.to_str()).unwrap_or("");
                if filename == "template_schema" {
                    continue;
                }

                match fs::read_to_string(&path) {
                    Ok(content) => match serde_json::from_str::<TemplateConfig>(&content) {
                        Ok(config) => {
                            debug!("Loaded template: {}", filename);
                            self.templates.insert(filename.to_string(), config);
                        },
                        Err(e) => {
                            error!("Failed to parse template {}: {}", filename, e);
                        },
                    },
                    Err(e) => {
                        error!("Failed to read template file {}: {}", path.display(), e);
                    },
                }
            }
        }

        info!("Loaded {} templates", self.templates.len());
    }

    /// Get font at specified size
    fn get_font(&self, size: f32) -> Option<(FontRef<'_>, PxScale)> {
        FontRef::try_from_slice(&self.font_data)
            .ok()
            .map(|font| (font, PxScale::from(size)))
    }

    /// Wrap text to fit within max width
    fn wrap_text(&self, text: &str, font: &FontRef, scale: PxScale, max_width: i32) -> Vec<String> {
        let scaled = font.as_scaled(scale);
        let mut lines = Vec::new();
        let mut current_line = String::new();

        for word in text.split_whitespace() {
            let test_line = if current_line.is_empty() {
                word.to_string()
            } else {
                format!("{} {}", current_line, word)
            };

            let width: f32 = test_line
                .chars()
                .map(|c| scaled.h_advance(font.glyph_id(c)))
                .sum();

            if width <= max_width as f32 {
                current_line = test_line;
            } else if current_line.is_empty() {
                // Word is too long, add it anyway
                lines.push(word.to_string());
            } else {
                lines.push(current_line);
                current_line = word.to_string();
            }
        }

        if !current_line.is_empty() {
            lines.push(current_line);
        }

        lines
    }

    /// Calculate text width
    fn text_width(&self, text: &str, font: &FontRef, scale: PxScale) -> f32 {
        let scaled = font.as_scaled(scale);
        text.chars()
            .map(|c| scaled.h_advance(font.glyph_id(c)))
            .sum()
    }

    /// Auto-adjust font size to fit text in area
    fn auto_adjust_font_size(&self, text: &str, area: &TextArea) -> (f32, Vec<String>) {
        let max_size = area.max_font_size as f32;
        let min_size = area.min_font_size as f32;

        for size in (min_size as i32..=max_size as i32).rev().step_by(2) {
            let size = size as f32;
            if let Some((font, scale)) = self.get_font(size) {
                let lines = self.wrap_text(text, &font, scale, area.width);
                let total_height = lines.len() as f32 * size;

                if total_height <= area.height as f32 {
                    return (size, lines);
                }
            }
        }

        // Fallback to minimum size
        if let Some((font, scale)) = self.get_font(min_size) {
            let lines = self.wrap_text(text, &font, scale, area.width);
            return (min_size, lines);
        }

        (min_size, vec![text.to_string()])
    }

    /// Parse color string to RGB
    fn parse_color(&self, color: &str) -> Rgb<u8> {
        match color.to_lowercase().as_str() {
            "white" => Rgb([255, 255, 255]),
            "black" => Rgb([0, 0, 0]),
            "red" => Rgb([255, 0, 0]),
            "green" => Rgb([0, 255, 0]),
            "blue" => Rgb([0, 0, 255]),
            "yellow" => Rgb([255, 255, 0]),
            _ => {
                // Try to parse hex color
                if color.starts_with('#') && color.len() == 7 {
                    let r = u8::from_str_radix(&color[1..3], 16).unwrap_or(255);
                    let g = u8::from_str_radix(&color[3..5], 16).unwrap_or(255);
                    let b = u8::from_str_radix(&color[5..7], 16).unwrap_or(255);
                    Rgb([r, g, b])
                } else {
                    Rgb([255, 255, 255]) // Default to white
                }
            },
        }
    }

    /// Draw text with stroke/outline effect
    #[allow(clippy::too_many_arguments)]
    fn draw_text_with_stroke(
        &self,
        img: &mut RgbImage,
        x: i32,
        y: i32,
        text: &str,
        font: &FontRef,
        scale: PxScale,
        text_color: Rgb<u8>,
        stroke_color: Rgb<u8>,
        stroke_width: i32,
    ) {
        // Draw stroke (outline) by drawing text at offset positions
        for dx in -stroke_width..=stroke_width {
            for dy in -stroke_width..=stroke_width {
                if dx != 0 || dy != 0 {
                    draw_text_mut(img, stroke_color, x + dx, y + dy, scale, font, text);
                }
            }
        }

        // Draw main text
        draw_text_mut(img, text_color, x, y, scale, font, text);
    }

    /// Generate a meme from template with text overlays
    pub fn generate_meme(
        &self,
        template_id: &str,
        texts: &HashMap<String, String>,
        font_size_override: Option<&HashMap<String, i32>>,
        auto_resize: bool,
        thumbnail_only: bool,
    ) -> MemeResult {
        // Check template exists
        let template = match self.templates.get(template_id) {
            Some(t) => t,
            None => {
                return MemeResult {
                    success: false,
                    error: Some(format!("Template '{}' not found", template_id)),
                    ..Default::default()
                };
            },
        };

        // Load template image
        let template_path = self.templates_dir.join(&template.template_file);
        if !template_path.exists() {
            return MemeResult {
                success: false,
                error: Some(format!(
                    "Template image not found: {}",
                    template_path.display()
                )),
                ..Default::default()
            };
        }

        let img = match image::open(&template_path) {
            Ok(i) => i,
            Err(e) => {
                return MemeResult {
                    success: false,
                    error: Some(format!("Failed to load template image: {}", e)),
                    ..Default::default()
                };
            },
        };

        let mut img = img.to_rgb8();

        // Draw text for each area
        for area in &template.text_areas {
            let text = match texts.get(&area.id) {
                Some(t) if !t.is_empty() => t,
                _ => continue,
            };

            // Determine font size
            let (font_size, lines) = if let Some(overrides) = font_size_override {
                if let Some(&size) = overrides.get(&area.id) {
                    if let Some((font, scale)) = self.get_font(size as f32) {
                        let lines = self.wrap_text(text, &font, scale, area.width);
                        (size as f32, lines)
                    } else {
                        continue;
                    }
                } else if auto_resize {
                    self.auto_adjust_font_size(text, area)
                } else if let Some((font, scale)) = self.get_font(area.default_font_size as f32) {
                    let lines = self.wrap_text(text, &font, scale, area.width);
                    (area.default_font_size as f32, lines)
                } else {
                    continue;
                }
            } else if auto_resize {
                self.auto_adjust_font_size(text, area)
            } else if let Some((font, scale)) = self.get_font(area.default_font_size as f32) {
                let lines = self.wrap_text(text, &font, scale, area.width);
                (area.default_font_size as f32, lines)
            } else {
                continue;
            };

            let (font, scale) = match self.get_font(font_size) {
                Some(f) => f,
                None => continue,
            };

            let text_color = self.parse_color(&area.text_color);
            let stroke_color = self.parse_color(&area.stroke_color);

            // Calculate vertical starting position
            let total_height = lines.len() as f32 * font_size;
            let start_y = area.position.y as f32 - total_height / 2.0;

            // Draw each line
            for (i, line) in lines.iter().enumerate() {
                let line_width = self.text_width(line, &font, scale);

                let x = match area.text_align.as_str() {
                    "left" => area.position.x - area.width / 2,
                    "right" => area.position.x + area.width / 2 - line_width as i32,
                    _ => area.position.x - (line_width / 2.0) as i32, // center
                };

                let y = start_y as i32 + (i as f32 * font_size) as i32;

                self.draw_text_with_stroke(
                    &mut img,
                    x,
                    y,
                    line,
                    &font,
                    scale,
                    text_color,
                    stroke_color,
                    area.stroke_width,
                );
            }
        }

        // Convert to output format
        let (img_data, format) = if thumbnail_only {
            // Create thumbnail
            let max_width = 150u32;
            let resized = if img.width() > max_width {
                let ratio = max_width as f32 / img.width() as f32;
                let new_height = (img.height() as f32 * ratio) as u32;
                image::imageops::resize(
                    &img,
                    max_width,
                    new_height,
                    image::imageops::FilterType::Lanczos3,
                )
            } else {
                img
            };

            let mut buffer = Cursor::new(Vec::new());
            let dynamic = DynamicImage::ImageRgb8(resized);
            if let Err(e) = dynamic.write_to(&mut buffer, ImageFormat::WebP) {
                return MemeResult {
                    success: false,
                    error: Some(format!("Failed to encode thumbnail: {}", e)),
                    ..Default::default()
                };
            }
            (buffer.into_inner(), "webp")
        } else {
            // Full size PNG
            let mut buffer = Cursor::new(Vec::new());
            let dynamic = DynamicImage::ImageRgb8(img);
            if let Err(e) = dynamic.write_to(&mut buffer, ImageFormat::Png) {
                return MemeResult {
                    success: false,
                    error: Some(format!("Failed to encode image: {}", e)),
                    ..Default::default()
                };
            }
            (buffer.into_inner(), "png")
        };

        let size_kb = img_data.len() as f64 / 1024.0;
        let image_data = BASE64.encode(&img_data);

        MemeResult {
            success: true,
            error: None,
            output_path: None,
            template_used: Some(template_id.to_string()),
            image_data: Some(image_data),
            format: Some(format.to_string()),
            size_kb: Some(size_kb),
            share_url: None,
            embed_url: None,
            upload_service: None,
            visual_feedback: None,
        }
    }

    /// Generate a meme and optionally upload it
    pub async fn generate_and_upload(
        &self,
        template_id: &str,
        texts: &HashMap<String, String>,
        font_size_override: Option<&HashMap<String, i32>>,
        auto_resize: bool,
        upload: bool,
    ) -> MemeResult {
        // Generate full-size meme
        let result = self.generate_meme(template_id, texts, font_size_override, auto_resize, false);

        if !result.success {
            return result;
        }

        let image_data = match &result.image_data {
            Some(data) => BASE64.decode(data).unwrap_or_default(),
            None => {
                return MemeResult {
                    success: false,
                    error: Some("No image data generated".to_string()),
                    ..Default::default()
                };
            },
        };

        // Save to file
        let timestamp = chrono::Utc::now().timestamp();
        let filename = format!("meme_{}_{}.png", template_id, timestamp);
        let output_path = self.output_dir.join(&filename);

        if let Err(e) = fs::create_dir_all(&self.output_dir) {
            return MemeResult {
                success: false,
                error: Some(format!("Failed to create output directory: {}", e)),
                ..Default::default()
            };
        }

        if let Err(e) = fs::write(&output_path, &image_data) {
            return MemeResult {
                success: false,
                error: Some(format!("Failed to save image: {}", e)),
                ..Default::default()
            };
        }

        // Generate thumbnail for visual feedback
        let thumbnail_result =
            self.generate_meme(template_id, texts, font_size_override, auto_resize, true);

        let visual_feedback = if thumbnail_result.success {
            thumbnail_result.image_data.map(|data| VisualFeedback {
                format: "webp".to_string(),
                encoding: "base64".to_string(),
                data,
                size_kb: thumbnail_result.size_kb.unwrap_or(0.0),
            })
        } else {
            None
        };

        // Upload if requested
        let (share_url, embed_url, upload_service) = if upload {
            let upload_result = MemeUploader::upload(&output_path, "auto").await;
            if upload_result.success {
                (
                    upload_result.url,
                    upload_result.embed_url,
                    upload_result.service,
                )
            } else {
                warn!("Upload failed: {:?}", upload_result.error);
                (None, None, None)
            }
        } else {
            (None, None, None)
        };

        MemeResult {
            success: true,
            error: None,
            output_path: Some(output_path.display().to_string()),
            template_used: Some(template_id.to_string()),
            image_data: None, // Don't include raw image data in final response
            format: Some("png".to_string()),
            size_kb: Some(image_data.len() as f64 / 1024.0),
            share_url,
            embed_url,
            upload_service,
            visual_feedback,
        }
    }

    /// List all available templates
    pub fn list_templates(&self) -> Vec<TemplateSummary> {
        self.templates
            .iter()
            .map(|(id, config)| TemplateSummary {
                id: id.clone(),
                name: config.name.clone(),
                description: config.description.clone(),
                text_areas: config.text_areas.iter().map(|a| a.id.clone()).collect(),
            })
            .collect()
    }

    /// Get template information
    pub fn get_template_info(&self, template_id: &str) -> Option<&TemplateConfig> {
        self.templates.get(template_id)
    }

    /// Get number of loaded templates
    pub fn template_count(&self) -> usize {
        self.templates.len()
    }

    /// Get output directory
    #[allow(dead_code)]
    pub fn output_dir(&self) -> &Path {
        &self.output_dir
    }

    /// Get templates directory
    #[allow(dead_code)]
    pub fn templates_dir(&self) -> &Path {
        &self.templates_dir
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_parse_color() {
        let generator = MemeGenerator {
            templates_dir: PathBuf::new(),
            output_dir: PathBuf::new(),
            templates: HashMap::new(),
            font_data: Vec::new(),
        };

        assert_eq!(generator.parse_color("white"), Rgb([255, 255, 255]));
        assert_eq!(generator.parse_color("black"), Rgb([0, 0, 0]));
        assert_eq!(generator.parse_color("#FF0000"), Rgb([255, 0, 0]));
    }
}
