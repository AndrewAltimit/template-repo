//! Compositing, overlays, scaling, and PNG / animated GIF encoding.

use base64::Engine;
use image::{Rgba, RgbaImage};
use std::io::Cursor;

use crate::engine;
use crate::font;
use crate::types::*;

/// Maximum width/height of any rendered output image (after scaling).
pub const MAX_OUTPUT_DIM: u32 = 16_384;

/// Maximum pixel count of any rendered output image (after scaling).
pub const MAX_OUTPUT_PIXELS: u64 = 64 * 1024 * 1024;

/// Maximum nearest-neighbor scale factor.
pub const MAX_SCALE: u32 = 64;

/// Validate that a `w x h` image scaled by `scale` stays within output limits.
pub fn check_output_size(w: u32, h: u32, scale: u32) -> Result<(), String> {
    if scale == 0 || scale > MAX_SCALE {
        return Err(format!("scale must be between 1 and {MAX_SCALE}"));
    }
    let (sw, sh) = (
        u64::from(w) * u64::from(scale),
        u64::from(h) * u64::from(scale),
    );
    if sw == 0 || sh == 0 {
        return Err("Nothing to render: output would be empty".into());
    }
    if sw > u64::from(MAX_OUTPUT_DIM)
        || sh > u64::from(MAX_OUTPUT_DIM)
        || sw * sh > MAX_OUTPUT_PIXELS
    {
        return Err(format!(
            "Output {sw}x{sh} exceeds limits ({MAX_OUTPUT_DIM} px per side, \
             {MAX_OUTPUT_PIXELS} px total); lower the scale or render a region"
        ));
    }
    Ok(())
}

/// Composite all visible layers over the whole canvas.
pub fn composite(p: &SpriteProject) -> RgbaImage {
    composite_region(p, 0, 0, p.canvas.width, p.canvas.height)
}

/// Composite visible layers for a canvas region.
///
/// The region may extend beyond the canvas; out-of-canvas pixels are fully
/// transparent (no background). Layers are drawn in ascending `z_order`
/// (ties keep list order). Only pixels inside the region are touched.
pub fn composite_region(p: &SpriteProject, rx: u32, ry: u32, rw: u32, rh: u32) -> RgbaImage {
    let (cw, ch) = (p.canvas.width, p.canvas.height);
    let bg = Rgba(p.canvas.background_color);
    let mut img = RgbaImage::from_fn(rw, rh, |x, y| {
        let (cx, cy) = (u64::from(rx) + u64::from(x), u64::from(ry) + u64::from(y));
        if cx < u64::from(cw) && cy < u64::from(ch) {
            bg
        } else {
            Rgba([0, 0, 0, 0])
        }
    });
    let lut = p.palette.lut();
    let mut layers: Vec<&Layer> = p
        .layers
        .iter()
        .filter(|l| l.visible && l.opacity > 0)
        .collect();
    layers.sort_by_key(|l| l.z_order);
    let (rx1, ry1) = (u64::from(rx) + u64::from(rw), u64::from(ry) + u64::from(rh));
    for layer in layers {
        for (&(x, y), &ci) in layer.pixels.iter() {
            if x >= cw || y >= ch {
                continue;
            }
            let (xu, yu) = (u64::from(x), u64::from(y));
            if xu < u64::from(rx) || yu < u64::from(ry) || xu >= rx1 || yu >= ry1 {
                continue;
            }
            let Some(src) = lut[ci as usize] else {
                continue;
            };
            let (ix, iy) = (x - rx, y - ry);
            let dst = img.get_pixel(ix, iy).0;
            img.put_pixel(
                ix,
                iy,
                Rgba(blend(dst, src, layer.opacity, layer.blend_mode)),
            );
        }
    }
    img
}

/// Copy a `w x h` window at `(x, y)` out of `img`; parts outside `img` are
/// transparent, so the result always has exactly the requested size.
pub fn crop_padded(img: &RgbaImage, x: u32, y: u32, w: u32, h: u32) -> RgbaImage {
    RgbaImage::from_fn(w, h, |dx, dy| {
        match (x.checked_add(dx), y.checked_add(dy)) {
            (Some(sx), Some(sy)) if sx < img.width() && sy < img.height() => *img.get_pixel(sx, sy),
            _ => Rgba([0, 0, 0, 0]),
        }
    })
}

