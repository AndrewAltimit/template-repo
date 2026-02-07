//! In-memory VFS implementation.
//!
//! Useful for unit tests and ephemeral terminals. The entire file tree lives
//! in a `HashMap<String, Node>` where keys are normalized absolute paths.

use std::collections::HashMap;

use crate::error::{OasisError, Result};
use crate::vfs::{EntryKind, Vfs, VfsEntry, VfsMetadata};

#[derive(Debug, Clone)]
enum Node {
    File(Vec<u8>),
    Dir,
}

/// A fully in-memory virtual file system.
#[derive(Debug)]
pub struct MemoryVfs {
    nodes: HashMap<String, Node>,
}

impl MemoryVfs {
    pub fn new() -> Self {
        let mut nodes = HashMap::new();
        nodes.insert("/".to_string(), Node::Dir);
        Self { nodes }
    }
}

impl Default for MemoryVfs {
    fn default() -> Self {
        Self::new()
    }
}

/// Normalize a path: ensure leading `/`, collapse `//`, strip trailing `/`
/// (except for root).
fn normalize(path: &str) -> String {
    let path = if path.starts_with('/') {
        path.to_string()
    } else {
        format!("/{path}")
    };
    // Collapse repeated slashes.
    let mut result = String::with_capacity(path.len());
    let mut prev_slash = false;
    for ch in path.chars() {
        if ch == '/' {
            if !prev_slash {
                result.push(ch);
            }
            prev_slash = true;
        } else {
            result.push(ch);
            prev_slash = false;
        }
    }
    // Strip trailing slash unless root.
    if result.len() > 1 && result.ends_with('/') {
        result.pop();
    }
    result
}

/// Return the parent of a normalized path.
fn parent(path: &str) -> &str {
    if path == "/" {
        return "/";
    }
    match path.rfind('/') {
        Some(0) => "/",
        Some(i) => &path[..i],
        None => "/",
    }
}

impl Vfs for MemoryVfs {
    fn readdir(&self, path: &str) -> Result<Vec<VfsEntry>> {
        let path = normalize(path);
        match self.nodes.get(&path) {
            Some(Node::Dir) => {},
            Some(Node::File(_)) => {
                return Err(OasisError::Vfs(format!("not a directory: {path}")));
            },
            None => {
                return Err(OasisError::Vfs(format!("no such directory: {path}")));
            },
        }

        let prefix = if path == "/" {
            "/".to_string()
        } else {
            format!("{path}/")
        };

        let mut entries = Vec::new();
        for (key, node) in &self.nodes {
            if key == &path {
                continue;
            }
            // Must start with prefix and not have another `/` after it
            // (i.e. direct child only).
            if let Some(rest) = key.strip_prefix(&prefix) {
                if !rest.contains('/') {
                    entries.push(VfsEntry {
                        name: rest.to_string(),
                        kind: match node {
                            Node::Dir => EntryKind::Directory,
                            Node::File(_) => EntryKind::File,
                        },
                        size: match node {
                            Node::File(data) => data.len() as u64,
                            Node::Dir => 0,
                        },
                    });
                }
            }
        }
        entries.sort_by(|a, b| a.name.cmp(&b.name));
        Ok(entries)
    }

    fn read(&self, path: &str) -> Result<Vec<u8>> {
        let path = normalize(path);
        match self.nodes.get(&path) {
            Some(Node::File(data)) => Ok(data.clone()),
            Some(Node::Dir) => Err(OasisError::Vfs(format!("is a directory: {path}"))),
            None => Err(OasisError::Vfs(format!("no such file: {path}"))),
        }
    }

    fn write(&mut self, path: &str, data: &[u8]) -> Result<()> {
        let path = normalize(path);
        // Ensure parent directory exists.
        let par = parent(&path).to_string();
        if !self.nodes.contains_key(&par) {
            return Err(OasisError::Vfs(format!(
                "parent directory does not exist: {par}"
            )));
        }
        self.nodes.insert(path, Node::File(data.to_vec()));
        Ok(())
    }

    fn stat(&self, path: &str) -> Result<VfsMetadata> {
        let path = normalize(path);
        match self.nodes.get(&path) {
            Some(Node::File(data)) => Ok(VfsMetadata {
                kind: EntryKind::File,
                size: data.len() as u64,
            }),
            Some(Node::Dir) => Ok(VfsMetadata {
                kind: EntryKind::Directory,
                size: 0,
            }),
            None => Err(OasisError::Vfs(format!("no such path: {path}"))),
        }
    }

    fn mkdir(&mut self, path: &str) -> Result<()> {
        let path = normalize(path);
        if self.nodes.contains_key(&path) {
            return Ok(()); // Already exists, no error.
        }
        // Ensure parent exists (create parents recursively).
        let par = parent(&path).to_string();
        if par != path && !self.nodes.contains_key(&par) {
            self.mkdir(&par)?;
        }
        self.nodes.insert(path, Node::Dir);
        Ok(())
    }

