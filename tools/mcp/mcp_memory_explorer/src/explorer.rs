//! Memory exploration engine.
//!
//! [`MemoryExplorer`] holds the session state (attached process, module cache,
//! watches, value-scan candidates) and implements every operation on top of the
//! read-only [`ProcessMemory`] backend. Nothing in this file is OS specific, so
//! the whole engine is unit tested against [`crate::backend::mock::MockMemory`].
//!
//! All methods are synchronous and may block (large scans take seconds); the
//! MCP layer runs them on tokio's blocking thread pool.

use std::collections::BTreeMap;
use std::time::{Duration, Instant};

use serde::Serialize;
use serde_json::{Value, json};
use thiserror::Error;

use crate::address;
use crate::backend::{self, ProcessMemory, check_range, read_exact, read_prefix};
use crate::pattern::Pattern;
use crate::types::*;

/// Largest single read (`read_memory`, `dump_memory`).
pub const MAX_READ_SIZE: usize = 64 * 1024;
/// Largest watched region for `bytes`/`string`/`wstring` watches.
pub const MAX_WATCH_SIZE: usize = 4096;
/// Maximum number of simultaneous watches.
pub const MAX_WATCHES: usize = 256;
/// Maximum candidates retained from `find_value` for `refine_value`.
pub const MAX_CANDIDATES: usize = 100_000;
/// Maximum pointer chain depth.
pub const MAX_POINTER_DEPTH: usize = 32;
/// Default and maximum wall-clock budget for one scan.
pub const DEFAULT_SCAN_TIMEOUT: Duration = Duration::from_secs(30);
pub const MAX_SCAN_TIMEOUT: Duration = Duration::from_secs(300);
/// Bytes read per scan chunk (bounded memory regardless of region size).
const SCAN_CHUNK: usize = 1 << 20;

#[derive(Error, Debug)]
pub enum ExplorerError {
    #[error("Not attached to any process. Call attach_process first.")]
    NotAttached,

    #[error("Process not found: {0}")]
    ProcessNotFound(String),

    #[error("Target process (pid {0}) has exited. Call detach_process, then attach again.")]
    ProcessExited(u32),

    #[error("Module not found: {0}")]
    ModuleNotFound(String),

    #[error("Failed to read memory at {address:#x}: {reason}")]
    Read { address: u64, reason: String },

    #[error("Failed to open process: {0}")]
    OpenProcess(String),

    #[error("{0}")]
    InvalidInput(String),

    #[error("Watch not found: {0}")]
    WatchNotFound(String),

    #[error("Pointer chain failed: {0}")]
    PointerChain(String),

    // Only constructed on platforms without a backend.
    #[cfg_attr(any(windows, target_os = "linux"), allow(dead_code))]
    #[error(
        "Process memory access is not supported on this platform (Windows and Linux only); \
         only list_processes is available"
    )]
    PlatformNotSupported,
}

type Result<T> = std::result::Result<T, ExplorerError>;

/// Which part of the address space a scan covers.
#[derive(Debug, Clone, PartialEq, Eq)]
pub enum ScanScope {
    /// The main executable's image.
    MainModule,
    /// A named module's image.
    Module(String),
    /// Every readable committed region (optionally only writable ones).
    AllMemory { writable_only: bool },
}

impl ScanScope {
    /// Map the tool-level `module` argument to a scope. `*` / `all` mean the
    /// whole process; `None` selects `default`.
    pub fn from_module_arg(module: Option<&str>, default: ScanScope) -> Self {
        match module.map(str::trim) {
            None | Some("") => default,
            Some("*") | Some("all") => ScanScope::AllMemory {
                writable_only: false,
            },
            Some(m) => ScanScope::Module(m.to_string()),
        }
    }

    fn describe(&self) -> String {
        match self {
            ScanScope::MainModule => "main module".into(),
            ScanScope::Module(m) => format!("module {}", m),
            ScanScope::AllMemory {
                writable_only: true,
            } => "all writable memory".into(),
            ScanScope::AllMemory {
                writable_only: false,
            } => "all readable memory".into(),
        }
    }
}

/// A scan hit.
#[derive(Debug, Clone, Serialize)]
pub struct ScanHit {
    #[serde(serialize_with = "ser_hex")]
    pub address: u64,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub module: Option<String>,
    /// `module+0xOFFSET` form, stable across ASLR restarts.
    #[serde(skip_serializing_if = "Option::is_none")]
    pub module_offset: Option<String>,
}

/// Summary of a scan run.
#[derive(Debug, Clone, Serialize)]
pub struct ScanOutcome {
    pub scope: String,
    pub results: Vec<ScanHit>,
    /// Total matches found (may exceed `results.len()`).
    pub total_found: usize,
    /// True when scanning stopped because the result cap was reached.
    pub truncated: bool,
    pub timed_out: bool,
    pub bytes_scanned: u64,
    pub regions_scanned: usize,
    pub elapsed_ms: u128,
}

/// How `refine_value` filters the candidates of the previous `find_value`.
#[derive(Debug, Clone, PartialEq)]
pub enum RefineMode {
    /// Keep addresses whose current value equals `value` (within `tolerance`
    /// for float/double candidates).
    Equal {
        value: Value,
        tolerance: Option<f64>,
    },
    Changed,
    Unchanged,
    Increased,
    Decreased,
}

/// Summary of a refine run.
#[derive(Debug, Clone, Serialize)]
pub struct RefineOutcome {
    pub before: usize,
    pub remaining: usize,
    #[serde(rename = "type")]
    pub value_type: ValueType,
    pub results: Vec<Value>,
}

fn ser_hex<S: serde::Serializer>(v: &u64, s: S) -> std::result::Result<S::Ok, S::Error> {
    s.serialize_str(&format!("{:#x}", v))
}

struct Attached {
    mem: Box<dyn ProcessMemory>,
    name: String,
    /// Sorted by base address.
    modules: Vec<ModuleInfo>,
    main_module: Option<String>,
}

struct Candidates {
    value_type: ValueType,
    width: usize,
    /// (address, last observed bytes)
    entries: Vec<(u64, [u8; 8])>,
}

/// Session state for one MCP server instance.
#[derive(Default)]
pub struct MemoryExplorer {
    target: Option<Attached>,
    watches: BTreeMap<String, WatchedAddress>,
    candidates: Option<Candidates>,
    scans_run: usize,
}

// ============================================================================
// Process discovery (no attachment needed)
// ============================================================================

/// List running processes, optionally filtered by a case-insensitive substring.
pub fn list_processes(filter: Option<&str>) -> Vec<ProcessInfo> {
    let filter = filter.map(|f| f.to_lowercase()).filter(|f| !f.is_empty());
    let mut out: Vec<ProcessInfo> = snapshot_processes()
        .into_iter()
        .filter(|(_, name, exe)| match &filter {
            None => true,
            Some(f) => {
                name.to_lowercase().contains(f)
                    || exe.as_deref().is_some_and(|e| e.to_lowercase().contains(f))
            },
        })
        .map(|(pid, name, _)| ProcessInfo { name, pid })
        .collect();
    out.sort_by(|a, b| {
        a.name
            .to_lowercase()
            .cmp(&b.name.to_lowercase())
            .then(a.pid.cmp(&b.pid))
    });
    out
}

