#!/usr/bin/env python3
"""
Quick test of the Gaea2 file validation system
"""

import requests


# Test the validation system
def test_validation_tools():
    """Test the new validation tools"""

    server_url = "http://192.168.0.152:8007"

    print("Testing Gaea2 Validation Tools")
    print("=" * 60)

    # 1. Check if validation tools are registered
    print("\n1. Checking registered tools...")
    try:
        response = requests.get(f"{server_url}/mcp/tools")
        if response.status_code == 200:
            tools = response.json().get("tools", [])
            validation_tools = [t for t in tools if "validate_gaea2" in t["name"] or "test_gaea2" in t["name"]]

            if validation_tools:
                print(f"✓ Found {len(validation_tools)} validation tools:")
                for tool in validation_tools:
                    print(f"  - {tool['name']}: {tool['description']}")
            else:
                print("✗ No validation tools found!")
                return
        else:
            print(f"✗ Failed to get tools: HTTP {response.status_code}")
            return
    except Exception as e:
        print(f"✗ Error: {e}")
        return

    # 2. Test single file validation (using existing test file)
    print("\n2. Testing single file validation...")
    test_file = "/tmp/test_basic_terrain.terrain"

    # First, create a test file using basic_terrain template
    print("   Creating test file...")
    payload = {
        "tool": "create_gaea2_from_template",
        "parameters": {
            "template_name": "basic_terrain",
            "project_name": "test_basic_terrain",
            "output_path": test_file,
        },
    }

    try:
        response = requests.post(f"{server_url}/mcp/execute", json=payload, timeout=30)
        if response.status_code == 200:
            result = response.json()
            if result.get("success"):
                print(f"   ✓ Test file created: {test_file}")
            else:
                print(f"   ✗ Failed to create test file: {result.get('error')}")
                return
        else:
            print(f"   ✗ HTTP error {response.status_code}")
            return
    except Exception as e:
        print(f"   ✗ Error creating test file: {e}")
        return

    # Now validate the file
    print("\n   Validating test file...")
    payload = {
        "tool": "validate_gaea2_file",
        "parameters": {"file_path": test_file, "timeout": 30},
    }

    try:
        response = requests.post(f"{server_url}/mcp/execute", json=payload, timeout=60)
        if response.status_code == 200:
            result = response.json()

            if result.get("success"):
                print("   ✓ File validation completed!")
                opens_in_gaea = "Yes" if result.get("success") else "No"
                print(f"   - File opens in Gaea2: {opens_in_gaea}")
                print(f"   - Duration: {result.get('duration', 0):.2f} seconds")

                if not result.get("success") and result.get("error_info"):
                    err_types = result["error_info"].get("error_types", [])
                    print("   - Error types:", ", ".join(err_types))
                    if result["error_info"].get("error_messages"):
                        print("   - Error messages:")
                        for msg in result["error_info"]["error_messages"][:3]:
                            print(f"     • {msg}")
            else:
                print(f"   ✗ Validation failed: {result.get('error')}")
        else:
            print(f"   ✗ HTTP error {response.status_code}")
    except Exception as e:
        print(f"   ✗ Error during validation: {e}")

    # 3. Test template validation
    print("\n3. Testing template validation...")
    payload = {
        "tool": "test_gaea2_template",
        "parameters": {
            "template_name": "basic_terrain",
            "variations": 2,
            "server_url": server_url,
        },
    }

    try:
        response = requests.post(f"{server_url}/mcp/execute", json=payload, timeout=120)
        if response.status_code == 200:
            result = response.json()

            if result.get("success"):
                print("   ✓ Template validation completed!")
                print(f"   - Template: {result.get('template_name', 'unknown')}")
                print(f"   - Variations tested: {result.get('variations_tested', 0)}")
                print(f"   - Successful: {result.get('successful', 0)}")
                print(f"   - Failed: {result.get('failed', 0)}")

                if result.get("common_errors"):
                    print("   - Common errors:")
                    for error_type, count in result["common_errors"][:3]:
                        print(f"     • {error_type}: {count}")
            else:
                print(f"   ✗ Template test failed: {result.get('error')}")
        else:
            print(f"   ✗ HTTP error {response.status_code}")
    except Exception as e:
        print(f"   ✗ Error during template test: {e}")

    print("\n" + "=" * 60)
    print("Validation system test complete!")


if __name__ == "__main__":
    test_validation_tools()
