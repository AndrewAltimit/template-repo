//! Locate the real binary a wrapper delegates to.
//!
//! Resolution order:
//!
//! 1. **Hardened location** `/usr/lib/wrapper-guard/<name>.real`. Only the
//!    setgid wrapper (group `wrapper-guard`) can see it; for everyone else
//!    the directory is unreadable and this step silently falls through.
//! 2. **PATH scan**, with these safety rules:
//!    - only *absolute* PATH entries are considered. Empty and relative
//!      entries (`""`, `.`, `bin`) resolve against the current directory,
//!      which lets a malicious repository plant its own `git`/`gh`.
//!    - candidates must be regular executable files (directories named
//!      `git` are skipped).
//!    - candidates are canonicalized (symlinks resolved) and skipped if they
//!      are this wrapper or any wrapper already on the exec chain.
//!
//! # Wrapper chains and recursion
//!
//! Several wrapper copies can be on PATH (e.g. `~/.local/bin/git` plus the
//! setgid `/usr/bin/git`). Each wrapper passes the canonical paths of every
//! wrapper on the chain so far to its child in `__WRAPPER_GUARD_RECURSION_<NAME>`
//! (a PATH-style list). A wrapper never selects a binary on that list, so
//! the chain always makes progress and cannot loop, and both policies run.
//!
//! Because the variable is a *visited list* rather than an "abort" flag, a
//! wrapper invoked from inside the real binary (e.g. a git hook that runs
//! `git status`) still resolves the real binary normally.

use crate::error::{CommonError, Result};
use std::ffi::{OsStr, OsString};
use std::path::{Path, PathBuf};
use std::process::Command;

/// Base directory for hardened (relocated) binaries.
pub const HARDENED_BASE_DIR: &str = "/usr/lib/wrapper-guard";

/// Prefix of the per-binary chain variable (suffix is the upper-cased name,
/// so git-guard and gh-validator never interfere: `gh` runs `git` itself).
const RECURSION_GUARD_PREFIX: &str = "__WRAPPER_GUARD_RECURSION_";

#[cfg(windows)]
const EXE_SUFFIX: &str = ".exe";
#[cfg(not(windows))]
const EXE_SUFFIX: &str = "";

/// A resolved real binary plus the wrapper chain to hand to it.
#[derive(Debug, Clone)]
pub struct RealBinary {
    name: String,
    path: PathBuf,
    guard_var: String,
    chain: OsString,
}

impl RealBinary {
    /// Human-readable name ("git", "gh").
    pub fn name(&self) -> &str {
        &self.name
    }

    /// Canonical path of the real binary.
    pub fn path(&self) -> &Path {
        &self.path
    }

    /// A [`Command`] for the real binary with the wrapper chain variable set.
    ///
    /// The variable is set on the child only; the wrapper's own environment
    /// is never mutated (so no `unsafe` `std::env::set_var` is needed).
    pub fn command(&self) -> Command {
        let mut cmd = Command::new(&self.path);
        cmd.env(&self.guard_var, &self.chain);
        cmd
    }
}

/// Name of the chain variable for `binary_name`.
pub fn recursion_guard_var(binary_name: &str) -> String {
    format!(
        "{RECURSION_GUARD_PREFIX}{}",
        binary_name.to_ascii_uppercase()
    )
}

/// Path of the hardened copy of `binary_name`.
pub fn hardened_path(binary_name: &str) -> PathBuf {
    PathBuf::from(HARDENED_BASE_DIR).join(format!("{binary_name}{EXE_SUFFIX}.real"))
}

/// Find the real binary: hardened location first, then PATH.
pub fn find_real_binary(binary_name: &str) -> Result<RealBinary> {
    let guard_var = recursion_guard_var(binary_name);
    let self_exe = std::env::current_exe()
        .ok()
        .and_then(|p| p.canonicalize().ok());
    let visited = build_chain(std::env::var_os(&guard_var).as_deref(), self_exe.as_deref());
    let chain = join_chain(&visited);

    let make = |path: PathBuf| RealBinary {
        name: binary_name.to_string(),
        path,
        guard_var: guard_var.clone(),
        chain: chain.clone(),
    };

    let hardened = hardened_path(binary_name);
    if is_executable_file(&hardened)
        && let Ok(canonical) = hardened.canonicalize()
    {
        return Ok(make(canonical));
    }

    let path_var = std::env::var_os("PATH").unwrap_or_default();
    find_in_path(binary_name, &path_var, &visited).map(make)
}

