//! MCP server implementation for memory exploration.

use async_trait::async_trait;
use mcp_core::prelude::*;
use serde_json::{Value, json};
use std::sync::Arc;
use tokio::sync::RwLock;
use tracing::info;

use crate::explorer::MemoryExplorer;
use crate::types::ValueType;

/// Memory explorer MCP server.
pub struct MemoryExplorerServer {
    explorer: Arc<RwLock<MemoryExplorer>>,
}

impl MemoryExplorerServer {
    /// Create a new memory explorer server.
    pub fn new() -> Self {
        Self {
            explorer: Arc::new(RwLock::new(MemoryExplorer::new())),
        }
    }

    /// Get all tools as boxed trait objects.
    pub fn tools(&self) -> Vec<BoxedTool> {
        vec![
            Arc::new(ListProcessesTool {
                server: self.clone_refs(),
            }),
            Arc::new(AttachProcessTool {
                server: self.clone_refs(),
            }),
            Arc::new(DetachProcessTool {
                server: self.clone_refs(),
            }),
            Arc::new(GetModulesTool {
                server: self.clone_refs(),
            }),
            Arc::new(ReadMemoryTool {
                server: self.clone_refs(),
            }),
            Arc::new(DumpMemoryTool {
                server: self.clone_refs(),
            }),
            Arc::new(ScanPatternTool {
                server: self.clone_refs(),
            }),
            Arc::new(FindValueTool {
                server: self.clone_refs(),
            }),
            Arc::new(ResolvePointerTool {
                server: self.clone_refs(),
            }),
            Arc::new(WatchAddressTool {
                server: self.clone_refs(),
            }),
            Arc::new(ReadWatchesTool {
                server: self.clone_refs(),
            }),
            Arc::new(RemoveWatchTool {
                server: self.clone_refs(),
            }),
            Arc::new(GetStatusTool {
                server: self.clone_refs(),
            }),
        ]
    }

    /// Clone the Arc references for tools.
    fn clone_refs(&self) -> ServerRefs {
        ServerRefs {
            explorer: self.explorer.clone(),
        }
    }
}

impl Default for MemoryExplorerServer {
    fn default() -> Self {
        Self::new()
    }
}

/// Shared references for tools.
#[derive(Clone)]
struct ServerRefs {
    explorer: Arc<RwLock<MemoryExplorer>>,
}

// ============================================================================
// Tool: list_processes
// ============================================================================

struct ListProcessesTool {
    server: ServerRefs,
}

#[async_trait]
impl Tool for ListProcessesTool {
    fn name(&self) -> &str {
        "list_processes"
    }

    fn description(&self) -> &str {
        "List running processes. Optionally filter by name substring."
    }

    fn schema(&self) -> Value {
        json!({
            "type": "object",
            "properties": {
                "filter": {
                    "type": "string",
                    "description": "Optional filter substring for process names (e.g., 'NMS' to find No Man's Sky)"
                }
            }
        })
    }

    async fn execute(&self, args: Value) -> Result<ToolResult> {
        let filter = args.get("filter").and_then(|v| v.as_str());

        let explorer = self.server.explorer.read().await;
        let processes = explorer.list_processes(filter);

        ToolResult::json(&json!({
            "success": true,
            "count": processes.len(),
            "processes": processes
        }))
    }
}

// ============================================================================
// Tool: attach_process
// ============================================================================

struct AttachProcessTool {
    server: ServerRefs,
}

#[async_trait]
impl Tool for AttachProcessTool {
    fn name(&self) -> &str {
        "attach_process"
    }

    fn description(&self) -> &str {
        "Attach to a process by name. Required before any memory operations."
    }

    fn schema(&self) -> Value {
        json!({
            "type": "object",
            "properties": {
                "process_name": {
                    "type": "string",
                    "description": "Process name (e.g., 'NMS.exe')"
                }
            },
            "required": ["process_name"]
        })
    }

    async fn execute(&self, args: Value) -> Result<ToolResult> {
        let process_name = args
            .get("process_name")
            .and_then(|v| v.as_str())
            .ok_or_else(|| {
                MCPError::InvalidParameters("Missing 'process_name' parameter".to_string())
            })?;

        info!("Attaching to process: {}", process_name);

        let mut explorer = self.server.explorer.write().await;
        match explorer.attach(process_name) {
            Ok(result) => ToolResult::json(&json!({
                "success": true,
                "result": result
            })),
            Err(e) => ToolResult::json(&json!({
                "success": false,
                "error": e.to_string()
            })),
        }
    }
}

