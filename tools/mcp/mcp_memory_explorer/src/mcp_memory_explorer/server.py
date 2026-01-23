"""MCP server for memory exploration and game reverse engineering."""

from __future__ import annotations

import asyncio
import json
import logging
import sys
from typing import Any

from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import Tool, TextContent

from .explorer import get_explorer, MemoryExplorer

# Configure logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

# Create MCP server
server = Server("memory-explorer")


def _format_result(data: Any) -> str:
    """Format result data as JSON string."""
    if isinstance(data, (dict, list)):
        return json.dumps(data, indent=2, default=str)
    return str(data)


@server.list_tools()
async def list_tools() -> list[Tool]:
    """List available memory exploration tools."""
    return [
        Tool(
            name="list_processes",
            description="List running processes. Optionally filter by name substring.",
            inputSchema={
                "type": "object",
                "properties": {
                    "filter": {
                        "type": "string",
                        "description": "Optional filter substring for process names (e.g., 'NMS' to find No Man's Sky)",
                    },
                },
            },
        ),
        Tool(
            name="attach_process",
            description="Attach to a process by name. Required before any memory operations.",
            inputSchema={
                "type": "object",
                "properties": {
                    "process_name": {
                        "type": "string",
                        "description": "Process name (e.g., 'NMS.exe')",
                    },
                },
                "required": ["process_name"],
            },
        ),
        Tool(
            name="detach_process",
            description="Detach from the currently attached process.",
            inputSchema={"type": "object", "properties": {}},
        ),
        Tool(
            name="get_modules",
            description="List all loaded modules (DLLs) in the attached process with their base addresses.",
            inputSchema={"type": "object", "properties": {}},
        ),
        Tool(
            name="read_memory",
            description="Read memory at an address. Returns data in various formats based on type parameter.",
            inputSchema={
                "type": "object",
                "properties": {
                    "address": {
                        "type": "string",
                        "description": "Memory address in hex (e.g., '0x7FF6A1B2C3D4') or decimal",
                    },
                    "type": {
                        "type": "string",
                        "enum": ["bytes", "int32", "int64", "uint32", "uint64", "float", "double", "string", "pointer", "vector3", "vector4", "matrix4x4"],
                        "description": "Data type to read",
                        "default": "bytes",
                    },
                    "size": {
                        "type": "integer",
                        "description": "Number of bytes to read (for 'bytes' and 'string' types)",
                        "default": 64,
                    },
                },
                "required": ["address"],
            },
        ),
        Tool(
            name="dump_memory",
            description="Dump a region of memory as a hex dump with ASCII representation.",
            inputSchema={
                "type": "object",
                "properties": {
                    "address": {
                        "type": "string",
                        "description": "Starting address in hex or decimal",
                    },
                    "size": {
                        "type": "integer",
                        "description": "Number of bytes to dump",
                        "default": 256,
                    },
                },
                "required": ["address"],
            },
        ),
        Tool(
            name="scan_pattern",
            description="Scan memory for a byte pattern. Use ?? for wildcard bytes. Example: '48 8B 05 ?? ?? ?? ?? 48 85 C0'",
            inputSchema={
                "type": "object",
                "properties": {
                    "pattern": {
                        "type": "string",
                        "description": "Byte pattern with optional ?? wildcards",
                    },
                    "module": {
                        "type": "string",
                        "description": "Optional: limit scan to a specific module",
                    },
                    "return_all": {
                        "type": "boolean",
                        "description": "Return all matches instead of just the first",
                        "default": False,
                    },
                    "max_results": {
                        "type": "integer",
                        "description": "Maximum number of results",
                        "default": 20,
                    },
                },
                "required": ["pattern"],
            },
        ),
        Tool(
            name="find_value",
            description="Search memory for a specific value (useful for finding player health, position, etc.)",
            inputSchema={
                "type": "object",
                "properties": {
                    "value": {
                        "type": "number",
                        "description": "The value to search for",
                    },
                    "type": {
                        "type": "string",
                        "enum": ["int32", "int64", "uint32", "uint64", "float", "double"],
                        "description": "Value type",
                        "default": "float",
                    },
                    "module": {
                        "type": "string",
                        "description": "Optional: limit search to a specific module",
                    },
                    "max_results": {
                        "type": "integer",
                        "description": "Maximum number of results",
                        "default": 50,
                    },
                },
                "required": ["value"],
            },
        ),
        Tool(
            name="resolve_pointer",
            description="Resolve a pointer chain. Start from a base address and follow offsets to find the final address.",
            inputSchema={
                "type": "object",
                "properties": {
                    "base": {
                        "type": "string",
                        "description": "Base address or module name (e.g., '0x7FF6A1B2C3D4' or 'NMS.exe')",
                    },
                    "offsets": {
                        "type": "array",
                        "items": {"type": "integer"},
                        "description": "List of offsets to follow (e.g., [0x100, 0x20, 0x8])",
                    },
                },
                "required": ["base", "offsets"],
            },
        ),
        Tool(
            name="watch_address",
            description="Add an address to the watch list for monitoring changes.",
            inputSchema={
                "type": "object",
                "properties": {
                    "label": {
                        "type": "string",
                        "description": "Name for this watch (e.g., 'player_health')",
                    },
                    "address": {
                        "type": "string",
                        "description": "Memory address",
                    },
                    "type": {
                        "type": "string",
                        "enum": ["bytes", "int32", "int64", "uint32", "uint64", "float", "double", "string"],
                        "description": "Value type",
                        "default": "float",
                    },
                    "size": {
                        "type": "integer",
                        "description": "Size in bytes (for bytes/string types)",
                        "default": 4,
                    },
                },
                "required": ["label", "address"],
            },
        ),
        Tool(
            name="read_watches",
            description="Read current values of all watched addresses.",
            inputSchema={"type": "object", "properties": {}},
        ),
        Tool(
            name="remove_watch",
            description="Remove an address from the watch list.",
            inputSchema={
                "type": "object",
                "properties": {
                    "label": {
                        "type": "string",
                        "description": "Watch label to remove",
                    },
                },
                "required": ["label"],
            },
        ),
        Tool(
            name="get_status",
            description="Get current status: attached process, watched addresses, recent scans.",
            inputSchema={"type": "object", "properties": {}},
        ),
    ]


