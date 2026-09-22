//! MCP tool layer for the memory explorer.
//!
//! Every tool:
//! - deserializes its arguments into a typed struct (missing/mistyped input is
//!   an `InvalidParameters` error, never a panic);
//! - runs the explorer operation on tokio's blocking pool, because scans and
//!   OS calls block for up to minutes and must not stall the async runtime;
//! - reports failures as `{"success": false, "error": ...}` with the MCP
//!   `isError` flag set, and successes as `{"success": true, ...}`.
//!
//! The JSON schemas are written by hand (rather than via `#[mcp_tool]`) because
//! several tools take a parameter literally named `type` and need `enum`
//! constraints and defaults in the schema that the macro cannot express.

use std::future::Future;
use std::pin::Pin;
use std::sync::Arc;
use std::time::Duration;

use async_trait::async_trait;
use mcp_core::prelude::*;
use serde::Deserialize;
use serde::de::DeserializeOwned;
use serde_json::{Value, json};
use tokio::sync::Mutex;
use tracing::info;

use crate::address;
use crate::explorer::{
    self, DEFAULT_SCAN_TIMEOUT, MAX_READ_SIZE, MAX_SCAN_TIMEOUT, MemoryExplorer, RefineMode,
    ScanScope,
};
use crate::types::{SCALAR_TYPE_NAMES, VALUE_TYPE_NAMES, ValueType};

/// Shared explorer state. A tokio mutex (not std) so a panic inside a tool
/// cannot poison it; the guard is moved into the blocking task.
pub type SharedExplorer = Arc<Mutex<MemoryExplorer>>;

/// Upper bound for `max_results`-style parameters.
const MAX_RESULTS_CAP: u64 = 10_000;

type ToolFuture = Pin<Box<dyn Future<Output = Result<ToolResult>> + Send>>;
type Handler = fn(SharedExplorer, Value) -> ToolFuture;

/// A tool backed by a plain async handler function.
struct ExplorerTool {
    name: &'static str,
    description: &'static str,
    schema: fn() -> Value,
    handler: Handler,
    state: SharedExplorer,
}

#[async_trait]
impl Tool for ExplorerTool {
    fn name(&self) -> &str {
        self.name
    }

    fn description(&self) -> &str {
        self.description
    }

    fn schema(&self) -> Value {
        (self.schema)()
    }

    async fn execute(&self, args: Value) -> Result<ToolResult> {
        (self.handler)(self.state.clone(), args).await
    }
}

/// Memory explorer MCP server: owns the shared state and builds the tools.
pub struct MemoryExplorerServer {
    explorer: SharedExplorer,
}

impl Default for MemoryExplorerServer {
    fn default() -> Self {
        Self::new()
    }
}

macro_rules! tool {
    ($state:expr, $name:literal, $desc:expr, $schema:ident, $handler:ident) => {
        Arc::new(ExplorerTool {
            name: $name,
            description: $desc,
            schema: $schema,
            handler: |s, a| Box::pin($handler(s, a)),
            state: $state.clone(),
        }) as BoxedTool
    };
}

impl MemoryExplorerServer {
    pub fn new() -> Self {
        Self::with_explorer(MemoryExplorer::new())
    }

    /// Build a server around an existing explorer (tests attach a mock first).
    pub fn with_explorer(explorer: MemoryExplorer) -> Self {
        Self {
            explorer: Arc::new(Mutex::new(explorer)),
        }
    }

    /// All tools as boxed trait objects.
    pub fn tools(&self) -> Vec<BoxedTool> {
        let s = &self.explorer;
        vec![
            tool!(
                s,
                "list_processes",
                "List running processes (name + pid). Optionally filter by a case-insensitive name substring. Works on every platform.",
                schema_list_processes,
                list_processes
            ),
            tool!(
                s,
                "attach_process",
                "Attach (read-only) to a process by name, e.g. 'NMS.exe' ('.exe' optional). Pass pid to pick one of several same-named processes. Required before any memory operation; replaces any previous attachment.",
                schema_attach,
                attach_process
            ),
            tool!(
                s,
                "detach_process",
                "Detach from the current process and clear its watches and scan candidates.",
                schema_empty,
                detach_process
            ),
            tool!(
                s,
                "get_modules",
                "List loaded modules (EXE/DLLs) of the attached process with base addresses and sizes, sorted by address. Optional name filter.",
                schema_get_modules,
                get_modules
            ),
            tool!(
                s,
                "get_memory_regions",
                "List committed memory regions (base, size, readable/writable/executable, kind, owning module). Useful to check whether an address is valid.",
                schema_get_memory_regions,
                get_memory_regions
            ),
            tool!(
                s,
                "read_memory",
                "Read and decode memory at an address. Address forms: '0x7FF6A1B2C3D4', decimal, 'Module.exe', 'Module.exe+0x1234', 'Module.exe-0x10'.",
                schema_read_memory,
                read_memory
            ),
            tool!(
                s,
                "dump_memory",
                "Hex dump with an ASCII column (16 bytes per line). Stops early at unreadable memory and reports truncated=true.",
                schema_dump_memory,
                dump_memory
            ),
            tool!(
                s,
                "scan_pattern",
                "Scan for a byte signature with ?? wildcards, e.g. '48 8B 05 ?? ?? ?? ?? 48 85 C0'. Scans the main module by default; module='*' scans all readable memory.",
                schema_scan_pattern,
                scan_pattern
            ),
            tool!(
                s,
                "find_value",
                "Search memory for a numeric value (health, ammo, coordinates). Scans all writable memory by default (heap/stack/globals). Matches are remembered for refine_value.",
                schema_find_value,
                find_value
            ),
            tool!(
                s,
                "refine_value",
                "Narrow the addresses from the last find_value by re-reading them: keep those now equal to a new value, or that changed/unchanged/increased/decreased.",
                schema_refine_value,
                refine_value
            ),
            tool!(
                s,
                "resolve_pointer",
                "Resolve a pointer chain: for each offset, read the pointer at the current address and add the offset ([[base]+o1]+o2...). Optionally read a typed value at the final address.",
                schema_resolve_pointer,
                resolve_pointer
            ),
            tool!(
                s,
                "watch_address",
                "Add (or replace) a labeled watch on an address; read_watches reports its value and whether it changed since the last read.",
                schema_watch_address,
                watch_address
            ),
            tool!(
                s,
                "read_watches",
                "Read all watched addresses, sorted by label, with changed flags and previous values. Unreadable watches are reported with an error field.",
                schema_empty,
                read_watches
            ),
            tool!(
                s,
                "remove_watch",
                "Remove a watch by label.",
                schema_remove_watch,
                remove_watch
            ),
            tool!(
                s,
                "get_status",
                "Get explorer status: attached process, pid, bitness, liveness, watches, scan counts, and platform support.",
                schema_empty,
                get_status
            ),
        ]
    }
}

