//! Platform-neutral key names and their X11 keysym / Win32 virtual-key
//! translations.
//!
//! Everything here is pure (no display connection needed) so the mapping
//! tables are unit-tested on every platform, even though each backend only
//! uses its own half at runtime.

use crate::types::KeyModifier;

/// A non-character key.
#[derive(Debug, Clone, Copy, PartialEq, Eq, Hash)]
pub enum NamedKey {
    Enter,
    Tab,
    Escape,
    Backspace,
    Delete,
    Insert,
    Home,
    End,
    PageUp,
    PageDown,
    Left,
    Right,
    Up,
    Down,
    Space,
    CapsLock,
    NumLock,
    ScrollLock,
    PrintScreen,
    Pause,
    Menu,
    Ctrl,
    Alt,
    Shift,
    Super,
    /// Function key F1..=F24.
    F(u8),
    VolumeUp,
    VolumeDown,
    VolumeMute,
    MediaPlayPause,
    MediaNext,
    MediaPrev,
}

/// A key to press: either a named key or the key that produces a character.
#[derive(Debug, Clone, Copy, PartialEq, Eq, Hash)]
pub enum Key {
    /// A named (non-printing or modifier) key.
    Named(NamedKey),
    /// The key that produces this character on the active layout.
    Char(char),
}

impl From<KeyModifier> for Key {
    fn from(m: KeyModifier) -> Self {
        Key::Named(match m {
            KeyModifier::Ctrl => NamedKey::Ctrl,
            KeyModifier::Alt => NamedKey::Alt,
            KeyModifier::Shift => NamedKey::Shift,
            KeyModifier::Win | KeyModifier::Super => NamedKey::Super,
        })
    }
}

/// Parse a user-supplied key name.
///
/// Single characters map to [`Key::Char`]; ASCII letters are lower-cased so
/// `"A"` in a hotkey means the A key (add `"shift"` explicitly for Shift+A).
/// Multi-character names are case-insensitive and ignore `_`, `-` and spaces,
/// so `"Page_Up"`, `"pageup"` and `"PAGE-UP"` are equivalent. X11 keysym names
/// such as `Return`, `BackSpace` and `Prior` are accepted as aliases.
pub fn parse_key(name: &str) -> Result<Key, String> {
    let mut chars = name.chars();
    if let (Some(c), None) = (chars.next(), chars.next()) {
        return Ok(match c {
            ' ' => Key::Named(NamedKey::Space),
            '\n' | '\r' => Key::Named(NamedKey::Enter),
            '\t' => Key::Named(NamedKey::Tab),
            c if c.is_control() => return Err(format!("Unsupported control character {c:?}")),
            c => Key::Char(c.to_ascii_lowercase()),
        });
    }

    let norm: String = name
        .trim()
        .chars()
        .filter(|c| !matches!(c, '_' | '-' | ' '))
        .flat_map(char::to_lowercase)
        .collect();

    use NamedKey::*;
    let named = match norm.as_str() {
        "enter" | "return" | "kpenter" => Enter,
        "tab" => Tab,
        "escape" | "esc" => Escape,
        "backspace" | "bksp" | "back" => Backspace,
        "delete" | "del" => Delete,
        "insert" | "ins" => Insert,
        "home" => Home,
        "end" => End,
        "pageup" | "pgup" | "prior" => PageUp,
        "pagedown" | "pgdn" | "next" => PageDown,
        "left" | "arrowleft" => Left,
        "right" | "arrowright" => Right,
        "up" | "arrowup" => Up,
        "down" | "arrowdown" => Down,
        "space" | "spacebar" => Space,
        "capslock" | "caps" => CapsLock,
        "numlock" => NumLock,
        "scrolllock" => ScrollLock,
        "printscreen" | "print" | "prtsc" | "prtscr" | "sysrq" => PrintScreen,
        "pause" | "break" => Pause,
        "menu" | "apps" | "contextmenu" => Menu,
        "ctrl" | "control" | "controll" | "lctrl" => Ctrl,
        "alt" | "altl" | "lalt" | "option" => Alt,
        "shift" | "shiftl" | "lshift" => Shift,
        "super" | "superl" | "win" | "windows" | "meta" | "cmd" | "command" => Super,
        "volumeup" | "audioraisevolume" => VolumeUp,
        "volumedown" | "audiolowervolume" => VolumeDown,
        "volumemute" | "mute" | "audiomute" => VolumeMute,
        "playpause" | "mediaplaypause" | "audioplay" => MediaPlayPause,
        "nexttrack" | "medianext" | "audionext" => MediaNext,
        "prevtrack" | "previoustrack" | "mediaprev" | "audioprev" => MediaPrev,
        // Symbolic names for punctuation that is awkward to pass in JSON/CLI.
        "plus" => return Ok(Key::Char('+')),
        "minus" => return Ok(Key::Char('-')),
        "equal" | "equals" => return Ok(Key::Char('=')),
        "comma" => return Ok(Key::Char(',')),
        "period" | "dot" => return Ok(Key::Char('.')),
        "slash" => return Ok(Key::Char('/')),
        "backslash" => return Ok(Key::Char('\\')),
        "semicolon" => return Ok(Key::Char(';')),
        "apostrophe" | "quote" => return Ok(Key::Char('\'')),
        "grave" | "backtick" => return Ok(Key::Char('`')),
        "bracketleft" | "leftbracket" => return Ok(Key::Char('[')),
        "bracketright" | "rightbracket" => return Ok(Key::Char(']')),
        other => {
            if let Some(n) = other.strip_prefix('f').and_then(|n| n.parse::<u8>().ok())
                && (1..=24).contains(&n)
            {
                F(n)
            } else {
                return Err(format!(
                    "Unknown key '{name}'. Use a single character or a key name such as \
                     enter, tab, escape, backspace, delete, home, end, pageup, pagedown, \
                     left, right, up, down, space, f1-f24, ctrl, alt, shift, super"
                ));
            }
        },
    };
    Ok(Key::Named(named))
}

