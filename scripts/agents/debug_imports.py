#!/usr/bin/env python3
"""
Debug script to test Python imports for the AI agents.
This helps diagnose import issues in the container environment.
"""
import os
import sys

print(f"Python version: {sys.version}")
print(f"Python executable: {sys.executable}")
print(f"Current directory: {os.getcwd()}")
print(f"PYTHONPATH: {os.environ.get('PYTHONPATH', 'Not set')}")
print("\nPython sys.path:")
for i, path in enumerate(sys.path):
    print(f"  {i}: {path}")

print("\n--- Testing imports ---")

# Test each module
modules = ["logging_security", "security", "utils"]
for module in modules:
    try:
        exec(f"import {module}")
        print(f"✓ {module}: OK")
    except ImportError as e:
        print(f"✗ {module}: ImportError - {e}")
    except Exception as e:
        print(f"✗ {module}: {type(e).__name__} - {e}")

# Test the main script
print("\n--- Testing main script import ---")
try:
    exec("import pr_review_monitor")
    print("✓ pr_review_monitor: OK")
except ImportError as e:
    print(f"✗ pr_review_monitor: ImportError - {e}")
except Exception as e:
    print(f"✗ pr_review_monitor: {type(e).__name__} - {e}")

print("\n--- Directory contents ---")
print("scripts/agents/:")
if os.path.exists("scripts/agents"):
    for item in sorted(os.listdir("scripts/agents")):
        print(f"  {item}")
else:
    print("  Directory not found!")