def _parse_address(addr: str, explorer: MemoryExplorer) -> int:
    """Parse an address string (hex or decimal) or module name + offset."""
    addr = addr.strip()

    # Check if it's a module reference like "NMS.exe+0x1234"
    if "+" in addr:
        parts = addr.split("+", 1)
        module_name = parts[0].strip()
        offset = int(parts[1].strip(), 16) if parts[1].strip().startswith("0x") else int(parts[1].strip())
        base = explorer.get_module_base(module_name)
        return base + offset

    # Check for just a module name
    if not addr.startswith("0x") and not addr.isdigit():
        try:
            return explorer.get_module_base(addr)
        except ValueError:
            pass

    # Parse as hex or decimal
    if addr.startswith("0x") or addr.startswith("0X"):
        return int(addr, 16)
    return int(addr)


@server.call_tool()
async def call_tool(name: str, arguments: dict[str, Any]) -> list[TextContent]:
    """Handle tool calls."""
    explorer = get_explorer()

    try:
        if name == "list_processes":
            result = explorer.list_processes(arguments.get("filter"))

        elif name == "attach_process":
            result = explorer.attach(arguments["process_name"])

        elif name == "detach_process":
            explorer.detach()
            result = {"detached": True}

        elif name == "get_modules":
            result = explorer.get_modules()

        elif name == "read_memory":
            addr = _parse_address(arguments["address"], explorer)
            read_type = arguments.get("type", "bytes")
            size = arguments.get("size", 64)

            if read_type == "bytes":
                data = explorer.read_bytes(addr, size)
                result = {"address": hex(addr), "hex": data.hex(), "size": len(data)}
            elif read_type == "int32":
                result = {"address": hex(addr), "value": explorer.read_int32(addr)}
            elif read_type == "int64":
                result = {"address": hex(addr), "value": explorer.read_int64(addr)}
            elif read_type == "uint32":
                result = {"address": hex(addr), "value": explorer.read_uint32(addr)}
            elif read_type == "uint64":
                result = {"address": hex(addr), "value": explorer.read_uint64(addr)}
            elif read_type == "float":
                result = {"address": hex(addr), "value": explorer.read_float(addr)}
            elif read_type == "double":
                result = {"address": hex(addr), "value": explorer.read_double(addr)}
            elif read_type == "string":
                result = {"address": hex(addr), "value": explorer.read_string(addr, size)}
            elif read_type == "pointer":
                ptr = explorer.read_pointer(addr)
                result = {"address": hex(addr), "pointer": hex(ptr)}
            elif read_type == "vector3":
                result = {"address": hex(addr), "value": explorer.read_vector3(addr)}
            elif read_type == "vector4":
                result = {"address": hex(addr), "value": explorer.read_vector4(addr)}
            elif read_type == "matrix4x4":
                result = {"address": hex(addr), "value": explorer.read_matrix4x4(addr)}
            else:
                result = {"error": f"Unknown type: {read_type}"}

        elif name == "dump_memory":
            addr = _parse_address(arguments["address"], explorer)
            size = arguments.get("size", 256)
            result = explorer.dump_memory(addr, size)

        elif name == "scan_pattern":
            results = explorer.scan_pattern(
                arguments["pattern"],
                module_name=arguments.get("module"),
                return_multiple=arguments.get("return_all", False),
                max_results=arguments.get("max_results", 20),
            )
            result = {
                "pattern": arguments["pattern"],
                "count": len(results),
                "results": [{"address": hex(r.address), "module": r.module} for r in results],
            }

        elif name == "find_value":
            results = explorer.find_value(
                arguments["value"],
                value_type=arguments.get("type", "float"),
                module_name=arguments.get("module"),
                max_results=arguments.get("max_results", 50),
            )
            result = {"value": arguments["value"], "type": arguments.get("type", "float"), "count": len(results), "results": results}

        elif name == "resolve_pointer":
            base_str = arguments["base"]
            base = _parse_address(base_str, explorer)
            offsets = arguments["offsets"]
            chain = explorer.resolve_pointer_chain(base, offsets)
            result = {
                "base": hex(chain.base_address),
                "offsets": [hex(o) for o in chain.offsets],
                "final_address": hex(chain.final_address),
                "steps": [hex(v) for v in chain.values_at_each_step],
            }

        elif name == "watch_address":
            addr = _parse_address(arguments["address"], explorer)
            result = explorer.add_watch(
                arguments["label"],
                addr,
                size=arguments.get("size", 4),
                value_type=arguments.get("type", "float"),
            )

        elif name == "read_watches":
            result = explorer.read_all_watches()

        elif name == "remove_watch":
            explorer.remove_watch(arguments["label"])
            result = {"removed": arguments["label"]}

        elif name == "get_status":
            result = {
                "attached": explorer.is_attached,
                "process": explorer.process_name,
                "watches": list(explorer._watches.keys()),
                "recent_scans": len(explorer._scan_results),
            }

        else:
            result = {"error": f"Unknown tool: {name}"}

        return [TextContent(type="text", text=_format_result(result))]

    except Exception as e:
        logger.exception(f"Tool {name} failed")
        return [TextContent(type="text", text=_format_result({"error": str(e)}))]


async def main() -> None:
    """Run the MCP server."""
    logger.info("Starting Memory Explorer MCP server")

    async with stdio_server() as (read_stream, write_stream):
        await server.run(read_stream, write_stream, server.create_initialization_options())


def run() -> None:
    """Entry point for the server."""
    asyncio.run(main())


if __name__ == "__main__":
    run()