// ---------------------------------------------------------------------------
// X11 keysyms
// ---------------------------------------------------------------------------

/// X11 keysym for a named key.
#[cfg_attr(not(target_os = "linux"), allow(dead_code))]
pub fn named_to_keysym(key: NamedKey) -> u32 {
    use NamedKey::*;
    match key {
        Enter => 0xff0d,
        Tab => 0xff09,
        Escape => 0xff1b,
        Backspace => 0xff08,
        Delete => 0xffff,
        Insert => 0xff63,
        Home => 0xff50,
        End => 0xff57,
        PageUp => 0xff55,
        PageDown => 0xff56,
        Left => 0xff51,
        Up => 0xff52,
        Right => 0xff53,
        Down => 0xff54,
        Space => 0x0020,
        CapsLock => 0xffe5,
        NumLock => 0xff7f,
        ScrollLock => 0xff14,
        PrintScreen => 0xff61,
        Pause => 0xff13,
        Menu => 0xff67,
        Ctrl => 0xffe3,
        Alt => 0xffe9,
        Shift => 0xffe1,
        Super => 0xffeb,
        // F1 = 0xffbe ... F24 = 0xffd5 (contiguous).
        F(n) => 0xffbe + u32::from(n.clamp(1, 24)) - 1,
        VolumeUp => 0x1008_ff13,
        VolumeDown => 0x1008_ff11,
        VolumeMute => 0x1008_ff12,
        MediaPlayPause => 0x1008_ff14,
        MediaNext => 0x1008_ff17,
        MediaPrev => 0x1008_ff16,
    }
}

/// X11 keysym for a character.
///
/// Latin-1 characters use their code point directly; everything else uses
/// the Unicode keysym range (`0x0100_0000 + code point`), which X servers
/// resolve for any character once it is bound to a keycode.
#[cfg_attr(not(target_os = "linux"), allow(dead_code))]
pub fn char_to_keysym(c: char) -> u32 {
    match c {
        '\n' | '\r' => 0xff0d,
        '\t' => 0xff09,
        '\u{8}' => 0xff08,
        c => {
            let cp = u32::from(c);
            if (0x20..=0x7e).contains(&cp) || (0xa0..=0xff).contains(&cp) {
                cp
            } else {
                0x0100_0000 + cp
            }
        },
    }
}

/// Keysym for a [`Key`].
#[cfg_attr(not(target_os = "linux"), allow(dead_code))]
pub fn key_to_keysym(key: Key) -> u32 {
    match key {
        Key::Named(n) => named_to_keysym(n),
        Key::Char(c) => char_to_keysym(c),
    }
}

/// A keycode that produces a keysym, and whether Shift is required.
#[cfg_attr(not(target_os = "linux"), allow(dead_code))]
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub struct KeyStroke {
    /// X11 keycode.
    pub keycode: u8,
    /// Whether the keysym is on the shifted level of the keycode.
    pub shift: bool,
}

/// Reverse keyboard map (keysym -> keycode) built from the server's
/// `GetKeyboardMapping` reply.
#[cfg_attr(not(target_os = "linux"), allow(dead_code))]
#[derive(Debug, Default, Clone)]
pub struct Keymap {
    map: std::collections::HashMap<u32, KeyStroke>,
    /// Keycodes with no keysyms bound, usable as scratch keys for characters
    /// the layout cannot produce.
    spare: Vec<u8>,
    /// Keysyms per keycode in the mapping (needed to rebind a scratch key).
    pub keysyms_per_keycode: u8,
}

