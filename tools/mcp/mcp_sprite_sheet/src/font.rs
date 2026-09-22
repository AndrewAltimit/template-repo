//! Tiny built-in 3x5 bitmap font for debug labels (sprite names overlay).
//!
//! Covers A-Z (lowercase is drawn as uppercase), 0-9, space, `_`, `-`, `.`;
//! anything else renders as `?`. Text is white with a 1px dark shadow so it
//! stays readable on any background.

use image::{Rgba, RgbaImage};

use crate::render::put_pixel_clipped;

/// Glyph width in font pixels.
pub const GLYPH_W: i64 = 3;

/// Rows of a glyph, top to bottom; bit 2 is the leftmost column.
fn glyph(c: char) -> [u8; 5] {
    match c.to_ascii_uppercase() {
        'A' => [0b010, 0b101, 0b111, 0b101, 0b101],
        'B' => [0b110, 0b101, 0b110, 0b101, 0b110],
        'C' => [0b011, 0b100, 0b100, 0b100, 0b011],
        'D' => [0b110, 0b101, 0b101, 0b101, 0b110],
        'E' => [0b111, 0b100, 0b110, 0b100, 0b111],
        'F' => [0b111, 0b100, 0b110, 0b100, 0b100],
        'G' => [0b011, 0b100, 0b101, 0b101, 0b011],
        'H' => [0b101, 0b101, 0b111, 0b101, 0b101],
        'I' => [0b111, 0b010, 0b010, 0b010, 0b111],
        'J' => [0b001, 0b001, 0b001, 0b101, 0b010],
        'K' => [0b101, 0b101, 0b110, 0b101, 0b101],
        'L' => [0b100, 0b100, 0b100, 0b100, 0b111],
        'M' => [0b101, 0b111, 0b111, 0b101, 0b101],
        'N' => [0b110, 0b101, 0b101, 0b101, 0b101],
        'O' => [0b010, 0b101, 0b101, 0b101, 0b010],
        'P' => [0b110, 0b101, 0b110, 0b100, 0b100],
        'Q' => [0b010, 0b101, 0b101, 0b110, 0b011],
        'R' => [0b110, 0b101, 0b110, 0b101, 0b101],
        'S' => [0b011, 0b100, 0b010, 0b001, 0b110],
        'T' => [0b111, 0b010, 0b010, 0b010, 0b010],
        'U' => [0b101, 0b101, 0b101, 0b101, 0b111],
        'V' => [0b101, 0b101, 0b101, 0b101, 0b010],
        'W' => [0b101, 0b101, 0b111, 0b111, 0b101],
        'X' => [0b101, 0b101, 0b010, 0b101, 0b101],
        'Y' => [0b101, 0b101, 0b010, 0b010, 0b010],
        'Z' => [0b111, 0b001, 0b010, 0b100, 0b111],
        '0' => [0b111, 0b101, 0b101, 0b101, 0b111],
        '1' => [0b010, 0b110, 0b010, 0b010, 0b111],
        '2' => [0b110, 0b001, 0b010, 0b100, 0b111],
        '3' => [0b110, 0b001, 0b010, 0b001, 0b110],
        '4' => [0b101, 0b101, 0b111, 0b001, 0b001],
        '5' => [0b111, 0b100, 0b110, 0b001, 0b110],
        '6' => [0b011, 0b100, 0b111, 0b101, 0b111],
        '7' => [0b111, 0b001, 0b010, 0b010, 0b010],
        '8' => [0b111, 0b101, 0b111, 0b101, 0b111],
        '9' => [0b111, 0b101, 0b111, 0b001, 0b110],
        ' ' => [0; 5],
        '_' => [0, 0, 0, 0, 0b111],
        '-' => [0, 0, 0b111, 0, 0],
        '.' => [0, 0, 0, 0, 0b010],
        _ => [0b110, 0b001, 0b010, 0, 0b010],
    }
}

/// Draw `text` with its top-left at `(x, y)`, clipped to the image.
pub fn draw_text(img: &mut RgbaImage, text: &str, x: i64, y: i64, size: u32) {
    let s = i64::from(size.max(1));
    let shadow = Rgba([0, 0, 0, 200]);
    let fg = Rgba([255, 255, 255, 255]);
    for (color, off) in [(shadow, s), (fg, 0)] {
        for (i, ch) in text.chars().enumerate() {
            let gx = x + i as i64 * (GLYPH_W + 1) * s + off;
            for (row, bits) in glyph(ch).iter().enumerate() {
                for col in 0..GLYPH_W {
                    if bits & (0b100 >> col) == 0 {
                        continue;
                    }
                    for dy in 0..s {
                        for dx in 0..s {
                            put_pixel_clipped(
                                img,
                                gx + col * s + dx,
                                y + off + row as i64 * s + dy,
                                color,
                            );
                        }
                    }
                }
            }
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn draws_and_clips() {
        let mut img = RgbaImage::new(4, 6);
        draw_text(&mut img, "I", 0, 0, 1);
        // Top row of 'I' is solid.
        assert_eq!(img.get_pixel(0, 0).0, [255, 255, 255, 255]);
        // Far off-image text must not panic.
        draw_text(&mut img, "hello world", -100, 1000, 3);
    }

    #[test]
    fn unknown_chars_render_placeholder() {
        assert_eq!(glyph('~'), glyph('?'));
        assert_eq!(glyph('a'), glyph('A'));
    }
}
