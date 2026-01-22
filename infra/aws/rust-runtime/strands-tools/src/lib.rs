//! Strands Tools - Tool registry and execution
//!
//! Provides tool registration, lookup, and execution capabilities,
//! with optional MCP (Model Context Protocol) integration.

pub mod registry;

#[cfg(feature = "mcp")]
pub mod mcp;

pub use registry::ToolRegistry;
