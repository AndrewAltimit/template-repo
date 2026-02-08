//! Procedural wallpaper generation.
//!
//! Generates PSIX-style gradient wallpapers as raw RGBA pixel buffers.
//! No external PNG files needed -- keeps CI clean and the binary self-contained.

/// Generate a vibrant gradient wallpaper similar to PSIX's green/yellow/orange style.
///
/// Returns an RGBA pixel buffer of `w * h * 4` bytes.
pub fn generate_gradient(w: u32, h: u32) -> Vec<u8> {
    let mut buf = vec![0u8; (w * h * 4) as usize];

    for y in 0..h {
        for x in 0..w {
            let offset = ((y * w + x) * 4) as usize;

            // Normalized coordinates [0.0, 1.0].
            let nx = x as f32 / w as f32;
            let ny = y as f32 / h as f32;

            // PSIX-style gradient: blend from teal (top-left) through green
            // (center) to warm orange (bottom-right) with a diagonal sweep.
            let t = nx * 0.6 + ny * 0.4; // diagonal blend factor

            let (r, g, b) = if t < 0.33 {
                // Teal -> green segment.
                let s = t / 0.33;
                lerp_rgb((20, 80, 100), (40, 120, 60), s)
            } else if t < 0.66 {
                // Green -> yellow-green segment.
                let s = (t - 0.33) / 0.33;
                lerp_rgb((40, 120, 60), (140, 160, 40), s)
            } else {
                // Yellow-green -> warm orange segment.
                let s = (t - 0.66) / 0.34;
                lerp_rgb((140, 160, 40), (200, 120, 30), s)
            };

            // Add a subtle radial vignette to darken edges.
            let cx = (nx - 0.5) * 2.0;
            let cy = (ny - 0.5) * 2.0;
            let vignette = 1.0 - (cx * cx + cy * cy).min(1.0) * 0.25;

            buf[offset] = (r as f32 * vignette).min(255.0) as u8;
            buf[offset + 1] = (g as f32 * vignette).min(255.0) as u8;
            buf[offset + 2] = (b as f32 * vignette).min(255.0) as u8;
            buf[offset + 3] = 255;
        }
    }

    buf
}

/// Linear interpolation between two RGB colors.
fn lerp_rgb(a: (u8, u8, u8), b: (u8, u8, u8), t: f32) -> (u8, u8, u8) {
    let r = a.0 as f32 + (b.0 as f32 - a.0 as f32) * t;
    let g = a.1 as f32 + (b.1 as f32 - a.1 as f32) * t;
    let b_val = a.2 as f32 + (b.2 as f32 - a.2 as f32) * t;
    (r as u8, g as u8, b_val as u8)
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn gradient_correct_size() {
        let buf = generate_gradient(480, 272);
        assert_eq!(buf.len(), 480 * 272 * 4);
    }

    #[test]
    fn gradient_all_opaque() {
        let buf = generate_gradient(16, 16);
        for y in 0..16u32 {
            for x in 0..16u32 {
                let offset = ((y * 16 + x) * 4 + 3) as usize;
                assert_eq!(buf[offset], 255, "pixel ({x},{y}) should be fully opaque");
            }
        }
    }

    #[test]
    fn gradient_not_uniform() {
        let buf = generate_gradient(480, 272);
        // Top-left and bottom-right should differ.
        let tl = (buf[0], buf[1], buf[2]);
        let idx = ((271 * 480 + 479) * 4) as usize;
        let br = (buf[idx], buf[idx + 1], buf[idx + 2]);
        assert_ne!(tl, br);
    }
}
