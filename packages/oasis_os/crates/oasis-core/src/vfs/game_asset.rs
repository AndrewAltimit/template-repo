//! Game asset virtual file system.
//!
//! Two-layer VFS with an immutable base (game-authored content) and a writable
//! overlay (player modifications). Used in UE5 where each in-game terminal
//! has its own pre-populated content defined by level designers.

use std::collections::{HashMap, HashSet};

use crate::error::{OasisError, Result};
use crate::vfs::{EntryKind, Vfs, VfsEntry, VfsMetadata};

/// An entry in the game asset VFS.
#[derive(Debug, Clone)]
enum Node {
    File(Vec<u8>),
    Dir,
}

/// Two-layer VFS: immutable base + writable overlay.
///
/// The base layer represents game-authored content that the player can read
/// but not directly modify. The overlay layer captures any writes the player
/// makes. A deleted set tracks base entries that have been "removed".
///
/// This enables gameplay patterns like:
/// - Pre-populated lore files that the player can `cat` but not accidentally destroy
/// - Writable directories where the player can create files to solve puzzles
/// - "Hacking" scenarios where the player edits config files (overlay captures edits)
pub struct GameAssetVfs {
    base: HashMap<String, Node>,
    overlay: HashMap<String, Node>,
    deleted: HashSet<String>,
}

impl GameAssetVfs {
    /// Create a new empty GameAssetVfs with only the root directory.
    pub fn new() -> Self {
        let mut base = HashMap::new();
        base.insert("/".to_string(), Node::Dir);
        Self {
            base,
            overlay: HashMap::new(),
            deleted: HashSet::new(),
        }
    }

    /// Add a file to the immutable base layer.
    ///
    /// Parent directories are created automatically.
    pub fn add_base_file(&mut self, path: &str, data: &[u8]) {
        let path = normalize(path);
        ensure_parents(&mut self.base, &path);
        self.base.insert(path, Node::File(data.to_vec()));
    }

    /// Add a directory to the immutable base layer.
    pub fn add_base_dir(&mut self, path: &str) {
        let path = normalize(path);
        ensure_parents(&mut self.base, &path);
        self.base.insert(path, Node::Dir);
    }

    /// Look up the effective entry at a path (overlay wins, deleted hides).
    fn effective_entry(&self, path: &str) -> Option<&Node> {
        if self.deleted.contains(path) {
            return None;
        }
        self.overlay.get(path).or_else(|| self.base.get(path))
    }

    /// Check if an effective directory exists, checking both overlay and base
    /// but also checking overlay directories that may have been added.
    fn effective_dir_exists(&self, path: &str) -> bool {
        if self.deleted.contains(path) {
            return false;
        }
        matches!(
            self.overlay.get(path).or_else(|| self.base.get(path)),
            Some(Node::Dir)
        )
    }
}

impl Default for GameAssetVfs {
    fn default() -> Self {
        Self::new()
    }
}