// ============================================================================
// Helpers
// ============================================================================

/// Deserialize tool arguments into `T`; absent/null arguments mean `{}`.
fn parse_args<T: DeserializeOwned>(args: Value) -> Result<T> {
    let args = if args.is_null() { json!({}) } else { args };
    serde_json::from_value(args).map_err(|e| MCPError::InvalidParameters(e.to_string()))
}

/// Successful result: `{"success": true, ...fields}`.
fn ok(mut body: Value) -> Result<ToolResult> {
    if let Value::Object(map) = &mut body {
        map.insert("success".into(), Value::Bool(true));
    }
    ToolResult::json(&body)
}

/// Failed result: `{"success": false, "error": ...}` with `isError` set.
fn fail(err: impl std::fmt::Display) -> Result<ToolResult> {
    let mut r = ToolResult::json(&json!({"success": false, "error": err.to_string()}))?;
    r.is_error = true;
    Ok(r)
}

/// Run `f` against the explorer on the blocking thread pool.
async fn run<R, F>(state: &SharedExplorer, f: F) -> Result<R>
where
    R: Send + 'static,
    F: FnOnce(&mut MemoryExplorer) -> R + Send + 'static,
{
    let mut guard = state.clone().lock_owned().await;
    tokio::task::spawn_blocking(move || f(&mut guard))
        .await
        .map_err(|e| MCPError::Internal(format!("explorer task failed: {}", e)))
}

/// Convert a result into a tool response, mapping `Err` to [`fail`].
fn respond<T>(
    r: std::result::Result<T, impl std::fmt::Display>,
    f: impl FnOnce(T) -> Value,
) -> Result<ToolResult> {
    match r {
        Ok(v) => ok(f(v)),
        Err(e) => fail(e),
    }
}

fn clamp_results(v: Option<u64>, default: u64) -> usize {
    v.unwrap_or(default).clamp(1, MAX_RESULTS_CAP) as usize
}

fn scan_timeout(secs: Option<u64>) -> Duration {
    secs.map(Duration::from_secs)
        .unwrap_or(DEFAULT_SCAN_TIMEOUT)
        .clamp(Duration::from_secs(1), MAX_SCAN_TIMEOUT)
}

/// Lenient deserializers: LLM clients often send numbers as strings and
/// addresses as integers.
mod de {
    use serde::{Deserialize, Deserializer, de::Error};
    use serde_json::Value;

    /// Optional unsigned integer from a JSON number or a decimal/`0x` string.
    pub fn opt_u64<'de, D: Deserializer<'de>>(d: D) -> Result<Option<u64>, D::Error> {
        match Option::<Value>::deserialize(d)? {
            None | Some(Value::Null) => Ok(None),
            Some(Value::Number(n)) => n.as_u64().map(Some).ok_or_else(|| {
                D::Error::custom(format!("expected a non-negative integer, got {}", n))
            }),
            Some(Value::String(s)) => crate::address::parse_unsigned(&s)
                .map(Some)
                .map_err(D::Error::custom),
            Some(other) => Err(D::Error::custom(format!(
                "expected an integer, got {}",
                other
            ))),
        }
    }

    /// Address expression from a string or a JSON integer.
    pub fn address<'de, D: Deserializer<'de>>(d: D) -> Result<String, D::Error> {
        match Value::deserialize(d)? {
            Value::String(s) => Ok(s),
            Value::Number(n) if n.as_u64().is_some() => Ok(n.to_string()),
            other => Err(D::Error::custom(format!(
                "expected an address string like '0x7FF6A1B2C3D4' or 'Module.exe+0x10', got {}",
                other
            ))),
        }
    }
}

