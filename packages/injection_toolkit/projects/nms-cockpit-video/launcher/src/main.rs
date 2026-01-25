//! NMS Video Launcher
//!
//! Launches NMS with --disable-eac, waits for the game process to start,
//! then injects the cockpit video DLL. Handles the case where NMS re-spawns
//! itself during startup by polling for the real game process.
//!
//! Defaults:
//!   NMS: D:\SteamLibrary\steamapps\common\No Man's Sky\Binaries\NMS.exe
//!   DLL: nms_cockpit_injector.dll (next to this launcher)
//!
//! Usage: nms-video-launcher.exe [nms-exe-path] [dll-path]

use std::env;
use std::ffi::c_void;
use std::path::{Path, PathBuf};
use std::process::{self, Command, Stdio};
use std::thread;
use std::time::{Duration, Instant};

use windows::core::PCSTR;
use windows::Win32::Foundation::{CloseHandle, WAIT_OBJECT_0};
use windows::Win32::System::Diagnostics::Debug::WriteProcessMemory;
use windows::Win32::System::LibraryLoader::{GetModuleHandleA, GetProcAddress};
use windows::Win32::System::Memory::{
    VirtualAllocEx, VirtualFreeEx, MEM_COMMIT, MEM_RELEASE, MEM_RESERVE, PAGE_READWRITE,
};
use windows::Win32::System::Threading::{
    CreateRemoteThread, OpenProcess, TerminateProcess, WaitForSingleObject, INFINITE,
    PROCESS_CREATE_THREAD, PROCESS_QUERY_INFORMATION, PROCESS_SYNCHRONIZE, PROCESS_TERMINATE,
    PROCESS_VM_OPERATION, PROCESS_VM_WRITE,
};

const DEFAULT_NMS: &str = r"D:\SteamLibrary\steamapps\common\No Man's Sky\Binaries\NMS.exe";
const DEFAULT_DLL: &str = "nms_cockpit_injector.dll";
const DEFAULT_DAEMON: &str = "nms-video-daemon.exe";

/// How long to wait for NMS to start before giving up.
const WAIT_TIMEOUT: Duration = Duration::from_secs(30);

/// How often to poll for the NMS process.
const POLL_INTERVAL: Duration = Duration::from_millis(500);

/// Delay after finding the process before injecting.
/// Must be short - the DLL waits internally for vulkan-1.dll, and hooks must be
/// installed BEFORE NMS calls vkCreateDevice (which sets up ICD hooks).
const INJECT_DELAY: Duration = Duration::from_millis(500);

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
        eprintln!(
            "Place {} next to this launcher, or pass the path as the second argument.",
            DEFAULT_DLL
        );
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

    // Strip \\?\ prefix from canonicalized path (LoadLibraryW handles regular paths fine)
    let dll_str = dll_abs
        .to_str()
        .unwrap_or("")
        .strip_prefix(r"\\?\")
        .unwrap_or(dll_abs.to_str().unwrap_or(""));
    let dll_clean = PathBuf::from(dll_str);

    println!("NMS:  {}", nms_path.display());
    println!("DLL:  {}", dll_clean.display());
    println!("Args: --disable-eac");
    println!();

    // Start the daemon as a separate process
    let daemon_pid = start_daemon(&dll_clean);

    // Launch NMS
    println!("Launching NMS with --disable-eac...");
    let nms_dir = nms_path.parent().map(|p| p.to_path_buf());

    let mut cmd = Command::new(&nms_path);
    cmd.arg("--disable-eac")
        .stdin(Stdio::null())
        .stdout(Stdio::null())
        .stderr(Stdio::null());

    if let Some(dir) = &nms_dir {
        cmd.current_dir(dir);
    }

    let initial_pid = match cmd.spawn() {
        Ok(child) => {
            let pid = child.id();
            println!("NMS launched: initial PID {}", pid);
            pid
        }
        Err(e) => {
            eprintln!("Error: failed to launch NMS: {}", e);
            process::exit(1);
        }
    };

    // Wait for the real NMS process to appear (skip the initial stub PID)
    println!(
        "Waiting for NMS game process (skipping initial PID {})...",
        initial_pid
    );
    let pid = match wait_for_nms(initial_pid) {
        Some(pid) => pid,
        None => {
            eprintln!("Error: NMS process not found within {:?}", WAIT_TIMEOUT);
            process::exit(1);
        }
    };

    println!("Found NMS game process: PID {}", pid);
    println!(
        "Waiting {}ms for process to initialize...",
        INJECT_DELAY.as_millis()
    );
    thread::sleep(INJECT_DELAY);

    // Inject into the running process
    unsafe {
        match inject_into_pid(pid, &dll_clean) {
            Ok(()) => println!("Success: DLL injected into NMS (PID {})", pid),
            Err(e) => {
                eprintln!("Error: {}", e);
                process::exit(1);
            }
        }
    }

    // Wait for NMS to exit, then shut down the daemon
    println!();
    println!("Waiting for NMS to exit...");
    wait_for_process_exit(pid);
    println!("NMS exited.");

    if let Some(dpid) = daemon_pid {
        println!("Shutting down daemon (PID {})...", dpid);
        kill_process(dpid);
    }
    println!("Done.");
}

