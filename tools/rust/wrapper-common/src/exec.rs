//! Run the real binary with faithful stdio, signal, and exit-code passthrough.
//!
//! - [`exec`] replaces the wrapper process on Unix (`execve`): the real
//!   binary inherits the PID, stdio, controlling terminal, and signal
//!   dispositions, so behaviour is identical to invoking it directly. On
//!   Windows there is no `exec`, so it runs the child and exits with its code.
//! - [`run`] spawns the real binary as a child and waits. Use it when work
//!   must happen afterwards (temp-file cleanup, post-command notices). While
//!   waiting, the wrapper ignores terminal interrupts (SIGINT/SIGQUIT on
//!   Unix, Ctrl-C/Ctrl-Break on Windows) so the child alone decides how to
//!   react, and the wrapper survives to clean up and forward the status.

use crate::binary_finder::RealBinary;
use crate::error::{CommonError, Result};
use std::ffi::OsStr;
use std::process::ExitStatus;

/// Replace the current process with the real binary (Unix), or run it and
/// exit with its status (Windows).
///
/// Arguments are passed as `OsStr` so non-UTF-8 arguments reach the real
/// binary byte-for-byte. Only returns on failure to start the binary.
pub fn exec<S: AsRef<OsStr>>(real: &RealBinary, args: &[S]) -> CommonError {
    #[cfg(unix)]
    {
        use std::os::unix::process::CommandExt;
        let source = real.command().args(args).exec();
        CommonError::ExecFailed {
            binary_name: real.name().to_string(),
            source,
        }
    }
    #[cfg(not(unix))]
    {
        match run(real, args) {
            Ok(code) => std::process::exit(code),
            Err(e) => e,
        }
    }
}

/// Spawn the real binary with inherited stdio, wait, and return the exit
/// code to forward (see [`exit_code`]).
pub fn run<S: AsRef<OsStr>>(real: &RealBinary, args: &[S]) -> Result<i32> {
    let mut child =
        real.command()
            .args(args)
            .spawn()
            .map_err(|source| CommonError::ExecFailed {
                binary_name: real.name().to_string(),
                source,
            })?;

    // Ignore interrupts only after the child exists, so it starts with the
    // default dispositions (ignored signals would be inherited across exec).
    let _guard = interrupts::IgnoreGuard::new();
    let status = child.wait().map_err(|source| CommonError::ExecFailed {
        binary_name: real.name().to_string(),
        source,
    })?;
    Ok(exit_code(status))
}

/// Exit code a wrapper should use to mirror `status`.
///
/// Normal exits pass through unchanged. On Unix, death by signal N maps to
/// `128 + N` (the shell convention, e.g. 130 for SIGINT) instead of a
/// generic 1, so callers can still tell an interrupt from a failure.
pub fn exit_code(status: ExitStatus) -> i32 {
    if let Some(code) = status.code() {
        return code;
    }
    #[cfg(unix)]
    {
        use std::os::unix::process::ExitStatusExt;
        if let Some(signal) = status.signal() {
            return 128 + signal;
        }
    }
    1
}

#[cfg(unix)]
mod interrupts {
    const SIGINT: i32 = 2;
    const SIGQUIT: i32 = 3;
    const SIG_IGN: usize = 1;
    const SIG_ERR: usize = usize::MAX;

    // `sighandler_t` is a pointer-sized function pointer; passing the
    // SIG_IGN / previous-handler values as usize is ABI-compatible on every
    // Unix target we support. SIGINT/SIGQUIT are 2/3 on Linux and macOS.
    unsafe extern "C" {
        fn signal(signum: i32, handler: usize) -> usize;
    }

    /// Ignores SIGINT/SIGQUIT for its lifetime, then restores the previous
    /// dispositions.
    pub struct IgnoreGuard {
        previous: [(i32, usize); 2],
    }

    impl IgnoreGuard {
        pub fn new() -> Self {
            let mut previous = [(SIGINT, SIG_ERR), (SIGQUIT, SIG_ERR)];
            for (sig, old) in &mut previous {
                // SAFETY: installing SIG_IGN has no memory-safety
                // preconditions; the wrappers are single-threaded here.
                *old = unsafe { signal(*sig, SIG_IGN) };
            }
            Self { previous }
        }
    }

    impl Drop for IgnoreGuard {
        fn drop(&mut self) {
            for &(sig, old) in &self.previous {
                if old != SIG_ERR {
                    // SAFETY: restores the exact value `signal` returned.
                    unsafe {
                        signal(sig, old);
                    }
                }
            }
        }
    }
}

#[cfg(windows)]
mod interrupts {
    type HandlerRoutine = Option<unsafe extern "system" fn(u32) -> i32>;

    #[link(name = "kernel32")]
    unsafe extern "system" {
        fn SetConsoleCtrlHandler(handler: HandlerRoutine, add: i32) -> i32;
    }

    /// Makes this process ignore Ctrl-C for its lifetime. The child was
    /// spawned before this is installed, so it does not inherit the flag.
    pub struct IgnoreGuard {
        active: bool,
    }

    impl IgnoreGuard {
        pub fn new() -> Self {
            // SAFETY: a null handler with add=TRUE only toggles the
            // process-wide "ignore Ctrl-C" flag.
            let active = unsafe { SetConsoleCtrlHandler(None, 1) } != 0;
            Self { active }
        }
    }

    impl Drop for IgnoreGuard {
        fn drop(&mut self) {
            if self.active {
                // SAFETY: see `new`.
                unsafe {
                    SetConsoleCtrlHandler(None, 0);
                }
            }
        }
    }
}

#[cfg(not(any(unix, windows)))]
mod interrupts {
    pub struct IgnoreGuard;
    impl IgnoreGuard {
        pub fn new() -> Self {
            Self
        }
    }
}

#[cfg(all(test, unix))]
mod tests {
    use super::*;
    use std::process::Command;

    #[test]
    fn exit_code_passthrough() {
        let status = Command::new("sh").args(["-c", "exit 42"]).status().unwrap();
        assert_eq!(exit_code(status), 42);
        let status = Command::new("sh").args(["-c", "exit 0"]).status().unwrap();
        assert_eq!(exit_code(status), 0);
    }

    #[test]
    fn signal_death_maps_to_128_plus_signal() {
        let status = Command::new("sh")
            .args(["-c", "kill -TERM $$"])
            .status()
            .unwrap();
        assert_eq!(exit_code(status), 128 + 15);
    }

    #[test]
    fn ignore_guard_restores() {
        // Constructing and dropping must not leave SIGINT ignored for
        // children spawned afterwards.
        drop(interrupts::IgnoreGuard::new());
        let status = Command::new("sh")
            .args(["-c", "kill -INT $$; exit 0"])
            .status()
            .unwrap();
        assert_eq!(exit_code(status), 128 + 2);
    }
}