// ============================================================================
// Tool: detach_process
// ============================================================================

struct DetachProcessTool {
    server: ServerRefs,
}

#[async_trait]
impl Tool for DetachProcessTool {
    fn name(&self) -> &str {
        "detach_process"
    }

    fn description(&self) -> &str {
        "Detach from the currently attached process."
    }

    fn schema(&self) -> Value {
        json!({
            "type": "object",
            "properties": {}
        })
    }

    async fn execute(&self, _args: Value) -> Result<ToolResult> {
        let mut explorer = self.server.explorer.write().await;
        explorer.detach();

        ToolResult::json(&json!({
            "success": true,
            "detached": true
        }))
    }
}

// ============================================================================
// Tool: get_modules
// ============================================================================

struct GetModulesTool {
    server: ServerRefs,
}

#[async_trait]
impl Tool for GetModulesTool {
    fn name(&self) -> &str {
        "get_modules"
    }

    fn description(&self) -> &str {
        "List all loaded modules (DLLs) in the attached process with their base addresses."
    }

    fn schema(&self) -> Value {
        json!({
            "type": "object",
            "properties": {}
        })
    }

    async fn execute(&self, _args: Value) -> Result<ToolResult> {
        let mut explorer = self.server.explorer.write().await;
        match explorer.get_modules() {
            Ok(modules) => {
                let formatted: Vec<Value> = modules
                    .iter()
                    .map(|m| {
                        json!({
                            "name": m.name,
                            "base_address": format!("{:#x}", m.base_address),
                            "size": m.size,
                            "size_mb": (m.size as f64 / 1024.0 / 1024.0 * 100.0).round() / 100.0,
                            "path": m.path
                        })
                    })
                    .collect();

                ToolResult::json(&json!({
                    "success": true,
                    "count": formatted.len(),
                    "modules": formatted
                }))
            }
            Err(e) => ToolResult::json(&json!({
                "success": false,
                "error": e.to_string()
            })),
        }
    }
}

// ============================================================================
// Tool: read_memory
// ============================================================================

struct ReadMemoryTool {
    server: ServerRefs,
}

#[async_trait]
impl Tool for ReadMemoryTool {
    fn name(&self) -> &str {
        "read_memory"
    }

    fn description(&self) -> &str {
        "Read memory at an address. Returns data in various formats based on type parameter."
    }

    fn schema(&self) -> Value {
        json!({
            "type": "object",
            "properties": {
                "address": {
                    "type": "string",
                    "description": "Memory address in hex (e.g., '0x7FF6A1B2C3D4') or decimal, or module+offset (e.g., 'NMS.exe+0x1234')"
                },
                "type": {
                    "type": "string",
                    "enum": ["bytes", "int32", "int64", "uint32", "uint64", "float", "double", "string", "pointer", "vector3", "vector4", "matrix4x4"],
                    "description": "Data type to read",
                    "default": "bytes"
                },
                "size": {
                    "type": "integer",
                    "description": "Number of bytes to read (for 'bytes' and 'string' types)",
                    "default": 64
                }
            },
            "required": ["address"]
        })
    }