/// (pid, process name, executable file name) for every visible process.
fn snapshot_processes() -> Vec<(u32, String, Option<String>)> {
    use sysinfo::{ProcessRefreshKind, RefreshKind, System, UpdateKind};
    // Only refresh what we need: enumerating CPU/memory/disks for every process
    // (System::new_all) is far slower and was done twice before.
    let sys = System::new_with_specifics(
        RefreshKind::nothing()
            .with_processes(ProcessRefreshKind::nothing().with_exe(UpdateKind::OnlyIfNotSet)),
    );
    sys.processes()
        .iter()
        .map(|(pid, p)| {
            let exe = p
                .exe()
                .and_then(|e| e.file_name())
                .map(|n| n.to_string_lossy().into_owned());
            (pid.as_u32(), p.name().to_string_lossy().into_owned(), exe)
        })
        .collect()
}

/// Whether a process called `name` (or with executable `exe`) matches `query`.
/// Case-insensitive; `.exe` may be omitted (`NMS` matches `NMS.exe`).
pub fn process_name_matches(name: &str, exe: Option<&str>, query: &str) -> bool {
    let q = query.trim();
    let check = |n: &str| {
        n.eq_ignore_ascii_case(q)
            || (n.len() == q.len() + 4
                && n[..q.len()].eq_ignore_ascii_case(q)
                && n[q.len()..].eq_ignore_ascii_case(".exe"))
    };
    !q.is_empty() && (check(name) || exe.is_some_and(check))
}

impl MemoryExplorer {
    pub fn new() -> Self {
        Self::default()
    }

    // ========================================================================
    // Attach / detach
    // ========================================================================

    /// Attach to a process by name, or to `pid` (which must match `process_name`).
    pub fn attach(&mut self, process_name: &str, pid: Option<u32>) -> Result<AttachResult> {
        let query = process_name.trim();
        if query.is_empty() {
            return Err(ExplorerError::InvalidInput(
                "process_name must not be empty".into(),
            ));
        }
        let procs = snapshot_processes();
        let mut matches: Vec<(u32, String)> = procs
            .iter()
            .filter(|(_, n, e)| process_name_matches(n, e.as_deref(), query))
            .map(|(p, n, _)| (*p, n.clone()))
            .collect();
        matches.sort_by_key(|(p, _)| *p);

        let (chosen, name) = match pid {
            Some(want) => {
                if let Some(m) = matches.iter().find(|(p, _)| *p == want) {
                    m.clone()
                } else if let Some((_, n, _)) = procs.iter().find(|(p, _, _)| *p == want) {
                    return Err(ExplorerError::InvalidInput(format!(
                        "pid {} is '{}', not '{}'",
                        want, n, query
                    )));
                } else {
                    return Err(ExplorerError::ProcessNotFound(format!("pid {}", want)));
                }
            },
            None => matches.first().cloned().ok_or_else(|| {
                ExplorerError::ProcessNotFound(format!(
                    "{} (use list_processes to see running processes)",
                    query
                ))
            })?,
        };
        let others: Vec<u32> = matches
            .iter()
            .map(|(p, _)| *p)
            .filter(|p| *p != chosen)
            .collect();

        let mem = backend::open(chosen)?;
        let mut result = self.attach_backend(mem, &name)?;
        result.other_matching_pids = others;
        Ok(result)
    }

    /// Attach to an already opened backend (also used by tests).
    pub fn attach_backend(
        &mut self,
        mem: Box<dyn ProcessMemory>,
        name: &str,
    ) -> Result<AttachResult> {
        self.detach();
        let mut modules = mem.modules()?;
        let main_module = modules.first().map(|m| m.name.clone());
        let base = modules.first().map(|m| m.base_address).unwrap_or(0);
        modules.sort_by_key(|m| m.base_address);
        let result = AttachResult {
            attached: true,
            process_name: name.to_string(),
            pid: mem.pid(),
            base_address: format!("{:#x}", base),
            main_module: main_module.clone(),
            module_count: modules.len(),
            is_32bit: mem.is_32bit(),
            other_matching_pids: Vec::new(),
        };
        self.target = Some(Attached {
            mem,
            name: name.to_string(),
            modules,
            main_module,
        });
        Ok(result)
    }

    /// Detach, closing the process handle and clearing all process-specific
    /// state (watches and scan candidates). Returns whether anything was attached.
    pub fn detach(&mut self) -> bool {
        self.watches.clear();
        self.candidates = None;
        self.target.take().is_some()
    }

    fn require(&self) -> Result<&Attached> {
        let t = self.target.as_ref().ok_or(ExplorerError::NotAttached)?;
        if !t.mem.is_alive() {
            return Err(ExplorerError::ProcessExited(t.mem.pid()));
        }
        Ok(t)
    }

    // ========================================================================
    // Modules and addresses
    // ========================================================================

    /// Re-enumerate modules (they load/unload at runtime) and return them
    /// sorted by base address.
    pub fn modules(&mut self) -> Result<Vec<ModuleInfo>> {
        self.refresh_modules()?;
        Ok(self.require()?.modules.clone())
    }

    fn refresh_modules(&mut self) -> Result<()> {
        let mut modules = self.require()?.mem.modules()?;
        modules.sort_by_key(|m| m.base_address);
        if let Some(t) = self.target.as_mut() {
            t.modules = modules;
        }
        Ok(())
    }

