#!/usr/bin/env python3
"""
Test the extract_project parameter for the download endpoint
"""
import json
import sys

import requests


def test_extract_project(server_url="http://192.168.0.152:8007", filename=None):
    """Test the extract_project parameter"""

    # If no filename provided, get the first available terrain file
    if not filename:
        print(f"Getting file list from {server_url}/list...")
        response = requests.get(f"{server_url}/list")
        if response.status_code == 200:
            data = response.json()
            if data.get("files"):
                # Find a terrain file with reasonable size (not an error file)
                for file in data["files"]:
                    if file["filename"].endswith(".terrain") and file["size"] > 100:
                        filename = file["filename"]
                        print(f"Found terrain file: {filename} ({file['size']:,} bytes)")
                        break

        if not filename:
            print("No suitable terrain files found")
            return

    print(f"\nTesting download of '{filename}':")

    # Test 1: Download without extract_project (default behavior)
    print("\n1. Download WITHOUT extract_project parameter:")
    url1 = f"{server_url}/download/{filename}"
    response1 = requests.get(url1)
    if response1.status_code == 200:
        content1 = response1.text
        try:
            data1 = json.loads(content1)
            if "project" in data1 and "success" in data1:
                print("   ✓ File contains wrapper (success, project, node_count, etc.)")
                print(f"   Keys: {list(data1.keys())}")
            else:
                print("   ✓ File is already in Gaea2 format (no wrapper)")
                print(f"   Top-level keys: {list(data1.keys())[:5]}...")
        except Exception:
            print("   ✗ Not valid JSON")
    else:
        print(f"   ✗ Download failed: {response1.status_code}")

    # Test 2: Download with extract_project=true
    print("\n2. Download WITH extract_project=true parameter:")
    url2 = f"{server_url}/download/{filename}?extract_project=true"
    response2 = requests.get(url2)
    if response2.status_code == 200:
        content2 = response2.text
        try:
            data2 = json.loads(content2)
            if "$id" in data2 and "Assets" in data2:
                print("   ✓ Successfully extracted project data (Gaea2 format)")
                print(f"   Top-level keys: {list(data2.keys())[:5]}...")
            else:
                print("   ✓ Returned data as-is (no wrapper found)")
                print(f"   Keys: {list(data2.keys())}")
        except Exception:
            print("   ✗ Not valid JSON")
    else:
        print(f"   ✗ Download failed: {response2.status_code}")

    # Show the difference
    if response1.status_code == 200 and response2.status_code == 200:
        size1 = len(content1)
        size2 = len(content2)
        print("\n3. Size comparison:")
        print(f"   Without extract_project: {size1:,} bytes")
        print(f"   With extract_project:    {size2:,} bytes")
        diff = size1 - size2
        print(f"   Difference:              {abs(diff):,} bytes {'removed' if diff > 0 else 'added'}")


if __name__ == "__main__":
    if len(sys.argv) > 1:
        test_extract_project(filename=sys.argv[1])
    else:
        test_extract_project()
