//! NMS Video Launcher
//!
//! Creates the NMS process in a suspended state with --disable-eac,
//! injects the cockpit video DLL before Vulkan initializes, then resumes.
//!
//! Defaults:
//!   NMS: D:\SteamLibrary\steamapps\common\No Man's Sky\Binaries\NMS.exe
//!   DLL: nms_cockpit_injector.dll (next to this launcher)
//!
//! Usage: nms-video-launcher.exe [nms-exe-path] [dll-path]

use std::env;
use std::path::{Path, PathBuf};
use std::process::{self, Command, Stdio};

use windows::core::{PCSTR, PCWSTR, PWSTR};
use windows::Win32::Foundation::{CloseHandle, WAIT_OBJECT_0};
use windows::Win32::System::Diagnostics::Debug::WriteProcessMemory;
use windows::Win32::System::LibraryLoader::{GetModuleHandleA, GetProcAddress};
use windows::Win32::System::Memory::{VirtualAllocEx, VirtualFreeEx, MEM_COMMIT, MEM_RELEASE, MEM_RESERVE, PAGE_READWRITE};
use windows::Win32::System::Threading::{
    CreateProcessW, CreateRemoteThread, ResumeThread, WaitForSingleObject,
    CREATE_SUSPENDED, INFINITE, PROCESS_INFORMATION, STARTUPINFOW,
};

const DEFAULT_NMS: &str = r"D:\SteamLibrary\steamapps\common\No Man's Sky\Binaries\NMS.exe";
const DEFAULT_DLL: &str = "nms_cockpit_injector.dll";
const DEFAULT_DAEMON: &str = "nms-video-daemon.exe";

fn main() {
    let args: Vec<String> = env::args().collect();

    // Resolve NMS path
    let nms_path = if args.len() > 1 {
        PathBuf::from(&args[1])
    } else {
        PathBuf::from(DEFAULT_NMS)
    };

    // Resolve DLL path (default: next to this exe)
    let dll_path = if args.len() > 2 {
        PathBuf::from(&args[2])
    } else {
        let exe_dir = env::current_exe()
            .ok()
            .and_then(|p| p.parent().map(|d| d.to_path_buf()))
            .unwrap_or_else(|| PathBuf::from("."));
        exe_dir.join(DEFAULT_DLL)
    };

    // Validate paths
    if !nms_path.exists() {
        eprintln!("Error: NMS executable not found: {}", nms_path.display());
        eprintln!("Pass the correct path as the first argument.");
        process::exit(1);
    }
    if !dll_path.exists() {
        eprintln!("Error: DLL not found: {}", dll_path.display());
        eprintln!("Place {} next to this launcher, or pass the path as the second argument.", DEFAULT_DLL);
        process::exit(1);
    }

    // Get absolute path for the DLL (needed for remote process context)
    let dll_abs = match dll_path.canonicalize() {
        Ok(p) => p,
        Err(e) => {
            eprintln!("Error: cannot resolve DLL path: {}", e);
            process::exit(1);
        }
    };

    println!("NMS:  {}", nms_path.display());
    println!("DLL:  {}", dll_abs.display());
    println!("Args: --disable-eac");
    println!();

    // Start the daemon as a separate process
    start_daemon(&dll_abs);

    unsafe {
        match inject(&nms_path, &dll_abs) {
            Ok(()) => println!("Success: NMS launched with DLL injected"),
            Err(e) => {
                eprintln!("Error: {}", e);
                process::exit(1);
            }
        }
    }
}

/// Start the video daemon as a detached background process.
fn start_daemon(dll_path: &Path) {
    // Look for daemon next to the DLL (or next to this exe)
    let daemon_path = dll_path.parent()
        .map(|d| d.join(DEFAULT_DAEMON))
        .unwrap_or_else(|| PathBuf::from(DEFAULT_DAEMON));

    if !daemon_path.exists() {
        // Also try next to the launcher exe
        let exe_dir = env::current_exe()
            .ok()
            .and_then(|p| p.parent().map(|d| d.to_path_buf()));
        let alt_path = exe_dir.map(|d| d.join(DEFAULT_DAEMON));

        if let Some(alt) = &alt_path {
            if alt.exists() {
                spawn_daemon(alt);
                return;
            }
        }

        println!("Warning: {} not found, skipping daemon launch", DEFAULT_DAEMON);
        println!("  Looked in: {}", daemon_path.display());
        if let Some(alt) = alt_path {
            println!("  Looked in: {}", alt.display());
        }
        println!("  Start the daemon manually if needed.");
        println!();
        return;
    }

    spawn_daemon(&daemon_path);
}

/// Spawn the daemon process detached.
fn spawn_daemon(path: &Path) {
    match Command::new(path)
        .stdin(Stdio::null())
        .stdout(Stdio::null())
        .stderr(Stdio::null())
        .spawn()
    {
        Ok(child) => {
            println!("Daemon started: PID {} ({})", child.id(), path.display());
        }
        Err(e) => {
            println!("Warning: failed to start daemon: {}", e);
            println!("  Start the daemon manually if needed.");
        }
    }
    println!();
}