/// Parse `offsets` entries: integers or strings like `"0x10"` / `"-0x8"`.
fn parse_offsets(raw: &[Value]) -> std::result::Result<Vec<i64>, String> {
    raw.iter()
        .enumerate()
        .map(|(i, v)| match v {
            Value::Number(n) => n
                .as_i64()
                .ok_or_else(|| format!("offsets[{}]: {} is not a 64-bit integer", i, n)),
            Value::String(s) => {
                address::parse_offset(s).map_err(|e| format!("offsets[{}]: {}", i, e))
            },
            other => Err(format!(
                "offsets[{}]: expected integer or hex string, got {}",
                i, other
            )),
        })
        .collect()
}

fn hex(v: u64) -> String {
    format!("{:#x}", v)
}

// ============================================================================
// Schemas
// ============================================================================

fn schema_empty() -> Value {
    json!({"type": "object", "properties": {}})
}

fn schema_list_processes() -> Value {
    json!({
        "type": "object",
        "properties": {
            "filter": {"type": "string", "description": "Case-insensitive substring of the process name (e.g. 'NMS' for No Man's Sky)"}
        }
    })
}

fn schema_attach() -> Value {
    json!({
        "type": "object",
        "properties": {
            "process_name": {"type": "string", "description": "Process name, e.g. 'NMS.exe' (case-insensitive, '.exe' optional)"},
            "pid": {"type": "integer", "description": "Optional: exact process id when several processes share the name"}
        },
        "required": ["process_name"]
    })
}

fn schema_get_modules() -> Value {
    json!({
        "type": "object",
        "properties": {
            "filter": {"type": "string", "description": "Optional case-insensitive substring of the module name"}
        }
    })
}

fn schema_get_memory_regions() -> Value {
    json!({
        "type": "object",
        "properties": {
            "module": {"type": "string", "description": "Only regions overlapping this module's image"},
            "writable_only": {"type": "boolean", "default": false},
            "executable_only": {"type": "boolean", "default": false},
            "limit": {"type": "integer", "default": 200, "description": "Maximum regions returned (1-10000)"}
        }
    })
}

fn schema_read_memory() -> Value {
    json!({
        "type": "object",
        "properties": {
            "address": {"type": "string", "description": "Address: '0x7FF6A1B2C3D4', decimal, 'NMS.exe', 'NMS.exe+0x1234' or 'NMS.exe-0x10'"},
            "type": {"type": "string", "enum": VALUE_TYPE_NAMES, "default": "bytes", "description": "How to decode the data (pointer width follows the target's bitness)"},
            "size": {"type": "integer", "default": 64, "description": format!("Bytes to read for bytes/string/wstring (1-{}); ignored for fixed-size types", MAX_READ_SIZE)}
        },
        "required": ["address"]
    })
}

fn schema_dump_memory() -> Value {
    json!({
        "type": "object",
        "properties": {
            "address": {"type": "string", "description": "Start address (same forms as read_memory)"},
            "size": {"type": "integer", "default": 256, "description": format!("Bytes to dump (1-{})", MAX_READ_SIZE)}
        },
        "required": ["address"]
    })
}

fn schema_scan_pattern() -> Value {
    json!({
        "type": "object",
        "properties": {
            "pattern": {"type": "string", "description": "Hex bytes with ?? wildcards, e.g. '48 8B 05 ?? ?? ?? ??' (at least one literal byte)"},
            "module": {"type": "string", "description": "Module to scan (default: main executable); '*' scans all readable memory"},
            "return_all": {"type": "boolean", "default": false, "description": "Return up to max_results matches instead of just the first"},
            "max_results": {"type": "integer", "default": 20, "description": "Maximum matches when return_all is true (1-10000)"},
            "timeout_secs": {"type": "integer", "default": 30, "description": "Scan time budget in seconds (1-300); partial results are returned with timed_out=true"}
        },
        "required": ["pattern"]
    })
}

fn schema_find_value() -> Value {
    json!({
        "type": "object",
        "properties": {
            "value": {"type": ["number", "string"], "description": "Value to find. Strings allow exact 64-bit integers and hex (e.g. '0x7FF6A1B2C3D4' for pointer searches)"},
            "type": {"type": "string", "enum": SCALAR_TYPE_NAMES, "default": "float"},
            "module": {"type": "string", "description": "Limit to one module's image; '*' = all readable memory. Default: all writable memory"},
            "tolerance": {"type": "number", "description": "float/double only: match values within +/- tolerance (default exact)"},
            "aligned": {"type": "boolean", "default": true, "description": "Only check addresses aligned to the value size (much faster; values are almost always aligned)"},
            "max_results": {"type": "integer", "default": 50, "description": "Matches returned (1-10000). Up to 100000 are kept for refine_value"},
            "timeout_secs": {"type": "integer", "default": 30, "description": "Scan time budget in seconds (1-300)"}
        },
        "required": ["value"]
    })
}

fn schema_refine_value() -> Value {
    json!({
        "type": "object",
        "properties": {
            "mode": {"type": "string", "enum": ["equal", "changed", "unchanged", "increased", "decreased"], "default": "equal"},
            "value": {"type": ["number", "string"], "description": "New value (required for mode 'equal')"},
            "tolerance": {"type": "number", "description": "float/double only: tolerance for mode 'equal'"},
            "max_results": {"type": "integer", "default": 50, "description": "Matches returned (1-10000)"}
        }
    })
}