#[cfg_attr(not(target_os = "linux"), allow(dead_code))]
impl Keymap {
    /// Build from a raw mapping: `keysyms` holds `keysyms_per_keycode` entries
    /// for each keycode starting at `min_keycode`.
    ///
    /// Only the first two levels (unshifted / shifted of group 1) are used;
    /// AltGr levels are ignored because selecting them portably is not
    /// possible via XTEST. Level 0 wins when a keysym appears more than once.
    pub fn from_mapping(min_keycode: u8, keysyms_per_keycode: u8, keysyms: &[u32]) -> Self {
        let per = usize::from(keysyms_per_keycode.max(1));
        let mut map = std::collections::HashMap::new();
        let mut spare = Vec::new();
        for (i, syms) in keysyms.chunks(per).enumerate() {
            let Some(keycode) = u8::try_from(usize::from(min_keycode) + i).ok() else {
                break;
            };
            if syms.iter().all(|&s| s == 0) {
                spare.push(keycode);
                continue;
            }
            for (level, &sym) in syms.iter().take(2).enumerate() {
                if sym == 0 {
                    continue;
                }
                let stroke = KeyStroke {
                    keycode,
                    shift: level == 1,
                };
                map.entry(sym)
                    .and_modify(|e: &mut KeyStroke| {
                        if e.shift && !stroke.shift {
                            *e = stroke;
                        }
                    })
                    .or_insert(stroke);
            }
            // A keycode with only a level-0 letter keysym (e.g. `a` with no
            // `A`) still produces the upper-case letter with Shift.
            if syms.get(1).is_none_or(|&s| s == 0)
                && let Some(upper) = syms
                    .first()
                    .and_then(|&s| char::from_u32(s))
                    .filter(char::is_ascii_lowercase)
                    .map(|c| u32::from(c.to_ascii_uppercase()))
            {
                map.entry(upper).or_insert(KeyStroke {
                    keycode,
                    shift: true,
                });
            }
        }
        Self {
            map,
            spare,
            keysyms_per_keycode,
        }
    }

    /// Look up the keystroke that produces `keysym`.
    pub fn lookup(&self, keysym: u32) -> Option<KeyStroke> {
        self.map.get(&keysym).copied()
    }

    /// A keycode with no bound keysyms (highest first, least likely to clash
    /// with real hardware keys).
    pub fn spare_keycode(&self) -> Option<u8> {
        self.spare.iter().max().copied()
    }
}

// ---------------------------------------------------------------------------
// Win32 virtual-key codes
// ---------------------------------------------------------------------------

/// Win32 virtual-key code for a named key.
#[cfg_attr(not(windows), allow(dead_code))]
pub fn named_to_vk(key: NamedKey) -> u16 {
    use NamedKey::*;
    match key {
        Enter => 0x0D,
        Tab => 0x09,
        Escape => 0x1B,
        Backspace => 0x08,
        Delete => 0x2E,
        Insert => 0x2D,
        Home => 0x24,
        End => 0x23,
        PageUp => 0x21,
        PageDown => 0x22,
        Left => 0x25,
        Up => 0x26,
        Right => 0x27,
        Down => 0x28,
        Space => 0x20,
        CapsLock => 0x14,
        NumLock => 0x90,
        ScrollLock => 0x91,
        PrintScreen => 0x2C,
        Pause => 0x13,
        Menu => 0x5D,
        Ctrl => 0x11,
        Alt => 0x12,
        Shift => 0x10,
        Super => 0x5B,
        // VK_F1 = 0x70 ... VK_F24 = 0x87 (contiguous).
        F(n) => 0x70 + u16::from(n.clamp(1, 24)) - 1,
        VolumeMute => 0xAD,
        VolumeDown => 0xAE,
        VolumeUp => 0xAF,
        MediaNext => 0xB0,
        MediaPrev => 0xB1,
        MediaPlayPause => 0xB3,
    }
}

