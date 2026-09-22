//! Text layout and rasterization for meme captions.
//!
//! This module is pure (no I/O) so it can be unit tested offline:
//!
//! - [`measure`] / [`wrap`] measure and greedily word-wrap text using real
//!   glyph advances *and* kerning (the same metrics used when drawing, so the
//!   fit calculation matches what ends up on the image).
//! - [`fit_text`] picks the largest font size whose wrapped block fits the
//!   area both horizontally and vertically, preferring sizes that do not have
//!   to split a word mid-way.
//! - [`draw_block`] rasterizes each line once into a coverage mask, derives a
//!   round, anti-aliased outline by dilating that mask, and composites
//!   outline + fill in a single pass. (The previous implementation re-drew the
//!   whole string `(2w+1)^2 - 1` times at offsets, which was slow and produced
//!   a blocky, square outline.)

use ab_glyph::{Font, FontArc, GlyphId, PxScale, ScaleFont, point};
use image::{Rgb, RgbImage};

use crate::types::TextAlign;

/// Maximum caption length accepted per text area (characters).
pub const MAX_TEXT_CHARS: usize = 500;

/// Inclusive font size range accepted from callers and template configs.
pub const FONT_SIZE_RANGE: std::ops::RangeInclusive<i32> = 6..=300;

/// Largest outline radius accepted from template configs.
pub const MAX_STROKE_WIDTH: i32 = 16;

/// An RGB color with opacity in `0.0..=1.0`.
#[derive(Debug, Clone, Copy, PartialEq)]
pub struct Color {
    /// Red, green, blue channels.
    pub rgb: [u8; 3],
    /// Opacity multiplier (1.0 = opaque).
    pub alpha: f32,
}

impl Color {
    /// An opaque color.
    pub const fn opaque(r: u8, g: u8, b: u8) -> Self {
        Self {
            rgb: [r, g, b],
            alpha: 1.0,
        }
    }
}

/// Parse a color: a CSS-style name (`white`, `black`, `red`, ...) or hex
/// `#RGB`, `#RRGGBB`, `#RRGGBBAA`. Returns `None` for anything else so config
/// validation can report it instead of silently rendering white.
pub fn parse_color(s: &str) -> Option<Color> {
    let s = s.trim();
    let named = match s.to_ascii_lowercase().as_str() {
        "white" => Some(Color::opaque(255, 255, 255)),
        "black" => Some(Color::opaque(0, 0, 0)),
        "red" => Some(Color::opaque(255, 0, 0)),
        "green" => Some(Color::opaque(0, 128, 0)),
        "lime" => Some(Color::opaque(0, 255, 0)),
        "blue" => Some(Color::opaque(0, 0, 255)),
        "yellow" => Some(Color::opaque(255, 255, 0)),
        "orange" => Some(Color::opaque(255, 165, 0)),
        "purple" => Some(Color::opaque(128, 0, 128)),
        "pink" => Some(Color::opaque(255, 192, 203)),
        "cyan" => Some(Color::opaque(0, 255, 255)),
        "magenta" => Some(Color::opaque(255, 0, 255)),
        "gray" | "grey" => Some(Color::opaque(128, 128, 128)),
        "brown" => Some(Color::opaque(165, 42, 42)),
        _ => None,
    };
    if named.is_some() {
        return named;
    }

    let hex = s.strip_prefix('#')?;
    if !hex.bytes().all(|b| b.is_ascii_hexdigit()) {
        return None;
    }
    let byte = |i: usize| u8::from_str_radix(&hex[i..i + 2], 16).ok();
    let nibble = |i: usize| u8::from_str_radix(&hex[i..=i], 16).ok().map(|v| v * 17);
    match hex.len() {
        3 => Some(Color::opaque(nibble(0)?, nibble(1)?, nibble(2)?)),
        6 => Some(Color::opaque(byte(0)?, byte(2)?, byte(4)?)),
        8 => Some(Color {
            rgb: [byte(0)?, byte(2)?, byte(4)?],
            alpha: f32::from(byte(6)?) / 255.0,
        }),
        _ => None,
    }
}

