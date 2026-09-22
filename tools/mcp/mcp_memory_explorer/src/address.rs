//! Address and number parsing.
//!
//! Supported address syntaxes:
//!
//! | Input                      | Meaning                                   |
//! |----------------------------|-------------------------------------------|
//! | `0x7FF6A1B2C3D4`           | Hexadecimal absolute address              |
//! | `140737488355328`          | Decimal absolute address                  |
//! | `NMS.exe`                  | Base address of a module                  |
//! | `NMS.exe+0x1234`           | Module base plus a hex offset             |
//! | `NMS.exe+4660`             | Module base plus a decimal offset         |
//! | `NMS.exe-0x10`             | Module base minus an offset               |
//!
//! Module names may themselves contain `-` or `+` (e.g.
//! `api-ms-win-core-synch-l1-2-0.dll`): the input is only split at the *last*
//! `+`/`-` when the text after it is a valid number.

/// Parse an unsigned number: `0x`-prefixed hex or plain decimal.
pub fn parse_unsigned(s: &str) -> Result<u64, String> {
    let s = s.trim();
    let parsed = if let Some(hex) = strip_hex_prefix(s) {
        u64::from_str_radix(&hex.replace('_', ""), 16)
    } else {
        s.replace('_', "").parse::<u64>()
    };
    parsed.map_err(|_| format!("'{}' is not a valid number", s))
}

/// Parse a signed number (`-0x10`, `+16`, `0x20`, `-8`) into an `i128`
/// so the full `u64` and `i64` ranges are both representable.
pub fn parse_signed_number(s: &str) -> Result<i128, String> {
    let t = s.trim();
    let (neg, rest) = match t.as_bytes().first() {
        Some(b'-') => (true, &t[1..]),
        Some(b'+') => (false, &t[1..]),
        _ => (false, t),
    };
    if rest.starts_with(['-', '+']) {
        return Err(format!("'{}' is not a valid number", s));
    }
    let magnitude = parse_unsigned(rest).map_err(|_| format!("'{}' is not a valid number", s))?;
    let v = magnitude as i128;
    Ok(if neg { -v } else { v })
}

/// Parse a signed offset that must fit in an `i64`.
pub fn parse_offset(s: &str) -> Result<i64, String> {
    let v = parse_signed_number(s)?;
    i64::try_from(v).map_err(|_| format!("offset '{}' does not fit in a signed 64-bit value", s))
}

fn strip_hex_prefix(s: &str) -> Option<&str> {
    s.strip_prefix("0x").or_else(|| s.strip_prefix("0X"))
}

/// Parse an address expression, resolving module names with `resolve_module`.
///
/// `resolve_module` returns the module base address, or an error message that
/// is surfaced to the caller verbatim (e.g. "not attached" or "module not found").
pub fn parse_address<F>(input: &str, mut resolve_module: F) -> Result<u64, String>
where
    F: FnMut(&str) -> Result<u64, String>,
{
    let addr = input.trim();
    if addr.is_empty() {
        return Err("address is empty".into());
    }

    // Plain number?
    if let Ok(v) = parse_unsigned(addr) {
        return Ok(v);
    }

    // module+offset / module-offset: split at the last sign whose suffix is numeric.
    if let Some(idx) = addr.rfind(['+', '-'])
        && idx > 0
    {
        let (module, rest) = addr.split_at(idx);
        let module = module.trim();
        if let Ok(offset) = parse_signed_number(rest) {
            if module.is_empty() {
                return Err(format!("invalid address '{}': missing module name", addr));
            }
            let base = resolve_module(module)?;
            let result = (base as i128) + offset;
            return u64::try_from(result).map_err(|_| {
                format!(
                    "address '{}' overflows: {:#x} {:+#x} is outside the 64-bit range",
                    addr, base, offset
                )
            });
        }
    }

    // Anything else must be a bare module name.
    if looks_like_bare_hex(addr) {
        return Err(format!(
            "invalid address '{}': hexadecimal addresses need a 0x prefix (e.g. 0x{})",
            addr, addr
        ));
    }
    resolve_module(addr)
}

