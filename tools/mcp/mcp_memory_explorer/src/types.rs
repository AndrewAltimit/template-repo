//! Data types for memory exploration.

use serde::{Deserialize, Serialize};

/// Information about a running process.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ProcessInfo {
    pub name: String,
    pub pid: u32,
}

/// Information about a loaded module (DLL/EXE).
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ModuleInfo {
    pub name: String,
    pub base_address: u64,
    pub size: u64,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub path: Option<String>,
}

/// Result from a pattern scan.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ScanResult {
    pub address: u64,
    pub pattern: String,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub module: Option<String>,
}

/// Result of resolving a pointer chain.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct PointerChain {
    pub base_address: u64,
    pub offsets: Vec<i64>,
    pub final_address: u64,
    pub values_at_each_step: Vec<u64>,
}

/// An address being watched for changes.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct WatchedAddress {
    pub address: u64,
    pub size: usize,
    pub label: String,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub last_value: Option<Vec<u8>>,
    pub value_type: ValueType,
}

/// Supported data types for memory reading.
#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "snake_case")]
pub enum ValueType {
    Bytes,
    Int32,
    Int64,
    Uint32,
    Uint64,
    Float,
    Double,
    String,
    Pointer,
    Vector3,
    Vector4,
    Matrix4x4,
}

impl Default for ValueType {
    fn default() -> Self {
        Self::Bytes
    }
}

impl std::str::FromStr for ValueType {
    type Err = String;

    fn from_str(s: &str) -> Result<Self, Self::Err> {
        match s.to_lowercase().as_str() {
            "bytes" => Ok(Self::Bytes),
            "int32" => Ok(Self::Int32),
            "int64" => Ok(Self::Int64),
            "uint32" => Ok(Self::Uint32),
            "uint64" => Ok(Self::Uint64),
            "float" => Ok(Self::Float),
            "double" => Ok(Self::Double),
            "string" => Ok(Self::String),
            "pointer" => Ok(Self::Pointer),
            "vector3" => Ok(Self::Vector3),
            "vector4" => Ok(Self::Vector4),
            "matrix4x4" => Ok(Self::Matrix4x4),
            _ => Err(format!("Unknown value type: {}", s)),
        }
    }
}

/// A 3D vector (3 floats).
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct Vector3 {
    pub x: f32,
    pub y: f32,
    pub z: f32,
}

/// A 4D vector (4 floats).
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct Vector4 {
    pub x: f32,
    pub y: f32,
    pub z: f32,
    pub w: f32,
}

/// Result of reading a watch.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct WatchResult {
    pub label: String,
    pub address: String,
    pub value: serde_json::Value,
    pub raw_hex: String,
    pub changed: bool,
}

/// Memory dump result.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct MemoryDump {
    pub address: String,
    pub size: usize,
    pub data: String,
}

/// Attachment result.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct AttachResult {
    pub attached: bool,
    pub process_name: String,
    pub pid: u32,
    pub base_address: String,
    pub module_count: usize,
}

/// Explorer status.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ExplorerStatus {
    pub attached: bool,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub process: Option<String>,
    pub watches: Vec<String>,
    pub recent_scans: usize,
}
