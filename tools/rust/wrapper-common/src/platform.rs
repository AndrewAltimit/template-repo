//! Minimal OS queries without a libc dependency.
//!
//! These symbols are always present in the C runtime std already links
//! against, and none of them have preconditions, so they are declared `safe`.

#[cfg(unix)]
mod ffi {
    // uid_t / gid_t are u32 on every Unix target we build for (Linux, macOS).
    unsafe extern "C" {
        pub safe fn getuid() -> u32;
        pub safe fn getgid() -> u32;
        pub safe fn getegid() -> u32;
    }
}

/// Real user id of the caller (0 on non-Unix platforms).
pub fn uid() -> u32 {
    #[cfg(unix)]
    {
        ffi::getuid()
    }
    #[cfg(not(unix))]
    {
        0
    }
}

/// True when the process runs with an effective group different from its
/// real group, i.e. it is the setgid `wrapper-guard` wrapper installed by
/// `setup-wrapper-guard.sh` / the hardened container.
///
/// Anything the real binary spawns in this mode (hooks, aliases,
/// extensions) inherits that group and can therefore reach
/// `/usr/lib/wrapper-guard/*.real` directly, so wrappers apply stricter
/// rules here.
pub fn is_setgid_elevated() -> bool {
    #[cfg(unix)]
    {
        ffi::getegid() != ffi::getgid()
    }
    #[cfg(not(unix))]
    {
        false
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_process_is_not_setgid() {
        // The test harness is never installed setgid.
        assert!(!is_setgid_elevated());
    }

    #[cfg(unix)]
    #[test]
    fn uid_matches_proc_status() {
        if let Ok(status) = std::fs::read_to_string("/proc/self/status") {
            let expected = status
                .lines()
                .find_map(|l| l.strip_prefix("Uid:"))
                .and_then(|rest| rest.split_whitespace().next())
                .and_then(|s| s.parse::<u32>().ok());
            if let Some(expected) = expected {
                assert_eq!(uid(), expected);
            }
        }
    }
}