fn schema_resolve_pointer() -> Value {
    json!({
        "type": "object",
        "properties": {
            "base": {"type": "string", "description": "Address holding the first pointer, e.g. 'NMS.exe+0x3A1B2C0' or '0x7FF6A1B2C3D4'"},
            "offsets": {
                "type": "array",
                "items": {"type": ["integer", "string"]},
                "description": "Offsets applied after each dereference; integers or strings like '0x10' / '-0x8'"
            },
            "type": {"type": "string", "enum": VALUE_TYPE_NAMES, "description": "Optional: also read a value of this type at the final address"},
            "size": {"type": "integer", "description": "Size for bytes/string/wstring reads (default 64)"}
        },
        "required": ["base", "offsets"]
    })
}

fn schema_watch_address() -> Value {
    json!({
        "type": "object",
        "properties": {
            "label": {"type": "string", "description": "Name for this watch, e.g. 'player_health' (1-128 chars)"},
            "address": {"type": "string", "description": "Address (same forms as read_memory); must be readable now"},
            "type": {"type": "string", "enum": VALUE_TYPE_NAMES, "default": "float"},
            "size": {"type": "integer", "description": "Bytes for bytes/string/wstring watches (default 16/64/128, max 4096); ignored for fixed-size types"}
        },
        "required": ["label", "address"]
    })
}

fn schema_remove_watch() -> Value {
    json!({
        "type": "object",
        "properties": {
            "label": {"type": "string", "description": "Watch label to remove"}
        },
        "required": ["label"]
    })
}

// ============================================================================
// Handlers
// ============================================================================

#[derive(Deserialize)]
struct FilterArgs {
    filter: Option<String>,
}

async fn list_processes(_state: SharedExplorer, args: Value) -> Result<ToolResult> {
    let a: FilterArgs = parse_args(args)?;
    let procs = tokio::task::spawn_blocking(move || explorer::list_processes(a.filter.as_deref()))
        .await
        .map_err(|e| MCPError::Internal(format!("process listing failed: {}", e)))?;
    ok(json!({"count": procs.len(), "processes": procs}))
}

#[derive(Deserialize)]
struct AttachArgs {
    process_name: String,
    #[serde(default, deserialize_with = "de::opt_u64")]
    pid: Option<u64>,
}

async fn attach_process(state: SharedExplorer, args: Value) -> Result<ToolResult> {
    let a: AttachArgs = parse_args(args)?;
    let pid = match a.pid.map(u32::try_from).transpose() {
        Ok(p) => p,
        Err(_) => return Err(MCPError::InvalidParameters("pid is out of range".into())),
    };
    info!("Attaching to process: {} (pid {:?})", a.process_name, pid);
    let r = run(&state, move |e| e.attach(&a.process_name, pid)).await?;
    respond(r, |result| json!({"result": result}))
}

async fn detach_process(state: SharedExplorer, _args: Value) -> Result<ToolResult> {
    let was_attached = run(&state, |e| e.detach()).await?;
    ok(json!({"detached": true, "was_attached": was_attached}))
}

async fn get_modules(state: SharedExplorer, args: Value) -> Result<ToolResult> {
    let a: FilterArgs = parse_args(args)?;
    let r = run(&state, |e| e.modules()).await?;
    let filter = a.filter.map(|f| f.to_lowercase());
    respond(r, |modules| {
        let formatted: Vec<Value> = modules
            .iter()
            .filter(|m| {
                filter
                    .as_deref()
                    .is_none_or(|f| m.name.to_lowercase().contains(f))
            })
            .map(|m| {
                json!({
                    "name": m.name,
                    "base_address": hex(m.base_address),
                    "end_address": hex(m.end()),
                    "size": m.size,
                    "size_mb": (m.size as f64 / 1024.0 / 1024.0 * 100.0).round() / 100.0,
                    "path": m.path
                })
            })
            .collect();
        json!({"count": formatted.len(), "total_modules": modules.len(), "modules": formatted})
    })
}

#[derive(Deserialize)]
struct RegionArgs {
    module: Option<String>,
    #[serde(default)]
    writable_only: bool,
    #[serde(default)]
    executable_only: bool,
    #[serde(default, deserialize_with = "de::opt_u64")]
    limit: Option<u64>,
}

async fn get_memory_regions(state: SharedExplorer, args: Value) -> Result<ToolResult> {
    let a: RegionArgs = parse_args(args)?;
    let limit = clamp_results(a.limit, 200);
    let r = run(&state, move |e| {
        e.regions(a.module.as_deref(), a.writable_only, a.executable_only)
    })
    .await?;
    respond(r, |regions| {
        let total = regions.len();
        let rows: Vec<Value> = regions
            .into_iter()
            .take(limit)
            .map(|(r, module)| {
                json!({
                    "base": hex(r.base),
                    "end": hex(r.end()),
                    "size": r.size,
                    "readable": r.readable,
                    "writable": r.writable,
                    "executable": r.executable,
                    "kind": r.kind,
                    "module": module
                })
            })
            .collect();
        json!({"count": rows.len(), "total": total, "truncated": total > rows.len(), "regions": rows})
    })
}