/// Normalize caller text: CRLF/CR become `\n`, tabs become spaces, and other
/// control characters are dropped (they would render as missing-glyph boxes).
pub fn sanitize_text(text: &str) -> String {
    text.replace("\r\n", "\n")
        .chars()
        .filter_map(|c| match c {
            '\r' | '\n' => Some('\n'),
            '\t' => Some(' '),
            c if c.is_control() => None,
            c => Some(c),
        })
        .collect()
}

/// Characters in `text` the font has no glyph for (deduplicated, in order).
pub fn unsupported_chars(font: &FontArc, text: &str) -> Vec<char> {
    let mut missing = Vec::new();
    for c in text.chars() {
        if !c.is_whitespace() && font.glyph_id(c) == GlyphId(0) && !missing.contains(&c) {
            missing.push(c);
        }
    }
    missing
}

/// Vertical metrics for one font size.
#[derive(Debug, Clone, Copy)]
pub struct LineMetrics {
    /// Distance from line top to baseline.
    pub ascent: f32,
    /// Distance between consecutive baselines.
    pub line_height: f32,
}

/// Vertical metrics at `size` px. Line gap is deliberately omitted: meme
/// captions are conventionally set tight.
pub fn line_metrics(font: &FontArc, size: f32) -> LineMetrics {
    let scaled = font.as_scaled(PxScale::from(size));
    LineMetrics {
        ascent: scaled.ascent(),
        line_height: scaled.ascent() - scaled.descent(),
    }
}

/// Advance width of `text` at `size` px, including kerning.
pub fn measure(font: &FontArc, size: f32, text: &str) -> f32 {
    let scaled = font.as_scaled(PxScale::from(size));
    let mut width = 0.0;
    let mut prev: Option<GlyphId> = None;
    for c in text.chars() {
        let id = scaled.glyph_id(c);
        if let Some(p) = prev {
            width += scaled.kern(p, id);
        }
        width += scaled.h_advance(id);
        prev = Some(id);
    }
    width
}

/// Result of wrapping text at one size.
#[derive(Debug, Clone, PartialEq)]
pub struct Wrapped {
    /// Lines in drawing order.
    pub lines: Vec<String>,
    /// True if some word was wider than the area and had to be split.
    pub split_word: bool,
}

/// Greedy word wrap to `max_width` px. Explicit `\n` starts a new line.
/// A word wider than `max_width` is split between characters (and flagged via
/// [`Wrapped::split_word`]) instead of overflowing the area.
pub fn wrap(font: &FontArc, size: f32, text: &str, max_width: f32) -> Wrapped {
    let space = measure(font, size, " ");
    let mut lines = Vec::new();
    let mut split_word = false;

    for paragraph in text.split('\n') {
        let mut current = String::new();
        let mut current_width = 0.0f32;

        for word in paragraph.split_whitespace() {
            let word_width = measure(font, size, word);

            if !current.is_empty() && current_width + space + word_width <= max_width {
                current.push(' ');
                current.push_str(word);
                current_width += space + word_width;
                continue;
            }
            if !current.is_empty() {
                lines.push(std::mem::take(&mut current));
            }
            if word_width <= max_width {
                current = word.to_string();
                current_width = word_width;
                continue;
            }

            // Hard-break an over-long word into chunks that fit.
            split_word = true;
            let mut chunk = String::new();
            for c in word.chars() {
                let mut candidate = chunk.clone();
                candidate.push(c);
                if !chunk.is_empty() && measure(font, size, &candidate) > max_width {
                    lines.push(std::mem::take(&mut chunk));
                    chunk.push(c);
                } else {
                    chunk = candidate;
                }
            }
            current_width = measure(font, size, &chunk);
            current = chunk;
        }
        // Keep intentional blank lines, but not a trailing empty paragraph.
        lines.push(current);
    }
    while lines.last().is_some_and(String::is_empty) {
        lines.pop();
    }
    Wrapped { lines, split_word }
}

/// A text block laid out for a specific area.
#[derive(Debug, Clone, PartialEq)]
pub struct Layout {
    /// Chosen font size in px.
    pub font_size: f32,
    /// Wrapped lines.
    pub lines: Vec<String>,
    /// Whether the block fits the area without overflow.
    pub fits: bool,
    /// Whether a word had to be split across lines.
    pub split_word: bool,
}

