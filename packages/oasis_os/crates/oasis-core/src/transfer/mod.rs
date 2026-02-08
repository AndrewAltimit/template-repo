//! File transfer services -- FTP-like server and push/pull commands.
//!
//! Provides a minimal file transfer protocol over TCP using the
//! `NetworkBackend` trait. The protocol is line-based:
//!
//! - `LIST <path>` -- list directory contents
//! - `GET <path>`  -- retrieve file (response: size + data)
//! - `PUT <path> <size>` -- upload file
//! - `QUIT` -- close connection
//!
//! Also provides terminal commands: `ftp start/stop`, `push`, `pull`.

use crate::error::{OasisError, Result};
use crate::terminal::{Command, CommandOutput, Environment};
use crate::vfs::Vfs;

/// Default FTP server port.
pub const DEFAULT_FTP_PORT: u16 = 2121;

/// VFS path for FTP configuration.
pub const FTP_STATUS_PATH: &str = "/var/ftp/status";
pub const FTP_REQUEST_PATH: &str = "/var/ftp/request";

/// Process an FTP protocol request line against the VFS.
///
/// Returns a response string to send back to the client.
pub fn process_ftp_request(line: &str, vfs: &mut dyn Vfs) -> String {
    let parts: Vec<&str> = line.trim().splitn(3, ' ').collect();
    let cmd = parts.first().copied().unwrap_or("").to_uppercase();

    match cmd.as_str() {
        "LIST" => {
            let path = parts.get(1).copied().unwrap_or("/");
            match vfs.readdir(path) {
                Ok(entries) => {
                    if entries.is_empty() {
                        return "200 (empty)\n".to_string();
                    }
                    let mut resp = String::from("200 ");
                    for entry in &entries {
                        let kind = match entry.kind {
                            crate::vfs::EntryKind::Directory => "d",
                            crate::vfs::EntryKind::File => "f",
                        };
                        resp.push_str(&format!("{kind} {} {}\n", entry.size, entry.name));
                    }
                    resp
                },
                Err(e) => format!("500 {e}\n"),
            }
        },
        "GET" => {
            let path = parts.get(1).copied().unwrap_or("");
            if path.is_empty() {
                return "400 missing path\n".to_string();
            }
            match vfs.read(path) {
                Ok(data) => {
                    // For text mode: return content as text.
                    let text = String::from_utf8_lossy(&data);
                    format!("200 {} bytes\n{text}", data.len())
                },
                Err(e) => format!("500 {e}\n"),
            }
        },
        "PUT" => {
            let path = parts.get(1).copied().unwrap_or("");
            let content = parts.get(2).copied().unwrap_or("");
            if path.is_empty() {
                return "400 missing path\n".to_string();
            }
            match vfs.write(path, content.as_bytes()) {
                Ok(()) => format!("200 written {} bytes to {path}\n", content.len()),
                Err(e) => format!("500 {e}\n"),
            }
        },
        "MKDIR" => {
            let path = parts.get(1).copied().unwrap_or("");
            if path.is_empty() {
                return "400 missing path\n".to_string();
            }
            match vfs.mkdir(path) {
                Ok(()) => format!("200 created {path}\n"),
                Err(e) => format!("500 {e}\n"),
            }
        },
        "DELETE" => {
            let path = parts.get(1).copied().unwrap_or("");
            if path.is_empty() {
                return "400 missing path\n".to_string();
            }
            match vfs.remove(path) {
                Ok(()) => format!("200 deleted {path}\n"),
                Err(e) => format!("500 {e}\n"),
            }
        },
        "STAT" => {
            let path = parts.get(1).copied().unwrap_or("");
            if path.is_empty() {
                return "400 missing path\n".to_string();
            }
            match vfs.stat(path) {
                Ok(meta) => {
                    let kind = match meta.kind {
                        crate::vfs::EntryKind::Directory => "directory",
                        crate::vfs::EntryKind::File => "file",
                    };
                    format!("200 {kind} {} bytes\n", meta.size)
                },
                Err(e) => format!("500 {e}\n"),
            }
        },
        "QUIT" => "200 goodbye\n".to_string(),
        "" => "400 empty command\n".to_string(),
        _ => format!("400 unknown command: {cmd}\n"),
    }
}

