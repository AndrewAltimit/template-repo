//! Dataset scanning and image upload handling.
//!
//! A dataset is a directory of images with optional same-stem `.txt` caption
//! files, which is the layout AI Toolkit's `folder_path` datasets expect.

use base64::{Engine, engine::general_purpose::STANDARD as BASE64};
use serde::{Deserialize, Serialize};
use std::collections::HashSet;
use std::path::Path;

use crate::config::validate_filename;

/// Image extensions AI Toolkit loads from a dataset folder.
pub const IMAGE_EXTENSIONS: &[&str] = &["jpg", "jpeg", "png", "webp"];

/// Maximum decoded size of a single uploaded image.
pub const MAX_IMAGE_BYTES: usize = 50 * 1024 * 1024;

/// Maximum caption length in bytes.
pub const MAX_CAPTION_BYTES: usize = 16 * 1024;

/// Summary statistics of a dataset directory.
#[derive(Debug, Clone, Default, Serialize)]
pub struct DatasetStats {
    pub image_count: usize,
    pub caption_count: usize,
    pub missing_caption_count: usize,
    /// First N images lacking a caption (N is the `max_missing` scan argument).
    pub missing_captions: Vec<String>,
    /// Total size of image files in bytes.
    pub total_size_bytes: u64,
}

/// Whether `path` has a supported image extension.
pub fn is_image(path: &Path) -> bool {
    path.extension()
        .map(|e| e.to_string_lossy().to_ascii_lowercase())
        .is_some_and(|e| IMAGE_EXTENSIONS.contains(&e.as_str()))
}

/// Scan a dataset directory (non-recursive, blocking I/O).
///
/// `max_missing` caps the number of names collected in `missing_captions`.
pub fn scan_dataset(dir: &Path, max_missing: usize) -> std::io::Result<DatasetStats> {
    let mut images = Vec::new();
    let mut captions = HashSet::new();
    let mut stats = DatasetStats::default();

    for entry in std::fs::read_dir(dir)? {
        let entry = entry?;
        let path = entry.path();
        let Ok(meta) = entry.metadata() else { continue };
        if !meta.is_file() {
            continue;
        }
        let ext = path
            .extension()
            .map(|e| e.to_string_lossy().to_ascii_lowercase())
            .unwrap_or_default();
        let stem = path
            .file_stem()
            .map(|s| s.to_string_lossy().to_string())
            .unwrap_or_default();
        if ext == "txt" {
            captions.insert(stem);
        } else if IMAGE_EXTENSIONS.contains(&ext.as_str()) {
            stats.total_size_bytes += meta.len();
            images.push((
                stem,
                path.file_name()
                    .map(|n| n.to_string_lossy().to_string())
                    .unwrap_or_default(),
            ));
        }
    }

    images.sort();
    stats.image_count = images.len();
    for (stem, file_name) in &images {
        if captions.contains(stem) {
            stats.caption_count += 1;
        } else {
            stats.missing_caption_count += 1;
            if stats.missing_captions.len() < max_missing {
                stats.missing_captions.push(file_name.clone());
            }
        }
    }
    Ok(stats)
}

/// Detect an image format from magic bytes.
pub fn sniff_image_format(bytes: &[u8]) -> Option<&'static str> {
    if bytes.starts_with(&[0x89, b'P', b'N', b'G', 0x0D, 0x0A, 0x1A, 0x0A]) {
        Some("png")
    } else if bytes.starts_with(&[0xFF, 0xD8, 0xFF]) {
        Some("jpeg")
    } else if bytes.len() >= 12 && &bytes[0..4] == b"RIFF" && &bytes[8..12] == b"WEBP" {
        Some("webp")
    } else {
        None
    }
}

/// Decode base64 image data, accepting an optional `data:<mime>;base64,` prefix
/// and embedded whitespace/newlines.
pub fn decode_base64_image(data: &str) -> Result<Vec<u8>, String> {
    let payload = match data.split_once(";base64,") {
        Some((prefix, rest)) if prefix.starts_with("data:") => rest,
        _ => data,
    };
    let cleaned: String = payload.chars().filter(|c| !c.is_whitespace()).collect();
    if cleaned.is_empty() {
        return Err("image data is empty".into());
    }
    // Reject oversized input before allocating the decoded buffer.
    if cleaned.len() / 4 * 3 > MAX_IMAGE_BYTES + 3 {
        return Err(format!(
            "image exceeds the {} MB limit",
            MAX_IMAGE_BYTES / 1024 / 1024
        ));
    }
    BASE64
        .decode(cleaned.as_bytes())
        .map_err(|e| format!("invalid base64: {e}"))
}