    async fn execute(&self, args: Value) -> Result<ToolResult> {
        let address_str = args
            .get("address")
            .and_then(|v| v.as_str())
            .ok_or_else(|| {
                MCPError::InvalidParameters("Missing 'address' parameter".to_string())
            })?;

        let read_type = args.get("type").and_then(|v| v.as_str()).unwrap_or("bytes");

        let size = args
            .get("size")
            .and_then(|v| v.as_u64())
            .map(|v| v as usize)
            .unwrap_or(64);

        let mut explorer = self.server.explorer.write().await;

        let address = match explorer.parse_address(address_str) {
            Ok(a) => a,
            Err(e) => {
                return ToolResult::json(&json!({
                    "success": false,
                    "error": e.to_string()
                }));
            }
        };

        let result: std::result::Result<Value, String> = match read_type {
            "bytes" => explorer
                .read_bytes(address, size)
                .map(|data| {
                    json!({
                        "address": format!("{:#x}", address),
                        "hex": data.iter().map(|b| format!("{:02x}", b)).collect::<String>(),
                        "size": data.len()
                    })
                })
                .map_err(|e| e.to_string()),
            "int32" => explorer
                .read_i32(address)
                .map(|v| json!({"address": format!("{:#x}", address), "value": v}))
                .map_err(|e| e.to_string()),
            "int64" => explorer
                .read_i64(address)
                .map(|v| json!({"address": format!("{:#x}", address), "value": v}))
                .map_err(|e| e.to_string()),
            "uint32" => explorer
                .read_u32(address)
                .map(|v| json!({"address": format!("{:#x}", address), "value": v}))
                .map_err(|e| e.to_string()),
            "uint64" => explorer
                .read_u64(address)
                .map(|v| json!({"address": format!("{:#x}", address), "value": v}))
                .map_err(|e| e.to_string()),
            "float" => explorer
                .read_f32(address)
                .map(|v| json!({"address": format!("{:#x}", address), "value": v}))
                .map_err(|e| e.to_string()),
            "double" => explorer
                .read_f64(address)
                .map(|v| json!({"address": format!("{:#x}", address), "value": v}))
                .map_err(|e| e.to_string()),
            "string" => explorer
                .read_string(address, size)
                .map(|v| json!({"address": format!("{:#x}", address), "value": v}))
                .map_err(|e| e.to_string()),
            "pointer" => explorer
                .read_pointer(address)
                .map(|v| {
                    json!({"address": format!("{:#x}", address), "pointer": format!("{:#x}", v)})
                })
                .map_err(|e| e.to_string()),
            "vector3" => explorer
                .read_vector3(address)
                .map(|v| json!({"address": format!("{:#x}", address), "value": v}))
                .map_err(|e| e.to_string()),
            "vector4" => explorer
                .read_vector4(address)
                .map(|v| json!({"address": format!("{:#x}", address), "value": v}))
                .map_err(|e| e.to_string()),
            "matrix4x4" => explorer
                .read_matrix4x4(address)
                .map(|v| json!({"address": format!("{:#x}", address), "value": v}))
                .map_err(|e| e.to_string()),
            _ => Err(format!("Unknown type: {}", read_type)),
        };

        match result {
            Ok(data) => ToolResult::json(&json!({
                "success": true,
                "data": data
            })),
            Err(e) => ToolResult::json(&json!({
                "success": false,
                "error": e
            })),
        }
    }
}

// ============================================================================
// Tool: dump_memory
// ============================================================================

struct DumpMemoryTool {
    server: ServerRefs,
}

#[async_trait]
impl Tool for DumpMemoryTool {
    fn name(&self) -> &str {
        "dump_memory"
    }

    fn description(&self) -> &str {
        "Dump a region of memory as a hex dump with ASCII representation."
    }

    fn schema(&self) -> Value {
        json!({
            "type": "object",
            "properties": {
                "address": {
                    "type": "string",
                    "description": "Starting address in hex or decimal"
                },
                "size": {
                    "type": "integer",
                    "description": "Number of bytes to dump",
                    "default": 256
                }
            },
            "required": ["address"]
        })
    }

    async fn execute(&self, args: Value) -> Result<ToolResult> {
        let address_str = args
            .get("address")
            .and_then(|v| v.as_str())
            .ok_or_else(|| {
                MCPError::InvalidParameters("Missing 'address' parameter".to_string())
            })?;

        let size = args
            .get("size")
            .and_then(|v| v.as_u64())
            .map(|v| v as usize)
            .unwrap_or(256);

        let mut explorer = self.server.explorer.write().await;

        let address = match explorer.parse_address(address_str) {
            Ok(a) => a,
            Err(e) => {
                return ToolResult::json(&json!({
                    "success": false,
                    "error": e.to_string()
                }));
            }
        };

        match explorer.dump_memory(address, size) {
            Ok(dump) => ToolResult::json(&json!({
                "success": true,
                "dump": dump
            })),
            Err(e) => ToolResult::json(&json!({
                "success": false,
                "error": e.to_string()
            })),
        }
    }
}

// ============================================================================
// Tool: scan_pattern
// ============================================================================

struct ScanPatternTool {
    server: ServerRefs,
}