/// Create NMS suspended with --disable-eac, inject DLL, resume.
unsafe fn inject(nms_path: &Path, dll_path: &Path) -> Result<(), String> {
    // Convert paths to wide strings
    let nms_wide = to_wide(nms_path.to_str().unwrap_or(""));
    let dll_wide = to_wide(dll_path.to_str().unwrap_or(""));

    // Command line: "NMS.exe" --disable-eac (mutable because CreateProcessW may modify it)
    let cmd_line_str = format!(
        "\"{}\" --disable-eac",
        nms_path.to_str().unwrap_or("")
    );
    let mut cmd_wide = to_wide(&cmd_line_str);

    // Byte size of the DLL path (including null terminator, already in to_wide)
    let dll_path_bytes = dll_wide.len() * 2; // u16 -> bytes

    // Create process suspended
    let mut si = STARTUPINFOW::default();
    si.cb = std::mem::size_of::<STARTUPINFOW>() as u32;
    let mut pi = PROCESS_INFORMATION::default();

    println!("Creating NMS process (suspended)...");

    CreateProcessW(
        PCWSTR(nms_wide.as_ptr()),
        PWSTR(cmd_wide.as_mut_ptr()),
        None,
        None,
        false,
        CREATE_SUSPENDED,
        None,
        None,
        &si,
        &mut pi,
    )
    .map_err(|e| format!("CreateProcessW failed: {}", e))?;

    println!("Process created: PID {}", pi.dwProcessId);

    // From here, we must resume or terminate the process on failure
    let result = inject_into_process(&pi, &dll_wide, dll_path_bytes);

    if result.is_err() {
        // If injection failed, terminate the suspended process
        let _ = windows::Win32::System::Threading::TerminateProcess(pi.hProcess, 1);
    }

    // Close process/thread handles (process keeps running)
    let _ = CloseHandle(pi.hProcess);
    let _ = CloseHandle(pi.hThread);

    result
}

/// Perform the actual DLL injection into an already-created suspended process.
unsafe fn inject_into_process(
    pi: &PROCESS_INFORMATION,
    dll_wide: &[u16],
    dll_path_bytes: usize,
) -> Result<(), String> {
    // Allocate memory in target process for the DLL path
    let remote_buf = VirtualAllocEx(
        pi.hProcess,
        None,
        dll_path_bytes,
        MEM_COMMIT | MEM_RESERVE,
        PAGE_READWRITE,
    );

    if remote_buf.is_null() {
        return Err("VirtualAllocEx failed: could not allocate in target process".into());
    }

    println!("Allocated {} bytes in target at {:p}", dll_path_bytes, remote_buf);

    // Write DLL path into target memory
    let write_result = WriteProcessMemory(
        pi.hProcess,
        remote_buf,
        dll_wide.as_ptr() as *const _,
        dll_path_bytes,
        None,
    );

    if write_result.is_err() {
        let _ = VirtualFreeEx(pi.hProcess, remote_buf, 0, MEM_RELEASE);
        return Err("WriteProcessMemory failed".into());
    }

    // Get LoadLibraryW address (same in all processes due to ASLR kernel32 base sharing)
    let kernel32_name = b"kernel32.dll\0";
    let kernel32 = GetModuleHandleA(PCSTR(kernel32_name.as_ptr()))
        .map_err(|e| format!("GetModuleHandleA(kernel32.dll) failed: {}", e))?;

    let load_library_name = b"LoadLibraryW\0";
    let load_library_addr = GetProcAddress(kernel32, PCSTR(load_library_name.as_ptr()));

    let load_library_addr = match load_library_addr {
        Some(addr) => addr,
        None => {
            let _ = VirtualFreeEx(pi.hProcess, remote_buf, 0, MEM_RELEASE);
            return Err("GetProcAddress(LoadLibraryW) failed".into());
        }
    };

    println!("LoadLibraryW at {:p}", load_library_addr as *const ());

    // Create remote thread to call LoadLibraryW(dll_path)
    let thread = CreateRemoteThread(
        pi.hProcess,
        None,
        0,
        Some(std::mem::transmute(load_library_addr)),
        Some(remote_buf),
        0,
        None,
    )
    .map_err(|e| format!("CreateRemoteThread failed: {}", e))?;

    println!("Remote thread created, waiting for DLL load...");

    // Wait for the remote thread (DLL load) to complete
    let wait_result = WaitForSingleObject(thread, INFINITE);
    if wait_result != WAIT_OBJECT_0 {
        let _ = CloseHandle(thread);
        let _ = VirtualFreeEx(pi.hProcess, remote_buf, 0, MEM_RELEASE);
        return Err(format!("WaitForSingleObject returned {:?}", wait_result));
    }

    let _ = CloseHandle(thread);

    // Free the remote buffer (no longer needed after LoadLibrary)
    let _ = VirtualFreeEx(pi.hProcess, remote_buf, 0, MEM_RELEASE);

    println!("DLL injected successfully, resuming main thread...");

    // Resume the main thread
    let resume_result = ResumeThread(pi.hThread);
    if resume_result == u32::MAX {
        return Err("ResumeThread failed".into());
    }

    Ok(())
}

/// Convert a string to a null-terminated wide (UTF-16) string.
fn to_wide(s: &str) -> Vec<u16> {
    s.encode_utf16().chain(std::iter::once(0)).collect()
}