#[derive(Deserialize)]
struct ReadArgs {
    #[serde(deserialize_with = "de::address")]
    address: String,
    #[serde(rename = "type", default)]
    value_type: ValueType,
    #[serde(default, deserialize_with = "de::opt_u64")]
    size: Option<u64>,
}

async fn read_memory(state: SharedExplorer, args: Value) -> Result<ToolResult> {
    let a: ReadArgs = parse_args(args)?;
    let size = a.size.unwrap_or(64).min(usize::MAX as u64) as usize;
    let r = run(&state, move |e| {
        let addr = e.parse_address(&a.address)?;
        e.read_value(addr, a.value_type, size)
    })
    .await?;
    respond(r, |data| json!({"data": data}))
}

#[derive(Deserialize)]
struct DumpArgs {
    #[serde(deserialize_with = "de::address")]
    address: String,
    #[serde(default, deserialize_with = "de::opt_u64")]
    size: Option<u64>,
}

async fn dump_memory(state: SharedExplorer, args: Value) -> Result<ToolResult> {
    let a: DumpArgs = parse_args(args)?;
    let size = a.size.unwrap_or(256).min(usize::MAX as u64) as usize;
    let r = run(&state, move |e| {
        let addr = e.parse_address(&a.address)?;
        e.dump_memory(addr, size)
    })
    .await?;
    respond(r, |dump| json!({"dump": dump}))
}

#[derive(Deserialize)]
struct ScanArgs {
    pattern: String,
    module: Option<String>,
    #[serde(default)]
    return_all: bool,
    #[serde(default, deserialize_with = "de::opt_u64")]
    max_results: Option<u64>,
    #[serde(default, deserialize_with = "de::opt_u64")]
    timeout_secs: Option<u64>,
}

async fn scan_pattern(state: SharedExplorer, args: Value) -> Result<ToolResult> {
    let a: ScanArgs = parse_args(args)?;
    let max = if a.return_all {
        clamp_results(a.max_results, 20)
    } else {
        1
    };
    let timeout = scan_timeout(a.timeout_secs);
    let scope = ScanScope::from_module_arg(a.module.as_deref(), ScanScope::MainModule);
    let pattern_text = a.pattern.clone();
    let r = run(&state, move |e| {
        e.scan_pattern(&a.pattern, scope, max, timeout)
    })
    .await?;
    respond(r, |o| {
        json!({
            "pattern": pattern_text,
            "scope": o.scope,
            "count": o.results.len(),
            "results": o.results,
            "truncated": o.truncated,
            "timed_out": o.timed_out,
            "bytes_scanned": o.bytes_scanned,
            "regions_scanned": o.regions_scanned,
            "elapsed_ms": o.elapsed_ms
        })
    })
}

#[derive(Deserialize)]
struct FindArgs {
    value: Value,
    #[serde(rename = "type", default = "default_float")]
    value_type: ValueType,
    module: Option<String>,
    tolerance: Option<f64>,
    #[serde(default = "default_true")]
    aligned: bool,
    #[serde(default, deserialize_with = "de::opt_u64")]
    max_results: Option<u64>,
    #[serde(default, deserialize_with = "de::opt_u64")]
    timeout_secs: Option<u64>,
}

fn default_float() -> ValueType {
    ValueType::Float
}

fn default_true() -> bool {
    true
}

async fn find_value(state: SharedExplorer, args: Value) -> Result<ToolResult> {
    let a: FindArgs = parse_args(args)?;
    if a.value.is_null() {
        return Err(MCPError::InvalidParameters(
            "Missing 'value' parameter".into(),
        ));
    }
    let max = clamp_results(a.max_results, 50);
    let timeout = scan_timeout(a.timeout_secs);
    let scope = ScanScope::from_module_arg(
        a.module.as_deref(),
        ScanScope::AllMemory {
            writable_only: true,
        },
    );
    let (value, vt) = (a.value.clone(), a.value_type);
    let r = run(&state, move |e| {
        e.find_value(
            a.value_type,
            &a.value,
            a.tolerance,
            scope,
            max,
            a.aligned,
            timeout,
        )
    })
    .await?;
    respond(r, |o| {
        let results: Vec<Value> = o
            .results
            .iter()
            .map(|h| {
                json!({
                    "address": hex(h.address),
                    "module": h.module,
                    "module_offset": h.module_offset,
                    "value": value,
                    "type": vt
                })
            })
            .collect();
        json!({
            "value": value,
            "type": vt,
            "scope": o.scope,
            "count": results.len(),
            "total_found": o.total_found,
            "results": results,
            "candidates_truncated": o.truncated,
            "timed_out": o.timed_out,
            "bytes_scanned": o.bytes_scanned,
            "regions_scanned": o.regions_scanned,
            "elapsed_ms": o.elapsed_ms,
            "hint": "Change the value in the target, then call refine_value to narrow these candidates."
        })
    })
}

#[derive(Deserialize)]
struct RefineArgs {
    mode: Option<String>,
    value: Option<Value>,
    tolerance: Option<f64>,
    #[serde(default, deserialize_with = "de::opt_u64")]
    max_results: Option<u64>,
}