    fn find_module<'a>(modules: &'a [ModuleInfo], name: &str) -> Option<&'a ModuleInfo> {
        let name = name.trim();
        modules
            .iter()
            .find(|m| m.name.eq_ignore_ascii_case(name))
            .or_else(|| {
                // Allow omitting the extension when unambiguous ("NMS" -> "NMS.exe").
                let mut it = modules.iter().filter(|m| {
                    m.name
                        .rsplit_once('.')
                        .is_some_and(|(stem, _)| stem.eq_ignore_ascii_case(name))
                });
                match (it.next(), it.next()) {
                    (Some(m), None) => Some(m),
                    _ => None,
                }
            })
    }

    /// Look up a module by name, refreshing the cache once on a miss.
    pub fn module(&mut self, name: &str) -> Result<ModuleInfo> {
        if let Some(m) = Self::find_module(&self.require()?.modules, name) {
            return Ok(m.clone());
        }
        self.refresh_modules()?;
        Self::find_module(&self.require()?.modules, name)
            .cloned()
            .ok_or_else(|| {
                ExplorerError::ModuleNotFound(format!(
                    "{} (use get_modules to list loaded modules)",
                    name
                ))
            })
    }

    /// Parse an address expression (see [`crate::address`]).
    pub fn parse_address(&mut self, input: &str) -> Result<u64> {
        // Numeric addresses do not need an attached process.
        if let Ok(v) = address::parse_unsigned(input) {
            return Ok(v);
        }
        let mut err: Option<ExplorerError> = None;
        let parsed = address::parse_address(input, |m| {
            self.module(m).map(|mi| mi.base_address).map_err(|e| {
                let msg = e.to_string();
                err = Some(e);
                msg
            })
        });
        match parsed {
            Ok(v) => Ok(v),
            // Preserve typed errors (NotAttached, ProcessExited, ...) from the resolver.
            Err(msg) => Err(err.unwrap_or(ExplorerError::InvalidInput(msg))),
        }
    }

    /// `module+0xOFFSET` for an address inside a known module.
    fn module_offset(modules: &[ModuleInfo], address: u64) -> Option<(String, String)> {
        let idx = modules.partition_point(|m| m.base_address <= address);
        let m = modules.get(idx.checked_sub(1)?)?;
        m.contains(address).then(|| {
            (
                m.name.clone(),
                format!("{}+{:#x}", m.name, address - m.base_address),
            )
        })
    }

    // ========================================================================
    // Reading
    // ========================================================================

    fn check_size(size: usize, max: usize, what: &str) -> Result<()> {
        if size == 0 || size > max {
            return Err(ExplorerError::InvalidInput(format!(
                "{} must be between 1 and {} bytes (got {})",
                what, max, size
            )));
        }
        Ok(())
    }

    /// Read a typed value. `size` applies to `bytes`/`string`/`wstring` only.
    /// Returns the JSON payload for the `read_memory` tool.
    pub fn read_value(&self, address: u64, value_type: ValueType, size: usize) -> Result<Value> {
        let t = self.require()?;
        let is32 = t.mem.is_32bit();
        let addr_hex = format!("{:#x}", address);
        match value_type.fixed_size(is32) {
            Some(n) => {
                check_range(address, n, is32)?;
                let data = read_exact(t.mem.as_ref(), address, n)?;
                let value = value_type
                    .decode(&data, is32)
                    .map_err(|reason| ExplorerError::Read { address, reason })?;
                Ok(if value_type == ValueType::Pointer {
                    // Keep the historical `pointer` key; `value` added for uniformity.
                    json!({"address": addr_hex, "type": value_type, "pointer": value, "value": value})
                } else {
                    json!({"address": addr_hex, "type": value_type, "value": value})
                })
            },
            None => {
                Self::check_size(size, MAX_READ_SIZE, "size")?;
                check_range(address, size, is32)?;
                let data = read_prefix(t.mem.as_ref(), address, size)?;
                let truncated = data.len() < size;
                if value_type == ValueType::Bytes {
                    Ok(json!({
                        "address": addr_hex,
                        "type": value_type,
                        "hex": hex_encode(&data),
                        "size": data.len(),
                        "truncated": truncated
                    }))
                } else {
                    let value = value_type
                        .decode(&data, is32)
                        .map_err(|reason| ExplorerError::Read { address, reason })?;
                    Ok(json!({
                        "address": addr_hex,
                        "type": value_type,
                        "value": value,
                        "bytes_read": data.len(),
                        "truncated": truncated
                    }))
                }
            },
        }
    }

    /// Hex dump with ASCII column. Stops early (with `truncated`) at the first
    /// unreadable page instead of failing the whole dump.
    pub fn dump_memory(&self, address: u64, size: usize) -> Result<MemoryDump> {
        let t = self.require()?;
        Self::check_size(size, MAX_READ_SIZE, "size")?;
        check_range(address, size, t.mem.is_32bit())?;
        let data = read_prefix(t.mem.as_ref(), address, size)?;
        Ok(MemoryDump {
            address: format!("{:#x}", address),
            size: data.len(),
            requested: size,
            truncated: data.len() < size,
            data: format_hex_dump(address, &data),
        })
    }

    /// Committed regions of the target, optionally filtered.
    pub fn regions(
        &mut self,
        module: Option<&str>,
        writable_only: bool,
        executable_only: bool,
    ) -> Result<Vec<(MemoryRegion, Option<String>)>> {
        let module = match module {
            Some(m) => Some(self.module(m)?),
            None => None,
        };
        let t = self.require()?;
        let regions = t.mem.regions()?;
        Ok(regions
            .into_iter()
            .filter(|r| !writable_only || r.writable)
            .filter(|r| !executable_only || r.executable)
            .filter(|r| {
                module
                    .as_ref()
                    .is_none_or(|m| r.base < m.end() && r.end() > m.base_address)
            })
            .map(|r| {
                let owner = Self::module_offset(&t.modules, r.base).map(|(n, _)| n);
                (r, owner)
            })
            .collect())
    }

    // ========================================================================
    // Scanning
    // ========================================================================

    /// Resolve a scope to merged `[start, end)` ranges of readable memory.
    fn scope_ranges(&mut self, scope: &ScanScope) -> Result<Vec<(u64, u64)>> {
        let (window, writable_only) = match scope {
            ScanScope::MainModule => {
                let main = self.require()?.main_module.clone().ok_or_else(|| {
                    ExplorerError::ModuleNotFound(
                        "main module unknown; pass module explicitly or '*'".into(),
                    )
                })?;
                let m = self.module(&main)?;
                (Some((m.base_address, m.end())), false)
            },
            ScanScope::Module(name) => {
                let m = self.module(name)?;
                (Some((m.base_address, m.end())), false)
            },
            ScanScope::AllMemory { writable_only } => (None, *writable_only),
        };
        let regions = self.require()?.mem.regions()?;
        let mut ranges: Vec<(u64, u64)> = Vec::new();
        for r in regions {
            if !r.readable || (writable_only && !r.writable) {
                continue;
            }
            let (mut s, mut e) = (r.base, r.end());
            if let Some((ws, we)) = window {
                s = s.max(ws);
                e = e.min(we);
            }
            if s >= e {
                continue;
            }
            match ranges.last_mut() {
                Some(last) if last.1 == s => last.1 = e,
                _ => ranges.push((s, e)),
            }
        }
        Ok(ranges)
    }

    /// Stream `ranges` in bounded chunks. `visit(chunk_base, data, limit)`
    /// must only report matches starting before `limit`; the extra `overlap`
    /// bytes let matches straddle chunk boundaries without being missed or
    /// reported twice. Returns (bytes scanned, timed out).
    fn scan_ranges(
        mem: &dyn ProcessMemory,
        ranges: &[(u64, u64)],
        overlap: usize,
        deadline: Instant,
        mut visit: impl FnMut(u64, &[u8], usize) -> bool,
    ) -> (u64, bool) {
        let mut scanned = 0u64;
        for &(start, end) in ranges {
            let mut pos = start;
            while pos < end {
                if Instant::now() >= deadline {
                    return (scanned, true);
                }
                let remaining = end - pos;
                let body = (SCAN_CHUNK as u64).min(remaining);
                let want = body + (overlap as u64).min(remaining - body);
                if let Ok(data) = read_prefix(mem, pos, want as usize) {
                    scanned += data.len().min(body as usize) as u64;
                    let limit = (body as usize).min(data.len());
                    if !visit(pos, &data, limit) {
                        return (scanned, false);
                    }
                }
                pos += body;
            }
        }
        (scanned, false)
    }

    /// Scan for a byte signature.
    pub fn scan_pattern(
        &mut self,
        pattern: &str,
        scope: ScanScope,
        max_results: usize,
        timeout: Duration,
    ) -> Result<ScanOutcome> {
        let pattern = Pattern::parse(pattern).map_err(ExplorerError::InvalidInput)?;
        let ranges = self.scope_ranges(&scope)?;
        let started = Instant::now();
        let t = self.require()?;
        let mut hits = Vec::new();
        let (bytes, timed_out) = Self::scan_ranges(
            t.mem.as_ref(),
            &ranges,
            pattern.len() - 1,
            started + timeout,
            |base, data, limit| {
                let mut keep_going = true;
                pattern.find_each(data, limit, |pos| {
                    hits.push(base + pos as u64);
                    keep_going = hits.len() < max_results;
                    keep_going
                });
                keep_going
            },
        );
        let truncated = hits.len() >= max_results;
        let results = self.annotate(&hits);
        self.scans_run += 1;
        Ok(ScanOutcome {
            scope: scope.describe(),
            total_found: results.len(),
            results,
            truncated,
            timed_out,
            bytes_scanned: bytes,
            regions_scanned: ranges.len(),
            elapsed_ms: started.elapsed().as_millis(),
        })
    }

    fn annotate(&self, addrs: &[u64]) -> Vec<ScanHit> {
        let modules = self
            .target
            .as_ref()
            .map(|t| t.modules.as_slice())
            .unwrap_or(&[]);
        addrs
            .iter()
            .map(|&address| {
                let (module, module_offset) = Self::module_offset(modules, address).unzip();
                ScanHit {
                    address,
                    module,
                    module_offset,
                }
            })
            .collect()
    }

    /// Search for a scalar value. All matches (up to [`MAX_CANDIDATES`]) are
    /// retained for [`Self::refine_value`]; the first `max_results` are returned.
    #[allow(clippy::too_many_arguments)]
    pub fn find_value(
        &mut self,
        value_type: ValueType,
        value: &Value,
        tolerance: Option<f64>,
        scope: ScanScope,
        max_results: usize,
        aligned: bool,
        timeout: Duration,
    ) -> Result<ScanOutcome> {
        let is32 = self.require()?.mem.is_32bit();
        let target = SearchTarget::from_json(value_type, value, tolerance, is32)
            .map_err(ExplorerError::InvalidInput)?;
        let width = target.width();
        let align = if aligned { width as u64 } else { 1 };
        let ranges = self.scope_ranges(&scope)?;
        let started = Instant::now();
        let t = self.require()?;

        let exact = match &target {
            SearchTarget::Exact(bytes) => {
                Some(Pattern::exact(bytes).map_err(ExplorerError::InvalidInput)?)
            },
            SearchTarget::Approx { .. } => None,
        };
        let mut found: Vec<(u64, [u8; 8])> = Vec::new();
        let (bytes, timed_out) = Self::scan_ranges(
            t.mem.as_ref(),
            &ranges,
            width - 1,
            started + timeout,
            |base, data, limit| {
                let mut push = |pos: usize| {
                    let mut raw = [0u8; 8];
                    raw[..width].copy_from_slice(&data[pos..pos + width]);
                    found.push((base + pos as u64, raw));
                    found.len() < MAX_CANDIDATES
                };
                match &exact {
                    Some(p) => {
                        let mut more = true;
                        p.find_each(data, limit, |pos| {
                            if !(base + pos as u64).is_multiple_of(align) {
                                return true;
                            }
                            more = push(pos);
                            more
                        });
                        more
                    },
                    None => {
                        let first = ((align - base % align) % align) as usize;
                        let mut pos = first;
                        while pos < limit && pos + width <= data.len() {
                            if target.matches(&data[pos..pos + width]) && !push(pos) {
                                return false;
                            }
                            pos += align as usize;
                        }
                        true
                    },
                }
            },
        );

        let total = found.len();
        let shown: Vec<u64> = found.iter().take(max_results).map(|(a, _)| *a).collect();
        let results = self.annotate(&shown);
        self.candidates = Some(Candidates {
            value_type,
            width,
            entries: found,
        });
        self.scans_run += 1;
        Ok(ScanOutcome {
            scope: scope.describe(),
            total_found: total,
            results,
            truncated: total >= MAX_CANDIDATES,
            timed_out,
            bytes_scanned: bytes,
            regions_scanned: ranges.len(),
            elapsed_ms: started.elapsed().as_millis(),
        })
    }

    /// Re-read the candidates of the last `find_value` and keep those that
    /// satisfy `mode` (Cheat Engine style "next scan").
    pub fn refine_value(&mut self, mode: RefineMode, max_results: usize) -> Result<RefineOutcome> {
        let t = self.require()?;
        let is32 = t.mem.is_32bit();
        let cands = self.candidates.as_ref().ok_or_else(|| {
            ExplorerError::InvalidInput(
                "no previous find_value results to refine; run find_value first".into(),
            )
        })?;
        let (vt, width) = (cands.value_type, cands.width);
        let target = match &mode {
            RefineMode::Equal { value, tolerance } => Some(
                SearchTarget::from_json(vt, value, *tolerance, is32)
                    .map_err(ExplorerError::InvalidInput)?,
            ),
            _ => None,
        };
        let before = cands.entries.len();
        let mut kept = Vec::new();
        let mut buf = [0u8; 8];
        for (addr, old) in &cands.entries {
            let n = match t.mem.read(*addr, &mut buf[..width]) {
                Ok(n) => n,
                Err(_) => continue, // freed/unmapped: drop the candidate
            };
            if n < width {
                continue;
            }
            let new = &buf[..width];
            let keep = match &mode {
                RefineMode::Equal { .. } => target.as_ref().is_some_and(|t| t.matches(new)),
                RefineMode::Changed => new != &old[..width],
                RefineMode::Unchanged => new == &old[..width],
                RefineMode::Increased | RefineMode::Decreased => {
                    match (
                        vt.scalar_as_f64(&old[..width], is32),
                        vt.scalar_as_f64(new, is32),
                    ) {
                        (Some(o), Some(n)) if matches!(mode, RefineMode::Increased) => n > o,
                        (Some(o), Some(n)) => n < o,
                        _ => false,
                    }
                },
            };
            if keep {
                let mut raw = [0u8; 8];
                raw[..width].copy_from_slice(new);
                kept.push((*addr, raw));
            }
        }
        let modules = &t.modules;
        let results: Vec<Value> = kept
            .iter()
            .take(max_results)
            .map(|(addr, raw)| {
                let mut v = json!({
                    "address": format!("{:#x}", addr),
                    "value": vt.decode(&raw[..width], is32).unwrap_or(Value::Null),
                });
                if let Some((m, off)) = Self::module_offset(modules, *addr) {
                    v["module"] = json!(m);
                    v["module_offset"] = json!(off);
                }
                v
            })
            .collect();
        let remaining = kept.len();
        if let Some(c) = self.candidates.as_mut() {
            c.entries = kept;
        }
        Ok(RefineOutcome {
            before,
            remaining,
            value_type: vt,
            results,
        })
    }

    // ========================================================================
    // Pointer chains
    // ========================================================================

    /// Follow a pointer chain Cheat Engine style: for each offset, read a
    /// pointer at the current address and add the offset:
    /// `final = [[[base] + o0] + o1] + o2`. With no offsets the base is returned.
    pub fn resolve_pointer_chain(&self, base: u64, offsets: &[i64]) -> Result<PointerChain> {
        let t = self.require()?;
        if offsets.len() > MAX_POINTER_DEPTH {
            return Err(ExplorerError::InvalidInput(format!(
                "pointer chains are limited to {} offsets",
                MAX_POINTER_DEPTH
            )));
        }
        let is32 = t.mem.is_32bit();
        let psize = if is32 { 4 } else { 8 };
        let mut current = base;
        let mut steps = Vec::with_capacity(offsets.len());
        for (i, &offset) in offsets.iter().enumerate() {
            let raw = read_exact(t.mem.as_ref(), current, psize).map_err(|e| {
                ExplorerError::PointerChain(format!(
                    "step {}: cannot read pointer at {:#x}: {}",
                    i, current, e
                ))
            })?;
            let pointer = read_pointer_le(&raw, is32);
            if pointer == 0 {
                return Err(ExplorerError::PointerChain(format!(
                    "step {}: null pointer at {:#x}",
                    i, current
                )));
            }
            let mut next = pointer.wrapping_add_signed(offset);
            if is32 {
                next &= 0xffff_ffff;
            }
            steps.push(PointerStep {
                read_from: current,
                pointer,
                offset,
                result: next,
            });
            current = next;
        }
        Ok(PointerChain {
            base_address: base,
            offsets: offsets.to_vec(),
            final_address: current,
            steps,
        })
    }

    // ========================================================================
    // Watches
    // ========================================================================

    /// Add (or replace) a watch. The address must be readable now; the
    /// initial value is returned.
    pub fn add_watch(
        &mut self,
        label: &str,
        address: u64,
        value_type: ValueType,
        size: Option<usize>,
    ) -> Result<WatchResult> {
        let label = label.trim();
        if label.is_empty() || label.len() > 128 {
            return Err(ExplorerError::InvalidInput(
                "label must be 1-128 characters".into(),
            ));
        }
        let is32 = self.require()?.mem.is_32bit();
        if !self.watches.contains_key(label) && self.watches.len() >= MAX_WATCHES {
            return Err(ExplorerError::InvalidInput(format!(
                "too many watches (max {}); remove some first",
                MAX_WATCHES
            )));
        }
        let size = match value_type.fixed_size(is32) {
            Some(n) => n,
            None => {
                let n = size.unwrap_or(match value_type {
                    ValueType::String => 64,
                    ValueType::Wstring => 128,
                    _ => 16,
                });
                Self::check_size(n, MAX_WATCH_SIZE, "watch size")?;
                n
            },
        };
        check_range(address, size, is32)?;
        let watch = WatchedAddress {
            address,
            size,
            label: label.to_string(),
            last_value: None,
            value_type,
        };
        // Validate readability before committing the watch.
        let (result, bytes) = self.evaluate_watch(&watch)?;
        let mut stored = watch;
        stored.last_value = Some(bytes);
        self.watches.insert(label.to_string(), stored);
        Ok(result)
    }

    fn read_watch_bytes(&self, w: &WatchedAddress) -> Result<Vec<u8>> {
        let t = self.require()?;
        if w.value_type.fixed_size(t.mem.is_32bit()).is_some() {
            read_exact(t.mem.as_ref(), w.address, w.size)
        } else {
            read_prefix(t.mem.as_ref(), w.address, w.size)
        }
    }

    /// Read a watch once; returns the report and the raw bytes it was built
    /// from (so the stored "last value" is exactly what was reported).
    fn evaluate_watch(&self, w: &WatchedAddress) -> Result<(WatchResult, Vec<u8>)> {
        let is32 = self.require()?.mem.is_32bit();
        let data = self.read_watch_bytes(w)?;
        let decode = |d: &[u8]| {
            w.value_type
                .decode(d, is32)
                .unwrap_or_else(|e| json!(format!("<{}>", e)))
        };
        let changed = w.last_value.as_ref().is_some_and(|old| old != &data);
        let result = WatchResult {
            label: w.label.clone(),
            address: format!("{:#x}", w.address),
            value_type: w.value_type,
            value: decode(&data),
            raw_hex: hex_encode(&data),
            changed,
            previous_value: if changed {
                w.last_value.as_deref().map(decode)
            } else {
                None
            },
            error: None,
        };
        Ok((result, data))
    }

    /// Read every watch, reporting per-watch errors instead of dropping them.
    /// Results are sorted by label.
    pub fn read_all_watches(&mut self) -> Result<Vec<WatchResult>> {
        self.require()?;
        let mut out = Vec::with_capacity(self.watches.len());
        let mut updates = Vec::new();
        for (label, w) in &self.watches {
            match self.evaluate_watch(w) {
                Ok((r, bytes)) => {
                    updates.push((label.clone(), bytes));
                    out.push(r);
                },
                Err(e) => out.push(WatchResult {
                    label: label.clone(),
                    address: format!("{:#x}", w.address),
                    value_type: w.value_type,
                    value: Value::Null,
                    raw_hex: String::new(),
                    changed: false,
                    previous_value: None,
                    error: Some(e.to_string()),
                }),
            }
        }
        for (label, bytes) in updates {
            if let Some(w) = self.watches.get_mut(&label) {
                w.last_value = Some(bytes);
            }
        }
        Ok(out)
    }

    /// Remove a watch.
    pub fn remove_watch(&mut self, label: &str) -> Result<()> {
        self.watches
            .remove(label.trim())
            .map(|_| ())
            .ok_or_else(|| ExplorerError::WatchNotFound(label.to_string()))
    }

    // ========================================================================
    // Status
    // ========================================================================

    pub fn status(&self) -> ExplorerStatus {
        let t = self.target.as_ref();
        ExplorerStatus {
            attached: t.is_some(),
            process: t.map(|t| t.name.clone()),
            pid: t.map(|t| t.mem.pid()),
            is_32bit: t.map(|t| t.mem.is_32bit()),
            process_alive: t.map(|t| t.mem.is_alive()),
            watches: self.watches.keys().cloned().collect(),
            recent_scans: self.scans_run,
            scan_candidates: self.candidates.as_ref().map_or(0, |c| c.entries.len()),
            platform: std::env::consts::OS,
            memory_access_supported: backend::MEMORY_ACCESS_SUPPORTED,
        }
    }
}