impl Vfs for GameAssetVfs {
    fn readdir(&self, path: &str) -> Result<Vec<VfsEntry>> {
        let path = normalize(path);
        match self.effective_entry(&path) {
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

        // Merge entries from both layers using a HashMap to deduplicate.
        let mut entries: HashMap<String, (EntryKind, u64)> = HashMap::new();

        // Base layer (skip deleted entries).
        for (p, node) in &self.base {
            if self.deleted.contains(p) {
                continue;
            }
            if let Some(name) = direct_child(p, &prefix) {
                let (kind, size) = match node {
                    Node::File(data) => (EntryKind::File, data.len() as u64),
                    Node::Dir => (EntryKind::Directory, 0),
                };
                entries.insert(name, (kind, size));
            }
        }

        // Overlay overrides base.
        for (p, node) in &self.overlay {
            if let Some(name) = direct_child(p, &prefix) {
                let (kind, size) = match node {
                    Node::File(data) => (EntryKind::File, data.len() as u64),
                    Node::Dir => (EntryKind::Directory, 0),
                };
                entries.insert(name, (kind, size));
            }
        }

        let mut result: Vec<VfsEntry> = entries
            .into_iter()
            .map(|(name, (kind, size))| VfsEntry { name, kind, size })
            .collect();
        result.sort_by(|a, b| a.name.cmp(&b.name));
        Ok(result)
    }

    fn read(&self, path: &str) -> Result<Vec<u8>> {
        let path = normalize(path);
        match self.effective_entry(&path) {
            Some(Node::File(data)) => Ok(data.clone()),
            Some(Node::Dir) => Err(OasisError::Vfs(format!("is a directory: {path}"))),
            None => Err(OasisError::Vfs(format!("no such file: {path}"))),
        }
    }

    fn write(&mut self, path: &str, data: &[u8]) -> Result<()> {
        let path = normalize(path);
        let par = parent(&path);
        if !self.effective_dir_exists(par) {
            return Err(OasisError::Vfs(format!(
                "parent directory does not exist: {par}"
            )));
        }
        // Un-delete if it was previously deleted.
        self.deleted.remove(&path);
        self.overlay.insert(path, Node::File(data.to_vec()));
        Ok(())
    }

    fn stat(&self, path: &str) -> Result<VfsMetadata> {
        let path = normalize(path);
        match self.effective_entry(&path) {
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
        if self.effective_entry(&path).is_some() {
            return Ok(());
        }
        // Ensure parent exists.
        let par = parent(&path).to_string();
        if par != path && !self.effective_dir_exists(&par) {
            self.mkdir(&par)?;
        }
        self.deleted.remove(&path);
        self.overlay.insert(path, Node::Dir);
        Ok(())
    }

    fn remove(&mut self, path: &str) -> Result<()> {
        let path = normalize(path);
        if path == "/" {
            return Err(OasisError::Vfs("cannot remove root".to_string()));
        }
        match self.effective_entry(&path) {
            Some(Node::Dir) => {
                let prefix = format!("{path}/");
                // Check both layers for children (non-deleted).
                let has_children = self
                    .base
                    .keys()
                    .filter(|k| !self.deleted.contains(*k))
                    .chain(self.overlay.keys())
                    .any(|k| k.starts_with(&prefix));
                if has_children {
                    return Err(OasisError::Vfs(format!("directory not empty: {path}")));
                }
            },
            Some(Node::File(_)) => {},
            None => {
                return Err(OasisError::Vfs(format!("no such path: {path}")));
            },
        }
        self.overlay.remove(&path);
        self.deleted.insert(path);
        Ok(())
    }

    fn exists(&self, path: &str) -> bool {
        let path = normalize(path);
        self.effective_entry(&path).is_some()
    }
}

/// Normalize a path: ensure leading `/`, collapse `//`, strip trailing `/`.
fn normalize(path: &str) -> String {
    let path = if path.starts_with('/') {
        path.to_string()
    } else {
        format!("/{path}")
    };
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

/// Extract the direct child name from a full path given a parent prefix.
fn direct_child(full_path: &str, prefix: &str) -> Option<String> {
    let rest = full_path.strip_prefix(prefix)?;
    if rest.is_empty() || rest.contains('/') {
        return None;
    }
    Some(rest.to_string())
}

/// Ensure all ancestor directories exist in the given map.
fn ensure_parents(map: &mut HashMap<String, Node>, path: &str) {
    let mut current = String::new();
    for component in path.split('/').filter(|c| !c.is_empty()) {
        let segment = if current.is_empty() {
            format!("/{component}")
        } else {
            format!("{current}/{component}")
        };
        if segment != *path {
            map.entry(segment.clone()).or_insert(Node::Dir);
        }
        current = segment;
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn root_exists() {
        let vfs = GameAssetVfs::new();
        assert!(vfs.exists("/"));
    }

    #[test]
    fn base_files_readable() {
        let mut vfs = GameAssetVfs::new();
        vfs.add_base_dir("/home");
        vfs.add_base_file("/home/readme.txt", b"Hello from the game!");
        assert_eq!(
            vfs.read("/home/readme.txt").unwrap(),
            b"Hello from the game!"
        );
    }

    #[test]
    fn base_dirs_listable() {
        let mut vfs = GameAssetVfs::new();
        vfs.add_base_dir("/home");
        vfs.add_base_dir("/etc");
        let entries = vfs.readdir("/").unwrap();
        let names: Vec<&str> = entries.iter().map(|e| e.name.as_str()).collect();
        assert!(names.contains(&"home"));
        assert!(names.contains(&"etc"));
    }

    #[test]
    fn overlay_write_creates_file() {
        let mut vfs = GameAssetVfs::new();
        vfs.add_base_dir("/tmp");
        vfs.write("/tmp/player.txt", b"player data").unwrap();
        assert_eq!(vfs.read("/tmp/player.txt").unwrap(), b"player data");
    }

    #[test]
    fn overlay_overrides_base() {
        let mut vfs = GameAssetVfs::new();
        vfs.add_base_dir("/etc");
        vfs.add_base_file("/etc/config", b"original");
        // Player edits the config.
        vfs.write("/etc/config", b"modified by player").unwrap();
        assert_eq!(vfs.read("/etc/config").unwrap(), b"modified by player");
    }

    #[test]
    fn readdir_merges_layers() {
        let mut vfs = GameAssetVfs::new();
        vfs.add_base_dir("/data");
        vfs.add_base_file("/data/base.txt", b"from game");
        vfs.write("/data/player.txt", b"from player").unwrap();
        let entries = vfs.readdir("/data").unwrap();
        let names: Vec<&str> = entries.iter().map(|e| e.name.as_str()).collect();
        assert!(names.contains(&"base.txt"));
        assert!(names.contains(&"player.txt"));
    }

    #[test]
    fn delete_base_file() {
        let mut vfs = GameAssetVfs::new();
        vfs.add_base_dir("/docs");
        vfs.add_base_file("/docs/secret.txt", b"hidden");
        assert!(vfs.exists("/docs/secret.txt"));
        vfs.remove("/docs/secret.txt").unwrap();
        assert!(!vfs.exists("/docs/secret.txt"));
    }

    #[test]
    fn delete_overlay_file() {
        let mut vfs = GameAssetVfs::new();
        vfs.add_base_dir("/tmp");
        vfs.write("/tmp/scratch", b"temp").unwrap();
        vfs.remove("/tmp/scratch").unwrap();
        assert!(!vfs.exists("/tmp/scratch"));
    }

    #[test]
    fn undelete_via_write() {
        let mut vfs = GameAssetVfs::new();
        vfs.add_base_dir("/etc");
        vfs.add_base_file("/etc/conf", b"old");
        vfs.remove("/etc/conf").unwrap();
        assert!(!vfs.exists("/etc/conf"));
        // Writing to a deleted path resurrects it in the overlay.
        vfs.write("/etc/conf", b"new").unwrap();
        assert!(vfs.exists("/etc/conf"));
        assert_eq!(vfs.read("/etc/conf").unwrap(), b"new");
    }

    #[test]
    fn remove_nonempty_dir_fails() {
        let mut vfs = GameAssetVfs::new();
        vfs.add_base_dir("/dir");
        vfs.add_base_file("/dir/file", b"x");
        assert!(vfs.remove("/dir").is_err());
    }

    #[test]
    fn remove_root_fails() {
        let mut vfs = GameAssetVfs::new();
        assert!(vfs.remove("/").is_err());
    }

    #[test]
    fn write_without_parent_fails() {
        let mut vfs = GameAssetVfs::new();
        assert!(vfs.write("/no/such/dir/file", b"x").is_err());
    }

    #[test]
    fn mkdir_creates_parents_in_overlay() {
        let mut vfs = GameAssetVfs::new();
        vfs.mkdir("/a/b/c").unwrap();
        assert!(vfs.exists("/a"));
        assert!(vfs.exists("/a/b"));
        assert!(vfs.exists("/a/b/c"));
    }

    #[test]
    fn stat_base_file() {
        let mut vfs = GameAssetVfs::new();
        vfs.add_base_file("/file", b"abc");
        let meta = vfs.stat("/file").unwrap();
        assert_eq!(meta.kind, EntryKind::File);
        assert_eq!(meta.size, 3);
    }

    #[test]
    fn stat_overlay_dir() {
        let mut vfs = GameAssetVfs::new();
        vfs.mkdir("/mydir").unwrap();
        let meta = vfs.stat("/mydir").unwrap();
        assert_eq!(meta.kind, EntryKind::Directory);
    }

    #[test]
    fn deleted_base_not_in_readdir() {
        let mut vfs = GameAssetVfs::new();
        vfs.add_base_dir("/data");
        vfs.add_base_file("/data/a.txt", b"a");
        vfs.add_base_file("/data/b.txt", b"b");
        vfs.remove("/data/a.txt").unwrap();
        let entries = vfs.readdir("/data").unwrap();
        let names: Vec<&str> = entries.iter().map(|e| e.name.as_str()).collect();
        assert!(!names.contains(&"a.txt"));
        assert!(names.contains(&"b.txt"));
    }

    #[test]
    fn default_constructor() {
        let vfs = GameAssetVfs::default();
        assert!(vfs.exists("/"));
    }

    #[test]
    fn add_base_file_creates_parents() {
        let mut vfs = GameAssetVfs::new();
        vfs.add_base_file("/a/b/c/file.txt", b"deep");
        assert!(vfs.exists("/a"));
        assert!(vfs.exists("/a/b"));
        assert!(vfs.exists("/a/b/c"));
        assert_eq!(vfs.read("/a/b/c/file.txt").unwrap(), b"deep");
    }
}
