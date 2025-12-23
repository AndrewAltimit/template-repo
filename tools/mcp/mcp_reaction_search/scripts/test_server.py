#!/usr/bin/env python3
"""
Test script for Reaction Search MCP Server

Usage:
    python scripts/test_server.py
"""

import asyncio
from pathlib import Path
import sys

# Add parent paths for imports
sys.path.insert(0, str(Path(__file__).parent.parent))
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent / "mcp_core"))

from mcp_reaction_search.server import ReactionSearchServer


async def test_server():
    """Run basic server tests."""
    print("=" * 60)
    print("Reaction Search MCP Server Test")
    print("=" * 60)

    server = ReactionSearchServer()

    # Test 1: Status (before initialization)
    print("\n[1] Testing status (pre-init)...")
    status = await server.reaction_search_status()
    print(f"    Initialized: {status.get('initialized')}")
    assert status["initialized"] is False, "Should not be initialized yet"
    print("    PASSED")

    # Test 2: Search (triggers lazy initialization)
    print("\n[2] Testing search (triggers initialization)...")
    print("    This may take a few seconds on first run (downloading model)...")
    result = await server.search_reactions(query="celebrating after fixing a bug", limit=3)
    print(f"    Success: {result.get('success')}")
    print(f"    Results: {result.get('count')}")
    if result.get("results"):
        for r in result["results"]:
            print(f"      - {r['id']}: {r['similarity']:.3f}")
            print(f"        {r['description'][:50]}...")
    assert result["success"], f"Search failed: {result.get('error')}"
    assert result["count"] > 0, "No results returned"
    print("    PASSED")

    # Test 3: Search with tags filter
    print("\n[3] Testing search with tag filter...")
    result = await server.search_reactions(query="feeling happy", limit=5, tags=["smug"])
    print(f"    Results with 'smug' tag: {result.get('count')}")
    if result.get("results"):
        for r in result["results"]:
            print(f"      - {r['id']}: tags={r['tags']}")
    assert result["success"], f"Search failed: {result.get('error')}"
    print("    PASSED")

    # Test 4: Get specific reaction
    print("\n[4] Testing get_reaction...")
    result = await server.get_reaction("felix")
    print(f"    Success: {result.get('success')}")
    if result.get("reaction"):
        r = result["reaction"]
        print(f"    ID: {r['id']}")
        print(f"    URL: {r['url']}")
        print(f"    Markdown: {r['markdown'][:60]}...")
    assert result["success"], f"Get failed: {result.get('error')}"
    print("    PASSED")

    # Test 5: Get non-existent reaction
    print("\n[5] Testing get_reaction (not found)...")
    result = await server.get_reaction("this_does_not_exist_12345")
    print(f"    Success: {result.get('success')}")
    print(f"    Error: {result.get('error')}")
    assert not result["success"], "Should have failed"
    print("    PASSED")

    # Test 6: List tags
    print("\n[6] Testing list_reaction_tags...")
    result = await server.list_reaction_tags()
    print(f"    Total tags: {result.get('total_tags')}")
    if result.get("tags"):
        top_tags = list(result["tags"].items())[:10]
        print(f"    Top 10 tags: {dict(top_tags)}")
    assert result["success"], f"List tags failed: {result.get('error')}"
    print("    PASSED")

    # Test 7: Status (after initialization)
    print("\n[7] Testing status (post-init)...")
    status = await server.reaction_search_status()
    print(f"    Initialized: {status.get('initialized')}")
    print(f"    Reaction count: {status.get('engine', {}).get('reaction_count')}")
    print(f"    Model: {status.get('engine', {}).get('model_name')}")
    assert status["initialized"] is True, "Should be initialized"
    print("    PASSED")

    # Test 8: Various query types
    print("\n[8] Testing various queries...")
    queries = [
        "confused about the error",
        "typing code furiously",
        "smug after winning an argument",
        "sad and disappointed",
        "nervous about the deadline",
    ]
    for query in queries:
        result = await server.search_reactions(query=query, limit=1)
        if result.get("results"):
            top = result["results"][0]
            print(f"    '{query}' -> {top['id']} ({top['similarity']:.3f})")
        else:
            print(f"    '{query}' -> no results")
    print("    PASSED")

    print("\n" + "=" * 60)
    print("All tests PASSED!")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(test_server())
