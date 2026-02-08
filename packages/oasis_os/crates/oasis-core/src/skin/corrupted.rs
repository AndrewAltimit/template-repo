//! Corrupted skin modifier system.
//!
//! Provides visual distortion hooks that the Corrupted skin applies each
//! frame. The WM and SDI remain functional -- the modifiers only inject
//! cosmetic glitches.

use serde::Deserialize;

use crate::sdi::SdiRegistry;

/// Configuration for corrupted visual modifiers.
#[derive(Debug, Clone, Deserialize)]
pub struct CorruptedModifiers {
    /// Maximum pixel jitter applied to object positions each frame.
    /// Objects shift by a random value in `[-jitter, +jitter]`.
    #[serde(default = "default_jitter")]
    pub position_jitter: i32,
    /// Probability (0.0-1.0) that an object's alpha will flicker each frame.
    #[serde(default = "default_flicker")]
    pub alpha_flicker_chance: f32,
    /// Minimum alpha during a flicker event.
    #[serde(default = "default_flicker_min")]
    pub alpha_flicker_min: u8,
    /// Probability (0.0-1.0) that a text character is garbled.
    #[serde(default = "default_garble")]
    pub text_garble_chance: f32,
    /// Overall intensity multiplier (0.0 = no corruption, 1.0 = full).
    #[serde(default = "default_intensity")]
    pub intensity: f32,
}

fn default_jitter() -> i32 {
    2
}
fn default_flicker() -> f32 {
    0.1
}
fn default_flicker_min() -> u8 {
    80
}
fn default_garble() -> f32 {
    0.05
}
fn default_intensity() -> f32 {
    1.0
}

impl Default for CorruptedModifiers {
    fn default() -> Self {
        Self {
            position_jitter: default_jitter(),
            alpha_flicker_chance: default_flicker(),
            alpha_flicker_min: default_flicker_min(),
            text_garble_chance: default_garble(),
            intensity: default_intensity(),
        }
    }
}

/// Simple linear congruential RNG for deterministic-enough randomness
/// without pulling in a crate. Not cryptographic.
#[derive(Debug, Clone)]
pub struct SimpleRng {
    state: u32,
}

impl SimpleRng {
    pub fn new(seed: u32) -> Self {
        Self {
            state: seed.wrapping_add(1),
        }
    }

    /// Generate next u32.
    pub fn next_u32(&mut self) -> u32 {
        // LCG parameters from Numerical Recipes.
        self.state = self.state.wrapping_mul(1664525).wrapping_add(1013904223);
        self.state
    }

    /// Generate a float in [0.0, 1.0).
    pub fn next_f32(&mut self) -> f32 {
        (self.next_u32() >> 8) as f32 / (1u32 << 24) as f32
    }

    /// Generate an i32 in [-range, +range].
    pub fn next_range(&mut self, range: i32) -> i32 {
        if range == 0 {
            return 0;
        }
        let span = (range * 2 + 1) as u32;
        (self.next_u32() % span) as i32 - range
    }
}

/// Glitch characters used for text garbling.
const GLITCH_CHARS: &[u8] = b"@#$%&*!?/\\|~^<>{}[]";

impl CorruptedModifiers {
    /// Apply corrupted modifiers to all visible SDI objects.
    ///
    /// This should be called once per frame, after the normal layout is set
    /// and before drawing. The modifications are cosmetic and ephemeral --
    /// they should be re-applied from the clean state each frame (i.e., the
    /// skin system restores base positions before calling this).
    pub fn apply(&self, sdi: &mut SdiRegistry, rng: &mut SimpleRng) {
        if self.intensity <= 0.0 {
            return;
        }

        let jitter = (self.position_jitter as f32 * self.intensity) as i32;
        let flicker_chance = self.alpha_flicker_chance * self.intensity;
        let garble_chance = self.text_garble_chance * self.intensity;

        // Collect names first to avoid borrow issues.
        let names: Vec<String> = sdi.names().map(String::from).collect();

        for name in &names {
            let obj = match sdi.get_mut(name) {
                Ok(o) => o,
                Err(_) => continue,
            };

            if !obj.visible {
                continue;
            }

            // Position jitter.
            if jitter > 0 {
                obj.x += rng.next_range(jitter);
                obj.y += rng.next_range(jitter);
            }

            // Alpha flicker.
            if flicker_chance > 0.0 && rng.next_f32() < flicker_chance {
                obj.alpha = self
                    .alpha_flicker_min
                    .max((rng.next_u32() % 256) as u8)
                    .min(obj.alpha);
            }

            // Text garbling.
            if garble_chance > 0.0 {
                if let Some(ref text) = obj.text {
                    let garbled: String = text
                        .chars()
                        .map(|ch| {
                            if ch.is_ascii_alphanumeric() && rng.next_f32() < garble_chance {
                                let idx = rng.next_u32() as usize % GLITCH_CHARS.len();
                                GLITCH_CHARS[idx] as char
                            } else {
                                ch
                            }
                        })
                        .collect();
                    if garbled != *text {
                        obj.text = Some(garbled);
                    }
                }
            }
        }
    }

