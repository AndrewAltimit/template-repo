#!/usr/bin/env python3
"""Test script for Memory Explorer MCP server."""

import sys
sys.path.insert(0, str(__file__).replace("\\", "/").rsplit("/", 2)[0] + "/src")

from mcp_memory_explorer.explorer import MemoryExplorer


def test_basic_functionality():
    """Test basic explorer functionality."""
    explorer = MemoryExplorer()

    print("Testing Memory Explorer...")
    print()

    # Test process listing
    print("1. Listing processes (filtering for common ones)...")
    processes = explorer.list_processes(filter_name="python")
    print(f"   Found {len(processes)} Python processes")
    for p in processes[:3]:
        print(f"   - {p['name']} (PID: {p['pid']})")
    print()

    # Test pattern parsing
    print("2. Testing pattern parsing...")
    pattern = "48 8B 05 ?? ?? ?? ?? 48 85 C0"
    pattern_bytes, mask = explorer._parse_pattern(pattern)
    print(f"   Pattern: {pattern}")
    print(f"   Bytes: {pattern_bytes.hex()}")
    print(f"   Mask: {mask}")
    print()

    # Check if we can find a game
    print("3. Looking for game processes...")
    games = ["NMS.exe", "Notepad.exe", "explorer.exe"]
    for game in games:
        procs = explorer.list_processes(filter_name=game.replace(".exe", ""))
        if procs:
            print(f"   Found: {game} ({len(procs)} instance(s))")
    print()

    print("Basic tests passed!")
    print()
    print("To test memory operations, run with a target process:")
    print("  python -c \"from mcp_memory_explorer.explorer import get_explorer; e = get_explorer(); print(e.attach('notepad.exe'))\"")


if __name__ == "__main__":
    test_basic_functionality()
