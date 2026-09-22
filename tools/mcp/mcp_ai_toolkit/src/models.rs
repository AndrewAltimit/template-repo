//! Discovery and transfer of trained model files under the outputs directory.
//!
//! AI Toolkit writes weights to `<training_folder>/<run>/<run>.safetensors`
//! (plus step checkpoints `<run>_000000250.safetensors`), so model names are
//! relative paths without extension, e.g. `my_lora/my_lora` or
//! `exports/my_lora`. A bare run name (`my_lora`) also resolves to the final
//! weights of that run.

use serde::Serialize;
use sha2::{Digest, Sha256};
use std::io::{Read, Seek, SeekFrom};
use std::path::{Path, PathBuf};

use crate::config::validate_path;

/// Recognised model weight extensions, in lookup priority order.
pub const MODEL_EXTENSIONS: &[&str] = &["safetensors", "ckpt", "pt"];

/// Directory depth searched below the outputs directory.
const MAX_DEPTH: usize = 3;

/// File names that carry the model extension but are not weights.
const NON_MODEL_FILES: &[&str] = &["optimizer.pt"];

/// Directories never searched for weights.
const SKIP_DIRS: &[&str] = &["samples", ".cache", "logs"];

/// A model file found under the outputs directory.
#[derive(Debug, Clone, Serialize)]
pub struct ModelInfo {
    /// Name usable with export/download/delete (relative path, no extension).
    pub name: String,
    pub path: String,
    pub size: u64,
    pub extension: String,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub modified_at: Option<String>,
}

fn model_ext(path: &Path) -> Option<String> {
    let ext = path.extension()?.to_string_lossy().to_ascii_lowercase();
    MODEL_EXTENSIONS.contains(&ext.as_str()).then_some(ext)
}

fn is_model_file(path: &Path) -> bool {
    let name = path
        .file_name()
        .map(|n| n.to_string_lossy().to_ascii_lowercase())
        .unwrap_or_default();
    model_ext(path).is_some() && !NON_MODEL_FILES.contains(&name.as_str())
}

/// List model files below `outputs` (blocking; depth-limited, skips samples).
pub fn list_models(outputs: &Path) -> Vec<ModelInfo> {
    let mut models = Vec::new();
    walk(outputs, outputs, 0, &mut models);
    models.sort_by(|a, b| a.name.cmp(&b.name));
    models
}

fn walk(root: &Path, dir: &Path, depth: usize, out: &mut Vec<ModelInfo>) {
    let Ok(entries) = std::fs::read_dir(dir) else {
        return;
    };
    for entry in entries.flatten() {
        let path = entry.path();
        // Do not follow symlinks (avoids cycles and escapes).
        let Ok(ft) = entry.file_type() else { continue };
        if ft.is_dir() {
            let name = entry.file_name().to_string_lossy().to_string();
            if depth < MAX_DEPTH && !name.starts_with('.') && !SKIP_DIRS.contains(&name.as_str()) {
                walk(root, &path, depth + 1, out);
            }
        } else if ft.is_file() && is_model_file(&path) {
            let Ok(meta) = entry.metadata() else { continue };
            let rel = path.strip_prefix(root).unwrap_or(&path).with_extension("");
            let name = rel
                .components()
                .map(|c| c.as_os_str().to_string_lossy().to_string())
                .collect::<Vec<_>>()
                .join("/");
            out.push(ModelInfo {
                name,
                path: path.display().to_string(),
                size: meta.len(),
                extension: model_ext(&path).unwrap_or_default(),
                modified_at: meta
                    .modified()
                    .ok()
                    .map(|t| chrono::DateTime::<chrono::Utc>::from(t).to_rfc3339()),
            });
        }
    }
}

/// Candidate files for a model name, in priority order.
pub fn model_candidates(outputs: &Path, name: &str) -> Result<Vec<PathBuf>, String> {
    let name = name.trim().trim_end_matches(['/', '\\']);
    let base = validate_path(name, outputs, "model").map_err(|e| e.to_string())?;
    let mut out = Vec::new();

    // Name given with its extension.
    if model_ext(&base).is_some() {
        out.push(base.clone());
    }
    for ext in MODEL_EXTENSIONS {
        out.push(PathBuf::from(format!("{}.{ext}", base.display())));
    }
    // Bare run name -> final weights inside the run folder.
    if let Some(last) = base.file_name() {
        let last = last.to_string_lossy();
        for ext in MODEL_EXTENSIONS {
            out.push(base.join(format!("{last}.{ext}")));
        }
    }
    Ok(out)
}

/// Resolve a model name to an existing weight file.
pub fn resolve_model(outputs: &Path, name: &str) -> Result<PathBuf, String> {
    let candidates = model_candidates(outputs, name)?;
    candidates
        .into_iter()
        .find(|p| p.is_file() && is_model_file(p))
        .ok_or_else(|| {
            format!(
                "Model '{name}' not found under outputs (use list_exported_models to see names)"
            )
        })
}

/// SHA-256 of a file as lowercase hex (blocking).
pub fn sha256_file(path: &Path) -> std::io::Result<String> {
    let mut file = std::fs::File::open(path)?;
    let mut hasher = Sha256::new();
    let mut buf = vec![0u8; 1024 * 1024];
    loop {
        let n = file.read(&mut buf)?;
        if n == 0 {
            break;
        }
        hasher.update(&buf[..n]);
    }
    Ok(to_hex(&hasher.finalize()))
}

