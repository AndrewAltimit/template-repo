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

            let nx = x as f32 / w as f32;
            let ny = y as f32 / h as f32;

            // PSIX gradient: hot orange (left) -> vivid yellow -> bright lime green (right).
            // Strong horizontal sweep with subtle vertical tint.
            let t = nx * 0.88 + ny * 0.12;

            let (r, g, b) = if t < 0.15 {
                // Hot orange-red -> vivid orange.
                let s = t / 0.15;
                lerp_rgb((245, 110, 15), (255, 170, 15), s)
            } else if t < 0.32 {
                // Vivid orange -> bright golden yellow.
                let s = (t - 0.15) / 0.17;
                lerp_rgb((255, 170, 15), (255, 230, 30), s)
            } else if t < 0.48 {
                // Golden yellow -> yellow-green.
                let s = (t - 0.32) / 0.16;
                lerp_rgb((255, 230, 30), (230, 245, 40), s)
            } else if t < 0.65 {
                // Yellow-green -> bright green.
                let s = (t - 0.48) / 0.17;
                lerp_rgb((230, 245, 40), (140, 235, 50), s)
            } else {
                // Bright green -> vivid lime.
                let s = (t - 0.65) / 0.35;
                lerp_rgb((140, 235, 50), (200, 252, 130), s)
            };

            // Vertical brightness: lighter toward top, slightly darker at bottom.
            let vert = 1.0 + (0.5 - ny) * 0.18;

            // PSIX-style curved stripe arcs emanating from the lower-left.
            // Prominent overlapping wave bands -- the characteristic PSIX pattern.
            let dx = nx + 0.05;
            let dy = ny - 1.3;
            let dist = (dx * dx + dy * dy).sqrt();

            // Primary wave arcs (wide bands, high amplitude).
            let arc1 = (dist * 12.0).sin() * 0.18;
            // Secondary bands (medium frequency, visible layering).
            let arc2 = (dist * 22.0 + 1.2).sin() * 0.09;
            // Tertiary fine ripple.
            let arc3 = (dist * 36.0 + nx * 2.5).sin() * 0.04;

            // Arcs fade out toward the right (strongest on left).
            let arc_fade = (1.0 - nx * 0.45).clamp(0.0, 1.0);
            let wave = 1.0 + (arc1 + arc2 + arc3) * arc_fade;

            let scale = vert * wave;
            buf[offset] = (r as f32 * scale).clamp(0.0, 255.0) as u8;
            buf[offset + 1] = (g as f32 * scale).clamp(0.0, 255.0) as u8;
            buf[offset + 2] = (b as f32 * scale).clamp(0.0, 255.0) as u8;
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
