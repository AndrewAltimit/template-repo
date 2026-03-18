//! Built-in palette presets and utilities.

use crate::types::{Palette, PaletteColor};

/// Create a palette from a preset name
pub fn from_preset(name: &str) -> Option<Palette> {
    match name {
        "pico8" => Some(pico8()),
        "gameboy" => Some(gameboy()),
        "nes" => Some(nes()),
        "snes" => Some(snes()),
        "endesga32" => Some(endesga32()),
        _ => None,
    }
}

/// List available preset names
pub fn preset_names() -> Vec<&'static str> {
    vec!["pico8", "gameboy", "nes", "snes", "endesga32"]
}

fn make_palette(name: &str, colors: &[(&str, [u8; 4])]) -> Palette {
    Palette {
        name: name.to_string(),
        colors: colors
            .iter()
            .enumerate()
            .map(|(i, (cname, rgba))| PaletteColor {
                index: i as u8,
                name: cname.to_string(),
                rgba: *rgba,
            })
            .collect(),
        enforce: true,
    }
}

/// PICO-8 16-color palette
pub fn pico8() -> Palette {
    make_palette(
        "pico8",
        &[
            ("black", [0, 0, 0, 255]),
            ("dark_blue", [29, 43, 83, 255]),
            ("dark_purple", [126, 37, 83, 255]),
            ("dark_green", [0, 135, 81, 255]),
            ("brown", [171, 82, 54, 255]),
            ("dark_grey", [95, 87, 79, 255]),
            ("light_grey", [194, 195, 199, 255]),
            ("white", [255, 241, 232, 255]),
            ("red", [255, 0, 77, 255]),
            ("orange", [255, 163, 0, 255]),
            ("yellow", [255, 236, 39, 255]),
            ("green", [0, 228, 54, 255]),
            ("blue", [41, 173, 255, 255]),
            ("lavender", [131, 118, 156, 255]),
            ("pink", [255, 119, 168, 255]),
            ("peach", [255, 204, 170, 255]),
        ],
    )
}

/// Game Boy 4-color palette
pub fn gameboy() -> Palette {
    make_palette(
        "gameboy",
        &[
            ("darkest", [15, 56, 15, 255]),
            ("dark", [48, 98, 48, 255]),
            ("light", [139, 172, 15, 255]),
            ("lightest", [155, 188, 15, 255]),
        ],
    )
}

/// NES-inspired 54-color palette (subset of the full 64)
pub fn nes() -> Palette {
    make_palette(
        "nes",
        &[
            ("black", [0, 0, 0, 255]),
            ("dark_grey", [88, 88, 88, 255]),
            ("medium_grey", [160, 160, 160, 255]),
            ("light_grey", [192, 192, 192, 255]),
            ("white", [255, 255, 255, 255]),
            ("dark_red", [168, 16, 0, 255]),
            ("red", [228, 0, 0, 255]),
            ("bright_red", [248, 56, 0, 255]),
            ("dark_orange", [196, 80, 0, 255]),
            ("orange", [228, 92, 16, 255]),
            ("dark_yellow", [172, 124, 0, 255]),
            ("yellow", [248, 184, 0, 255]),
            ("dark_green", [0, 120, 0, 255]),
            ("green", [0, 168, 0, 255]),
            ("bright_green", [0, 228, 0, 255]),
            ("dark_blue", [0, 0, 168, 255]),
            ("blue", [0, 120, 248, 255]),
            ("bright_blue", [60, 188, 252, 255]),
            ("dark_purple", [104, 68, 168, 255]),
            ("purple", [148, 120, 248, 255]),
            ("dark_pink", [168, 0, 116, 255]),
            ("pink", [248, 120, 248, 255]),
            ("dark_cyan", [0, 148, 136, 255]),
            ("cyan", [0, 232, 216, 255]),
        ],
    )
}

