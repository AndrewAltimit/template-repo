#!/usr/bin/env python3
"""Test the improved validation system that detects successful file openings"""

import requests
import time
import json

GAEA2_SERVER = "http://192.168.0.152:8007"

def test_improved_validation():
    print("Testing Improved Gaea2 Validation System")
    print("=" * 60)
    print("This should now correctly detect when files open successfully")
    print()
    
    # Create a simple working file
    print("1. Creating a simple terrain file...")
    project_name = f"improved_validation_test_{int(time.time())}"
    
    payload = {
        "tool": "create_gaea2_project",
        "parameters": {
            "project_name": project_name,
            "nodes": [
                {
                    "id": 1,
                    "type": "Mountain",
                    "name": "Mountain1",
                    "position": {"x": 100, "y": 100}
                },
                {
                    "id": 2,
                    "type": "Export",
                    "name": "Export1",
                    "position": {"x": 400, "y": 100}
                }
            ],
            "connections": [
                {"from_node": 1, "to_node": 2, "from_port": "Out", "to_port": "In"}
            ],
            "property_mode": "none"
        }
    }
    
    try:
        response = requests.post(f"{GAEA2_SERVER}/mcp/execute", json=payload, timeout=30)
        result = response.json()
        
        if result.get("success"):
            file_path = result.get("project_path") or result.get("saved_path")
            print(f"✅ File created: {file_path}")
            
            # Now validate with improved system
            print("\n2. Validating with improved detection...")
            time.sleep(2)
            
            validate_payload = {
                "tool": "validate_gaea2_file",
                "parameters": {
                    "file_path": file_path,
                    "timeout": 30
                }
            }
            
            val_response = requests.post(
                f"{GAEA2_SERVER}/mcp/execute", 
                json=validate_payload, 
                timeout=60
            )
            val_result = val_response.json()
            
            print("\n3. Validation Result:")
            print("-" * 40)
            
            if val_result.get("success"):
                print("✅ SUCCESS DETECTED! File opens in Gaea2!")
                print(f"   Duration: {val_result.get('duration', 0):.2f} seconds")
                print(f"   Success pattern found: {val_result.get('success_detected', False)}")
                print(f"   Error pattern found: {val_result.get('error_detected', False)}")
                
                # Show what patterns were detected
                if val_result.get("stdout"):
                    stdout_lines = val_result["stdout"].split("\n")
                    for line in stdout_lines:
                        if "Opening" in line or "Loading" in line or "Activated" in line:
                            print(f"   Detected: {line}")
                
                print("\n🎉 The improved validation correctly identifies successful files!")
                
            else:
                print("❌ File validation failed")
                print(f"   Error: {val_result.get('error', 'Unknown')}")
                print(f"   Duration: {val_result.get('duration', 0):.2f} seconds")
                
                if val_result.get("error_info"):
                    print(f"   Error types: {val_result['error_info'].get('error_types', [])}")
                
        else:
            print(f"❌ Failed to create file: {result.get('error')}")
            
    except Exception as e:
        print(f"❌ Error: {e}")

    print("\n" + "="*60)
    print("The improved validation system should now:")
    print("- Detect 'Opening [filename]' as success")
    print("- Wait 3 seconds after detection to confirm no errors")
    print("- Kill Gaea2 process after determining result")
    print("- Correctly report successful file openings")

if __name__ == "__main__":
    test_improved_validation()