//! Procedural wallpaper generation.
//!
//! Generates PSIX-style gradient wallpapers as raw RGBA pixel buffers.
//! No external PNG files needed -- keeps CI clean and the binary self-contained.

/// Generate a vibrant gradient wallpaper matching PSIX's orange->yellow->green style.
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

            // PSIX uses a strong left-to-right gradient:
            // Left = warm orange/red, Center = golden yellow, Right = bright green/lime.
            // Vertical component adds subtle variation.
            let t = nx * 0.85 + ny * 0.15;

            let (r, g, b) = if t < 0.25 {
                // Orange -> golden yellow.
                let s = t / 0.25;
                lerp_rgb((220, 120, 30), (240, 200, 40), s)
            } else if t < 0.50 {
                // Golden yellow -> yellow-green.
                let s = (t - 0.25) / 0.25;
                lerp_rgb((240, 200, 40), (180, 220, 50), s)
            } else if t < 0.75 {
                // Yellow-green -> bright green.
                let s = (t - 0.50) / 0.25;
                lerp_rgb((180, 220, 50), (100, 210, 60), s)
            } else {
                // Bright green -> lime/light green.
                let s = (t - 0.75) / 0.25;
                lerp_rgb((100, 210, 60), (140, 230, 100), s)
            };

            // Subtle vertical brightness variation (lighter toward top).
            let vert = 1.0 + (0.5 - ny) * 0.15;

            buf[offset] = (r as f32 * vert).clamp(0.0, 255.0) as u8;
            buf[offset + 1] = (g as f32 * vert).clamp(0.0, 255.0) as u8;
            buf[offset + 2] = (b as f32 * vert).clamp(0.0, 255.0) as u8;
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
