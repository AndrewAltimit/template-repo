#!/usr/bin/env python3
"""Quick test of MCP server modules"""

import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))

print("Testing MCP Server Imports...")
print("=" * 50)

# Test each server import
servers = [
    ("Code Quality", "tools.mcp.code_quality", "CodeQualityMCPServer"),
    ("Content Creation", "tools.mcp.content_creation", "ContentCreationMCPServer"),
    ("Gemini", "tools.mcp.gemini", "GeminiMCPServer"),
    ("Gaea2", "tools.mcp.gaea2", "Gaea2MCPServer"),
]

for name, module, class_name in servers:
    try:
        exec(f"from {module} import {class_name}")
        print(f"✓ {name}: Import successful")
    except ImportError as e:
        print(f"✗ {name}: Import failed - {e}")
    except Exception as e:
        print(f"✗ {name}: Error - {e}")

print("\nTesting server instantiation...")
print("-" * 50)

# Test creating servers
try:
    from tools.mcp.code_quality import CodeQualityMCPServer

    server = CodeQualityMCPServer()
    print(f"✓ Code Quality: Created successfully (port {server.port})")
except Exception as e:
    print(f"✗ Code Quality: Failed - {e}")

try:
    from tools.mcp.content_creation import ContentCreationMCPServer

    server = ContentCreationMCPServer()
    print(f"✓ Content Creation: Created successfully (port {server.port})")
except Exception as e:
    print(f"✗ Content Creation: Failed - {e}")

print("\nNote: Gemini and Gaea2 servers may have additional dependencies.")
print("Run them directly to see specific requirements.")