/// SNES-inspired 32-color palette
pub fn snes() -> Palette {
    make_palette(
        "snes",
        &[
            ("black", [0, 0, 0, 255]),
            ("dark_grey", [49, 49, 49, 255]),
            ("grey", [99, 99, 99, 255]),
            ("light_grey", [173, 173, 173, 255]),
            ("white", [255, 255, 255, 255]),
            ("dark_red", [132, 0, 0, 255]),
            ("red", [214, 40, 40, 255]),
            ("dark_orange", [181, 99, 0, 255]),
            ("orange", [247, 127, 0, 255]),
            ("dark_yellow", [181, 166, 66, 255]),
            ("yellow", [252, 211, 77, 255]),
            ("dark_green", [0, 100, 0, 255]),
            ("green", [46, 139, 87, 255]),
            ("bright_green", [119, 221, 119, 255]),
            ("dark_blue", [0, 0, 139, 255]),
            ("blue", [65, 105, 225, 255]),
            ("sky_blue", [100, 149, 237, 255]),
            ("light_blue", [173, 216, 230, 255]),
            ("dark_purple", [72, 0, 120, 255]),
            ("purple", [138, 43, 226, 255]),
            ("dark_pink", [199, 21, 133, 255]),
            ("pink", [255, 182, 193, 255]),
            ("dark_cyan", [0, 128, 128, 255]),
            ("cyan", [0, 206, 209, 255]),
            ("dark_brown", [101, 67, 33, 255]),
            ("brown", [160, 82, 45, 255]),
            ("tan", [210, 180, 140, 255]),
            ("skin_light", [255, 218, 185, 255]),
            ("skin_dark", [205, 133, 63, 255]),
            ("gold", [255, 215, 0, 255]),
            ("silver", [192, 192, 192, 255]),
            ("transparent", [0, 0, 0, 0]),
        ],
    )
}

/// ENDESGA 32-color palette
pub fn endesga32() -> Palette {
    make_palette(
        "endesga32",
        &[
            ("void", [19, 19, 19, 255]),
            ("ash", [43, 43, 43, 255]),
            ("blind", [68, 68, 68, 255]),
            ("iron", [109, 109, 109, 255]),
            ("light", [174, 174, 174, 255]),
            ("white", [255, 255, 255, 255]),
            ("highlight", [192, 203, 220, 255]),
            ("sap", [18, 78, 74, 255]),
            ("leaf", [38, 137, 34, 255]),
            ("grass", [76, 196, 49, 255]),
            ("honey", [226, 196, 56, 255]),
            ("beeswax", [248, 230, 109, 255]),
            ("peach", [236, 157, 82, 255]),
            ("ember", [209, 106, 35, 255]),
            ("carmine", [183, 44, 37, 255]),
            ("crimson", [119, 17, 31, 255]),
            ("dried_blood", [60, 22, 22, 255]),
            ("flesh", [255, 184, 134, 255]),
            ("salmon", [234, 115, 101, 255]),
            ("blossom", [223, 72, 131, 255]),
            ("lilac", [162, 63, 141, 255]),
            ("indigo", [75, 43, 116, 255]),
            ("deep_sea", [44, 58, 105, 255]),
            ("navy", [51, 87, 132, 255]),
            ("sky", [66, 130, 171, 255]),
            ("crystal", [83, 196, 193, 255]),
            ("aqua", [173, 231, 146, 255]),
            ("moss", [82, 127, 57, 255]),
            ("pine", [56, 86, 58, 255]),
            ("earth", [83, 62, 42, 255]),
            ("cocoa", [121, 90, 61, 255]),
            ("sand", [195, 163, 126, 255]),
        ],
    )
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_preset_lookup() {
        for name in preset_names() {
            let palette = from_preset(name).unwrap();
            assert!(
                !palette.colors.is_empty(),
                "Palette {name} should have colors"
            );
            assert!(palette.enforce);
        }
    }

    #[test]
    fn test_unknown_preset() {
        assert!(from_preset("nonexistent").is_none());
    }

    #[test]
    fn test_pico8_has_16_colors() {
        let p = pico8();
        assert_eq!(p.colors.len(), 16);
    }

    #[test]
    fn test_palette_get_color() {
        let p = pico8();
        assert_eq!(p.get_color(0), Some([0, 0, 0, 255]));
        assert!(p.get_color(200).is_none());
    }
}