/// Lay out `text` at a fixed `size` and report whether it fits a
/// `box_w` x `box_h` area (accounting for the outline on both sides).
pub fn layout_at_size(
    font: &FontArc,
    text: &str,
    size: f32,
    box_w: f32,
    box_h: f32,
    stroke: f32,
) -> Layout {
    let usable_w = (box_w - 2.0 * stroke).max(1.0);
    let wrapped = wrap(font, size, text, usable_w);
    let metrics = line_metrics(font, size);
    let block_h = wrapped.lines.len() as f32 * metrics.line_height + 2.0 * stroke;
    let widest = wrapped
        .lines
        .iter()
        .map(|l| measure(font, size, l))
        .fold(0.0f32, f32::max);
    Layout {
        font_size: size,
        fits: block_h <= box_h && widest <= usable_w,
        split_word: wrapped.split_word,
        lines: wrapped.lines,
    }
}

/// Find the largest size in `min..=max` whose layout fits the area, trying
/// sizes that keep every word intact first. Falls back to `min` (with
/// `fits == false`) when nothing fits.
pub fn fit_text(
    font: &FontArc,
    text: &str,
    box_w: f32,
    box_h: f32,
    min: i32,
    max: i32,
    stroke: f32,
) -> Layout {
    let (min, max) = (min.min(max), max.max(min));
    let mut first_fit_with_split: Option<Layout> = None;
    for size in (min..=max).rev() {
        let layout = layout_at_size(font, text, size as f32, box_w, box_h, stroke);
        if layout.fits && !layout.split_word {
            return layout;
        }
        if layout.fits && first_fit_with_split.is_none() {
            first_fit_with_split = Some(layout);
        }
    }
    first_fit_with_split
        .unwrap_or_else(|| layout_at_size(font, text, min as f32, box_w, box_h, stroke))
}

/// Visual style for a text block.
#[derive(Debug, Clone, Copy)]
pub struct TextStyle {
    /// Fill color.
    pub fill: Color,
    /// Outline color.
    pub stroke: Color,
    /// Outline radius in px (0 = none).
    pub stroke_width: f32,
    /// Horizontal alignment.
    pub align: TextAlign,
}

/// Area geometry (center + width) used for positioning.
#[derive(Debug, Clone, Copy)]
pub struct AreaRect {
    /// Horizontal center.
    pub cx: f32,
    /// Vertical center.
    pub cy: f32,
    /// Width in px.
    pub width: f32,
}

/// Draw a laid-out block, vertically centered on `rect.cy`.
pub fn draw_block(
    img: &mut RgbImage,
    font: &FontArc,
    layout: &Layout,
    rect: AreaRect,
    style: &TextStyle,
) {
    let metrics = line_metrics(font, layout.font_size);
    let block_h = layout.lines.len() as f32 * metrics.line_height;
    let top = rect.cy - block_h / 2.0;
    let left = rect.cx - rect.width / 2.0;
    let inset = style.stroke_width;

    for (i, line) in layout.lines.iter().enumerate() {
        if line.is_empty() {
            continue;
        }
        let w = measure(font, layout.font_size, line);
        let x = match style.align {
            TextAlign::Left => left + inset,
            TextAlign::Right => left + rect.width - inset - w,
            TextAlign::Center => rect.cx - w / 2.0,
        };
        let baseline = top + metrics.ascent + i as f32 * metrics.line_height;
        draw_line(
            img,
            font,
            layout.font_size,
            line,
            x.round(),
            baseline.round(),
            style,
        );
    }
}

/// Coverage mask over an image-space rectangle.
struct Mask {
    x0: i32,
    y0: i32,
    w: usize,
    h: usize,
    data: Vec<f32>,
}

impl Mask {
    fn get(&self, x: i32, y: i32) -> f32 {
        if x < 0 || y < 0 || x as usize >= self.w || y as usize >= self.h {
            return 0.0;
        }
        self.data[y as usize * self.w + x as usize]
    }
}