// ---------------------------------------------------------------------------
// Terminal commands
// ---------------------------------------------------------------------------

/// `ftp` -- manage the FTP server.
pub struct FtpCmd;

impl Command for FtpCmd {
    fn name(&self) -> &str {
        "ftp"
    }
    fn description(&self) -> &str {
        "Manage the file transfer server"
    }
    fn usage(&self) -> &str {
        "ftp [start [port]|stop|status]"
    }
    fn execute(&self, args: &[&str], env: &mut Environment<'_>) -> Result<CommandOutput> {
        let subcmd = args.first().copied().unwrap_or("status");

        match subcmd {
            "start" => {
                let port = args
                    .get(1)
                    .and_then(|s| s.parse::<u16>().ok())
                    .unwrap_or(DEFAULT_FTP_PORT);

                // Signal the FTP server to start via VFS IPC.
                if !env.vfs.exists("/var/ftp") {
                    env.vfs.mkdir("/var").ok();
                    env.vfs.mkdir("/var/ftp").ok();
                }
                let request = format!("start {port}");
                env.vfs.write(FTP_REQUEST_PATH, request.as_bytes())?;
                let status = format!("active port={port}");
                env.vfs.write(FTP_STATUS_PATH, status.as_bytes())?;
                Ok(CommandOutput::Text(format!(
                    "FTP server starting on port {port}"
                )))
            },
            "stop" => {
                env.vfs.write(FTP_REQUEST_PATH, b"stop")?;
                env.vfs.write(FTP_STATUS_PATH, b"inactive")?;
                Ok(CommandOutput::Text("FTP server stopping".to_string()))
            },
            "status" => {
                if env.vfs.exists(FTP_STATUS_PATH) {
                    let data = env.vfs.read(FTP_STATUS_PATH)?;
                    let text = String::from_utf8_lossy(&data).into_owned();
                    Ok(CommandOutput::Text(format!("FTP: {text}")))
                } else {
                    Ok(CommandOutput::Text("FTP: inactive".to_string()))
                }
            },
            _ => Err(OasisError::Command(format!(
                "unknown subcommand: {subcmd}\nusage: {}",
                self.usage()
            ))),
        }
    }
}

/// `push` -- upload a local VFS file (placeholder for remote transfer).
pub struct PushCmd;

impl Command for PushCmd {
    fn name(&self) -> &str {
        "push"
    }
    fn description(&self) -> &str {
        "Copy a file to a transfer staging area"
    }
    fn usage(&self) -> &str {
        "push <source> <dest>"
    }
    fn execute(&self, args: &[&str], env: &mut Environment<'_>) -> Result<CommandOutput> {
        let src = args
            .first()
            .copied()
            .ok_or_else(|| OasisError::Command("usage: push <source> <dest>".to_string()))?;
        let dest = args
            .get(1)
            .copied()
            .ok_or_else(|| OasisError::Command("usage: push <source> <dest>".to_string()))?;

        let data = env.vfs.read(src)?;
        env.vfs.write(dest, &data)?;
        Ok(CommandOutput::Text(format!(
            "Copied {} bytes: {src} -> {dest}",
            data.len()
        )))
    }
}

/// `pull` -- download a file (VFS copy for now).
pub struct PullCmd;

impl Command for PullCmd {
    fn name(&self) -> &str {
        "pull"
    }
    fn description(&self) -> &str {
        "Copy a file from a transfer staging area"
    }
    fn usage(&self) -> &str {
        "pull <source> <dest>"
    }
    fn execute(&self, args: &[&str], env: &mut Environment<'_>) -> Result<CommandOutput> {
        let src = args
            .first()
            .copied()
            .ok_or_else(|| OasisError::Command("usage: pull <source> <dest>".to_string()))?;
        let dest = args
            .get(1)
            .copied()
            .ok_or_else(|| OasisError::Command("usage: pull <source> <dest>".to_string()))?;

        let data = env.vfs.read(src)?;
        env.vfs.write(dest, &data)?;
        Ok(CommandOutput::Text(format!(
            "Copied {} bytes: {src} -> {dest}",
            data.len()
        )))
    }
}