/// Start the video daemon as a detached background process.
/// Returns the daemon's PID if successfully started.
fn start_daemon(dll_path: &Path) -> Option<u32> {
    let daemon_path = dll_path
        .parent()
        .map(|d| d.join(DEFAULT_DAEMON))
        .unwrap_or_else(|| PathBuf::from(DEFAULT_DAEMON));

    if !daemon_path.exists() {
        let exe_dir = env::current_exe()
            .ok()
            .and_then(|p| p.parent().map(|d| d.to_path_buf()));
        let alt_path = exe_dir.map(|d| d.join(DEFAULT_DAEMON));

        if let Some(alt) = &alt_path {
            if alt.exists() {
                return spawn_daemon(alt);
            }
        }

        println!("Note: {} not found, skipping daemon launch", DEFAULT_DAEMON);
        println!();
        return None;
    }

    spawn_daemon(&daemon_path)
}

/// Find a video file to auto-load (checks next to the launcher/DLL).
fn find_video_file() -> Option<PathBuf> {
    let exe_dir = env::current_exe()
        .ok()
        .and_then(|p| p.parent().map(|d| d.to_path_buf()))?;

    // Check for nms_video.txt config first
    let config_path = exe_dir.join("nms_video.txt");
    if config_path.exists() {
        if let Ok(content) = std::fs::read_to_string(&config_path) {
            let path = content.trim().to_string();
            if !path.is_empty() {
                let p = PathBuf::from(&path);
                if p.exists() {
                    return Some(p);
                }
            }
        }
    }

    // Check for nms_video.mp4
    let video_path = exe_dir.join("nms_video.mp4");
    if video_path.exists() {
        return Some(video_path);
    }

    None
}

/// Spawn the daemon process detached, optionally with --load.
/// Returns the daemon's PID if successfully started.
fn spawn_daemon(path: &Path) -> Option<u32> {
    // Write daemon logs to a file so we can diagnose issues
    let log_path = env::temp_dir().join("nms_video_daemon.log");
    println!("Daemon log: {}", log_path.display());

    let log_file = std::fs::File::create(&log_path).ok();
    let stderr_cfg = match &log_file {
        Some(f) => Stdio::from(
            f.try_clone()
                .unwrap_or_else(|_| std::fs::File::create(&log_path).expect("create log")),
        ),
        None => Stdio::null(),
    };

    let mut cmd = Command::new(path);
    cmd.stdin(Stdio::null())
        .stdout(Stdio::null())
        .stderr(stderr_cfg);

    // Enable debug logging for diagnostics
    cmd.arg("--log-level").arg("debug");

    if let Some(video) = find_video_file() {
        println!("Video: {}", video.display());
        cmd.arg("--load").arg(&video);
    }

    let pid = match cmd.spawn() {
        Ok(child) => {
            let pid = child.id();
            println!("Daemon started: PID {}", pid);
            Some(pid)
        }
        Err(e) => {
            println!("Warning: failed to start daemon: {}", e);
            None
        }
    };
    println!();
    pid
}

/// Poll for an NMS.exe process. Returns the PID when found.
///
/// NMS may re-spawn itself during startup. Strategy:
/// 1. First look for a re-spawned process (different PID) for up to 10 seconds
/// 2. If not found, accept the initial PID (NMS didn't re-spawn)
fn wait_for_nms(initial_pid: u32) -> Option<u32> {
    let start = Instant::now();
    let respawn_timeout = Duration::from_secs(10);

    // Phase 1: Look for a re-spawned process (skip initial PID)
    while start.elapsed() < respawn_timeout {
        if let Some(pid) = find_nms_process(initial_pid) {
            return Some(pid);
        }
        thread::sleep(POLL_INTERVAL);
    }

    // Phase 2: NMS didn't re-spawn, accept initial PID if still running
    println!("No re-spawn detected, checking initial PID...");
    find_any_nms_process()
}

/// Find any NMS.exe process (no PID skipping).
fn find_any_nms_process() -> Option<u32> {
    find_nms_process(0)
}

/// Find an NMS.exe process by scanning the process list, skipping `skip_pid`.
fn find_nms_process(skip_pid: u32) -> Option<u32> {
    use windows::Win32::System::Diagnostics::ToolHelp::{
        CreateToolhelp32Snapshot, Process32FirstW, Process32NextW, PROCESSENTRY32W,
        TH32CS_SNAPPROCESS,
    };

    unsafe {
        let snapshot = CreateToolhelp32Snapshot(TH32CS_SNAPPROCESS, 0).ok()?;

        let mut entry = PROCESSENTRY32W {
            dwSize: std::mem::size_of::<PROCESSENTRY32W>() as u32,
            ..Default::default()
        };

        if Process32FirstW(snapshot, &mut entry).is_err() {
            let _ = CloseHandle(snapshot);
            return None;
        }

        let mut found_pid = None;

        loop {
            let name: String = entry
                .szExeFile
                .iter()
                .take_while(|&&c| c != 0)
                .map(|&c| char::from_u32(c as u32).unwrap_or('?'))
                .collect();

            if name.eq_ignore_ascii_case("NMS.exe") && entry.th32ProcessID != skip_pid {
                found_pid = Some(entry.th32ProcessID);
            }

            if Process32NextW(snapshot, &mut entry).is_err() {
                break;
            }
        }

        let _ = CloseHandle(snapshot);
        found_pid
    }
}