async fn refine_value(state: SharedExplorer, args: Value) -> Result<ToolResult> {
    let a: RefineArgs = parse_args(args)?;
    let mode = match a
        .mode
        .as_deref()
        .unwrap_or("equal")
        .to_ascii_lowercase()
        .as_str()
    {
        "equal" | "exact" | "eq" => match a.value {
            Some(v) if !v.is_null() => RefineMode::Equal {
                value: v,
                tolerance: a.tolerance,
            },
            _ => {
                return Err(MCPError::InvalidParameters(
                    "mode 'equal' requires 'value'".into(),
                ));
            },
        },
        "changed" => RefineMode::Changed,
        "unchanged" => RefineMode::Unchanged,
        "increased" => RefineMode::Increased,
        "decreased" => RefineMode::Decreased,
        other => {
            return Err(MCPError::InvalidParameters(format!(
                "unknown mode '{}'; use equal, changed, unchanged, increased or decreased",
                other
            )));
        },
    };
    let max = clamp_results(a.max_results, 50);
    let r = run(&state, move |e| e.refine_value(mode, max)).await?;
    respond(r, |o| {
        json!({
            "before": o.before,
            "remaining": o.remaining,
            "type": o.value_type,
            "count": o.results.len(),
            "results": o.results
        })
    })
}

#[derive(Deserialize)]
struct PointerArgs {
    #[serde(deserialize_with = "de::address")]
    base: String,
    offsets: Vec<Value>,
    #[serde(rename = "type")]
    value_type: Option<ValueType>,
    #[serde(default, deserialize_with = "de::opt_u64")]
    size: Option<u64>,
}

async fn resolve_pointer(state: SharedExplorer, args: Value) -> Result<ToolResult> {
    let a: PointerArgs = parse_args(args)?;
    let offsets = parse_offsets(&a.offsets).map_err(MCPError::InvalidParameters)?;
    let size = a.size.unwrap_or(64).min(usize::MAX as u64) as usize;
    let r = run(&state, move |e| {
        let base = e.parse_address(&a.base)?;
        let chain = e.resolve_pointer_chain(base, &offsets)?;
        let value = match a.value_type {
            Some(t) => Some(e.read_value(chain.final_address, t, size)),
            None => None,
        };
        Ok::<_, explorer::ExplorerError>((chain, value))
    })
    .await?;
    respond(r, |(chain, value)| {
        let mut steps = vec![hex(chain.base_address)];
        steps.extend(chain.steps.iter().map(|s| hex(s.result)));
        let mut body = json!({
            "base": hex(chain.base_address),
            "offsets": chain.offsets.iter().map(|o| {
                if *o < 0 { format!("-{:#x}", o.unsigned_abs()) } else { format!("{:#x}", o) }
            }).collect::<Vec<_>>(),
            "final_address": hex(chain.final_address),
            "steps": steps,
            "chain": chain.steps.iter().map(|s| json!({
                "read_from": hex(s.read_from),
                "pointer": hex(s.pointer),
                "offset": s.offset,
                "result": hex(s.result)
            })).collect::<Vec<_>>()
        });
        match value {
            Some(Ok(v)) => body["value"] = v,
            Some(Err(e)) => body["value_error"] = json!(e.to_string()),
            None => {},
        }
        body
    })
}

#[derive(Deserialize)]
struct WatchArgs {
    label: String,
    #[serde(deserialize_with = "de::address")]
    address: String,
    #[serde(rename = "type", default = "default_float")]
    value_type: ValueType,
    #[serde(default, deserialize_with = "de::opt_u64")]
    size: Option<u64>,
}

async fn watch_address(state: SharedExplorer, args: Value) -> Result<ToolResult> {
    let a: WatchArgs = parse_args(args)?;
    let size = a.size.map(|s| s.min(usize::MAX as u64) as usize);
    let r = run(&state, move |e| {
        let addr = e.parse_address(&a.address)?;
        e.add_watch(&a.label, addr, a.value_type, size)
    })
    .await?;
    respond(r, |watch| json!({"watch": watch}))
}

async fn read_watches(state: SharedExplorer, _args: Value) -> Result<ToolResult> {
    let r = run(&state, |e| e.read_all_watches()).await?;
    respond(
        r,
        |watches| json!({"count": watches.len(), "watches": watches}),
    )
}

#[derive(Deserialize)]
struct LabelArgs {
    label: String,
}

async fn remove_watch(state: SharedExplorer, args: Value) -> Result<ToolResult> {
    let a: LabelArgs = parse_args(args)?;
    let label = a.label.clone();
    let r = run(&state, move |e| e.remove_watch(&a.label)).await?;
    respond(r, |()| json!({"removed": label}))
}

async fn get_status(state: SharedExplorer, _args: Value) -> Result<ToolResult> {
    let status = run(&state, |e| e.status()).await?;
    ok(json!({"status": status}))
}

// ============================================================================
// Tests
// ============================================================================

#[cfg(test)]
mod tests {
    use super::*;
    use crate::backend::mock::MockMemory;
    use mcp_core::Content;

    const HEAP: u64 = 0x2000_0000;

    fn body(r: &ToolResult) -> Value {
        match &r.content[0] {
            Content::Text { text } => serde_json::from_str(text).unwrap(),
            _ => panic!("expected text content"),
        }
    }