/// Previously visited wrappers (from the inherited chain variable) plus us.
fn build_chain(inherited: Option<&OsStr>, self_exe: Option<&Path>) -> Vec<PathBuf> {
    let mut visited: Vec<PathBuf> = inherited
        .map(|v| {
            std::env::split_paths(v)
                .filter(|p| p.is_absolute())
                .collect()
        })
        .unwrap_or_default();
    if let Some(me) = self_exe
        && !visited.iter().any(|p| p == me)
    {
        visited.push(me.to_path_buf());
    }
    visited
}

/// Join the chain into a PATH-style list, dropping entries that cannot be
/// represented (a path containing the separator). Dropping is safe: the only
/// effect is that a later wrapper might re-visit that copy once, after which
/// its own path is appended again.
fn join_chain(visited: &[PathBuf]) -> OsString {
    let representable = visited
        .iter()
        .filter(|p| std::env::join_paths(std::iter::once(p)).is_ok());
    std::env::join_paths(representable).unwrap_or_default()
}

/// Scan `path_var` for `binary_name`, skipping anything in `visited`.
fn find_in_path(binary_name: &str, path_var: &OsStr, visited: &[PathBuf]) -> Result<PathBuf> {
    let file_name = format!("{binary_name}{EXE_SUFFIX}");
    let mut searched = Vec::new();
    let mut skipped = Vec::new();

    for dir in std::env::split_paths(path_var) {
        if !dir.is_absolute() {
            if !dir.as_os_str().is_empty() {
                skipped.push(format!("{} (relative PATH entry)", dir.display()));
            }
            continue;
        }
        searched.push(dir.display().to_string());

        let candidate = dir.join(&file_name);
        if !is_executable_file(&candidate) {
            continue;
        }
        let Ok(canonical) = candidate.canonicalize() else {
            continue;
        };
        if visited.contains(&canonical) {
            skipped.push(format!("{} (wrapper)", canonical.display()));
            continue;
        }
        return Ok(canonical);
    }

    let mut detail = searched.join(", ");
    if !skipped.is_empty() {
        detail.push_str(&format!("; skipped: {}", skipped.join(", ")));
    }
    Err(CommonError::BinaryNotFound {
        binary_name: binary_name.to_string(),
        searched_paths: detail,
    })
}