/// SHA-256 of a byte slice as lowercase hex.
pub fn sha256_bytes(bytes: &[u8]) -> String {
    to_hex(&Sha256::digest(bytes))
}

fn to_hex(bytes: &[u8]) -> String {
    use std::fmt::Write;
    bytes.iter().fold(String::with_capacity(64), |mut s, b| {
        let _ = write!(s, "{b:02x}");
        s
    })
}

/// Read `len` bytes starting at `offset` (blocking). Returns fewer bytes at EOF.
pub fn read_chunk(path: &Path, offset: u64, len: usize) -> std::io::Result<Vec<u8>> {
    let mut file = std::fs::File::open(path)?;
    file.seek(SeekFrom::Start(offset))?;
    let mut buf = Vec::with_capacity(len);
    file.take(len as u64).read_to_end(&mut buf)?;
    Ok(buf)
}

/// Compute the destination of an export.
///
/// Without `output_path` the model is copied to `outputs/exports/<file name>`.
/// An `output_path` is validated to stay under `outputs`; if it has no model
/// extension the source extension is appended.
pub fn export_destination(
    outputs: &Path,
    exports: &Path,
    source: &Path,
    output_path: Option<&str>,
) -> Result<PathBuf, String> {
    let src_ext = model_ext(source).unwrap_or_else(|| "safetensors".into());
    let dest = match output_path {
        None => {
            let file = source
                .file_name()
                .ok_or_else(|| "source model has no file name".to_string())?;
            exports.join(file)
        },
        Some(p) => {
            let p = validate_path(p, outputs, "output").map_err(|e| e.to_string())?;
            if model_ext(&p).is_some() {
                p
            } else {
                PathBuf::from(format!("{}.{src_ext}", p.display()))
            }
        },
    };
    if same_file(source, &dest) {
        return Err("output_path is the same file as the source model".into());
    }
    Ok(dest)
}

fn same_file(a: &Path, b: &Path) -> bool {
    match (a.canonicalize(), b.canonicalize()) {
        (Ok(x), Ok(y)) => x == y,
        _ => a == b,
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    fn touch(p: &Path, bytes: &[u8]) {
        std::fs::create_dir_all(p.parent().unwrap()).unwrap();
        std::fs::write(p, bytes).unwrap();
    }

    #[test]
    fn list_and_resolve() {
        let tmp = tempfile::tempdir().unwrap();
        let out = tmp.path();
        touch(&out.join("root.safetensors"), b"a");
        touch(&out.join("run1/run1.safetensors"), b"bb");
        touch(&out.join("run1/run1_000000250.safetensors"), b"c");
        touch(&out.join("run1/optimizer.pt"), b"x");
        touch(&out.join("run1/samples/x.safetensors"), b"x");
        touch(&out.join("run1/config.yaml"), b"x");

        let names: Vec<_> = list_models(out).into_iter().map(|m| m.name).collect();
        assert_eq!(
            names,
            vec!["root", "run1/run1", "run1/run1_000000250"],
            "{names:?}"
        );

        assert_eq!(
            resolve_model(out, "root").unwrap(),
            out.join("root.safetensors")
        );
        assert_eq!(
            resolve_model(out, "run1").unwrap(),
            out.join("run1").join("run1.safetensors")
        );
        assert!(
            resolve_model(out, "run1/run1_000000250.safetensors")
                .unwrap()
                .ends_with("run1_000000250.safetensors")
        );
        assert!(resolve_model(out, "run1/optimizer").is_err());
        assert!(resolve_model(out, "../x").is_err());
        assert!(resolve_model(out, "missing").is_err());
    }

    #[test]
    fn export_destination_rules() {
        let tmp = tempfile::tempdir().unwrap();
        let out = tmp.path();
        let exports = out.join("exports");
        let src = out.join("run1").join("run1.safetensors");
        touch(&src, b"x");

        assert_eq!(
            export_destination(out, &exports, &src, None).unwrap(),
            exports.join("run1.safetensors")
        );
        assert_eq!(
            export_destination(out, &exports, &src, Some("final/cat")).unwrap(),
            PathBuf::from(format!(
                "{}.safetensors",
                out.join("final").join("cat").display()
            ))
        );
        // Copying onto itself would truncate the model.
        assert!(export_destination(out, &exports, &src, Some("run1/run1.safetensors")).is_err());
        assert!(export_destination(out, &exports, &src, Some("../escape")).is_err());
    }

    #[test]
    fn hashing_and_chunks() {
        let tmp = tempfile::tempdir().unwrap();
        let f = tmp.path().join("m.safetensors");
        std::fs::write(&f, b"abc").unwrap();
        let expected = "ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad";
        assert_eq!(sha256_file(&f).unwrap(), expected);
        assert_eq!(sha256_bytes(b"abc"), expected);
        assert_eq!(read_chunk(&f, 1, 10).unwrap(), b"bc");
        assert_eq!(read_chunk(&f, 5, 10).unwrap(), b"");
    }
}