/// Whether a virtual key must be sent with `KEYEVENTF_EXTENDEDKEY` so that it
/// is not confused with its numeric-keypad twin.
#[cfg_attr(not(windows), allow(dead_code))]
pub fn is_extended_vk(vk: u16) -> bool {
    matches!(
        vk,
        0x21..=0x28 // PageUp, PageDown, End, Home, arrows
            | 0x2C // PrintScreen
            | 0x2D // Insert
            | 0x2E // Delete
            | 0x5B | 0x5C // Windows keys
            | 0x5D // Apps/Menu
            | 0x90 // NumLock
            | 0xA3 | 0xA5 // Right Ctrl / Right Alt
            | 0xAD..=0xB3 // Media / volume keys
    )
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn parse_single_characters() {
        assert_eq!(parse_key("a").unwrap(), Key::Char('a'));
        assert_eq!(parse_key("A").unwrap(), Key::Char('a'));
        assert_eq!(parse_key("!").unwrap(), Key::Char('!'));
        assert_eq!(parse_key("\u{e9}").unwrap(), Key::Char('\u{e9}'));
        assert_eq!(parse_key(" ").unwrap(), Key::Named(NamedKey::Space));
        assert_eq!(parse_key("\n").unwrap(), Key::Named(NamedKey::Enter));
        assert!(parse_key("\u{7}").is_err());
    }

    #[test]
    fn parse_named_keys_and_aliases() {
        for (name, want) in [
            ("Return", NamedKey::Enter),
            ("enter", NamedKey::Enter),
            ("Escape", NamedKey::Escape),
            ("esc", NamedKey::Escape),
            ("BackSpace", NamedKey::Backspace),
            ("Page_Up", NamedKey::PageUp),
            ("page-down", NamedKey::PageDown),
            ("Prior", NamedKey::PageUp),
            ("ArrowLeft", NamedKey::Left),
            ("control", NamedKey::Ctrl),
            ("Control_L", NamedKey::Ctrl),
            ("cmd", NamedKey::Super),
            ("F1", NamedKey::F(1)),
            ("f12", NamedKey::F(12)),
            ("F24", NamedKey::F(24)),
            ("PrtSc", NamedKey::PrintScreen),
        ] {
            assert_eq!(parse_key(name).unwrap(), Key::Named(want), "{name}");
        }
        assert_eq!(parse_key("plus").unwrap(), Key::Char('+'));
        assert!(parse_key("f0").is_err());
        assert!(parse_key("f25").is_err());
        assert!(parse_key("hyperdrive").is_err());
        assert!(parse_key("").is_err());
    }

    #[test]
    fn modifiers_convert_to_keys() {
        assert_eq!(Key::from(KeyModifier::Win), Key::Named(NamedKey::Super));
        assert_eq!(Key::from(KeyModifier::Ctrl), Key::Named(NamedKey::Ctrl));
    }

    #[test]
    fn keysym_translation() {
        assert_eq!(char_to_keysym('a'), 0x61);
        assert_eq!(char_to_keysym('~'), 0x7e);
        assert_eq!(char_to_keysym('\u{e9}'), 0xe9);
        assert_eq!(char_to_keysym('\u{20ac}'), 0x0100_20ac);
        assert_eq!(char_to_keysym('\n'), 0xff0d);
        assert_eq!(named_to_keysym(NamedKey::F(1)), 0xffbe);
        assert_eq!(named_to_keysym(NamedKey::F(12)), 0xffc9);
        assert_eq!(named_to_keysym(NamedKey::F(24)), 0xffd5);
        assert_eq!(key_to_keysym(Key::Named(NamedKey::Enter)), 0xff0d);
    }

    #[test]
    fn keymap_prefers_unshifted_level_and_tracks_spares() {
        // keycode 10: '1' / '!', keycode 11: nothing (spare), keycode 12: 'a' only,
        // keycode 13: '!' on level 0 (should win over keycode 10's shifted '!').
        let per = 4u8;
        let syms = [
            0x31, 0x21, 0, 0, // 10
            0, 0, 0, 0, // 11
            0x61, 0, 0, 0, // 12
            0x21, 0, 0, 0, // 13
        ];
        let km = Keymap::from_mapping(10, per, &syms);
        assert_eq!(
            km.lookup(0x31),
            Some(KeyStroke {
                keycode: 10,
                shift: false
            })
        );
        assert_eq!(
            km.lookup(0x21),
            Some(KeyStroke {
                keycode: 13,
                shift: false
            })
        );
        assert_eq!(
            km.lookup(0x41),
            Some(KeyStroke {
                keycode: 12,
                shift: true
            }),
            "upper-case letter derived from lower-case-only keycode"
        );
        assert_eq!(km.lookup(0x20ac), None);
        assert_eq!(km.spare_keycode(), Some(11));
        assert_eq!(km.keysyms_per_keycode, 4);
    }

    #[test]
    fn keymap_handles_keycode_overflow() {
        // More entries than fit in the u8 keycode range must not panic.
        let syms = vec![0x61u32; 300];
        let km = Keymap::from_mapping(250, 1, &syms);
        assert!(km.lookup(0x61).is_some());
    }

    #[test]
    fn vk_translation() {
        assert_eq!(named_to_vk(NamedKey::Enter), 0x0D);
        assert_eq!(named_to_vk(NamedKey::F(1)), 0x70);
        assert_eq!(named_to_vk(NamedKey::F(24)), 0x87);
        assert!(is_extended_vk(named_to_vk(NamedKey::Left)));
        assert!(is_extended_vk(named_to_vk(NamedKey::Delete)));
        assert!(is_extended_vk(named_to_vk(NamedKey::Super)));
        assert!(!is_extended_vk(named_to_vk(NamedKey::Enter)));
        assert!(!is_extended_vk(named_to_vk(NamedKey::Ctrl)));
    }
}