#[async_trait]
impl Tool for ScanPatternTool {
    fn name(&self) -> &str {
        "scan_pattern"
    }

    fn description(&self) -> &str {
        r#"Scan memory for a byte pattern. Use ?? for wildcard bytes.
Example: '48 8B 05 ?? ?? ?? ?? 48 85 C0'"#
    }

    fn schema(&self) -> Value {
        json!({
            "type": "object",
            "properties": {
                "pattern": {
                    "type": "string",
                    "description": "Byte pattern with optional ?? wildcards"
                },
                "module": {
                    "type": "string",
                    "description": "Optional: limit scan to a specific module"
                },
                "return_all": {
                    "type": "boolean",
                    "description": "Return all matches instead of just the first",
                    "default": false
                },
                "max_results": {
                    "type": "integer",
                    "description": "Maximum number of results",
                    "default": 20
                }
            },
            "required": ["pattern"]
        })
    }

    async fn execute(&self, args: Value) -> Result<ToolResult> {
        let pattern = args
            .get("pattern")
            .and_then(|v| v.as_str())
            .ok_or_else(|| {
                MCPError::InvalidParameters("Missing 'pattern' parameter".to_string())
            })?;

        let module = args.get("module").and_then(|v| v.as_str());
        let return_all = args
            .get("return_all")
            .and_then(|v| v.as_bool())
            .unwrap_or(false);
        let max_results = args
            .get("max_results")
            .and_then(|v| v.as_u64())
            .map(|v| v as usize)
            .unwrap_or(20);

        let mut explorer = self.server.explorer.write().await;
        match explorer.scan_pattern(pattern, module, return_all, max_results) {
            Ok(results) => {
                let formatted: Vec<Value> = results
                    .iter()
                    .map(|r| {
                        json!({
                            "address": format!("{:#x}", r.address),
                            "module": r.module
                        })
                    })
                    .collect();

                ToolResult::json(&json!({
                    "success": true,
                    "pattern": pattern,
                    "count": formatted.len(),
                    "results": formatted
                }))
            }
            Err(e) => ToolResult::json(&json!({
                "success": false,
                "error": e.to_string()
            })),
        }
    }
}

// ============================================================================
// Tool: find_value
// ============================================================================

struct FindValueTool {
    server: ServerRefs,
}

#[async_trait]
impl Tool for FindValueTool {
    fn name(&self) -> &str {
        "find_value"
    }

    fn description(&self) -> &str {
        "Search memory for a specific value (useful for finding player health, position, etc.)"
    }

    fn schema(&self) -> Value {
        json!({
            "type": "object",
            "properties": {
                "value": {
                    "type": "number",
                    "description": "The value to search for"
                },
                "type": {
                    "type": "string",
                    "enum": ["int32", "int64", "uint32", "uint64", "float", "double"],
                    "description": "Value type",
                    "default": "float"
                },
                "module": {
                    "type": "string",
                    "description": "Optional: limit search to a specific module"
                },
                "max_results": {
                    "type": "integer",
                    "description": "Maximum number of results",
                    "default": 50
                }
            },
            "required": ["value"]
        })
    }

    async fn execute(&self, args: Value) -> Result<ToolResult> {
        let value = args
            .get("value")
            .and_then(|v| v.as_f64())
            .ok_or_else(|| MCPError::InvalidParameters("Missing 'value' parameter".to_string()))?;

        let value_type_str = args.get("type").and_then(|v| v.as_str()).unwrap_or("float");

        let value_type: ValueType = value_type_str
            .parse()
            .map_err(|e: String| MCPError::InvalidParameters(e))?;

        let module = args.get("module").and_then(|v| v.as_str());
        let max_results = args
            .get("max_results")
            .and_then(|v| v.as_u64())
            .map(|v| v as usize)
            .unwrap_or(50);

        let mut explorer = self.server.explorer.write().await;
        match explorer.find_value(value, value_type, module, max_results) {
            Ok(results) => {
                let formatted: Vec<Value> = results
                    .iter()
                    .map(|r| {
                        json!({
                            "address": format!("{:#x}", r.address),
                            "module": r.module,
                            "value": value,
                            "type": value_type_str
                        })
                    })
                    .collect();

                ToolResult::json(&json!({
                    "success": true,
                    "value": value,
                    "type": value_type_str,
                    "count": formatted.len(),
                    "results": formatted
                }))
            }
            Err(e) => ToolResult::json(&json!({
                "success": false,
                "error": e.to_string()
            })),
        }
    }
}

