//! Reference-image import: decoding with limits, background removal,
//! nearest-neighbor downscaling, palette extraction/mapping, and
//! anti-aliasing fringe trimming.

use std::collections::HashMap;
use std::path::Path;

use image::RgbaImage;

use crate::types::{Palette, PaletteColor, PixelMap};

/// Maximum accepted source image dimension (before resizing).
pub const MAX_SOURCE_DIM: u32 = 16_384;

/// Maximum decoder allocation for a source image.
pub const MAX_SOURCE_ALLOC: u64 = 512 * 1024 * 1024;

/// Decode an image file with dimension and allocation limits (guards against
/// decompression bombs). Blocking: call from `spawn_blocking`.
pub fn load_image(path: &Path) -> Result<RgbaImage, String> {
    let meta = std::fs::metadata(path)
        .map_err(|e| format!("Cannot read image '{}': {e}", path.display()))?;
    if !meta.is_file() {
        return Err(format!("'{}' is not a file", path.display()));
    }
    let mut reader = image::ImageReader::open(path)
        .map_err(|e| format!("Cannot open image '{}': {e}", path.display()))?
        .with_guessed_format()
        .map_err(|e| format!("Cannot detect format of '{}': {e}", path.display()))?;
    let mut limits = image::Limits::default();
    limits.max_image_width = Some(MAX_SOURCE_DIM);
    limits.max_image_height = Some(MAX_SOURCE_DIM);
    limits.max_alloc = Some(MAX_SOURCE_ALLOC);
    reader.limits(limits);
    let img = reader
        .decode()
        .map_err(|e| format!("Failed to decode image '{}': {e}", path.display()))?;
    Ok(img.to_rgba8())
}

/// Make every pixel within `tolerance` (per channel) of `bg` fully transparent.
/// Returns the number of pixels cleared.
pub fn remove_background(img: &mut RgbaImage, bg: [u8; 3], tolerance: u8) -> usize {
    let mut n = 0;
    for p in img.pixels_mut() {
        let close = (0..3).all(|i| p.0[i].abs_diff(bg[i]) <= tolerance);
        if close && p.0[3] != 0 {
            p.0[3] = 0;
            n += 1;
        }
    }
    n
}

/// Downscale with nearest-neighbor to fit within the max dimensions,
/// preserving aspect ratio. Never upscales.
pub fn resize_to_fit(img: RgbaImage, max_w: Option<u32>, max_h: Option<u32>) -> RgbaImage {
    let (w, h) = (img.width(), img.height());
    let sw = max_w
        .filter(|&m| w > m)
        .map(|m| f64::from(m) / f64::from(w));
    let sh = max_h
        .filter(|&m| h > m)
        .map(|m| f64::from(m) / f64::from(h));
    let scale = match (sw, sh) {
        (Some(a), Some(b)) => Some(a.min(b)),
        (Some(s), None) | (None, Some(s)) => Some(s),
        (None, None) => None,
    };
    match scale {
        Some(s) => {
            let nw = (f64::from(w) * s).round().max(1.0) as u32;
            let nh = (f64::from(h) * s).round().max(1.0) as u32;
            image::imageops::resize(&img, nw, nh, image::imageops::FilterType::Nearest)
        },
        None => img,
    }
}

fn color_distance_rgb(a: [u8; 4], b: [u8; 4]) -> u32 {
    (0..3)
        .map(|i| {
            let d = i32::from(a[i]) - i32::from(b[i]);
            (d * d) as u32
        })
        .sum()
}

/// Nearest non-transparent palette color (RGB distance).
pub fn nearest_palette_index(rgba: [u8; 4], palette: &Palette) -> Option<u8> {
    palette
        .colors
        .iter()
        .filter(|c| c.rgba[3] > 0)
        .min_by_key(|c| color_distance_rgb(rgba, c.rgba))
        .map(|c| c.index)
}

/// Extract up to `max_colors` of the most frequent opaque-enough colors.
///
/// Ties are broken by color value so the result is deterministic.
pub fn extract_palette(img: &RgbaImage, max_colors: usize, alpha_threshold: u8) -> Palette {
    let mut freq: HashMap<[u8; 4], usize> = HashMap::new();
    for p in img.pixels() {
        if p.0[3] >= alpha_threshold.max(1) {
            *freq.entry(p.0).or_insert(0) += 1;
        }
    }
    let mut colors: Vec<([u8; 4], usize)> = freq.into_iter().collect();
    colors.sort_by(|a, b| b.1.cmp(&a.1).then(a.0.cmp(&b.0)));
    colors.truncate(max_colors.clamp(1, 256));
    Palette {
        name: "extracted".to_string(),
        colors: colors
            .iter()
            .enumerate()
            .map(|(i, (rgba, _))| PaletteColor {
                index: i as u8,
                name: format!("color_{i}"),
                rgba: *rgba,
            })
            .collect(),
        enforce: false,
    }
}

/// Map every sufficiently opaque pixel to its nearest palette color.
///
/// Nearest-color lookups are memoized per distinct source color, which makes
/// photos and gradients (few distinct colors relative to pixel count) cheap.
pub fn map_to_palette(img: &RgbaImage, palette: &Palette, alpha_threshold: u8) -> PixelMap {
    let mut cache: HashMap<[u8; 4], Option<u8>> = HashMap::new();
    let mut pixels = PixelMap::new();
    for (x, y, p) in img.enumerate_pixels() {
        if p.0[3] < alpha_threshold.max(1) {
            continue;
        }
        let idx = *cache
            .entry(p.0)
            .or_insert_with(|| nearest_palette_index(p.0, palette));
        if let Some(i) = idx {
            pixels.insert((x, y), i);
        }
    }
    pixels
}