/// Rasterize one line (baseline-positioned at `x`, `baseline`) with outline.
fn draw_line(
    img: &mut RgbImage,
    font: &FontArc,
    size: f32,
    text: &str,
    x: f32,
    baseline: f32,
    style: &TextStyle,
) {
    let scale = PxScale::from(size);
    let scaled = font.as_scaled(scale);

    // Position glyphs (with kerning, matching `measure`).
    let mut outlined = Vec::new();
    let mut caret = x;
    let mut prev: Option<GlyphId> = None;
    for c in text.chars() {
        let id = scaled.glyph_id(c);
        if let Some(p) = prev {
            caret += scaled.kern(p, id);
        }
        let glyph = id.with_scale_and_position(scale, point(caret, baseline));
        caret += scaled.h_advance(id);
        prev = Some(id);
        if let Some(g) = font.outline_glyph(glyph) {
            outlined.push(g);
        }
    }
    if outlined.is_empty() {
        return;
    }

    // Mask covers the glyph union plus outline padding, clipped to the image.
    let pad = style.stroke_width.ceil() as i32 + 1;
    let (mut min_x, mut min_y, mut max_x, mut max_y) = (i32::MAX, i32::MAX, i32::MIN, i32::MIN);
    for g in &outlined {
        let b = g.px_bounds();
        min_x = min_x.min(b.min.x.floor() as i32);
        min_y = min_y.min(b.min.y.floor() as i32);
        max_x = max_x.max(b.max.x.ceil() as i32);
        max_y = max_y.max(b.max.y.ceil() as i32);
    }
    let (img_w, img_h) = (img.width() as i32, img.height() as i32);
    let x0 = (min_x - pad).max(-pad);
    let y0 = (min_y - pad).max(-pad);
    let x1 = (max_x + pad).min(img_w + pad);
    let y1 = (max_y + pad).min(img_h + pad);
    if x1 <= x0 || y1 <= y0 {
        return;
    }
    let (w, h) = ((x1 - x0) as usize, (y1 - y0) as usize);
    let mut mask = Mask {
        x0,
        y0,
        w,
        h,
        data: vec![0.0; w * h],
    };

    for g in &outlined {
        let b = g.px_bounds();
        let (gx0, gy0) = (b.min.x as i32, b.min.y as i32);
        g.draw(|gx, gy, cov| {
            let mx = gx0 + gx as i32 - mask.x0;
            let my = gy0 + gy as i32 - mask.y0;
            if mx >= 0 && my >= 0 && (mx as usize) < mask.w && (my as usize) < mask.h {
                let idx = my as usize * mask.w + mx as usize;
                let v = cov.clamp(0.0, 1.0);
                if v > mask.data[idx] {
                    mask.data[idx] = v;
                }
            }
        });
    }

    let outline = if style.stroke_width > 0.0 && style.stroke.alpha > 0.0 {
        Some(dilate(&mask, style.stroke_width))
    } else {
        None
    };

    let [fr, fg, fb] = style.fill.rgb;
    let [sr, sg, sb] = style.stroke.rgb;
    for my in 0..mask.h {
        let iy = mask.y0 + my as i32;
        if iy < 0 || iy >= img_h {
            continue;
        }
        for mx in 0..mask.w {
            let ix = mask.x0 + mx as i32;
            if ix < 0 || ix >= img_w {
                continue;
            }
            let idx = my * mask.w + mx;
            let fill_a = mask.data[idx] * style.fill.alpha;
            let stroke_a = outline
                .as_ref()
                .map_or(0.0, |o| o[idx] * style.stroke.alpha);
            if fill_a <= 0.0 && stroke_a <= 0.0 {
                continue;
            }
            let px = img.get_pixel_mut(ix as u32, iy as u32);
            let mut c = [f32::from(px[0]), f32::from(px[1]), f32::from(px[2])];
            if stroke_a > 0.0 {
                blend(&mut c, [sr, sg, sb], stroke_a);
            }
            if fill_a > 0.0 {
                blend(&mut c, [fr, fg, fb], fill_a);
            }
            *px = Rgb([
                c[0].round().clamp(0.0, 255.0) as u8,
                c[1].round().clamp(0.0, 255.0) as u8,
                c[2].round().clamp(0.0, 255.0) as u8,
            ]);
        }
    }
}

fn blend(dst: &mut [f32; 3], src: [u8; 3], a: f32) {
    let a = a.clamp(0.0, 1.0);
    for (d, s) in dst.iter_mut().zip(src) {
        *d = *d * (1.0 - a) + f32::from(s) * a;
    }
}

