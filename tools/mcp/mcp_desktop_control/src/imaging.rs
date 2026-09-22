//! Pixel conversion, downscaling and PNG encoding for screenshots.
//!
//! Backends hand over raw framebuffer bytes; everything after that (format
//! conversion, resizing, encoding) is pure and unit-tested here.

use image::{ImageEncoder, RgbaImage, imageops::FilterType};

/// Byte order of a 32-bit-per-pixel framebuffer.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum PixelLayout {
    /// Bytes are `B, G, R, X` (X11 LSBFirst servers, Win32 DIBs).
    Bgrx,
    /// Bytes are `X, R, G, B` (X11 MSBFirst servers).
    #[cfg_attr(not(target_os = "linux"), allow(dead_code))]
    Xrgb,
}

/// Convert a 32bpp framebuffer into an opaque RGBA image.
///
/// `stride` is the number of bytes per row (>= `width * 4`). The fourth byte
/// is always ignored and alpha forced to 255: screen pixels are opaque, and
/// depth-32 visuals often carry garbage (zero) alpha, which would otherwise
/// produce fully transparent PNGs.
#[cfg_attr(not(any(target_os = "linux", windows)), allow(dead_code))]
pub fn framebuffer_to_rgba(
    data: &[u8],
    width: u32,
    height: u32,
    stride: usize,
    layout: PixelLayout,
) -> Result<RgbaImage, String> {
    if width == 0 || height == 0 {
        return Err("Image has zero size".to_string());
    }
    let row_bytes = usize::try_from(width)
        .ok()
        .and_then(|w| w.checked_mul(4))
        .ok_or("Image too wide")?;
    if stride < row_bytes {
        return Err(format!(
            "Invalid stride {stride} for width {width} (need at least {row_bytes})"
        ));
    }
    let rows = usize::try_from(height).map_err(|_| "Image too tall")?;
    let needed = stride
        .checked_mul(rows - 1)
        .and_then(|n| n.checked_add(row_bytes))
        .ok_or("Image too large")?;
    if data.len() < needed {
        return Err(format!(
            "Framebuffer too small: got {} bytes, expected at least {needed}",
            data.len()
        ));
    }

    let mut out = Vec::with_capacity(row_bytes * rows);
    for row in data.chunks(stride).take(rows) {
        let (pixels, _) = row[..row_bytes].as_chunks::<4>();
        for &[p0, p1, p2, p3] in pixels {
            let (r, g, b) = match layout {
                PixelLayout::Bgrx => (p2, p1, p0),
                PixelLayout::Xrgb => (p1, p2, p3),
            };
            out.extend_from_slice(&[r, g, b, 255]);
        }
    }
    RgbaImage::from_raw(width, height, out).ok_or_else(|| "Pixel buffer size mismatch".to_string())
}

/// Downscale so that neither side exceeds `max_dimension`, preserving the
/// aspect ratio. Images already within bounds are returned unchanged.
pub fn downscale(img: RgbaImage, max_dimension: u32) -> RgbaImage {
    let (w, h) = img.dimensions();
    let max = max_dimension.max(1);
    if w <= max && h <= max {
        return img;
    }
    let scale = f64::from(max) / f64::from(w.max(h));
    // Rounded values are bounded by `max`, so the casts cannot truncate.
    let nw = ((f64::from(w) * scale).round() as u32).clamp(1, max);
    let nh = ((f64::from(h) * scale).round() as u32).clamp(1, max);
    image::imageops::resize(&img, nw, nh, FilterType::Triangle)
}

/// Encode an RGBA image as PNG.
pub fn encode_png(img: &RgbaImage) -> Result<Vec<u8>, String> {
    let mut png = Vec::new();
    image::codecs::png::PngEncoder::new(&mut png)
        .write_image(
            img.as_raw(),
            img.width(),
            img.height(),
            image::ExtendedColorType::Rgba8,
        )
        .map_err(|e| format!("PNG encoding failed: {e}"))?;
    Ok(png)
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn converts_bgrx_with_padding_and_forces_opaque_alpha() {
        // 2x2 image, stride 12 (4 bytes of row padding).
        let data = [
            1, 2, 3, 0, 4, 5, 6, 0, 0xEE, 0xEE, 0xEE, 0xEE, //
            7, 8, 9, 0, 10, 11, 12, 0, 0xEE, 0xEE, 0xEE, 0xEE,
        ];
        let img = framebuffer_to_rgba(&data, 2, 2, 12, PixelLayout::Bgrx).unwrap();
        assert_eq!(img.get_pixel(0, 0).0, [3, 2, 1, 255]);
        assert_eq!(img.get_pixel(1, 0).0, [6, 5, 4, 255]);
        assert_eq!(img.get_pixel(0, 1).0, [9, 8, 7, 255]);
        assert_eq!(img.get_pixel(1, 1).0, [12, 11, 10, 255]);
    }

    #[test]
    fn converts_xrgb() {
        let data = [0, 10, 20, 30];
        let img = framebuffer_to_rgba(&data, 1, 1, 4, PixelLayout::Xrgb).unwrap();
        assert_eq!(img.get_pixel(0, 0).0, [10, 20, 30, 255]);
    }

    #[test]
    fn last_row_may_omit_padding() {
        // X servers may not pad the final row; only row_bytes are required.
        let data = [1, 2, 3, 0, 0, 0, 0, 0, 4, 5, 6, 0];
        let img = framebuffer_to_rgba(&data, 1, 2, 8, PixelLayout::Bgrx).unwrap();
        assert_eq!(img.get_pixel(0, 1).0, [6, 5, 4, 255]);
    }

    #[test]
    fn rejects_bad_buffers() {
        assert!(framebuffer_to_rgba(&[0; 4], 0, 1, 4, PixelLayout::Bgrx).is_err());
        assert!(framebuffer_to_rgba(&[0; 4], 2, 1, 4, PixelLayout::Bgrx).is_err());
        assert!(framebuffer_to_rgba(&[0; 7], 1, 2, 4, PixelLayout::Bgrx).is_err());
    }

    #[test]
    fn downscale_preserves_aspect_ratio() {
        let img = RgbaImage::new(400, 100);
        let small = downscale(img, 200);
        assert_eq!(small.dimensions(), (200, 50));

        let tall = downscale(RgbaImage::new(10, 1000), 100);
        assert_eq!(tall.dimensions(), (1, 100));

        let unchanged = downscale(RgbaImage::new(50, 40), 100);
        assert_eq!(unchanged.dimensions(), (50, 40));
    }

    #[test]
    fn png_round_trip() {
        let mut img = RgbaImage::new(3, 2);
        img.put_pixel(2, 1, image::Rgba([9, 8, 7, 255]));
        let png = encode_png(&img).unwrap();
        assert_eq!(&png[..8], b"\x89PNG\r\n\x1a\n");
        let decoded = image::load_from_memory(&png).unwrap().to_rgba8();
        assert_eq!(decoded.dimensions(), (3, 2));
        assert_eq!(decoded.get_pixel(2, 1).0, [9, 8, 7, 255]);
    }
}