/// Register transfer commands.
pub fn register_transfer_commands(reg: &mut crate::terminal::CommandRegistry) {
    reg.register(Box::new(FtpCmd));
    reg.register(Box::new(PushCmd));
    reg.register(Box::new(PullCmd));
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::terminal::CommandRegistry;
    use crate::vfs::MemoryVfs;

    fn setup() -> (CommandRegistry, MemoryVfs) {
        let mut reg = CommandRegistry::new();
        register_transfer_commands(&mut reg);
        let mut vfs = MemoryVfs::new();
        vfs.mkdir("/home").unwrap();
        vfs.mkdir("/tmp").unwrap();
        vfs.mkdir("/var").unwrap();
        vfs.mkdir("/var/ftp").unwrap();
        vfs.write("/home/test.txt", b"Hello FTP").unwrap();
        (reg, vfs)
    }

    fn exec(reg: &CommandRegistry, vfs: &mut MemoryVfs, line: &str) -> Result<CommandOutput> {
        let mut env = Environment {
            cwd: "/".to_string(),
            vfs,
            power: None,
            time: None,
            usb: None,
        };
        reg.execute(line, &mut env)
    }

    // -- FTP protocol tests --

    #[test]
    fn ftp_list_root() {
        let mut vfs = MemoryVfs::new();
        vfs.mkdir("/home").unwrap();
        vfs.mkdir("/tmp").unwrap();
        let resp = process_ftp_request("LIST /", &mut vfs);
        assert!(resp.starts_with("200"));
        assert!(resp.contains("home"));
        assert!(resp.contains("tmp"));
    }

    #[test]
    fn ftp_list_empty() {
        let mut vfs = MemoryVfs::new();
        vfs.mkdir("/empty").unwrap();
        let resp = process_ftp_request("LIST /empty", &mut vfs);
        assert!(resp.contains("200"));
        assert!(resp.contains("empty"));
    }

    #[test]
    fn ftp_get_file() {
        let mut vfs = MemoryVfs::new();
        vfs.write("/test.txt", b"hello").unwrap();
        let resp = process_ftp_request("GET /test.txt", &mut vfs);
        assert!(resp.starts_with("200"));
        assert!(resp.contains("5 bytes"));
        assert!(resp.contains("hello"));
    }

    #[test]
    fn ftp_get_missing() {
        let mut vfs = MemoryVfs::new();
        let resp = process_ftp_request("GET /nope.txt", &mut vfs);
        assert!(resp.starts_with("500"));
    }

    #[test]
    fn ftp_put_file() {
        let mut vfs = MemoryVfs::new();
        let resp = process_ftp_request("PUT /new.txt hello world", &mut vfs);
        assert!(resp.starts_with("200"));
        let data = vfs.read("/new.txt").unwrap();
        assert_eq!(data, b"hello world");
    }

    #[test]
    fn ftp_mkdir() {
        let mut vfs = MemoryVfs::new();
        let resp = process_ftp_request("MKDIR /newdir", &mut vfs);
        assert!(resp.starts_with("200"));
        assert!(vfs.exists("/newdir"));
    }

    #[test]
    fn ftp_delete() {
        let mut vfs = MemoryVfs::new();
        vfs.write("/deleteme.txt", b"gone").unwrap();
        let resp = process_ftp_request("DELETE /deleteme.txt", &mut vfs);
        assert!(resp.starts_with("200"));
        assert!(!vfs.exists("/deleteme.txt"));
    }

    #[test]
    fn ftp_stat_file() {
        let mut vfs = MemoryVfs::new();
        vfs.write("/info.txt", b"data").unwrap();
        let resp = process_ftp_request("STAT /info.txt", &mut vfs);
        assert!(resp.starts_with("200"));
        assert!(resp.contains("file"));
        assert!(resp.contains("4 bytes"));
    }

    #[test]
    fn ftp_stat_dir() {
        let mut vfs = MemoryVfs::new();
        vfs.mkdir("/mydir").unwrap();
        let resp = process_ftp_request("STAT /mydir", &mut vfs);
        assert!(resp.contains("directory"));
    }

    #[test]
    fn ftp_quit() {
        let mut vfs = MemoryVfs::new();
        let resp = process_ftp_request("QUIT", &mut vfs);
        assert!(resp.contains("goodbye"));
    }

    #[test]
    fn ftp_unknown_command() {
        let mut vfs = MemoryVfs::new();
        let resp = process_ftp_request("BADCMD", &mut vfs);
        assert!(resp.starts_with("400"));
    }

    #[test]
    fn ftp_empty_command() {
        let mut vfs = MemoryVfs::new();
        let resp = process_ftp_request("", &mut vfs);
        assert!(resp.starts_with("400"));
    }

    #[test]
    fn ftp_get_missing_path() {
        let mut vfs = MemoryVfs::new();
        let resp = process_ftp_request("GET", &mut vfs);
        assert!(resp.starts_with("400"));
    }

    // -- Terminal command tests --

    #[test]
    fn ftp_cmd_status_inactive() {
        let (reg, mut vfs) = setup();
        // Remove the status file to test default.
        vfs.remove(FTP_STATUS_PATH).ok();
        match exec(&reg, &mut vfs, "ftp status").unwrap() {
            CommandOutput::Text(s) => assert!(s.contains("inactive")),
            _ => panic!("expected text"),
        }
    }

    #[test]
    fn ftp_cmd_start() {
        let (reg, mut vfs) = setup();
        match exec(&reg, &mut vfs, "ftp start 8021").unwrap() {
            CommandOutput::Text(s) => assert!(s.contains("8021")),
            _ => panic!("expected text"),
        }
        let data = vfs.read(FTP_STATUS_PATH).unwrap();
        let text = String::from_utf8_lossy(&data);
        assert!(text.contains("active"));
        assert!(text.contains("8021"));
    }

    #[test]
    fn ftp_cmd_stop() {
        let (reg, mut vfs) = setup();
        exec(&reg, &mut vfs, "ftp start").unwrap();
        match exec(&reg, &mut vfs, "ftp stop").unwrap() {
            CommandOutput::Text(s) => assert!(s.contains("stopping")),
            _ => panic!("expected text"),
        }
    }

    #[test]
    fn ftp_cmd_unknown() {
        let (reg, mut vfs) = setup();
        assert!(exec(&reg, &mut vfs, "ftp badcmd").is_err());
    }

    #[test]
    fn push_copies_file() {
        let (reg, mut vfs) = setup();
        match exec(&reg, &mut vfs, "push /home/test.txt /tmp/copy.txt").unwrap() {
            CommandOutput::Text(s) => assert!(s.contains("9 bytes")),
            _ => panic!("expected text"),
        }
        let data = vfs.read("/tmp/copy.txt").unwrap();
        assert_eq!(data, b"Hello FTP");
    }

    #[test]
    fn push_missing_source() {
        let (reg, mut vfs) = setup();
        assert!(exec(&reg, &mut vfs, "push /nope.txt /tmp/out.txt").is_err());
    }

    #[test]
    fn push_missing_args() {
        let (reg, mut vfs) = setup();
        assert!(exec(&reg, &mut vfs, "push").is_err());
        assert!(exec(&reg, &mut vfs, "push /home/test.txt").is_err());
    }

    #[test]
    fn pull_copies_file() {
        let (reg, mut vfs) = setup();
        match exec(&reg, &mut vfs, "pull /home/test.txt /tmp/pulled.txt").unwrap() {
            CommandOutput::Text(s) => assert!(s.contains("9 bytes")),
            _ => panic!("expected text"),
        }
    }
}