// ============================================================================
// Tool: resolve_pointer
// ============================================================================

struct ResolvePointerTool {
    server: ServerRefs,
}

#[async_trait]
impl Tool for ResolvePointerTool {
    fn name(&self) -> &str {
        "resolve_pointer"
    }

    fn description(&self) -> &str {
        "Resolve a pointer chain. Start from a base address and follow offsets to find the final address."
    }

    fn schema(&self) -> Value {
        json!({
            "type": "object",
            "properties": {
                "base": {
                    "type": "string",
                    "description": "Base address or module name (e.g., '0x7FF6A1B2C3D4' or 'NMS.exe')"
                },
                "offsets": {
                    "type": "array",
                    "items": {"type": "integer"},
                    "description": "List of offsets to follow (e.g., [0x100, 0x20, 0x8])"
                }
            },
            "required": ["base", "offsets"]
        })
    }

    async fn execute(&self, args: Value) -> Result<ToolResult> {
        let base_str = args
            .get("base")
            .and_then(|v| v.as_str())
            .ok_or_else(|| MCPError::InvalidParameters("Missing 'base' parameter".to_string()))?;

        let offsets: Vec<i64> = args
            .get("offsets")
            .and_then(|v| v.as_array())
            .ok_or_else(|| MCPError::InvalidParameters("Missing 'offsets' parameter".to_string()))?
            .iter()
            .filter_map(|v| v.as_i64())
            .collect();

        let mut explorer = self.server.explorer.write().await;

        let base = match explorer.parse_address(base_str) {
            Ok(a) => a,
            Err(e) => {
                return ToolResult::json(&json!({
                    "success": false,
                    "error": e.to_string()
                }));
            }
        };

        match explorer.resolve_pointer_chain(base, &offsets) {
            Ok(chain) => ToolResult::json(&json!({
                "success": true,
                "base": format!("{:#x}", chain.base_address),
                "offsets": chain.offsets.iter().map(|o| format!("{:#x}", o)).collect::<Vec<_>>(),
                "final_address": format!("{:#x}", chain.final_address),
                "steps": chain.values_at_each_step.iter().map(|v| format!("{:#x}", v)).collect::<Vec<_>>()
            })),
            Err(e) => ToolResult::json(&json!({
                "success": false,
                "error": e.to_string()
            })),
        }
    }
}

// ============================================================================
// Tool: watch_address
// ============================================================================

struct WatchAddressTool {
    server: ServerRefs,
}

#[async_trait]
impl Tool for WatchAddressTool {
    fn name(&self) -> &str {
        "watch_address"
    }

    fn description(&self) -> &str {
        "Add an address to the watch list for monitoring changes."
    }

    fn schema(&self) -> Value {
        json!({
            "type": "object",
            "properties": {
                "label": {
                    "type": "string",
                    "description": "Name for this watch (e.g., 'player_health')"
                },
                "address": {
                    "type": "string",
                    "description": "Memory address"
                },
                "type": {
                    "type": "string",
                    "enum": ["bytes", "int32", "int64", "uint32", "uint64", "float", "double", "string"],
                    "description": "Value type",
                    "default": "float"
                },
                "size": {
                    "type": "integer",
                    "description": "Size in bytes (for bytes/string types)",
                    "default": 4
                }
            },
            "required": ["label", "address"]
        })
    }

    async fn execute(&self, args: Value) -> Result<ToolResult> {
        let label = args
            .get("label")
            .and_then(|v| v.as_str())
            .ok_or_else(|| MCPError::InvalidParameters("Missing 'label' parameter".to_string()))?;

        let address_str = args
            .get("address")
            .and_then(|v| v.as_str())
            .ok_or_else(|| {
                MCPError::InvalidParameters("Missing 'address' parameter".to_string())
            })?;

        let value_type_str = args.get("type").and_then(|v| v.as_str()).unwrap_or("float");

        let value_type: ValueType = value_type_str
            .parse()
            .map_err(|e: String| MCPError::InvalidParameters(e))?;

        let size = args
            .get("size")
            .and_then(|v| v.as_u64())
            .map(|v| v as usize)
            .unwrap_or(4);

        let mut explorer = self.server.explorer.write().await;

        let address = match explorer.parse_address(address_str) {
            Ok(a) => a,
            Err(e) => {
                return ToolResult::json(&json!({
                    "success": false,
                    "error": e.to_string()
                }));
            }
        };

        match explorer.add_watch(label, address, size, value_type) {
            Ok(result) => ToolResult::json(&json!({
                "success": true,
                "watch": result
            })),
            Err(e) => ToolResult::json(&json!({
                "success": false,
                "error": e.to_string()
            })),
        }
    }
}