/// True for inputs like `DEADBEEF` that are valid hex but lack a `0x` prefix
/// and contain no `.` (so they are unlikely to be a module file name).
fn looks_like_bare_hex(s: &str) -> bool {
    !s.contains('.') && s.len() >= 4 && s.chars().all(|c| c.is_ascii_hexdigit())
}

#[cfg(test)]
mod tests {
    use super::*;

    fn resolver(name: &str) -> Result<u64, String> {
        match name.to_ascii_lowercase().as_str() {
            "game.exe" => Ok(0x1_4000_0000),
            "api-ms-win-core-synch-l1-2-0.dll" => Ok(0x7ff0_0000),
            _ => Err(format!("Module not found: {}", name)),
        }
    }

    #[test]
    fn numbers() {
        assert_eq!(parse_unsigned("0x10").unwrap(), 16);
        assert_eq!(parse_unsigned("0XfF").unwrap(), 255);
        assert_eq!(parse_unsigned("42").unwrap(), 42);
        assert_eq!(parse_unsigned("0x7FF6_A1B2").unwrap(), 0x7ff6_a1b2);
        assert!(parse_unsigned("0x").is_err());
        assert!(parse_unsigned("-1").is_err());
        assert!(parse_unsigned("0x1_0000_0000_0000_0000").is_err());

        assert_eq!(parse_signed_number("-0x10").unwrap(), -16);
        assert_eq!(parse_signed_number("+8").unwrap(), 8);
        assert_eq!(
            parse_signed_number("0xFFFFFFFFFFFFFFFF").unwrap(),
            u64::MAX as i128
        );
        assert!(parse_signed_number("--1").is_err());
        assert!(parse_signed_number("").is_err());

        assert_eq!(parse_offset("-0x8").unwrap(), -8);
        assert!(parse_offset("0xFFFFFFFFFFFFFFFF").is_err());
    }

    #[test]
    fn absolute_addresses() {
        assert_eq!(
            parse_address("0x7FF6A1B2C3D4", resolver).unwrap(),
            0x7ff6a1b2c3d4
        );
        assert_eq!(parse_address("  4096 ", resolver).unwrap(), 4096);
    }

    #[test]
    fn module_relative() {
        assert_eq!(parse_address("game.exe", resolver).unwrap(), 0x1_4000_0000);
        assert_eq!(
            parse_address("GAME.EXE+0x1234", resolver).unwrap(),
            0x1_4000_1234
        );
        assert_eq!(
            parse_address("game.exe + 16", resolver).unwrap(),
            0x1_4000_0010
        );
        assert_eq!(
            parse_address("game.exe-0x10", resolver).unwrap(),
            0x1_3fff_fff0
        );
        // Hyphenated module names are not mistaken for subtraction.
        assert_eq!(
            parse_address("api-ms-win-core-synch-l1-2-0.dll", resolver).unwrap(),
            0x7ff0_0000
        );
        assert_eq!(
            parse_address("api-ms-win-core-synch-l1-2-0.dll+0x20", resolver).unwrap(),
            0x7ff0_0020
        );
    }

    #[test]
    fn errors_are_descriptive() {
        let e = parse_address("missing.dll+0x10", resolver).unwrap_err();
        assert!(e.contains("Module not found"), "{e}");
        let e = parse_address("DEADBEEF", resolver).unwrap_err();
        assert!(e.contains("0x prefix"), "{e}");
        let e = parse_address("", resolver).unwrap_err();
        assert!(e.contains("empty"));
        let e = parse_address("+0x10", resolver).unwrap_err();
        assert!(
            e.contains("Module not found") || e.contains("missing module"),
            "{e}"
        );
        let e = parse_address("game.exe-0x200000000", resolver).unwrap_err();
        assert!(e.contains("overflows"), "{e}");
    }
}