/// Inject the DLL into a running process by PID.
unsafe fn inject_into_pid(pid: u32, dll_path: &Path) -> Result<(), String> {
    let dll_wide = to_wide(dll_path.to_str().unwrap_or(""));
    let dll_path_bytes = dll_wide.len() * 2;

    // Open the target process
    let access =
        PROCESS_CREATE_THREAD | PROCESS_VM_OPERATION | PROCESS_VM_WRITE | PROCESS_QUERY_INFORMATION;

    let process = OpenProcess(access, false, pid)
        .map_err(|e| format!("OpenProcess({}) failed: {} (try running as admin)", pid, e))?;

    let result = do_inject(process, &dll_wide, dll_path_bytes);

    let _ = CloseHandle(process);
    result
}

/// Core injection logic: allocate, write, CreateRemoteThread(LoadLibraryW).
unsafe fn do_inject(
    process: windows::Win32::Foundation::HANDLE,
    dll_wide: &[u16],
    dll_path_bytes: usize,
) -> Result<(), String> {
    // Allocate memory in target process for the DLL path
    let remote_buf = VirtualAllocEx(
        process,
        None,
        dll_path_bytes,
        MEM_COMMIT | MEM_RESERVE,
        PAGE_READWRITE,
    );

    if remote_buf.is_null() {
        return Err("VirtualAllocEx failed: could not allocate in target process".into());
    }

    println!("Allocated {} bytes at {:p}", dll_path_bytes, remote_buf);

    // Write DLL path into target memory
    let write_result = WriteProcessMemory(
        process,
        remote_buf,
        dll_wide.as_ptr() as *const _,
        dll_path_bytes,
        None,
    );

    if write_result.is_err() {
        let _ = VirtualFreeEx(process, remote_buf, 0, MEM_RELEASE);
        return Err("WriteProcessMemory failed".into());
    }

    // Get LoadLibraryW address
    let kernel32_name = b"kernel32.dll\0";
    let kernel32 = GetModuleHandleA(PCSTR(kernel32_name.as_ptr()))
        .map_err(|e| format!("GetModuleHandleA(kernel32.dll) failed: {}", e))?;

    let load_library_name = b"LoadLibraryW\0";
    let load_library_addr = GetProcAddress(kernel32, PCSTR(load_library_name.as_ptr()));

    let load_library_addr = match load_library_addr {
        Some(addr) => addr,
        None => {
            let _ = VirtualFreeEx(process, remote_buf, 0, MEM_RELEASE);
            return Err("GetProcAddress(LoadLibraryW) failed".into());
        }
    };

    println!("LoadLibraryW at {:p}", load_library_addr as *const ());

    // Create remote thread to call LoadLibraryW(dll_path)
    let thread = CreateRemoteThread(
        process,
        None,
        0,
        Some(std::mem::transmute::<
            unsafe extern "system" fn() -> isize,
            unsafe extern "system" fn(*mut c_void) -> u32,
        >(load_library_addr)),
        Some(remote_buf),
        0,
        None,
    )
    .map_err(|e| format!("CreateRemoteThread failed: {}", e))?;

    println!("Remote thread created, waiting for DLL load...");

    // Wait for DLL load to complete
    let wait_result = WaitForSingleObject(thread, INFINITE);
    if wait_result != WAIT_OBJECT_0 {
        let _ = CloseHandle(thread);
        let _ = VirtualFreeEx(process, remote_buf, 0, MEM_RELEASE);
        return Err(format!("WaitForSingleObject returned {:?}", wait_result));
    }

    let _ = CloseHandle(thread);
    let _ = VirtualFreeEx(process, remote_buf, 0, MEM_RELEASE);

    println!("DLL loaded successfully");
    Ok(())
}

/// Wait for a process to exit.
fn wait_for_process_exit(pid: u32) {
    unsafe {
        let handle = OpenProcess(PROCESS_SYNCHRONIZE, false, pid);
        match handle {
            Ok(h) => {
                // Wait indefinitely for the process to exit
                WaitForSingleObject(h, INFINITE);
                let _ = CloseHandle(h);
            }
            Err(_) => {
                // Process already exited or can't be opened
            }
        }
    }
}

/// Terminate a process by PID.
fn kill_process(pid: u32) {
    unsafe {
        let handle = OpenProcess(PROCESS_TERMINATE, false, pid);
        match handle {
            Ok(h) => {
                let _ = TerminateProcess(h, 0);
                let _ = CloseHandle(h);
            }
            Err(_) => {
                // Process already exited
            }
        }
    }
}

/// Convert a string to a null-terminated wide (UTF-16) string.
fn to_wide(s: &str) -> Vec<u16> {
    s.encode_utf16().chain(std::iter::once(0)).collect()
}
