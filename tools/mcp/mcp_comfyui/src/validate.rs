//! Input validation and decoding helpers shared by the tools.
//!
//! Everything a caller can influence that ends up in a filesystem path or a
//! ComfyUI request parameter goes through here.

use base64::{Engine, engine::general_purpose::STANDARD as BASE64};

/// File extensions accepted for LoRA files.
pub const LORA_EXTENSIONS: &[&str] = &["safetensors", "ckpt", "pt"];

/// File extensions accepted for images uploaded to / fetched from ComfyUI.
pub const IMAGE_EXTENSIONS: &[&str] = &["png", "jpg", "jpeg", "webp", "gif", "bmp"];

/// Validate a bare file name (no directories) with one of `allowed_exts`.
///
/// Rejects -- rather than silently rewriting -- anything that could escape the
/// target directory: path separators, `..`, drive prefixes, hidden files and
/// control characters. Returns the file name unchanged on success.
pub fn validate_filename<'a>(name: &'a str, allowed_exts: &[&str]) -> Result<&'a str, String> {
    if name.is_empty() {
        return Err("filename must not be empty".to_string());
    }
    if name.len() > 255 {
        return Err("filename is longer than 255 bytes".to_string());
    }
    if name.contains(['/', '\\', ':']) {
        return Err(format!(
            "filename {name:?} must be a bare file name without directories"
        ));
    }
    if name.starts_with('.') {
        return Err(format!(
            "filename {name:?} must not start with '.' (hidden files and '..' are not allowed)"
        ));
    }
    if name.chars().any(|c| c.is_control() || c == '"') {
        return Err(format!(
            "filename {name:?} contains control characters or quotes"
        ));
    }
    let ext = name
        .rsplit_once('.')
        .map(|(_, ext)| ext.to_ascii_lowercase())
        .unwrap_or_default();
    if !allowed_exts.contains(&ext.as_str()) {
        return Err(format!(
            "filename {name:?} must have one of these extensions: {}",
            allowed_exts.join(", ")
        ));
    }
    Ok(name)
}

/// Validate a ComfyUI subfolder (relative, `/`-separated, no traversal).
/// An empty string means the root of the input/output directory.
pub fn validate_subfolder(subfolder: &str) -> Result<&str, String> {
    if subfolder.is_empty() {
        return Ok(subfolder);
    }
    if subfolder.len() > 255 {
        return Err("subfolder is longer than 255 bytes".to_string());
    }
    if subfolder.contains(['\\', ':']) || subfolder.chars().any(char::is_control) {
        return Err(format!(
            "subfolder {subfolder:?} must use '/' separators and no drive prefixes"
        ));
    }
    for segment in subfolder.split('/') {
        if segment.is_empty() || segment == "." || segment == ".." {
            return Err(format!(
                "subfolder {subfolder:?} must be a relative path without empty, '.' or '..' segments"
            ));
        }
    }
    Ok(subfolder)
}

/// Decode base64 input, tolerating a `data:<mime>;base64,` prefix and
/// embedded whitespace/newlines (common when data is pasted or wrapped).
pub fn decode_base64(data: &str) -> Result<Vec<u8>, String> {
    let payload = match data.trim_start().strip_prefix("data:") {
        Some(rest) => rest
            .split_once(',')
            .map(|(_, b64)| b64)
            .ok_or_else(|| "malformed data URL: missing ','".to_string())?,
        None => data,
    };
    let cleaned: String = payload.chars().filter(|c| !c.is_whitespace()).collect();
    if cleaned.is_empty() {
        return Err("data is empty".to_string());
    }
    BASE64
        .decode(cleaned.as_bytes())
        .map_err(|e| format!("invalid base64 data: {e}"))
}

/// Encode bytes as standard base64.
pub fn encode_base64(data: &[u8]) -> String {
    BASE64.encode(data)
}

/// Sniff an image format from its magic bytes. Returns `(extension, mime)`.
pub fn sniff_image(data: &[u8]) -> Option<(&'static str, &'static str)> {
    if data.starts_with(b"\x89PNG\r\n\x1a\n") {
        Some(("png", "image/png"))
    } else if data.starts_with(&[0xFF, 0xD8, 0xFF]) {
        Some(("jpg", "image/jpeg"))
    } else if data.len() >= 12 && &data[0..4] == b"RIFF" && &data[8..12] == b"WEBP" {
        Some(("webp", "image/webp"))
    } else if data.starts_with(b"GIF87a") || data.starts_with(b"GIF89a") {
        Some(("gif", "image/gif"))
    } else if data.starts_with(b"BM") {
        Some(("bmp", "image/bmp"))
    } else {
        None
    }
}