/// Soft circular dilation: each output pixel is the max of neighboring
/// coverage weighted by how far inside radius `r` the neighbor lies, which
/// yields a round, anti-aliased outline edge.
fn dilate(mask: &Mask, r: f32) -> Vec<f32> {
    let reach = r.ceil() as i32 + 1;
    let mut kernel = Vec::new();
    for dy in -reach..=reach {
        for dx in -reach..=reach {
            let dist = ((dx * dx + dy * dy) as f32).sqrt();
            let weight = (r + 0.5 - dist).clamp(0.0, 1.0);
            if weight > 0.0 {
                kernel.push((dx, dy, weight));
            }
        }
    }
    let mut out = vec![0.0f32; mask.w * mask.h];
    for y in 0..mask.h as i32 {
        for x in 0..mask.w as i32 {
            let mut best = 0.0f32;
            for &(dx, dy, weight) in &kernel {
                let v = mask.get(x + dx, y + dy) * weight;
                if v > best {
                    best = v;
                    if best >= 1.0 {
                        break;
                    }
                }
            }
            out[y as usize * mask.w + x as usize] = best;
        }
    }
    out
}

#[cfg(test)]
pub(crate) mod tests {
    use super::*;

    /// The embedded fallback font, so tests do not depend on system fonts.
    pub(crate) fn test_font() -> FontArc {
        FontArc::try_from_slice(crate::fonts::EMBEDDED_FONT).expect("embedded font parses")
    }

    #[test]
    fn parses_named_and_hex_colors() {
        assert_eq!(parse_color("white"), Some(Color::opaque(255, 255, 255)));
        assert_eq!(parse_color(" Black "), Some(Color::opaque(0, 0, 0)));
        assert_eq!(parse_color("#FF0000"), Some(Color::opaque(255, 0, 0)));
        assert_eq!(parse_color("#0f0"), Some(Color::opaque(0, 255, 0)));
        let c = parse_color("#00000080").unwrap();
        assert_eq!(c.rgb, [0, 0, 0]);
        assert!((c.alpha - 128.0 / 255.0).abs() < 1e-6);
    }

    #[test]
    fn rejects_invalid_colors() {
        for bad in ["", "#", "#12", "#GGGGGG", "notacolor", "#1234567", "#é12"] {
            assert!(parse_color(bad).is_none(), "{bad:?} should be rejected");
        }
    }

    #[test]
    fn sanitize_normalizes_whitespace_and_controls() {
        assert_eq!(sanitize_text("a\r\nb\rc\td\u{7}e"), "a\nb\nc de");
    }

    #[test]
    fn measure_scales_with_size_and_length() {
        let font = test_font();
        let small = measure(&font, 20.0, "hello");
        let big = measure(&font, 40.0, "hello");
        assert!(small > 0.0);
        assert!((big / small - 2.0).abs() < 0.05);
        assert!(measure(&font, 20.0, "hello hello") > small * 2.0);
        assert_eq!(measure(&font, 20.0, ""), 0.0);
    }

    #[test]
    fn wrap_respects_width_and_keeps_words() {
        let font = test_font();
        let text = "the quick brown fox jumps over the lazy dog";
        let max = measure(&font, 20.0, "the quick brown");
        let w = wrap(&font, 20.0, text, max);
        assert!(w.lines.len() > 1);
        assert!(!w.split_word);
        for line in &w.lines {
            assert!(
                measure(&font, 20.0, line) <= max + 0.01,
                "{line:?} too wide"
            );
        }
        assert_eq!(w.lines.join(" "), text);
    }

    #[test]
    fn wrap_honors_explicit_newlines() {
        let font = test_font();
        let w = wrap(&font, 20.0, "top line\nbottom line", 10_000.0);
        assert_eq!(w.lines, vec!["top line", "bottom line"]);
        let w = wrap(&font, 20.0, "a\n\nb\n", 10_000.0);
        assert_eq!(w.lines, vec!["a", "", "b"]);
    }

    #[test]
    fn wrap_splits_overlong_word() {
        let font = test_font();
        let max = measure(&font, 20.0, "abcd");
        let w = wrap(&font, 20.0, "abcdefghijklmnop", max);
        assert!(w.split_word);
        assert!(w.lines.len() >= 4);
        assert_eq!(w.lines.concat(), "abcdefghijklmnop");
        for line in &w.lines {
            assert!(measure(&font, 20.0, line) <= max + 0.01);
        }
    }