/// One image in an `upload_dataset` request.
#[derive(Debug, Clone, Deserialize)]
pub struct ImageUpload {
    pub filename: String,
    pub data: String,
    #[serde(default)]
    pub caption: Option<String>,
}

/// A validated, decoded image ready to be written.
#[derive(Debug)]
pub struct PreparedImage {
    pub filename: String,
    pub bytes: Vec<u8>,
    pub caption: Option<String>,
    pub format: &'static str,
}

/// Validate one upload entry: file name, extension, base64 payload, content
/// type and caption size.
pub fn prepare_image(upload: &ImageUpload) -> Result<PreparedImage, String> {
    validate_filename(&upload.filename, "image").map_err(|e| e.to_string())?;
    if !is_image(Path::new(&upload.filename)) {
        return Err(format!(
            "unsupported extension (allowed: {})",
            IMAGE_EXTENSIONS.join(", ")
        ));
    }
    let bytes = decode_base64_image(&upload.data)?;
    let format = sniff_image_format(&bytes)
        .ok_or_else(|| "data is not a PNG, JPEG or WebP image".to_string())?;
    let caption = upload.caption.as_ref().map(|c| c.trim().to_string());
    if let Some(c) = &caption
        && c.len() > MAX_CAPTION_BYTES
    {
        return Err(format!("caption exceeds {MAX_CAPTION_BYTES} bytes"));
    }
    Ok(PreparedImage {
        filename: upload.filename.clone(),
        bytes,
        caption,
        format,
    })
}

#[cfg(test)]
mod tests {
    use super::*;

    const PNG_HEADER: &[u8] = &[0x89, b'P', b'N', b'G', 0x0D, 0x0A, 0x1A, 0x0A, 0, 0];

    #[test]
    fn sniff_formats() {
        assert_eq!(sniff_image_format(PNG_HEADER), Some("png"));
        assert_eq!(sniff_image_format(&[0xFF, 0xD8, 0xFF, 0xE0]), Some("jpeg"));
        assert_eq!(sniff_image_format(b"RIFF\0\0\0\0WEBPVP8 "), Some("webp"));
        assert_eq!(sniff_image_format(b"GIF89a"), None);
        assert_eq!(sniff_image_format(b""), None);
    }

    #[test]
    fn decode_variants() {
        let b64 = BASE64.encode(PNG_HEADER);
        assert_eq!(decode_base64_image(&b64).unwrap(), PNG_HEADER);
        let with_prefix = format!("data:image/png;base64,{b64}");
        assert_eq!(decode_base64_image(&with_prefix).unwrap(), PNG_HEADER);
        let wrapped = format!("{}\n{}", &b64[..4], &b64[4..]);
        assert_eq!(decode_base64_image(&wrapped).unwrap(), PNG_HEADER);
        assert!(decode_base64_image("").is_err());
        assert!(decode_base64_image("!!!notbase64").is_err());
    }

    #[test]
    fn prepare_validates() {
        let good = ImageUpload {
            filename: "a.png".into(),
            data: BASE64.encode(PNG_HEADER),
            caption: Some(" a cat ".into()),
        };
        let p = prepare_image(&good).unwrap();
        assert_eq!(p.format, "png");
        assert_eq!(p.caption.as_deref(), Some("a cat"));

        let mut bad = good.clone();
        bad.filename = "../a.png".into();
        assert!(prepare_image(&bad).is_err());

        let mut bad = good.clone();
        bad.filename = "a.txt".into();
        assert!(prepare_image(&bad).unwrap_err().contains("extension"));

        let mut bad = good.clone();
        bad.data = BASE64.encode(b"hello world");
        assert!(prepare_image(&bad).unwrap_err().contains("not a PNG"));
    }

    #[test]
    fn scan_counts_captions() {
        let tmp = tempfile::tempdir().unwrap();
        let d = tmp.path();
        std::fs::write(d.join("a.png"), b"1234").unwrap();
        std::fs::write(d.join("a.txt"), b"cap").unwrap();
        std::fs::write(d.join("b.JPG"), b"12").unwrap();
        std::fs::write(d.join("c.webp"), b"1").unwrap();
        std::fs::write(d.join("notes.md"), b"x").unwrap();
        std::fs::create_dir(d.join("sub.png")).unwrap();

        let s = scan_dataset(d, 1).unwrap();
        assert_eq!(s.image_count, 3);
        assert_eq!(s.caption_count, 1);
        assert_eq!(s.missing_caption_count, 2);
        assert_eq!(s.missing_captions, vec!["b.JPG".to_string()]);
        assert_eq!(s.total_size_bytes, 7);
    }
}