/// Classic 16-bytes-per-line hex dump with an ASCII column.
pub fn format_hex_dump(address: u64, data: &[u8]) -> String {
    use std::fmt::Write;
    let mut out = String::with_capacity(data.len() / 16 * 80 + 80);
    for (i, chunk) in data.chunks(16).enumerate() {
        if i > 0 {
            out.push('\n');
        }
        let hex: Vec<String> = chunk.iter().map(|b| format!("{:02X}", b)).collect();
        let ascii: String = chunk
            .iter()
            .map(|&b| {
                if (32..127).contains(&b) {
                    b as char
                } else {
                    '.'
                }
            })
            .collect();
        let _ = write!(
            out,
            "{:016X}  {:<47}  {}",
            address.wrapping_add((i * 16) as u64),
            hex.join(" "),
            ascii
        );
    }
    out
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::backend::mock::MockMemory;

    const IMAGE: u64 = 0x1_4000_0000;
    const HEAP: u64 = 0x2000_0000;

    /// A fake 64-bit game: an image with a code signature and a static pointer,
    /// plus a heap holding a player struct.
    fn game() -> MockMemory {
        let mut image = vec![0u8; 0x3000];
        image[0x100..0x107].copy_from_slice(&[0x48, 0x8B, 0x05, 0x11, 0x22, 0x33, 0x44]);
        // Static pointer at image+0x2000 -> HEAP+0x100 (player object).
        image[0x2000..0x2008].copy_from_slice(&(HEAP + 0x100).to_le_bytes());

        let mut heap = vec![0u8; 0x2000];
        // player+0x10 -> pointer to stats at HEAP+0x800
        heap[0x110..0x118].copy_from_slice(&(HEAP + 0x800).to_le_bytes());
        // stats+0x8 = health (float 100.0)
        heap[0x808..0x80c].copy_from_slice(&100.0f32.to_le_bytes());
        // Another 100.0 at an unaligned address and one aligned elsewhere.
        heap[0x901..0x905].copy_from_slice(&100.0f32.to_le_bytes());
        heap[0xA00..0xA04].copy_from_slice(&100.0f32.to_le_bytes());
        // ammo int32 = 30
        heap[0xB00..0xB04].copy_from_slice(&30i32.to_le_bytes());

        MockMemory::new()
            .with_module("Game.exe", IMAGE, 0x3000)
            .with_module("engine.dll", 0x1_8000_0000, 0x1000)
            .with_region_rw(IMAGE, image, false)
            .with_region(0x1_8000_0000, vec![0u8; 0x1000])
            .with_region(HEAP, heap)
    }

    fn attached() -> MemoryExplorer {
        let mut e = MemoryExplorer::new();
        let r = e.attach_backend(Box::new(game()), "Game.exe").unwrap();
        assert_eq!(r.base_address, "0x140000000");
        assert_eq!(r.main_module.as_deref(), Some("Game.exe"));
        e
    }

    fn secs(n: u64) -> Duration {
        Duration::from_secs(n)
    }

    #[test]
    fn requires_attachment() {
        let mut e = MemoryExplorer::new();
        assert!(matches!(
            e.read_value(0x1000, ValueType::Int32, 4),
            Err(ExplorerError::NotAttached)
        ));
        assert!(matches!(
            e.parse_address("Game.exe+0x10"),
            Err(ExplorerError::NotAttached)
        ));
        // Numeric addresses parse without a process.
        assert_eq!(e.parse_address("0x10").unwrap(), 0x10);
        assert!(!e.detach());
        assert!(!e.status().attached);
    }

    #[test]
    fn process_name_matching() {
        assert!(process_name_matches("NMS.exe", None, "nms.exe"));
        assert!(process_name_matches("NMS.exe", None, "NMS"));
        assert!(!process_name_matches("NMS.exe", None, "NM"));
        assert!(process_name_matches(
            "game-main",
            Some("GameBinary"),
            "gamebinary"
        ));
        assert!(!process_name_matches("x", None, "  "));
    }

    #[test]
    fn list_processes_includes_self() {
        let procs = list_processes(None);
        assert!(procs.iter().any(|p| p.pid == std::process::id()));
        assert!(list_processes(Some("definitely-not-a-real-process-name-xyz")).is_empty());
    }

    #[test]
    fn module_lookup_and_address_parsing() {
        let mut e = attached();
        assert_eq!(e.parse_address("game.exe+0x10").unwrap(), IMAGE + 0x10);
        assert_eq!(e.parse_address("Game").unwrap(), IMAGE);
        assert!(matches!(
            e.parse_address("nope.dll+4"),
            Err(ExplorerError::ModuleNotFound(_))
        ));
        let mods = e.modules().unwrap();
        assert_eq!(mods.len(), 2);
        assert!(mods[0].base_address < mods[1].base_address);
    }

    #[test]
    fn typed_reads() {
        let e = attached();
        let v = e.read_value(HEAP + 0x808, ValueType::Float, 0).unwrap();
        assert_eq!(v["value"], json!(100.0));
        let v = e.read_value(HEAP + 0xB00, ValueType::Int32, 0).unwrap();
        assert_eq!(v["value"], json!(30));
        let v = e.read_value(IMAGE + 0x2000, ValueType::Pointer, 0).unwrap();
        assert_eq!(v["pointer"], json!("0x20000100"));
        let v = e.read_value(IMAGE + 0x100, ValueType::Bytes, 3).unwrap();
        assert_eq!(v["hex"], json!("488b05"));

        // Reading past the end of the heap: fixed-size read fails cleanly.
        let err = e
            .read_value(HEAP + 0x1ffe, ValueType::Int32, 0)
            .unwrap_err();
        assert!(err.to_string().contains("only 2 of 4"), "{err}");
        // Variable-size read returns the readable prefix.
        let v = e.read_value(HEAP + 0x1ffe, ValueType::Bytes, 16).unwrap();
        assert_eq!(v["size"], json!(2));
        assert_eq!(v["truncated"], json!(true));

        assert!(e.read_value(HEAP, ValueType::Bytes, 0).is_err());
        assert!(
            e.read_value(HEAP, ValueType::Bytes, MAX_READ_SIZE + 1)
                .is_err()
        );
        assert!(e.read_value(u64::MAX - 1, ValueType::Int32, 0).is_err());
    }

    #[test]
    fn dump_truncates_at_unreadable_page() {
        let e = attached();
        let d = e.dump_memory(HEAP + 0x1ff0, 0x40).unwrap();
        assert_eq!(d.size, 0x10);
        assert!(d.truncated);
        assert_eq!(d.data.lines().count(), 1);
        assert!(e.dump_memory(0x10, 16).is_err());
    }

    #[test]
    fn hex_dump_format() {
        let s = format_hex_dump(0x1000, b"ABC\x00\x01");
        assert_eq!(
            s,
            format!("{:016X}  {:<47}  ABC..", 0x1000, "41 42 43 00 01")
        );
    }

    #[test]
    fn pattern_scan_scopes() {
        let mut e = attached();
        // Default scope: main module only.
        let r = e
            .scan_pattern("48 8B 05 ?? ??", ScanScope::MainModule, 10, secs(5))
            .unwrap();
        assert_eq!(r.results.len(), 1);
        assert_eq!(r.results[0].address, IMAGE + 0x100);
        assert_eq!(
            r.results[0].module_offset.as_deref(),
            Some("Game.exe+0x100")
        );
        assert!(!r.timed_out);

        // Not present in engine.dll.
        let r = e
            .scan_pattern(
                "48 8B 05",
                ScanScope::Module("engine.dll".into()),
                10,
                secs(5),
            )
            .unwrap();
        assert!(r.results.is_empty());

        // Whole process: finds 100.0f in heap three times.
        let r = e
            .scan_pattern(
                "00 00 C8 42",
                ScanScope::AllMemory {
                    writable_only: false,
                },
                10,
                secs(5),
            )
            .unwrap();
        assert_eq!(r.results.len(), 3);
        assert!(r.results.iter().all(|h| h.module.is_none()));

        // max_results cap.
        let r = e
            .scan_pattern(
                "00 00 C8 42",
                ScanScope::AllMemory {
                    writable_only: false,
                },
                1,
                secs(5),
            )
            .unwrap();
        assert_eq!(r.results.len(), 1);
        assert!(r.truncated);

        assert!(
            e.scan_pattern("?? ??", ScanScope::MainModule, 1, secs(1))
                .is_err()
        );
        assert!(
            e.scan_pattern("48", ScanScope::Module("missing.dll".into()), 1, secs(1))
                .is_err()
        );
        assert_eq!(e.status().recent_scans, 4);
    }

    #[test]
    fn scan_finds_match_straddling_chunk_boundary() {
        let mut data = vec![0u8; SCAN_CHUNK + 64];
        data[SCAN_CHUNK - 2..SCAN_CHUNK + 2].copy_from_slice(&[0xDE, 0xAD, 0xBE, 0xEF]);
        let mem = MockMemory::new()
            .with_module("big.exe", 0x10_0000, data.len() as u64)
            .with_region(0x10_0000, data);
        let mut e = MemoryExplorer::new();
        e.attach_backend(Box::new(mem), "big.exe").unwrap();
        let r = e
            .scan_pattern("DE AD BE EF", ScanScope::MainModule, 10, secs(5))
            .unwrap();
        assert_eq!(r.results.len(), 1, "exactly one hit, no duplicates");
        assert_eq!(r.results[0].address, 0x10_0000 + SCAN_CHUNK as u64 - 2);
    }

    #[test]
    fn scan_timeout_is_reported() {
        let mut e = attached();
        let r = e
            .scan_pattern(
                "48 8B",
                ScanScope::AllMemory {
                    writable_only: false,
                },
                10,
                Duration::ZERO,
            )
            .unwrap();
        assert!(r.timed_out);
        assert!(r.results.is_empty());
    }

    #[test]
    fn find_and_refine_value() {
        // Keep a handle to poke memory after attaching.
        let mem = std::sync::Arc::new(game());
        let mut e = MemoryExplorer::new();
        e.attach_backend(Box::new(mem.clone()), "Game.exe").unwrap();

        let all_writable = ScanScope::AllMemory {
            writable_only: true,
        };
        // Aligned search skips the unaligned copy at HEAP+0x901.
        let r = e
            .find_value(
                ValueType::Float,
                &json!(100),
                None,
                all_writable.clone(),
                50,
                true,
                secs(5),
            )
            .unwrap();
        assert_eq!(r.total_found, 2);
        // Unaligned finds all three.
        let r = e
            .find_value(
                ValueType::Float,
                &json!(100),
                None,
                all_writable.clone(),
                50,
                false,
                secs(5),
            )
            .unwrap();
        assert_eq!(r.total_found, 3);

        // Tolerance search.
        let r = e
            .find_value(
                ValueType::Float,
                &json!(99.9),
                Some(0.2),
                all_writable.clone(),
                1,
                true,
                secs(5),
            )
            .unwrap();
        assert_eq!(r.total_found, 2);
        assert_eq!(r.results.len(), 1, "max_results limits returned rows");
        assert_eq!(e.status().scan_candidates, 2);

        // Health drops to 75: refine by exact value.
        mem.poke(HEAP + 0x808, &75.0f32.to_le_bytes());
        let r = e
            .refine_value(
                RefineMode::Equal {
                    value: json!(75),
                    tolerance: None,
                },
                10,
            )
            .unwrap();
        assert_eq!((r.before, r.remaining), (2, 1));
        assert_eq!(
            r.results[0]["address"],
            json!(format!("{:#x}", HEAP + 0x808))
        );
        assert_eq!(r.results[0]["value"], json!(75.0));

        // Decreased / unchanged / changed.
        mem.poke(HEAP + 0x808, &50.0f32.to_le_bytes());
        let r = e.refine_value(RefineMode::Decreased, 10).unwrap();
        assert_eq!(r.remaining, 1);
        let r = e.refine_value(RefineMode::Unchanged, 10).unwrap();
        assert_eq!(r.remaining, 1);
        let r = e.refine_value(RefineMode::Increased, 10).unwrap();
        assert_eq!(r.remaining, 0);

        // int search with range checking.
        let r = e
            .find_value(
                ValueType::Int32,
                &json!(30),
                None,
                all_writable,
                10,
                true,
                secs(5),
            )
            .unwrap();
        assert_eq!(r.total_found, 1);
        assert!(
            e.find_value(
                ValueType::Int8,
                &json!(1000),
                None,
                ScanScope::MainModule,
                10,
                true,
                secs(5)
            )
            .is_err()
        );

        // Detach clears candidates.
        e.detach();
        assert!(e.refine_value(RefineMode::Changed, 10).is_err());
    }

    #[test]
    fn refine_without_find_is_error() {
        let mut e = attached();
        let err = e.refine_value(RefineMode::Changed, 10).unwrap_err();
        assert!(err.to_string().contains("find_value first"));
    }

    #[test]
    fn pointer_chain_semantics() {
        let e = attached();
        // [[Game.exe+0x2000] + 0x10] + 0x8 = health address
        let chain = e
            .resolve_pointer_chain(IMAGE + 0x2000, &[0x10, 0x8])
            .unwrap();
        assert_eq!(chain.final_address, HEAP + 0x808);
        assert_eq!(chain.steps.len(), 2);
        assert_eq!(chain.steps[0].pointer, HEAP + 0x100);
        assert_eq!(chain.steps[0].result, HEAP + 0x110);
        assert_eq!(chain.steps[1].pointer, HEAP + 0x800);

        // Single offset still dereferences the base.
        let chain = e.resolve_pointer_chain(IMAGE + 0x2000, &[0]).unwrap();
        assert_eq!(chain.final_address, HEAP + 0x100);

        // No offsets: base unchanged.
        assert_eq!(
            e.resolve_pointer_chain(IMAGE, &[]).unwrap().final_address,
            IMAGE
        );

        // Negative offsets.
        let chain = e.resolve_pointer_chain(IMAGE + 0x2000, &[-0x100]).unwrap();
        assert_eq!(chain.final_address, HEAP);

        // Null pointer and unreadable pointer are reported with the step.
        let err = e.resolve_pointer_chain(HEAP, &[0]).unwrap_err();
        assert!(err.to_string().contains("null pointer"), "{err}");
        let err = e.resolve_pointer_chain(0x10, &[0]).unwrap_err();
        assert!(err.to_string().contains("step 0"), "{err}");
        assert!(
            e.resolve_pointer_chain(IMAGE, &[0; MAX_POINTER_DEPTH + 1])
                .is_err()
        );
    }

    #[test]
    fn pointer_chain_32bit() {
        let mut data = vec![0u8; 0x100];
        data[0..4].copy_from_slice(&0x1000_0040u32.to_le_bytes());
        data[0x44..0x48].copy_from_slice(&0x1000_0080u32.to_le_bytes());
        let mem = MockMemory::new()
            .bits32(true)
            .with_module("old.exe", 0x1000_0000, 0x100)
            .with_region(0x1000_0000, data);
        let mut e = MemoryExplorer::new();
        let r = e.attach_backend(Box::new(mem), "old.exe").unwrap();
        assert!(r.is_32bit);
        let chain = e.resolve_pointer_chain(0x1000_0000, &[4, 0x10]).unwrap();
        assert_eq!(chain.final_address, 0x1000_0090);
        let v = e.read_value(0x1000_0000, ValueType::Pointer, 0).unwrap();
        assert_eq!(v["pointer"], json!("0x10000040"));
    }

    #[test]
    fn watches_track_changes() {
        let mem = std::sync::Arc::new(game());
        let mut e = MemoryExplorer::new();
        e.attach_backend(Box::new(mem.clone()), "Game.exe").unwrap();

        // Double watch reads 8 bytes regardless of the (ignored) size.
        let w = e
            .add_watch("hp", HEAP + 0x808, ValueType::Float, Some(2))
            .unwrap();
        assert_eq!(w.value, json!(100.0));
        assert!(!w.changed);
        e.add_watch("ammo", HEAP + 0xB00, ValueType::Int32, None)
            .unwrap();

        // Unreadable address is rejected and not stored.
        assert!(e.add_watch("bad", 0x10, ValueType::Int32, None).is_err());
        assert!(e.add_watch("", HEAP, ValueType::Int32, None).is_err());
        assert!(
            e.add_watch("big", HEAP, ValueType::Bytes, Some(MAX_WATCH_SIZE + 1))
                .is_err()
        );

        mem.poke(HEAP + 0x808, &90.0f32.to_le_bytes());
        let r = e.read_all_watches().unwrap();
        assert_eq!(r.len(), 2);
        assert_eq!(r[0].label, "ammo", "sorted by label");
        assert!(!r[0].changed);
        assert!(r[1].changed);
        assert_eq!(r[1].value, json!(90.0));
        assert_eq!(r[1].previous_value, Some(json!(100.0)));

        // Second read: no change since last read.
        let r = e.read_all_watches().unwrap();
        assert!(!r[1].changed);

        e.remove_watch("ammo").unwrap();
        assert!(matches!(
            e.remove_watch("ammo"),
            Err(ExplorerError::WatchNotFound(_))
        ));
        assert_eq!(e.status().watches, vec!["hp".to_string()]);

        // Process exit is detected.
        mem.kill();
        assert!(matches!(
            e.read_all_watches(),
            Err(ExplorerError::ProcessExited(_))
        ));
        assert_eq!(e.status().process_alive, Some(false));
        assert!(e.detach());
        assert!(e.status().watches.is_empty());
    }

    #[test]
    fn regions_filtering() {
        let mut e = attached();
        let all = e.regions(None, false, false).unwrap();
        assert_eq!(all.len(), 3);
        let w = e.regions(None, true, false).unwrap();
        assert_eq!(w.len(), 2);
        let m = e.regions(Some("Game.exe"), false, false).unwrap();
        assert_eq!(m.len(), 1);
        assert_eq!(m[0].1.as_deref(), Some("Game.exe"));
    }

    /// Exercise the real OS backend against this test process itself.
    #[cfg(any(windows, target_os = "linux"))]
    #[test]
    fn real_backend_reads_own_memory() {
        static MARKER: [u8; 16] = *b"MEMEXPLR-MARKER!";
        let pid = std::process::id();
        let mem = match backend::open(pid) {
            Ok(m) => m,
            // Hardened CI sandboxes may forbid even self-inspection via /proc.
            Err(e) => {
                eprintln!("skipping: cannot open self: {e}");
                return;
            },
        };
        let mut e = MemoryExplorer::new();
        let r = e.attach_backend(mem, "self").unwrap();
        assert_eq!(r.pid, pid);
        assert!(r.module_count > 0);
        assert!(e.status().process_alive.unwrap());

        let addr = MARKER.as_ptr() as u64;
        let v = e.read_value(addr, ValueType::Bytes, 16).unwrap();
        assert_eq!(v["hex"], json!(hex_encode(&MARKER)));
        let v = e.read_value(addr, ValueType::String, 16).unwrap();
        assert_eq!(v["value"], json!("MEMEXPLR-MARKER!"));

        // The marker lives in the main image's read-only data.
        let main = r.main_module.clone().unwrap();
        let hit = e
            .scan_pattern(
                &MARKER
                    .iter()
                    .map(|b| format!("{:02X} ", b))
                    .collect::<String>(),
                ScanScope::Module(main),
                10,
                secs(30),
            )
            .unwrap();
        assert!(
            hit.results.iter().any(|h| h.address == addr),
            "scan should find the marker at {:#x}: {:?}",
            addr,
            hit.results
        );

        let regions = e.regions(None, false, false).unwrap();
        assert!(
            regions
                .iter()
                .any(|(r, _)| r.base <= addr && addr < r.end())
        );
        // Address 0 is never mapped.
        assert!(e.read_value(0, ValueType::Int32, 0).is_err());
    }
}
