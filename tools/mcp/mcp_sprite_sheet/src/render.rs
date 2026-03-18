//! Compositing pipeline, overlay drawing, PNG encoding, base64 output.

use base64::Engine;
use image::{ImageBuffer, Rgba, RgbaImage};
use std::io::Cursor;

use crate::engine;
use crate::types::*;

/// Composite all visible layers onto a single RGBA image
pub fn composite(project: &SpriteProject) -> RgbaImage {
    let w = project.canvas.width;
    let h = project.canvas.height;
    let bg = project.canvas.background_color;

    let mut img = ImageBuffer::from_fn(w, h, |_x, _y| Rgba(bg));

    // Sort layers by z_order
    let mut sorted: Vec<&Layer> = project.layers.iter().filter(|l| l.visible).collect();
    sorted.sort_by_key(|l| l.z_order);

    for layer in sorted {
        for (&(x, y), &color_idx) in &layer.pixels {
            if x >= w || y >= h {
                continue;
            }
            let Some(rgba) = project.palette.get_color(color_idx) else {
                continue;
            };

            let src = Rgba(rgba);
            let src_a = (src.0[3] as u16 * layer.opacity as u16) / 255;
            if src_a == 0 {
                continue;
            }

            let dst = img.get_pixel(x, y);
            let blended = blend_pixel(*dst, src, src_a as u8, layer.blend_mode);
            img.put_pixel(x, y, blended);
        }
    }

    img
}

/// Composite only a specific region (for sprite rendering)
pub fn composite_region(project: &SpriteProject, rx: u32, ry: u32, rw: u32, rh: u32) -> RgbaImage {
    let full = composite(project);
    let mut region = RgbaImage::new(rw, rh);

    for dy in 0..rh {
        for dx in 0..rw {
            let sx = rx + dx;
            let sy = ry + dy;
            if sx < full.width() && sy < full.height() {
                region.put_pixel(dx, dy, *full.get_pixel(sx, sy));
            }
        }
    }

    region
}

/// Draw overlays (grid lines, bounding boxes, anchors, hitboxes) on an image
pub fn draw_overlays(
    img: &mut RgbaImage,
    project: &SpriteProject,
    opts: &OverlayOptions,
    offset_x: u32,
    offset_y: u32,
) {
    if opts.grid_lines {
        draw_grid_lines(
            img,
            &project.grid,
            project.canvas.width,
            project.canvas.height,
            offset_x,
            offset_y,
        );
    }
    if opts.bounding_boxes || opts.anchors || opts.hitboxes {
        for sprite in &project.sprites {
            let (sx, sy, sw, sh) = engine::sprite_pixel_bounds(project, sprite);
            if opts.bounding_boxes {
                draw_rect_outline(
                    img,
                    sx + offset_x,
                    sy + offset_y,
                    sw,
                    sh,
                    Rgba([0, 255, 0, 180]),
                );
            }
            if opts.anchors {
                let ax = sx + sprite.anchor_x + offset_x;
                let ay = sy + sprite.anchor_y + offset_y;
                draw_cross(img, ax, ay, 3, Rgba([255, 0, 0, 255]));
            }
            if opts.hitboxes
                && let Some(ref hb) = sprite.hitbox
            {
                draw_rect_outline(
                    img,
                    sx + hb.x + offset_x,
                    sy + hb.y + offset_y,
                    hb.width,
                    hb.height,
                    Rgba([255, 255, 0, 180]),
                );
            }
        }
    }
}

/// Scale image using nearest-neighbor interpolation
pub fn scale_nearest(img: &RgbaImage, factor: u32) -> RgbaImage {
    if factor <= 1 {
        return img.clone();
    }
    let w = img.width() * factor;
    let h = img.height() * factor;
    ImageBuffer::from_fn(w, h, |x, y| *img.get_pixel(x / factor, y / factor))
}

/// Encode an RGBA image as PNG bytes
pub fn encode_png(img: &RgbaImage) -> Result<Vec<u8>, String> {
    let mut buf = Cursor::new(Vec::new());
    img.write_to(&mut buf, image::ImageFormat::Png)
        .map_err(|e| format!("PNG encode error: {e}"))?;
    Ok(buf.into_inner())
}

/// Encode PNG to base64 string
pub fn png_to_base64(png_bytes: &[u8]) -> String {
    base64::engine::general_purpose::STANDARD.encode(png_bytes)
}

// ---------------------------------------------------------------------------
// Overlay drawing helpers
// ---------------------------------------------------------------------------

fn draw_grid_lines(
    img: &mut RgbaImage,
    grid: &Grid,
    canvas_w: u32,
    canvas_h: u32,
    ox: u32,
    oy: u32,
) {
    let color = Rgba([128, 128, 128, 100]);

    let mut x = grid.margin;
    while x <= canvas_w {
        for y in 0..canvas_h {
            put_pixel_safe(img, x + ox, y + oy, color);
        }
        x += grid.cell_width + grid.padding;
    }

    let mut y = grid.margin;
    while y <= canvas_h {
        for x in 0..canvas_w {
            put_pixel_safe(img, x + ox, y + oy, color);
        }
        y += grid.cell_height + grid.padding;
    }
}

fn draw_rect_outline(img: &mut RgbaImage, x: u32, y: u32, w: u32, h: u32, color: Rgba<u8>) {
    for dx in 0..w {
        put_pixel_safe(img, x + dx, y, color);
        put_pixel_safe(img, x + dx, y + h.saturating_sub(1), color);
    }
    for dy in 0..h {
        put_pixel_safe(img, x, y + dy, color);
        put_pixel_safe(img, x + w.saturating_sub(1), y + dy, color);
    }
}