/// W3C-style separable blend followed by source-over compositing.
///
/// `opacity` scales the source alpha. Computed in f32, so partially
/// transparent layers over partially transparent backdrops cannot overflow.
pub fn blend(dst: [u8; 4], src: [u8; 4], opacity: u8, mode: BlendMode) -> [u8; 4] {
    let sa = f32::from(src[3]) / 255.0 * f32::from(opacity) / 255.0;
    if sa <= 0.0 {
        return dst;
    }
    let da = f32::from(dst[3]) / 255.0;
    let out_a = sa + da * (1.0 - sa);
    let mut out = [0u8; 4];
    for i in 0..3 {
        let cs = f32::from(src[i]) / 255.0;
        let cb = f32::from(dst[i]) / 255.0;
        let b = match mode {
            BlendMode::Normal => cs,
            BlendMode::Multiply => cs * cb,
            BlendMode::Screen => cs + cb - cs * cb,
            BlendMode::Overlay => {
                if cb <= 0.5 {
                    2.0 * cs * cb
                } else {
                    1.0 - 2.0 * (1.0 - cs) * (1.0 - cb)
                }
            },
        };
        // Blend result only applies where the backdrop exists.
        let mixed = (1.0 - da) * cs + da * b;
        let premul = sa * mixed + da * cb * (1.0 - sa);
        let c = if out_a > 0.0 { premul / out_a } else { 0.0 };
        out[i] = (c * 255.0).round().clamp(0.0, 255.0) as u8;
    }
    out[3] = (out_a * 255.0).round().clamp(0.0, 255.0) as u8;
    out
}

/// Scale an image by an integer factor with nearest-neighbor sampling.
/// Callers must validate the size with [`check_output_size`] first.
pub fn scale_nearest(img: &RgbaImage, factor: u32) -> RgbaImage {
    if factor <= 1 {
        return img.clone();
    }
    RgbaImage::from_fn(img.width() * factor, img.height() * factor, |x, y| {
        *img.get_pixel(x / factor, y / factor)
    })
}

/// Draws overlays on an already-scaled image.
///
/// `origin` is the canvas coordinate shown at image pixel (0, 0) and `scale`
/// the factor the image was scaled by, so overlays line up for regions and
/// stay one output pixel thick at any zoom.
pub fn draw_overlays(
    img: &mut RgbaImage,
    p: &SpriteProject,
    opts: &OverlayOptions,
    origin: (i64, i64),
    scale: u32,
) {
    let s = i64::from(scale.max(1));
    let to_img = |cx: i64, cy: i64| ((cx - origin.0) * s, (cy - origin.1) * s);
    if opts.grid_lines {
        let color = Rgba([128, 128, 128, 110]);
        let g = &p.grid;
        let (cw, ch) = (i64::from(p.canvas.width), i64::from(p.canvas.height));
        let step_x = i64::from(g.cell_width) + i64::from(g.padding);
        let step_y = i64::from(g.cell_height) + i64::from(g.padding);
        let (top, bottom) = (to_img(0, 0).1, to_img(0, ch).1 - 1);
        let (left, right) = (to_img(0, 0).0, to_img(cw, 0).0 - 1);
        let mut x = i64::from(g.margin);
        while x <= cw {
            for edge in [x, x + i64::from(g.cell_width)] {
                if edge <= cw {
                    let ix = to_img(edge, 0).0.min(to_img(cw, 0).0 - 1);
                    vline(img, ix, top, bottom, color);
                }
            }
            x += step_x;
        }
        let mut y = i64::from(g.margin);
        while y <= ch {
            for edge in [y, y + i64::from(g.cell_height)] {
                if edge <= ch {
                    let iy = to_img(0, edge).1.min(to_img(0, ch).1 - 1);
                    hline(img, left, right, iy, color);
                }
            }
            y += step_y;
        }
    }
    for sprite in &p.sprites {
        let (sx, sy, sw, sh) = engine::sprite_pixel_bounds(p, sprite);
        let (sx, sy, sw, sh) = (i64::from(sx), i64::from(sy), i64::from(sw), i64::from(sh));
        let (ix, iy) = to_img(sx, sy);
        if opts.bounding_boxes {
            rect_outline(img, ix, iy, sw * s, sh * s, Rgba([0, 255, 0, 200]));
        }
        if opts.hitboxes
            && let Some(hb) = &sprite.hitbox
        {
            let (hx, hy) = to_img(sx + i64::from(hb.x), sy + i64::from(hb.y));
            rect_outline(
                img,
                hx,
                hy,
                i64::from(hb.width) * s,
                i64::from(hb.height) * s,
                Rgba([255, 255, 0, 200]),
            );
        }
        if opts.anchors {
            let (ax, ay) = to_img(
                sx + i64::from(sprite.anchor_x),
                sy + i64::from(sprite.anchor_y),
            );
            let arm = (s * 2).max(3);
            let red = Rgba([255, 0, 0, 255]);
            hline(img, ax - arm, ax + arm, ay, red);
            vline(img, ax, ay - arm, ay + arm, red);
        }
        if opts.sprite_names {
            let size = (scale / 4).max(1);
            font::draw_text(img, &sprite.name, ix + 1, iy + 1, size);
        }
    }
}