// ============================================================================
// Tool: read_watches
// ============================================================================

struct ReadWatchesTool {
    server: ServerRefs,
}

#[async_trait]
impl Tool for ReadWatchesTool {
    fn name(&self) -> &str {
        "read_watches"
    }

    fn description(&self) -> &str {
        "Read current values of all watched addresses."
    }

    fn schema(&self) -> Value {
        json!({
            "type": "object",
            "properties": {}
        })
    }

    async fn execute(&self, _args: Value) -> Result<ToolResult> {
        let mut explorer = self.server.explorer.write().await;
        match explorer.read_all_watches() {
            Ok(results) => ToolResult::json(&json!({
                "success": true,
                "count": results.len(),
                "watches": results
            })),
            Err(e) => ToolResult::json(&json!({
                "success": false,
                "error": e.to_string()
            })),
        }
    }
}

// ============================================================================
// Tool: remove_watch
// ============================================================================

struct RemoveWatchTool {
    server: ServerRefs,
}

#[async_trait]
impl Tool for RemoveWatchTool {
    fn name(&self) -> &str {
        "remove_watch"
    }

    fn description(&self) -> &str {
        "Remove an address from the watch list."
    }

    fn schema(&self) -> Value {
        json!({
            "type": "object",
            "properties": {
                "label": {
                    "type": "string",
                    "description": "Watch label to remove"
                }
            },
            "required": ["label"]
        })
    }

    async fn execute(&self, args: Value) -> Result<ToolResult> {
        let label = args
            .get("label")
            .and_then(|v| v.as_str())
            .ok_or_else(|| MCPError::InvalidParameters("Missing 'label' parameter".to_string()))?;

        let mut explorer = self.server.explorer.write().await;
        explorer.remove_watch(label);

        ToolResult::json(&json!({
            "success": true,
            "removed": label
        }))
    }
}

// ============================================================================
// Tool: get_status
// ============================================================================

struct GetStatusTool {
    server: ServerRefs,
}

#[async_trait]
impl Tool for GetStatusTool {
    fn name(&self) -> &str {
        "get_status"
    }

    fn description(&self) -> &str {
        "Get current status: attached process, watched addresses, recent scans."
    }

    fn schema(&self) -> Value {
        json!({
            "type": "object",
            "properties": {}
        })
    }

    async fn execute(&self, _args: Value) -> Result<ToolResult> {
        let explorer = self.server.explorer.read().await;
        let status = explorer.get_status();

        ToolResult::json(&json!({
            "success": true,
            "status": status
        }))
    }
}

// ============================================================================
// Tests
// ============================================================================

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_server_creation() {
        let server = MemoryExplorerServer::new();
        let tools = server.tools();
        assert_eq!(tools.len(), 13);
    }

    #[test]
    fn test_tool_names() {
        let server = MemoryExplorerServer::new();
        let tools = server.tools();
        let names: Vec<&str> = tools.iter().map(|t| t.name()).collect();

        assert!(names.contains(&"list_processes"));
        assert!(names.contains(&"attach_process"));
        assert!(names.contains(&"detach_process"));
        assert!(names.contains(&"get_modules"));
        assert!(names.contains(&"read_memory"));
        assert!(names.contains(&"dump_memory"));
        assert!(names.contains(&"scan_pattern"));
        assert!(names.contains(&"find_value"));
        assert!(names.contains(&"resolve_pointer"));
        assert!(names.contains(&"watch_address"));
        assert!(names.contains(&"read_watches"));
        assert!(names.contains(&"remove_watch"));
        assert!(names.contains(&"get_status"));
    }
}