fn draw_cross(img: &mut RgbaImage, cx: u32, cy: u32, size: u32, color: Rgba<u8>) {
    for d in 0..=size {
        put_pixel_safe(img, cx + d, cy, color);
        put_pixel_safe(img, cx.saturating_sub(d), cy, color);
        put_pixel_safe(img, cx, cy + d, color);
        put_pixel_safe(img, cx, cy.saturating_sub(d), color);
    }
}

fn put_pixel_safe(img: &mut RgbaImage, x: u32, y: u32, color: Rgba<u8>) {
    if x < img.width() && y < img.height() {
        let dst = img.get_pixel(x, y);
        let blended = alpha_blend(*dst, color);
        img.put_pixel(x, y, blended);
    }
}

fn alpha_blend(dst: Rgba<u8>, src: Rgba<u8>) -> Rgba<u8> {
    let sa = src.0[3] as u16;
    let da = dst.0[3] as u16;
    let out_a = sa + da * (255 - sa) / 255;
    if out_a == 0 {
        return Rgba([0, 0, 0, 0]);
    }
    let r = (src.0[0] as u16 * sa + dst.0[0] as u16 * da * (255 - sa) / 255) / out_a;
    let g = (src.0[1] as u16 * sa + dst.0[1] as u16 * da * (255 - sa) / 255) / out_a;
    let b = (src.0[2] as u16 * sa + dst.0[2] as u16 * da * (255 - sa) / 255) / out_a;
    Rgba([r as u8, g as u8, b as u8, out_a as u8])
}

fn blend_pixel(dst: Rgba<u8>, src: Rgba<u8>, src_alpha: u8, mode: BlendMode) -> Rgba<u8> {
    let sa = src_alpha as u16;
    let da = dst.0[3] as u16;

    let (sr, sg, sb) = match mode {
        BlendMode::Normal => (src.0[0] as u16, src.0[1] as u16, src.0[2] as u16),
        BlendMode::Multiply => (
            (src.0[0] as u16 * dst.0[0] as u16) / 255,
            (src.0[1] as u16 * dst.0[1] as u16) / 255,
            (src.0[2] as u16 * dst.0[2] as u16) / 255,
        ),
        BlendMode::Screen => (
            255 - ((255 - src.0[0] as u16) * (255 - dst.0[0] as u16)) / 255,
            255 - ((255 - src.0[1] as u16) * (255 - dst.0[1] as u16)) / 255,
            255 - ((255 - src.0[2] as u16) * (255 - dst.0[2] as u16)) / 255,
        ),
        BlendMode::Overlay => {
            fn overlay_ch(a: u8, b: u8) -> u16 {
                if a < 128 {
                    (2 * a as u16 * b as u16) / 255
                } else {
                    255 - (2 * (255 - a as u16) * (255 - b as u16)) / 255
                }
            }
            (
                overlay_ch(dst.0[0], src.0[0]),
                overlay_ch(dst.0[1], src.0[1]),
                overlay_ch(dst.0[2], src.0[2]),
            )
        },
    };

    let out_a = sa + da * (255 - sa) / 255;
    if out_a == 0 {
        return Rgba([0, 0, 0, 0]);
    }
    let r = (sr * sa + dst.0[0] as u16 * da * (255 - sa) / 255) / out_a;
    let g = (sg * sa + dst.0[1] as u16 * da * (255 - sa) / 255) / out_a;
    let b = (sb * sa + dst.0[2] as u16 * da * (255 - sa) / 255) / out_a;
    Rgba([
        r.min(255) as u8,
        g.min(255) as u8,
        b.min(255) as u8,
        out_a.min(255) as u8,
    ])
}

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

#[cfg(test)]
mod tests {
    use super::*;
    use crate::engine;

    fn test_project() -> SpriteProject {
        let mut p = engine::create_project("test", 8, 8, 8, 8, 0, 0, [0, 0, 0, 255], Some("pico8"))
            .unwrap();
        let id = engine::add_layer(&mut p, "Layer 1", None);
        engine::set_pixels(&mut p, &id, &[(0, 0, 7), (1, 1, 8)]).unwrap(); // white, red
        p
    }

    #[test]
    fn test_composite_basic() {
        let p = test_project();
        let img = composite(&p);
        assert_eq!(img.width(), 8);
        assert_eq!(img.height(), 8);
        // Pixel (0,0) should be white (pico8 index 7)
        let px = img.get_pixel(0, 0);
        assert_eq!(px.0, [255, 241, 232, 255]);
    }

    #[test]
    fn test_scale_nearest() {
        let p = test_project();
        let img = composite(&p);
        let scaled = scale_nearest(&img, 2);
        assert_eq!(scaled.width(), 16);
        assert_eq!(scaled.height(), 16);
        // Each original pixel should be 2x2
        assert_eq!(scaled.get_pixel(0, 0), scaled.get_pixel(1, 1));
    }

    #[test]
    fn test_png_encode_roundtrip() {
        let p = test_project();
        let img = composite(&p);
        let png = encode_png(&img).unwrap();
        assert!(!png.is_empty());
        let b64 = png_to_base64(&png);
        assert!(!b64.is_empty());
    }

    #[test]
    fn test_composite_region() {
        let p = test_project();
        let region = composite_region(&p, 0, 0, 4, 4);
        assert_eq!(region.width(), 4);
        assert_eq!(region.height(), 4);
    }
}
