#!/usr/bin/env python3
"""
Download Gaea2 terrain file from remote server using the new download tool
"""
import base64

import requests


def download_terrain_file(filename, local_filename, server_url="http://192.168.0.152:8007"):
    """
    Download terrain file from the Gaea2 MCP server using the new download tool.

    Args:
        filename: The terrain filename on the server
        local_filename: Where to save the file locally
        server_url: The Gaea2 MCP server URL
    """
    # Extract just the filename from any path
    filename_only = filename.split("\\")[-1].split("/")[-1]

    print(f"Downloading: {filename_only}")

    # First, try the direct HTTP download endpoint
    direct_url = f"{server_url}/download/{filename_only}"
    print(f"\nTrying direct download from: {direct_url}")

    try:
        response = requests.get(direct_url, timeout=10)
        if response.status_code == 200 and len(response.content) > 100:
            with open(local_filename, "wb") as f:
                f.write(response.content)
            print(f"✓ Successfully downloaded to: {local_filename}")
            print(f"  File size: {len(response.content):,} bytes")
            return True
        else:
            print(f"  Direct download failed: Status {response.status_code}")
    except Exception as e:
        print(f"  Direct download error: {e}")

    # If direct download fails, use the MCP download tool
    print("\nTrying MCP download tool...")

    mcp_request = {
        "tool": "download_gaea2_project",
        "parameters": {"filename": filename_only, "encoding": "base64"},
    }

    try:
        response = requests.post(f"{server_url}/mcp/execute", json=mcp_request, timeout=30)

        if response.status_code == 200:
            result = response.json()

            if result.get("success") and result.get("result", {}).get("success"):
                data = result["result"]["data"]
                file_info = result["result"]

                # Decode base64 data
                file_data = base64.b64decode(data)

                # Save to file
                with open(local_filename, "wb") as f:
                    f.write(file_data)

                print(f"✓ Successfully downloaded via MCP tool: {local_filename}")
                print(f"  Original filename: {file_info['filename']}")
                print(f"  File size: {file_info['size']:,} bytes")
                print(f"  Modified: {file_info['modified']}")
                return True
            else:
                error = result.get("result", {}).get("error") or result.get("error", "Unknown error")
                print(f"  MCP download failed: {error}")

                # List available files
                list_files(server_url)

        else:
            print(f"  MCP request failed: Status {response.status_code}")

    except Exception as e:
        print(f"  MCP download error: {e}")

    return False


def list_files(server_url="http://192.168.0.152:8007"):
    """List available terrain files on the server"""
    print("\nListing available terrain files...")

    try:
        # Try HTTP endpoint first
        response = requests.get(f"{server_url}/list", timeout=5)
        if response.status_code == 200:
            result = response.json()
            if result.get("success"):
                print(f"\nFound {result['count']} terrain files in {result['output_dir']}:")
                for file in result["files"][:10]:  # Show max 10 files
                    print(f"  - {file['filename']} ({file['size']:,} bytes, modified: {file['modified']})")
                if result["count"] > 10:
                    print(f"  ... and {result['count'] - 10} more files")
                return
    except Exception:
        pass

    # Fallback to MCP tool
    try:
        mcp_request = {"tool": "list_gaea2_projects", "parameters": {}}
        response = requests.post(f"{server_url}/mcp/execute", json=mcp_request, timeout=10)
        if response.status_code == 200:
            result = response.json()
            if result.get("success") and result.get("result", {}).get("success"):
                files = result["result"]["files"]
                print(f"\nFound {len(files)} terrain files:")
                for file in files[:10]:
                    print(f"  - {file['filename']} ({file['size']:,} bytes)")
    except Exception as e:
        print(f"  Failed to list files: {e}")


if __name__ == "__main__":
    # The filename we want to download
    filename = "test_volcanic_download_20250722_114743.terrain"
    local_filename = "test_volcanic_island.terrain"

    # Download the file
    success = download_terrain_file(filename, local_filename)

    if not success:
        print("\n❌ Download failed. The server may need to be restarted to use the new download functionality.")
        print("Please restart the Gaea2 MCP server and try again.")
