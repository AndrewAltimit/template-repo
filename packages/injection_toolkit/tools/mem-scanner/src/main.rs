//! Fast memory scanner for reverse engineering.
//!
//! Scans all committed readable memory regions of a target process
//! for byte patterns with optional wildcards.
//!
//! Usage: mem-scanner <pid> <pattern> [options]
//! Pattern format: "48 8B 05 ?? ?? ?? ?? 48 85 C0"
//!
//! Options:
//!   --min-addr <hex>    Minimum address (default: 0x10000)
//!   --max-addr <hex>    Maximum address (default: 0x7FFFFFFFFFFF)
//!   --max-results <n>   Maximum results (default: 50)
//!   --json              Output as JSON (default)
//!   --hex               Output addresses as hex lines

#[cfg(windows)]
mod scanner;

fn main() {
    #[cfg(windows)]
    {
        if let Err(e) = scanner::run() {
            eprintln!("Error: {e}");
            std::process::exit(1);
        }
    }

    #[cfg(not(windows))]
    {
        eprintln!("mem-scanner only supports Windows");
        std::process::exit(1);
    }
}
