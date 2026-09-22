//! Local LoRA file management in `<COMFYUI_PATH>/models/loras`.
//!
//! These operations touch the filesystem of the machine running the MCP
//! server, which is the ComfyUI host/container in the supported deployment.
//! All file names are validated as bare names (see
//! [`crate::validate::validate_filename`]) so nothing can escape the directory.

use std::path::{Path, PathBuf};

use serde::Serialize;
use serde_json::Value;
use tracing::info;

use crate::validate::{LORA_EXTENSIONS, validate_filename};

/// Information about a LoRA file on disk.
#[derive(Debug, Clone, PartialEq, Serialize)]
pub struct LoraInfo {
    /// File stem (what users usually call the LoRA).
    pub name: String,
    /// Full file name (what ComfyUI's `LoraLoader.lora_name` expects).
    pub filename: String,
    /// Size in bytes.
    pub size: u64,
    /// Whether a sidecar `<stem>.json` metadata file exists.
    pub has_metadata: bool,
}

/// Result of a successful upload.
#[derive(Debug, Clone, Serialize)]
pub struct UploadedLora {
    /// Absolute path written.
    pub path: PathBuf,
    /// Bytes written.
    pub size: usize,
    /// Whether an existing file was replaced.
    pub replaced: bool,
    /// Path of the metadata sidecar, if written.
    #[serde(skip_serializing_if = "Option::is_none")]
    pub metadata_path: Option<PathBuf>,
}

/// LoRA directory manager.
#[derive(Debug, Clone)]
pub struct LoraStore {
    dir: PathBuf,
    max_download_bytes: u64,
}

fn metadata_path_for(path: &Path) -> PathBuf {
    path.with_extension("json")
}

/// Write via a temporary file + rename so ComfyUI never loads a partial file.
async fn write_atomic(target: &Path, data: &[u8]) -> Result<(), String> {
    let parent = target
        .parent()
        .ok_or_else(|| format!("{} has no parent directory", target.display()))?;
    let file_name = target
        .file_name()
        .map(|n| n.to_string_lossy().into_owned())
        .unwrap_or_default();
    let tmp = parent.join(format!(
        ".{file_name}.{}.tmp",
        uuid::Uuid::new_v4().simple()
    ));
    if let Err(e) = tokio::fs::write(&tmp, data).await {
        let _ = tokio::fs::remove_file(&tmp).await;
        return Err(format!("failed to write {}: {e}", tmp.display()));
    }
    if let Err(e) = tokio::fs::rename(&tmp, target).await {
        let _ = tokio::fs::remove_file(&tmp).await;
        return Err(format!(
            "failed to move file into place at {}: {e}",
            target.display()
        ));
    }
    Ok(())
}

impl LoraStore {
    /// Manage LoRAs in `dir`; `download` refuses files over `max_download_bytes`.
    pub fn new(dir: PathBuf, max_download_bytes: u64) -> Self {
        Self {
            dir,
            max_download_bytes,
        }
    }

    /// The managed directory.
    pub fn dir(&self) -> &Path {
        &self.dir
    }

    /// Store a LoRA (and optional JSON metadata sidecar).
    pub async fn upload(
        &self,
        filename: &str,
        data: &[u8],
        metadata: Option<&Value>,
        overwrite: bool,
    ) -> Result<UploadedLora, String> {
        let filename = validate_filename(filename, LORA_EXTENSIONS)?;
        if data.is_empty() {
            return Err("LoRA data is empty".to_string());
        }
        tokio::fs::create_dir_all(&self.dir)
            .await
            .map_err(|e| format!("failed to create {}: {e}", self.dir.display()))?;

        let path = self.dir.join(filename);
        let replaced = tokio::fs::try_exists(&path).await.unwrap_or(false);
        if replaced && !overwrite {
            return Err(format!(
                "LoRA {filename:?} already exists; pass overwrite=true to replace it"
            ));
        }
        write_atomic(&path, data).await?;

        let metadata_path = match metadata {
            Some(meta) if !meta.is_null() => {
                let meta_path = metadata_path_for(&path);
                let text = serde_json::to_string_pretty(meta)
                    .map_err(|e| format!("failed to serialize metadata: {e}"))?;
                write_atomic(&meta_path, text.as_bytes()).await?;
                Some(meta_path)
            },
            _ => None,
        };

        info!("Stored LoRA {filename} ({} bytes)", data.len());
        Ok(UploadedLora {
            path,
            size: data.len(),
            replaced,
            metadata_path,
        })
    }

    /// List LoRA files (top level only), sorted by file name.
    pub async fn list(&self) -> Result<Vec<LoraInfo>, String> {
        let mut entries = match tokio::fs::read_dir(&self.dir).await {
            Ok(entries) => entries,
            Err(e) if e.kind() == std::io::ErrorKind::NotFound => return Ok(Vec::new()),
            Err(e) => return Err(format!("failed to read {}: {e}", self.dir.display())),
        };

        let mut loras = Vec::new();
        while let Some(entry) = entries
            .next_entry()
            .await
            .map_err(|e| format!("failed to read {}: {e}", self.dir.display()))?
        {
            let path = entry.path();
            let Some(filename) = path.file_name().and_then(|n| n.to_str()) else {
                continue;
            };
            if validate_filename(filename, LORA_EXTENSIONS).is_err() {
                continue;
            }
            let Ok(meta) = entry.metadata().await else {
                continue;
            };
            if !meta.is_file() {
                continue;
            }
            let has_metadata = tokio::fs::try_exists(metadata_path_for(&path))
                .await
                .unwrap_or(false);
            loras.push(LoraInfo {
                name: path
                    .file_stem()
                    .map(|s| s.to_string_lossy().into_owned())
                    .unwrap_or_default(),
                filename: filename.to_string(),
                size: meta.len(),
                has_metadata,
            });
        }
        loras.sort_by(|a, b| a.filename.cmp(&b.filename));
        Ok(loras)
    }