    fn tool(server: &MemoryExplorerServer, name: &str) -> BoxedTool {
        server
            .tools()
            .into_iter()
            .find(|t| t.name() == name)
            .unwrap_or_else(|| panic!("no tool {}", name))
    }

    async fn call(server: &MemoryExplorerServer, name: &str, args: Value) -> (bool, Value) {
        let r = tool(server, name).execute(args).await.unwrap();
        (r.is_error, body(&r))
    }

    fn mock_server() -> (MemoryExplorerServer, Arc<MockMemory>) {
        let mut heap = vec![0u8; 0x1000];
        heap[0x10..0x14].copy_from_slice(&100.0f32.to_le_bytes());
        heap[0x20..0x28].copy_from_slice(&(HEAP + 0x40).to_le_bytes());
        heap[0x48..0x4c].copy_from_slice(&7i32.to_le_bytes());
        let mut image = vec![0u8; 0x1000];
        image[0x10..0x14].copy_from_slice(&[0xDE, 0xAD, 0xBE, 0xEF]);
        let mem = Arc::new(
            MockMemory::new()
                .with_module("Game.exe", 0x1_4000_0000, 0x1000)
                .with_region_rw(0x1_4000_0000, image, false)
                .with_region(HEAP, heap),
        );
        let mut e = MemoryExplorer::new();
        e.attach_backend(Box::new(mem.clone()), "Game.exe").unwrap();
        (MemoryExplorerServer::with_explorer(e), mem)
    }

    #[test]
    fn tool_names_are_stable() {
        let server = MemoryExplorerServer::new();
        let names: Vec<String> = server
            .tools()
            .iter()
            .map(|t| t.name().to_string())
            .collect();
        for n in [
            "list_processes",
            "attach_process",
            "detach_process",
            "get_modules",
            "read_memory",
            "dump_memory",
            "scan_pattern",
            "find_value",
            "resolve_pointer",
            "watch_address",
            "read_watches",
            "remove_watch",
            "get_status",
            "refine_value",
            "get_memory_regions",
        ] {
            assert!(names.iter().any(|x| x == n), "missing tool {}", n);
        }
        assert_eq!(names.len(), 15);
    }

    #[test]
    fn schemas_keep_required_params() {
        let server = MemoryExplorerServer::new();
        let required = |name: &str| -> Vec<String> {
            tool(&server, name).schema()["required"]
                .as_array()
                .map(|a| a.iter().map(|v| v.as_str().unwrap().to_string()).collect())
                .unwrap_or_default()
        };
        assert_eq!(required("attach_process"), ["process_name"]);
        assert_eq!(required("read_memory"), ["address"]);
        assert_eq!(required("dump_memory"), ["address"]);
        assert_eq!(required("scan_pattern"), ["pattern"]);
        assert_eq!(required("find_value"), ["value"]);
        assert_eq!(required("resolve_pointer"), ["base", "offsets"]);
        assert_eq!(required("watch_address"), ["label", "address"]);
        assert_eq!(required("remove_watch"), ["label"]);
        for t in server.tools() {
            assert_eq!(t.schema()["type"], "object", "{}", t.name());
        }
    }

    #[tokio::test]
    async fn bad_arguments_are_invalid_parameters_not_panics() {
        let server = MemoryExplorerServer::new();
        for (name, args) in [
            ("attach_process", json!({})),
            ("attach_process", json!({"process_name": 5})),
            (
                "read_memory",
                json!({"address": "0x10", "type": "quaternion"}),
            ),
            ("read_memory", json!({"address": true})),
            ("dump_memory", json!({"address": "0x10", "size": -1})),
            ("find_value", json!({})),
            (
                "resolve_pointer",
                json!({"base": "0x10", "offsets": ["zz"]}),
            ),
            ("refine_value", json!({"mode": "sideways"})),
            ("refine_value", json!({"mode": "equal"})),
            ("remove_watch", json!(null)),
        ] {
            let err = tool(&server, name).execute(args.clone()).await.unwrap_err();
            assert!(
                matches!(err, MCPError::InvalidParameters(_)),
                "{} {}: {:?}",
                name,
                args,
                err
            );
        }
    }

    #[tokio::test]
    async fn not_attached_is_a_tool_error() {
        let server = MemoryExplorerServer::new();
        let (is_err, b) = call(&server, "read_memory", json!({"address": "0x1000"})).await;
        assert!(is_err);
        assert_eq!(b["success"], json!(false));
        assert!(b["error"].as_str().unwrap().contains("Not attached"));

        let (is_err, b) = call(&server, "get_status", json!({})).await;
        assert!(!is_err);
        assert_eq!(b["status"]["attached"], json!(false));
    }

    #[tokio::test]
    async fn list_processes_works_everywhere() {
        let server = MemoryExplorerServer::new();
        let (is_err, b) = call(&server, "list_processes", json!({})).await;
        assert!(!is_err);
        assert!(b["count"].as_u64().unwrap() > 0);
    }

    #[tokio::test]
    async fn attach_unknown_process_fails_cleanly() {
        let server = MemoryExplorerServer::new();
        let (is_err, b) = call(
            &server,
            "attach_process",
            json!({"process_name": "no-such-process-xyz.exe"}),
        )
        .await;
        assert!(is_err);
        assert!(b["error"].as_str().unwrap().contains("Process not found"));
    }