/// MIME type for an image file name, by extension.
pub fn mime_for_filename(name: &str) -> &'static str {
    let ext = name
        .rsplit_once('.')
        .map(|(_, e)| e.to_ascii_lowercase())
        .unwrap_or_default();
    match ext.as_str() {
        "png" => "image/png",
        "jpg" | "jpeg" => "image/jpeg",
        "webp" => "image/webp",
        "gif" => "image/gif",
        "bmp" => "image/bmp",
        _ => "application/octet-stream",
    }
}

/// Check that `value` lies in `[min, max]`, producing a readable error.
pub fn check_range<T: PartialOrd + std::fmt::Display>(
    name: &str,
    value: T,
    min: T,
    max: T,
) -> Result<T, String> {
    if value < min || value > max {
        Err(format!(
            "{name} must be between {min} and {max} (got {value})"
        ))
    } else {
        Ok(value)
    }
}

/// Validate an image dimension: within 64..=8192 and a multiple of 8
/// (the latent space granularity used by SD/SDXL/FLUX VAEs).
pub fn check_dimension(name: &str, value: u32) -> Result<u32, String> {
    check_range(name, value, 64, 8192)?;
    if !value.is_multiple_of(8) {
        return Err(format!("{name} must be a multiple of 8 (got {value})"));
    }
    Ok(value)
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn filename_accepts_plain_names() {
        assert!(validate_filename("my_lora.safetensors", LORA_EXTENSIONS).is_ok());
        assert!(validate_filename("Style v2.CKPT", LORA_EXTENSIONS).is_ok());
        assert!(validate_filename("cat.png", IMAGE_EXTENSIONS).is_ok());
    }

    #[test]
    fn filename_rejects_traversal_and_junk() {
        for bad in [
            "",
            "../evil.safetensors",
            "..\\evil.safetensors",
            "sub/dir.safetensors",
            "C:evil.safetensors",
            ".hidden.safetensors",
            "..",
            "no_extension",
            "wrong.exe",
            "new\nline.safetensors",
            "quo\"te.safetensors",
        ] {
            assert!(
                validate_filename(bad, LORA_EXTENSIONS).is_err(),
                "should reject {bad:?}"
            );
        }
        let long = format!("{}.safetensors", "a".repeat(300));
        assert!(validate_filename(&long, LORA_EXTENSIONS).is_err());
    }

    #[test]
    fn subfolder_rules() {
        assert!(validate_subfolder("").is_ok());
        assert!(validate_subfolder("refs/faces").is_ok());
        for bad in ["../x", "a/../b", "/abs", "a//b", "a\\b", "C:/x", "a/."] {
            assert!(validate_subfolder(bad).is_err(), "should reject {bad:?}");
        }
    }

    #[test]
    fn base64_variants() {
        assert_eq!(decode_base64("aGVsbG8=").unwrap(), b"hello");
        assert_eq!(decode_base64("aGVs\nbG8=\n").unwrap(), b"hello");
        assert_eq!(
            decode_base64("data:image/png;base64,aGVsbG8=").unwrap(),
            b"hello"
        );
        assert!(decode_base64("").is_err());
        assert!(decode_base64("data:image/png;base64").is_err());
        assert!(decode_base64("!!!").is_err());
        assert_eq!(encode_base64(b"hello"), "aGVsbG8=");
    }

    #[test]
    fn sniffing() {
        assert_eq!(sniff_image(b"\x89PNG\r\n\x1a\nrest").unwrap().0, "png");
        assert_eq!(sniff_image(&[0xFF, 0xD8, 0xFF, 0xE0]).unwrap().0, "jpg");
        assert_eq!(sniff_image(b"RIFF1234WEBPVP8 ").unwrap().0, "webp");
        assert_eq!(sniff_image(b"GIF89a").unwrap().0, "gif");
        assert!(sniff_image(b"hello").is_none());
        assert_eq!(mime_for_filename("a.JPG"), "image/jpeg");
        assert_eq!(mime_for_filename("a"), "application/octet-stream");
    }

    #[test]
    fn ranges_and_dimensions() {
        assert!(check_range("steps", 20u32, 1, 200).is_ok());
        assert!(check_range("steps", 0u32, 1, 200).is_err());
        assert!(check_dimension("width", 1024).is_ok());
        assert!(check_dimension("width", 1000).is_ok());
        assert!(check_dimension("width", 1004).is_err());
        assert!(check_dimension("width", 1001).is_err());
        assert!(check_dimension("width", 32).is_err());
        assert!(check_dimension("width", 16384).is_err());
    }
}
