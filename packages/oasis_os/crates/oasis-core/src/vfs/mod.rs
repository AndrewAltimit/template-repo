//! Virtual File System abstraction.
//!
//! The VFS trait provides a uniform interface over fundamentally different
//! storage backends. On PSP, `ls` lists Memory Stick contents. On Pi, it
//! lists real Linux directories. In UE5, it lists game-authored content.
//! In tests, MemoryVfs provides a fully in-memory tree.

mod game_asset;
mod memory;
mod real;

pub use game_asset::GameAssetVfs;
pub use memory::MemoryVfs;
pub use real::RealVfs;

use crate::error::Result;

/// Type of a VFS entry.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum EntryKind {
    File,
    Directory,
}

/// A single entry returned by `readdir`.
#[derive(Debug, Clone)]
pub struct VfsEntry {
    pub name: String,
    pub kind: EntryKind,
    pub size: u64,
}

/// Metadata about a file or directory.
#[derive(Debug, Clone)]
pub struct VfsMetadata {
    pub kind: EntryKind,
    pub size: u64,
}

/// The virtual file system trait.
///
/// All file operations in the command interpreter go through this trait.
/// Paths are always forward-slash separated, absolute (starting with `/`).
pub trait Vfs {
    /// List entries in a directory.
    fn readdir(&self, path: &str) -> Result<Vec<VfsEntry>>;

    /// Read entire file contents.
    fn read(&self, path: &str) -> Result<Vec<u8>>;

    /// Write data to a file, creating or overwriting it.
    fn write(&mut self, path: &str, data: &[u8]) -> Result<()>;

    /// Get metadata for a path.
    fn stat(&self, path: &str) -> Result<VfsMetadata>;

    /// Create a directory (and parents if needed).
    fn mkdir(&mut self, path: &str) -> Result<()>;

    /// Remove a file or empty directory.
    fn remove(&mut self, path: &str) -> Result<()>;

    /// Check whether a path exists.
    fn exists(&self, path: &str) -> bool;
}
