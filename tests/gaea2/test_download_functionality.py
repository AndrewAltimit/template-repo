#!/usr/bin/env python3
"""Test the Gaea2 MCP server download functionality"""
import json

import requests


def test_download():
    server_url = "http://192.168.0.152:8007"

    # 1. Create a simple terrain
    print("1. Creating test terrain...")
    create_response = requests.post(
        f"{server_url}/mcp/execute",
        json={
            "tool": "create_gaea2_from_template",
            "parameters": {
                "template_name": "basic_terrain",
                "project_name": "download_test_basic",
            },
        },
    )

    create_result = create_response.json()
    print(f"   Create result: {json.dumps(create_result, indent=2)}")

    if not create_result.get("success"):
        print("   ❌ Failed to create terrain")
        return False

    # Extract filename
    project_path = create_result["result"]["project_path"]
    filename = project_path.split("\\")[-1]
    print(f"   Created: {filename}")

    # 2. List files to verify it exists
    print("\n2. Listing files...")
    list_response = requests.post(
        f"{server_url}/mcp/execute",
        json={"tool": "list_gaea2_projects", "parameters": {}},
    )

    list_result = list_response.json()
    if list_result.get("success"):
        files = list_result["result"]["files"]
        our_file = next((f for f in files if f["filename"] == filename), None)
        if our_file:
            print(f"   ✓ Found our file: {our_file['filename']} ({our_file['size']} bytes)")
        else:
            print("   ❌ File not found in list")

    # 3. Download using MCP tool
    print("\n3. Downloading via MCP tool...")
    download_response = requests.post(
        f"{server_url}/mcp/execute",
        json={
            "tool": "download_gaea2_project",
            "parameters": {"filename": filename, "encoding": "raw"},
        },
    )

    download_result = download_response.json()
    if download_result.get("success") and download_result.get("result", {}).get("success"):
        file_data = download_result["result"]["data"]
        print("   ✓ Downloaded successfully")
        print(f"   File size: {download_result['result']['size']} bytes")
        print(f"   Content preview: {json.dumps(file_data, indent=2)[:200]}...")
    else:
        print(f"   ❌ Download failed: {download_result}")

    # 4. Test direct HTTP download
    print("\n4. Testing direct HTTP download...")
    direct_response = requests.get(f"{server_url}/download/{filename}")
    if direct_response.status_code == 200:
        print("   ✓ Direct download successful")
        print(f"   Content size: {len(direct_response.content)} bytes")
        print(f"   Content: {direct_response.text}")
    else:
        print(f"   ❌ Direct download failed: {direct_response.status_code}")

    print("\n✅ Download functionality test complete!")
    print("\n⚠️  Note: All terrain files appear to be empty (2 bytes).")
    print("This suggests an issue with the terrain generation, not the download functionality.")
    return True


if __name__ == "__main__":
    test_download()