    #[test]
    fn fit_prefers_largest_size_that_fits() {
        let font = test_font();
        let short = fit_text(&font, "HI", 400.0, 100.0, 12, 60, 2.0);
        assert!(short.fits);
        assert_eq!(short.font_size, 60.0);

        let long = fit_text(
            &font,
            "this is a much longer caption that will need to shrink to fit",
            300.0,
            80.0,
            10,
            60,
            2.0,
        );
        assert!(long.fits);
        assert!(long.font_size < 60.0);
        // The block really fits.
        let m = line_metrics(&font, long.font_size);
        assert!(long.lines.len() as f32 * m.line_height + 4.0 <= 80.0);
    }

    #[test]
    fn fit_avoids_splitting_words_when_a_smaller_size_works() {
        let font = test_font();
        let w = measure(&font, 30.0, "Kubernetes") + 4.0;
        let layout = fit_text(&font, "Kubernetes", w, 200.0, 10, 60, 2.0);
        assert!(layout.fits);
        assert!(!layout.split_word);
        assert_eq!(layout.lines, vec!["Kubernetes"]);
    }

    #[test]
    fn fit_reports_overflow_at_minimum() {
        let font = test_font();
        let text = "word ".repeat(200);
        let layout = fit_text(&font, &text, 100.0, 30.0, 12, 20, 1.0);
        assert!(!layout.fits);
        assert_eq!(layout.font_size, 12.0);
    }

    #[test]
    fn unsupported_chars_detects_missing_glyphs() {
        let font = test_font();
        assert!(unsupported_chars(&font, "Hello, world!").is_empty());
        // Private-use code point has no glyph in DejaVu.
        assert_eq!(
            unsupported_chars(&font, "a\u{E000}\u{E000}"),
            vec!['\u{E000}']
        );
    }

    fn style(stroke_width: f32) -> TextStyle {
        TextStyle {
            fill: Color::opaque(255, 255, 255),
            stroke: Color::opaque(0, 0, 0),
            stroke_width,
            align: TextAlign::Center,
        }
    }

    #[test]
    fn draw_block_paints_fill_and_outline_inside_area() {
        let font = test_font();
        let mut img = RgbImage::from_pixel(200, 100, Rgb([128, 128, 128]));
        let layout = fit_text(&font, "MEME", 180.0, 80.0, 10, 60, 3.0);
        let rect = AreaRect {
            cx: 100.0,
            cy: 50.0,
            width: 180.0,
        };
        draw_block(&mut img, &font, &layout, rect, &style(3.0));

        let white = img.pixels().filter(|p| p.0 == [255, 255, 255]).count();
        let black = img.pixels().filter(|p| p.0 == [0, 0, 0]).count();
        assert!(white > 100, "fill should be drawn ({white})");
        assert!(black > 100, "outline should be drawn ({black})");

        // Nothing painted outside the text area's horizontal extent.
        for y in 0..100 {
            for x in [0u32, 1, 198, 199] {
                assert_eq!(img.get_pixel(x, y).0, [128, 128, 128]);
            }
        }
    }

    #[test]
    fn draw_without_stroke_has_no_outline() {
        let font = test_font();
        let mut img = RgbImage::from_pixel(200, 100, Rgb([128, 128, 128]));
        let layout = fit_text(&font, "MEME", 180.0, 80.0, 10, 60, 0.0);
        let rect = AreaRect {
            cx: 100.0,
            cy: 50.0,
            width: 180.0,
        };
        draw_block(&mut img, &font, &layout, rect, &style(0.0));
        assert_eq!(img.pixels().filter(|p| p.0 == [0, 0, 0]).count(), 0);
        assert!(img.pixels().any(|p| p.0 == [255, 255, 255]));
    }

    #[test]
    fn draw_clips_text_hanging_off_the_image() {
        let font = test_font();
        let mut img = RgbImage::from_pixel(50, 20, Rgb([0, 0, 0]));
        let layout = layout_at_size(&font, "OVERFLOWING TEXT", 40.0, 400.0, 400.0, 2.0);
        let rect = AreaRect {
            cx: 0.0,
            cy: 0.0,
            width: 400.0,
        };
        // Must not panic even though most glyphs are out of bounds.
        draw_block(&mut img, &font, &layout, rect, &style(2.0));
    }
}