    /// Read a LoRA file, enforcing the configured size cap.
    pub async fn download(&self, filename: &str) -> Result<Vec<u8>, String> {
        let filename = validate_filename(filename, LORA_EXTENSIONS)?;
        let path = self.dir.join(filename);
        let meta = match tokio::fs::metadata(&path).await {
            Ok(meta) if meta.is_file() => meta,
            Ok(_) => return Err(format!("{filename:?} is not a regular file")),
            Err(e) if e.kind() == std::io::ErrorKind::NotFound => {
                return Err(format!("LoRA not found: {filename}"));
            },
            Err(e) => return Err(format!("failed to stat {}: {e}", path.display())),
        };
        if meta.len() > self.max_download_bytes {
            return Err(format!(
                "LoRA {filename:?} is {} bytes, above the {}-byte download limit \
                 (COMFYUI_MAX_LORA_DOWNLOAD_BYTES)",
                meta.len(),
                self.max_download_bytes
            ));
        }
        tokio::fs::read(&path)
            .await
            .map_err(|e| format!("failed to read {}: {e}", path.display()))
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use serde_json::json;

    fn store(max: u64) -> (tempfile::TempDir, LoraStore) {
        let tmp = tempfile::tempdir().unwrap();
        let s = LoraStore::new(tmp.path().join("models").join("loras"), max);
        (tmp, s)
    }

    #[tokio::test]
    async fn upload_list_download_roundtrip() {
        let (_tmp, s) = store(1024);
        assert!(
            s.list().await.unwrap().is_empty(),
            "missing dir lists empty"
        );

        let up = s
            .upload(
                "style.safetensors",
                b"weights",
                Some(&json!({"trigger": "zzz"})),
                false,
            )
            .await
            .unwrap();
        assert_eq!(up.size, 7);
        assert!(!up.replaced);
        let meta_path = up.metadata_path.unwrap();
        assert!(meta_path.ends_with("style.json"));
        let meta: Value =
            serde_json::from_str(&std::fs::read_to_string(meta_path).unwrap()).unwrap();
        assert_eq!(meta["trigger"], "zzz");

        s.upload("a.ckpt", b"x", None, false).await.unwrap();
        std::fs::write(s.dir().join("notes.txt"), "ignored").unwrap();

        let list = s.list().await.unwrap();
        let names: Vec<_> = list.iter().map(|l| l.filename.as_str()).collect();
        assert_eq!(names, ["a.ckpt", "style.safetensors"]);
        assert!(list[1].has_metadata);
        assert!(!list[0].has_metadata);
        assert_eq!(list[1].name, "style");

        assert_eq!(s.download("style.safetensors").await.unwrap(), b"weights");
        // No temp files left behind.
        assert!(
            std::fs::read_dir(s.dir()).unwrap().all(|e| !e
                .unwrap()
                .file_name()
                .to_string_lossy()
                .ends_with(".tmp"))
        );
    }

    #[tokio::test]
    async fn overwrite_protection() {
        let (_tmp, s) = store(1024);
        s.upload("x.safetensors", b"one", None, false)
            .await
            .unwrap();
        let err = s
            .upload("x.safetensors", b"two", None, false)
            .await
            .unwrap_err();
        assert!(err.contains("overwrite=true"), "{err}");
        let up = s.upload("x.safetensors", b"two", None, true).await.unwrap();
        assert!(up.replaced);
        assert_eq!(s.download("x.safetensors").await.unwrap(), b"two");
    }

    #[tokio::test]
    async fn rejects_traversal_bad_ext_and_empty() {
        let (tmp, s) = store(1024);
        assert!(
            s.upload("../escape.safetensors", b"x", None, true)
                .await
                .is_err()
        );
        assert!(s.upload("evil.sh", b"x", None, true).await.is_err());
        assert!(
            s.upload("empty.safetensors", b"", None, true)
                .await
                .is_err()
        );
        assert!(
            !tmp.path()
                .join("models")
                .join("escape.safetensors")
                .exists()
        );
        assert!(s.download("../../etc/passwd.safetensors").await.is_err());
    }

    #[tokio::test]
    async fn download_limits_and_missing() {
        let (_tmp, s) = store(4);
        s.upload("big.safetensors", b"12345", None, false)
            .await
            .unwrap();
        let err = s.download("big.safetensors").await.unwrap_err();
        assert!(err.contains("download limit"), "{err}");
        let err = s.download("nope.safetensors").await.unwrap_err();
        assert!(err.contains("not found"), "{err}");
    }
}