/// Regular file with an execute bit (any regular file on Windows).
fn is_executable_file(path: &Path) -> bool {
    let Ok(meta) = path.metadata() else {
        return false;
    };
    if !meta.is_file() {
        return false;
    }
    #[cfg(unix)]
    {
        use std::os::unix::fs::PermissionsExt;
        meta.permissions().mode() & 0o111 != 0
    }
    #[cfg(not(unix))]
    {
        true
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn guard_var_is_per_binary() {
        assert_eq!(recursion_guard_var("git"), "__WRAPPER_GUARD_RECURSION_GIT");
        assert_eq!(recursion_guard_var("gh"), "__WRAPPER_GUARD_RECURSION_GH");
    }

    #[test]
    fn hardened_path_layout() {
        #[cfg(not(windows))]
        assert_eq!(
            hardened_path("git"),
            PathBuf::from("/usr/lib/wrapper-guard/git.real")
        );
    }

    #[test]
    fn nonexistent_binary_is_error() {
        let err = find_real_binary("nonexistent_binary_that_does_not_exist_12345").unwrap_err();
        match err {
            CommonError::BinaryNotFound { binary_name, .. } => {
                assert_eq!(binary_name, "nonexistent_binary_that_does_not_exist_12345");
            },
            other => panic!("expected BinaryNotFound, got {other:?}"),
        }
    }

    /// A platform-absolute path (`/x/...` is not absolute on Windows).
    fn abs(rel: &str) -> PathBuf {
        std::env::temp_dir().join(rel)
    }

    #[test]
    fn chain_appends_self_once() {
        let me = abs("wrapper/git");
        let other = abs("a/git");
        let inherited = std::env::join_paths([other.as_path(), me.as_path()]).unwrap();
        let chain = build_chain(Some(&inherited), Some(&me));
        assert_eq!(chain, vec![other, me.clone()]);

        let chain = build_chain(None, Some(&me));
        assert_eq!(chain, vec![me]);
    }

    #[test]
    fn chain_ignores_relative_entries() {
        let absolute = abs("abs/git");
        let inherited =
            std::env::join_paths([Path::new("relative/git"), absolute.as_path()]).unwrap();
        let chain = build_chain(Some(&inherited), None);
        assert_eq!(chain, vec![absolute]);
    }

    #[cfg(unix)]
    mod unix {
        use super::super::*;
        use std::os::unix::fs::PermissionsExt;

        fn make_exe(dir: &Path, name: &str) -> PathBuf {
            let path = dir.join(name);
            std::fs::write(&path, "#!/bin/sh\n").unwrap();
            std::fs::set_permissions(&path, std::fs::Permissions::from_mode(0o755)).unwrap();
            path.canonicalize().unwrap()
        }

        #[test]
        fn relative_and_empty_path_entries_are_ignored() {
            let dir = tempfile::tempdir().unwrap();
            make_exe(dir.path(), "fakebin");
            // Only reachable via a relative entry: must not be found.
            let rel = pathdiff_to_cwd(dir.path());
            let path_var = std::env::join_paths([rel.as_os_str(), OsStr::new("")]).unwrap();
            assert!(find_in_path("fakebin", &path_var, &[]).is_err());
        }

        /// Relative spelling of `dir` from the current directory.
        fn pathdiff_to_cwd(dir: &Path) -> PathBuf {
            let cwd = std::env::current_dir().unwrap();
            let depth = cwd.components().count() - 1;
            let mut rel = PathBuf::new();
            for _ in 0..depth {
                rel.push("..");
            }
            rel.join(dir.strip_prefix("/").unwrap())
        }

        #[test]
        fn visited_wrappers_are_skipped() {
            let a = tempfile::tempdir().unwrap();
            let b = tempfile::tempdir().unwrap();
            let wrapper = make_exe(a.path(), "fakebin");
            let real = make_exe(b.path(), "fakebin");
            let path_var = std::env::join_paths([a.path(), b.path()]).unwrap();

            assert_eq!(find_in_path("fakebin", &path_var, &[]).unwrap(), wrapper);
            assert_eq!(
                find_in_path("fakebin", &path_var, std::slice::from_ref(&wrapper)).unwrap(),
                real
            );
            let err = find_in_path("fakebin", &path_var, &[wrapper, real]).unwrap_err();
            assert!(err.to_string().contains("skipped"));
        }

        #[test]
        fn symlinked_wrapper_is_recognized() {
            let a = tempfile::tempdir().unwrap();
            let b = tempfile::tempdir().unwrap();
            let wrapper = make_exe(a.path(), "wrapper-bin");
            std::os::unix::fs::symlink(&wrapper, b.path().join("fakebin")).unwrap();
            let path_var = std::env::join_paths([b.path()]).unwrap();
            assert!(find_in_path("fakebin", &path_var, &[wrapper]).is_err());
        }

        #[test]
        fn directories_and_non_executables_are_skipped() {
            let a = tempfile::tempdir().unwrap();
            let b = tempfile::tempdir().unwrap();
            let c = tempfile::tempdir().unwrap();
            std::fs::create_dir(a.path().join("fakebin")).unwrap();
            let plain = b.path().join("fakebin");
            std::fs::write(&plain, "data").unwrap();
            std::fs::set_permissions(&plain, std::fs::Permissions::from_mode(0o644)).unwrap();
            let real = make_exe(c.path(), "fakebin");
            let path_var = std::env::join_paths([a.path(), b.path(), c.path()]).unwrap();
            assert_eq!(find_in_path("fakebin", &path_var, &[]).unwrap(), real);
        }

        #[test]
        fn command_carries_chain_variable() {
            let real = RealBinary {
                name: "git".into(),
                path: PathBuf::from("/usr/bin/git"),
                guard_var: recursion_guard_var("git"),
                chain: OsString::from("/home/u/.local/bin/git"),
            };
            let cmd = real.command();
            let envs: Vec<_> = cmd.get_envs().collect();
            assert!(envs.iter().any(|(k, v)| {
                *k == "__WRAPPER_GUARD_RECURSION_GIT"
                    && *v == Some(OsStr::new("/home/u/.local/bin/git"))
            }));
        }
    }
}