/// Perceived luminance (BT.601).
fn luma(rgba: [u8; 4]) -> u32 {
    (u32::from(rgba[0]) * 299 + u32::from(rgba[1]) * 587 + u32::from(rgba[2]) * 114) / 1000
}

/// Remove edge pixels that look like anti-aliasing fringe.
///
/// A pixel is an *edge* pixel when at least one 4-neighbor is empty or off
/// canvas. An edge pixel is removed when either:
/// 1. its luminance is `>= luma_threshold` (near-white fringe), or
/// 2. it is brighter than the average of its filled neighbors by more than a
///    delta (`luma_threshold` itself when it is below 128, otherwise 25), or
///    it has no filled neighbors at all (isolated speck).
///
/// Each pass exposes new edges; iteration stops early when nothing changes.
/// Note that rule 2 also removes deliberate isolated single pixels, so this
/// is intended for imported/traced art, not hand-placed pixel art.
pub fn trim_border_fringe(
    pixels: &mut PixelMap,
    palette: &Palette,
    luma_threshold: u8,
    passes: u32,
    canvas_w: u32,
    canvas_h: u32,
) -> usize {
    let lut = palette.lut();
    let delta = if luma_threshold < 128 {
        u32::from(luma_threshold)
    } else {
        25
    };
    let mut total = 0;
    for _ in 0..passes {
        let to_remove: Vec<(u32, u32)> = pixels
            .iter()
            .filter(|&(&(x, y), &ci)| {
                let mut neighbor_luma = Vec::with_capacity(4);
                let mut has_empty = false;
                for (dx, dy) in [(0i64, -1i64), (0, 1), (-1, 0), (1, 0)] {
                    let nx = i64::from(x) + dx;
                    let ny = i64::from(y) + dy;
                    if nx < 0 || ny < 0 || nx >= i64::from(canvas_w) || ny >= i64::from(canvas_h) {
                        has_empty = true;
                        continue;
                    }
                    match pixels.get(&(nx as u32, ny as u32)) {
                        Some(&n) => {
                            if let Some(c) = lut[n as usize] {
                                neighbor_luma.push(luma(c));
                            }
                        },
                        None => has_empty = true,
                    }
                }
                if !has_empty {
                    return false;
                }
                let Some(rgba) = lut[ci as usize] else {
                    return false;
                };
                let me = luma(rgba);
                if me >= u32::from(luma_threshold) || neighbor_luma.is_empty() {
                    return true;
                }
                let avg = neighbor_luma.iter().sum::<u32>() / neighbor_luma.len() as u32;
                me > avg + delta
            })
            .map(|(&k, _)| k)
            .collect();
        if to_remove.is_empty() {
            break;
        }
        total += to_remove.len();
        for k in &to_remove {
            pixels.remove(k);
        }
    }
    total
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::palette;
    use image::Rgba;

    #[test]
    fn nearest_color_prefers_closest_opaque() {
        let p = palette::pico8();
        assert_eq!(nearest_palette_index([250, 0, 70, 255], &p), Some(8)); // red
        assert_eq!(nearest_palette_index([0, 0, 0, 255], &p), Some(0));
    }

    #[test]
    fn extract_palette_orders_by_frequency() {
        let mut img = RgbaImage::from_pixel(4, 1, Rgba([10, 10, 10, 255]));
        img.put_pixel(0, 0, Rgba([200, 0, 0, 255]));
        let pal = extract_palette(&img, 8, 128);
        assert_eq!(pal.colors.len(), 2);
        assert_eq!(pal.colors[0].rgba, [10, 10, 10, 255]);
        let pal = extract_palette(&img, 1, 128);
        assert_eq!(pal.colors.len(), 1);
    }

    #[test]
    fn map_to_palette_skips_transparent() {
        let mut img = RgbaImage::from_pixel(2, 2, Rgba([255, 255, 255, 255]));
        img.put_pixel(1, 1, Rgba([0, 0, 0, 0]));
        let pal = palette::pico8();
        let px = map_to_palette(&img, &pal, 128);
        assert_eq!(px.len(), 3);
        assert_eq!(px.get(&(0, 0)), Some(&7)); // white
    }

    #[test]
    fn background_removal_and_resize() {
        let mut img = RgbaImage::from_pixel(8, 4, Rgba([250, 250, 250, 255]));
        img.put_pixel(0, 0, Rgba([0, 0, 0, 255]));
        assert_eq!(remove_background(&mut img, [255, 255, 255], 10), 31);
        let small = resize_to_fit(img, Some(4), None);
        assert_eq!((small.width(), small.height()), (4, 2));
        let same = resize_to_fit(RgbaImage::new(3, 3), Some(10), Some(10));
        assert_eq!(same.width(), 3, "never upscales");
    }

    #[test]
    fn trim_removes_bright_edge_keeps_interior() {
        let pal = palette::pico8();
        // 3x3 dark block with a white pixel on its right edge.
        let mut px = PixelMap::new();
        for y in 0..3 {
            for x in 0..3 {
                px.insert((x + 1, y + 1), 1);
            }
        }
        px.insert((4, 2), 7); // white edge pixel
        let removed = trim_border_fringe(&mut px, &pal, 200, 1, 8, 8);
        assert_eq!(removed, 1);
        assert!(!px.contains_key(&(4, 2)));
        assert!(px.contains_key(&(2, 2)));
    }

    #[test]
    fn load_image_reports_missing_file() {
        let e = load_image(Path::new("/definitely/not/here.png")).unwrap_err();
        assert!(e.contains("Cannot read image"), "{e}");
    }
}