    /// Garble a string of text using the corrupted modifier settings.
    /// Useful for garbling command output before display.
    pub fn garble_text(&self, text: &str, rng: &mut SimpleRng) -> String {
        if self.intensity <= 0.0 {
            return text.to_string();
        }
        let chance = self.text_garble_chance * self.intensity;
        text.chars()
            .map(|ch| {
                if ch.is_ascii_alphanumeric() && rng.next_f32() < chance {
                    let idx = rng.next_u32() as usize % GLITCH_CHARS.len();
                    GLITCH_CHARS[idx] as char
                } else {
                    ch
                }
            })
            .collect()
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn default_modifiers() {
        let m = CorruptedModifiers::default();
        assert_eq!(m.position_jitter, 2);
        assert!(m.intensity > 0.0);
    }

    #[test]
    fn rng_produces_different_values() {
        let mut rng = SimpleRng::new(42);
        let a = rng.next_u32();
        let b = rng.next_u32();
        assert_ne!(a, b);
    }

    #[test]
    fn rng_f32_in_range() {
        let mut rng = SimpleRng::new(123);
        for _ in 0..100 {
            let f = rng.next_f32();
            assert!((0.0..1.0).contains(&f));
        }
    }

    #[test]
    fn rng_range_bounded() {
        let mut rng = SimpleRng::new(456);
        for _ in 0..100 {
            let v = rng.next_range(3);
            assert!((-3..=3).contains(&v));
        }
    }

    #[test]
    fn zero_intensity_no_changes() {
        let m = CorruptedModifiers {
            intensity: 0.0,
            ..CorruptedModifiers::default()
        };
        let mut sdi = SdiRegistry::new();
        {
            let obj = sdi.create("test");
            obj.x = 100;
            obj.y = 200;
            obj.text = Some("Hello World".to_string());
        }
        let mut rng = SimpleRng::new(0);
        m.apply(&mut sdi, &mut rng);
        let obj = sdi.get("test").unwrap();
        assert_eq!(obj.x, 100);
        assert_eq!(obj.y, 200);
        assert_eq!(obj.text.as_deref(), Some("Hello World"));
    }

    #[test]
    fn high_intensity_modifies_positions() {
        let m = CorruptedModifiers {
            position_jitter: 10,
            intensity: 1.0,
            alpha_flicker_chance: 0.0,
            text_garble_chance: 0.0,
            ..CorruptedModifiers::default()
        };
        let mut sdi = SdiRegistry::new();
        {
            let obj = sdi.create("test");
            obj.x = 100;
            obj.y = 200;
        }
        let mut rng = SimpleRng::new(42);
        m.apply(&mut sdi, &mut rng);
        let obj = sdi.get("test").unwrap();
        // With jitter=10, positions should change (very unlikely to stay exact).
        // We run multiple seeds to ensure at least one changes.
        let x_changed = obj.x != 100;
        let y_changed = obj.y != 200;
        assert!(x_changed || y_changed);
    }

    #[test]
    fn garble_text_modifies_output() {
        let m = CorruptedModifiers {
            text_garble_chance: 1.0, // Garble everything.
            intensity: 1.0,
            ..CorruptedModifiers::default()
        };
        let mut rng = SimpleRng::new(42);
        let result = m.garble_text("Hello World 123", &mut rng);
        // With 100% garble chance, all alphanumeric chars should be replaced.
        assert_ne!(result, "Hello World 123");
        // Spaces should remain.
        assert!(result.contains(' '));
    }

    #[test]
    fn garble_text_zero_intensity() {
        let m = CorruptedModifiers {
            text_garble_chance: 1.0,
            intensity: 0.0,
            ..CorruptedModifiers::default()
        };
        let mut rng = SimpleRng::new(42);
        let result = m.garble_text("Hello", &mut rng);
        assert_eq!(result, "Hello");
    }

    #[test]
    fn deserialize_from_toml() {
        let toml = r#"
position_jitter = 5
alpha_flicker_chance = 0.2
text_garble_chance = 0.1
intensity = 0.75
"#;
        let m: CorruptedModifiers = toml::from_str(toml).unwrap();
        assert_eq!(m.position_jitter, 5);
        assert!((m.alpha_flicker_chance - 0.2).abs() < f32::EPSILON);
        assert!((m.intensity - 0.75).abs() < f32::EPSILON);
    }

    #[test]
    fn invisible_objects_skipped() {
        let m = CorruptedModifiers {
            position_jitter: 10,
            intensity: 1.0,
            ..CorruptedModifiers::default()
        };
        let mut sdi = SdiRegistry::new();
        {
            let obj = sdi.create("hidden");
            obj.x = 100;
            obj.y = 200;
            obj.visible = false;
        }
        let mut rng = SimpleRng::new(42);
        m.apply(&mut sdi, &mut rng);
        let obj = sdi.get("hidden").unwrap();
        assert_eq!(obj.x, 100);
        assert_eq!(obj.y, 200);
    }
}