fn put(img: &mut RgbaImage, x: i64, y: i64, color: Rgba<u8>) {
    if x >= 0 && y >= 0 && x < i64::from(img.width()) && y < i64::from(img.height()) {
        let (x, y) = (x as u32, y as u32);
        let dst = img.get_pixel(x, y).0;
        img.put_pixel(x, y, Rgba(blend(dst, color.0, 255, BlendMode::Normal)));
    }
}

/// Put a pixel, clipped to the image (used by the font renderer).
pub(crate) fn put_pixel_clipped(img: &mut RgbaImage, x: i64, y: i64, color: Rgba<u8>) {
    put(img, x, y, color);
}

fn hline(img: &mut RgbaImage, x0: i64, x1: i64, y: i64, color: Rgba<u8>) {
    let lo = x0.max(0);
    let hi = x1.min(i64::from(img.width()) - 1);
    for x in lo..=hi {
        put(img, x, y, color);
    }
}

fn vline(img: &mut RgbaImage, x: i64, y0: i64, y1: i64, color: Rgba<u8>) {
    let lo = y0.max(0);
    let hi = y1.min(i64::from(img.height()) - 1);
    for y in lo..=hi {
        put(img, x, y, color);
    }
}

fn rect_outline(img: &mut RgbaImage, x: i64, y: i64, w: i64, h: i64, color: Rgba<u8>) {
    if w <= 0 || h <= 0 {
        return;
    }
    hline(img, x, x + w - 1, y, color);
    if h > 1 {
        hline(img, x, x + w - 1, y + h - 1, color);
    }
    if h > 2 {
        vline(img, x, y + 1, y + h - 2, color);
        if w > 1 {
            vline(img, x + w - 1, y + 1, y + h - 2, color);
        }
    }
}

/// Encode an RGBA image as PNG bytes.
pub fn encode_png(img: &RgbaImage) -> Result<Vec<u8>, String> {
    let mut buf = Cursor::new(Vec::new());
    img.write_to(&mut buf, image::ImageFormat::Png)
        .map_err(|e| format!("PNG encode error: {e}"))?;
    Ok(buf.into_inner())
}

/// Encode frames as an animated GIF.
///
/// `frames` pairs each image with its display duration in milliseconds.
/// GIF delays have 10 ms resolution and many viewers clamp delays below
/// 20 ms, so very short durations may play slower than requested.
/// Pixels with alpha below 128 become transparent (GIF has 1-bit alpha).
pub fn encode_gif(frames: Vec<(RgbaImage, u32)>, repeat_forever: bool) -> Result<Vec<u8>, String> {
    use image::codecs::gif::{GifEncoder, Repeat};
    use image::{Delay, Frame};
    let mut buf = Vec::new();
    {
        let mut enc = GifEncoder::new_with_speed(&mut buf, 10);
        enc.set_repeat(if repeat_forever {
            Repeat::Infinite
        } else {
            Repeat::Finite(0)
        })
        .map_err(|e| format!("GIF encode error: {e}"))?;
        for (mut img, ms) in frames {
            for p in img.pixels_mut() {
                p.0[3] = if p.0[3] >= 128 { 255 } else { 0 };
            }
            let delay = Delay::from_numer_denom_ms(ms.max(10), 1);
            enc.encode_frame(Frame::from_parts(img, 0, 0, delay))
                .map_err(|e| format!("GIF encode error: {e}"))?;
        }
    }
    Ok(buf)
}

/// Base64-encode bytes (standard alphabet, padded).
pub fn to_base64(bytes: &[u8]) -> String {
    base64::engine::general_purpose::STANDARD.encode(bytes)
}

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

#[cfg(test)]
mod tests {
    use super::*;
    use crate::engine;

    fn project() -> SpriteProject {
        let grid = Grid {
            cell_width: 4,
            cell_height: 4,
            padding: 0,
            margin: 0,
        };
        let mut p = engine::create_project("t", 8, 8, grid, [0, 0, 0, 255], Some("pico8")).unwrap();
        let id = engine::add_layer(&mut p, "L", None);
        engine::set_pixels(&mut p, &id, &[(0, 0, 7), (1, 1, 8)]).unwrap();
        p
    }