    #[tokio::test]
    async fn read_and_dump_through_tools() {
        let (server, _) = mock_server();
        let (_, b) = call(
            &server,
            "read_memory",
            json!({"address": format!("{:#x}", HEAP + 0x10), "type": "float"}),
        )
        .await;
        assert_eq!(b["data"]["value"], json!(100.0));

        // Numeric address and string size are accepted.
        let (_, b) = call(
            &server,
            "read_memory",
            json!({"address": HEAP + 0x48, "type": "int32"}),
        )
        .await;
        assert_eq!(b["data"]["value"], json!(7));
        let (_, b) = call(
            &server,
            "read_memory",
            json!({"address": "Game.exe+0x10", "size": "4"}),
        )
        .await;
        assert_eq!(b["data"]["hex"], json!("deadbeef"));

        let (is_err, b) = call(
            &server,
            "dump_memory",
            json!({"address": format!("{:#x}", HEAP + 0xff0), "size": 64}),
        )
        .await;
        assert!(!is_err);
        assert_eq!(b["dump"]["truncated"], json!(true));
        assert_eq!(b["dump"]["size"], json!(16));

        let (is_err, _) = call(
            &server,
            "dump_memory",
            json!({"address": "0x0", "size": 1_000_000}),
        )
        .await;
        assert!(is_err);
    }

    #[tokio::test]
    async fn scan_find_refine_pointer_and_watch_workflow() {
        let (server, mem) = mock_server();

        let (_, b) = call(&server, "scan_pattern", json!({"pattern": "DE AD ?? EF"})).await;
        assert_eq!(b["count"], json!(1));
        assert_eq!(b["results"][0]["module_offset"], json!("Game.exe+0x10"));

        let (is_err, b) = call(&server, "scan_pattern", json!({"pattern": "?? ??"})).await;
        assert!(is_err, "{b}");

        let (_, b) = call(
            &server,
            "find_value",
            json!({"value": 100, "type": "float"}),
        )
        .await;
        assert_eq!(b["total_found"], json!(1));
        assert_eq!(
            b["results"][0]["address"],
            json!(format!("{:#x}", HEAP + 0x10))
        );

        mem.poke(HEAP + 0x10, &80.0f32.to_le_bytes());
        let (_, b) = call(&server, "refine_value", json!({"mode": "decreased"})).await;
        assert_eq!(b["remaining"], json!(1));
        assert_eq!(b["results"][0]["value"], json!(80.0));

        let (_, b) = call(
            &server,
            "resolve_pointer",
            json!({"base": format!("{:#x}", HEAP + 0x20), "offsets": ["0x8"], "type": "int32"}),
        )
        .await;
        assert_eq!(b["final_address"], json!(format!("{:#x}", HEAP + 0x48)));
        assert_eq!(b["value"]["value"], json!(7));
        assert_eq!(b["steps"].as_array().unwrap().len(), 2);

        let (_, b) = call(
            &server,
            "watch_address",
            json!({"label": "hp", "address": format!("{:#x}", HEAP + 0x10)}),
        )
        .await;
        assert_eq!(b["watch"]["value"], json!(80.0));
        mem.poke(HEAP + 0x10, &60.0f32.to_le_bytes());
        let (_, b) = call(&server, "read_watches", json!({})).await;
        assert_eq!(b["watches"][0]["changed"], json!(true));
        assert_eq!(b["watches"][0]["previous_value"], json!(80.0));

        let (is_err, _) = call(&server, "remove_watch", json!({"label": "hp"})).await;
        assert!(!is_err);
        let (is_err, _) = call(&server, "remove_watch", json!({"label": "hp"})).await;
        assert!(is_err);

        let (_, b) = call(
            &server,
            "get_memory_regions",
            json!({"writable_only": true}),
        )
        .await;
        assert_eq!(b["count"], json!(1));

        let (_, b) = call(&server, "get_modules", json!({"filter": "game"})).await;
        assert_eq!(b["count"], json!(1));
        assert_eq!(b["modules"][0]["base_address"], json!("0x140000000"));

        let (_, b) = call(&server, "detach_process", json!({})).await;
        assert_eq!(b["was_attached"], json!(true));
        let (is_err, _) = call(&server, "read_watches", json!({})).await;
        assert!(is_err);
    }

    #[test]
    fn offsets_parse() {
        assert_eq!(
            parse_offsets(&[json!(16), json!("0x10"), json!("-0x8")]).unwrap(),
            vec![16, 16, -8]
        );
        assert!(parse_offsets(&[json!(1.5)]).is_err());
        assert!(parse_offsets(&[json!(null)]).is_err());
    }

    #[test]
    fn limits_are_clamped() {
        assert_eq!(clamp_results(Some(0), 20), 1);
        assert_eq!(clamp_results(Some(1_000_000), 20), MAX_RESULTS_CAP as usize);
        assert_eq!(clamp_results(None, 20), 20);
        assert_eq!(scan_timeout(Some(0)), Duration::from_secs(1));
        assert_eq!(scan_timeout(Some(100_000)), MAX_SCAN_TIMEOUT);
        assert_eq!(scan_timeout(None), DEFAULT_SCAN_TIMEOUT);
    }
}