    fn remove(&mut self, path: &str) -> Result<()> {
        let path = normalize(path);
        if path == "/" {
            return Err(OasisError::Vfs("cannot remove root".to_string()));
        }
        match self.nodes.get(&path) {
            Some(Node::Dir) => {
                // Check that directory is empty.
                let prefix = format!("{path}/");
                let has_children = self.nodes.keys().any(|k| k.starts_with(&prefix));
                if has_children {
                    return Err(OasisError::Vfs(format!("directory not empty: {path}")));
                }
            },
            Some(Node::File(_)) => {},
            None => {
                return Err(OasisError::Vfs(format!("no such path: {path}")));
            },
        }
        self.nodes.remove(&path);
        Ok(())
    }

    fn exists(&self, path: &str) -> bool {
        let path = normalize(path);
        self.nodes.contains_key(&path)
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn root_exists() {
        let vfs = MemoryVfs::new();
        assert!(vfs.exists("/"));
    }

    #[test]
    fn mkdir_and_readdir() {
        let mut vfs = MemoryVfs::new();
        vfs.mkdir("/home").unwrap();
        vfs.mkdir("/home/user").unwrap();
        let entries = vfs.readdir("/").unwrap();
        assert_eq!(entries.len(), 1);
        assert_eq!(entries[0].name, "home");
        assert_eq!(entries[0].kind, EntryKind::Directory);
    }

    #[test]
    fn write_and_read() {
        let mut vfs = MemoryVfs::new();
        vfs.mkdir("/tmp").unwrap();
        vfs.write("/tmp/test.txt", b"hello world").unwrap();
        let data = vfs.read("/tmp/test.txt").unwrap();
        assert_eq!(data, b"hello world");
    }

    #[test]
    fn stat_file() {
        let mut vfs = MemoryVfs::new();
        vfs.mkdir("/data").unwrap();
        vfs.write("/data/f.bin", &[1, 2, 3]).unwrap();
        let meta = vfs.stat("/data/f.bin").unwrap();
        assert_eq!(meta.kind, EntryKind::File);
        assert_eq!(meta.size, 3);
    }

    #[test]
    fn stat_dir() {
        let mut vfs = MemoryVfs::new();
        vfs.mkdir("/etc").unwrap();
        let meta = vfs.stat("/etc").unwrap();
        assert_eq!(meta.kind, EntryKind::Directory);
    }

    #[test]
    fn remove_file() {
        let mut vfs = MemoryVfs::new();
        vfs.mkdir("/tmp").unwrap();
        vfs.write("/tmp/x", b"data").unwrap();
        assert!(vfs.exists("/tmp/x"));
        vfs.remove("/tmp/x").unwrap();
        assert!(!vfs.exists("/tmp/x"));
    }

    #[test]
    fn remove_empty_dir() {
        let mut vfs = MemoryVfs::new();
        vfs.mkdir("/empty").unwrap();
        vfs.remove("/empty").unwrap();
        assert!(!vfs.exists("/empty"));
    }

    #[test]
    fn remove_nonempty_dir_fails() {
        let mut vfs = MemoryVfs::new();
        vfs.mkdir("/dir").unwrap();
        vfs.write("/dir/file", b"x").unwrap();
        assert!(vfs.remove("/dir").is_err());
    }

    #[test]
    fn remove_root_fails() {
        let mut vfs = MemoryVfs::new();
        assert!(vfs.remove("/").is_err());
    }

    #[test]
    fn write_without_parent_fails() {
        let mut vfs = MemoryVfs::new();
        assert!(vfs.write("/no/such/dir/file", b"x").is_err());
    }

    #[test]
    fn read_nonexistent_fails() {
        let vfs = MemoryVfs::new();
        assert!(vfs.read("/nope").is_err());
    }

    #[test]
    fn readdir_on_file_fails() {
        let mut vfs = MemoryVfs::new();
        vfs.write("/file", b"data").unwrap();
        assert!(vfs.readdir("/file").is_err());
    }

    #[test]
    fn mkdir_creates_parents() {
        let mut vfs = MemoryVfs::new();
        vfs.mkdir("/a/b/c").unwrap();
        assert!(vfs.exists("/a"));
        assert!(vfs.exists("/a/b"));
        assert!(vfs.exists("/a/b/c"));
    }

    #[test]
    fn normalize_paths() {
        let mut vfs = MemoryVfs::new();
        vfs.mkdir("/dir/").unwrap();
        assert!(vfs.exists("/dir"));
        vfs.write("//dir//file", b"ok").unwrap();
        let data = vfs.read("/dir/file").unwrap();
        assert_eq!(data, b"ok");
    }

    #[test]
    fn readdir_only_direct_children() {
        let mut vfs = MemoryVfs::new();
        vfs.mkdir("/a/b/c").unwrap();
        vfs.write("/a/file.txt", b"hi").unwrap();
        let entries = vfs.readdir("/a").unwrap();
        let names: Vec<&str> = entries.iter().map(|e| e.name.as_str()).collect();
        assert!(names.contains(&"b"));
        assert!(names.contains(&"file.txt"));
        assert!(!names.contains(&"c")); // c is a grandchild
    }

    #[test]
    fn overwrite_file() {
        let mut vfs = MemoryVfs::new();
        vfs.write("/file", b"old").unwrap();
        vfs.write("/file", b"new content").unwrap();
        assert_eq!(vfs.read("/file").unwrap(), b"new content");
    }
}