    #[test]
    fn composite_basic() {
        let img = composite(&project());
        assert_eq!((img.width(), img.height()), (8, 8));
        assert_eq!(img.get_pixel(0, 0).0, [255, 241, 232, 255]);
        assert_eq!(img.get_pixel(5, 5).0, [0, 0, 0, 255]);
    }

    #[test]
    fn composite_region_offsets_and_out_of_canvas() {
        let p = project();
        let r = composite_region(&p, 1, 1, 8, 8);
        assert_eq!(r.get_pixel(0, 0).0, [255, 0, 77, 255]); // (1,1) red
        assert_eq!(
            r.get_pixel(7, 7).0,
            [0, 0, 0, 0],
            "outside canvas is transparent"
        );
    }

    #[test]
    fn z_order_and_hidden_layers() {
        let mut p = project();
        let top = engine::add_layer(&mut p, "top", None);
        engine::set_pixels(&mut p, &top, &[(0, 0, 12)]).unwrap();
        assert_eq!(composite(&p).get_pixel(0, 0).0, [41, 173, 255, 255]);
        p.layers[1].z_order = -5;
        assert_eq!(composite(&p).get_pixel(0, 0).0, [255, 241, 232, 255]);
        p.layers[0].visible = false;
        assert_eq!(composite(&p).get_pixel(0, 0).0, [41, 173, 255, 255]);
    }

    #[test]
    fn blend_half_opacity_over_opaque_does_not_overflow() {
        // Previously computed in u16 and wrapped for these inputs.
        let out = blend([255, 255, 255, 255], [0, 0, 0, 255], 128, BlendMode::Normal);
        assert_eq!(out[3], 255);
        assert!((out[0] as i32 - 127).abs() <= 1, "{out:?}");
    }

    #[test]
    fn blend_modes() {
        let d = [200, 100, 50, 255];
        assert_eq!(blend(d, [255, 255, 255, 255], 255, BlendMode::Multiply), d);
        assert_eq!(blend(d, [0, 0, 0, 255], 255, BlendMode::Screen), d);
        assert_eq!(
            blend([0, 0, 0, 0], [10, 20, 30, 255], 255, BlendMode::Multiply),
            [10, 20, 30, 255],
            "blend modes do not apply over empty backdrop"
        );
        assert_eq!(blend(d, [9, 9, 9, 0], 255, BlendMode::Normal), d);
    }

    #[test]
    fn scale_and_output_limits() {
        let img = composite(&project());
        let s = scale_nearest(&img, 3);
        assert_eq!(s.width(), 24);
        assert_eq!(s.get_pixel(0, 0), s.get_pixel(2, 2));
        assert!(check_output_size(8, 8, 0).is_err());
        assert!(check_output_size(8, 8, 65).is_err());
        assert!(check_output_size(4096, 4096, 8).is_err());
        assert!(check_output_size(8, 8, 8).is_ok());
    }

    #[test]
    fn overlays_do_not_panic_and_draw() {
        let mut p = project();
        engine::define_sprite(
            &mut p,
            SpriteDef {
                id: String::new(),
                name: "hero".into(),
                grid_x: 1,
                grid_y: 1,
                width_cells: 1,
                height_cells: 1,
                anchor_x: 2,
                anchor_y: 4,
                hitbox: Some(HitboxRect {
                    x: 0,
                    y: 0,
                    width: 100,
                    height: 100,
                }),
                tags: vec![],
            },
        )
        .unwrap();
        let opts = OverlayOptions {
            grid_lines: true,
            bounding_boxes: true,
            anchors: true,
            hitboxes: true,
            sprite_names: true,
        };
        let base = scale_nearest(&composite(&p), 4);
        let mut img = base.clone();
        draw_overlays(&mut img, &p, &opts, (0, 0), 4);
        assert_ne!(img, base);
        // Region render with an origin inside the canvas.
        let mut region = composite_region(&p, 4, 4, 4, 4);
        draw_overlays(&mut region, &p, &opts, (4, 4), 1);
        // The bounding box starts at image (0,0) for a sprite at canvas (4,4).
        assert_ne!(region.get_pixel(0, 0).0, [0, 0, 0, 255]);
    }

    #[test]
    fn png_and_gif_encode() {
        let img = composite(&project());
        let png = encode_png(&img).unwrap();
        assert_eq!(&png[1..4], b"PNG");
        let gif = encode_gif(vec![(img.clone(), 100), (img, 5)], true).unwrap();
        assert_eq!(&gif[0..3], b"GIF");
        assert!(!to_base64(&png).is_empty());
    }
}
