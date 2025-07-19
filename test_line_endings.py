#!/usr/bin/env python3
"""Test script to demonstrate line ending behavior on different platforms."""

import os
import platform


def test_line_endings():
    """Test different ways of writing line endings."""
    print(f"Platform: {platform.system()}")
    print(f"Python newline default: {repr(os.linesep)}")

    # Test 1: Default text mode
    with open("test_default.txt", "w") as f:
        f.write("Line 1\n")
        f.write("Line 2\n")

    # Test 2: Text mode with newline='\n'
    with open("test_newline_lf.txt", "w", newline="\n") as f:
        f.write("Line 1\n")
        f.write("Line 2\n")

    # Test 3: Text mode with newline='' (no translation)
    with open("test_newline_empty.txt", "w", newline="") as f:
        f.write("Line 1\n")
        f.write("Line 2\n")

    # Test 4: Binary mode (no translation ever)
    with open("test_binary.txt", "wb") as f:
        f.write(b"Line 1\n")
        f.write(b"Line 2\n")

    # Check the actual bytes in each file
    for filename in [
        "test_default.txt",
        "test_newline_lf.txt",
        "test_newline_empty.txt",
        "test_binary.txt",
    ]:
        with open(filename, "rb") as f:
            content = f.read()
            print(f"\n{filename}:")
            print(f"  Raw bytes: {repr(content)}")
            has_crlf = b"\r\n" in content
            print(f"  Has CRLF: {has_crlf}")
            has_lf_only = b"\n" in content and b"\r\n" not in content
            print(f"  Has LF only: {has_lf_only}")

    # Cleanup
    for filename in [
        "test_default.txt",
        "test_newline_lf.txt",
        "test_newline_empty.txt",
        "test_binary.txt",
    ]:
        os.remove(filename)


def write_lf_only_examples():
    """Examples of the correct ways to write LF-only files on any platform."""
    print("\n" + "=" * 50)
    print("Correct ways to ensure LF-only line endings:")
    print("=" * 50)

    # Method 1: Using newline='' parameter
    print("\nMethod 1: Using newline='' (recommended for text)")
    with open("lf_method1.txt", "w", newline="") as f:
        f.write("This will have\n")
        f.write("LF line endings only\n")

    with open("lf_method1.txt", "rb") as f:
        print(f"  Result: {repr(f.read())}")
    os.remove("lf_method1.txt")

    # Method 2: Using binary mode
    print("\nMethod 2: Using binary mode")
    with open("lf_method2.txt", "wb") as f:
        f.write(b"This will have\n")
        f.write(b"LF line endings only\n")

    with open("lf_method2.txt", "rb") as f:
        print(f"  Result: {repr(f.read())}")
    os.remove("lf_method2.txt")

    # Method 3: Using io.open with newline parameter
    print("\nMethod 3: Using io.open (same as built-in open)")
    import io

    with io.open("lf_method3.txt", "w", newline="") as f:
        f.write("This will have\n")
        f.write("LF line endings only\n")

    with open("lf_method3.txt", "rb") as f:
        print(f"  Result: {repr(f.read())}")
    os.remove("lf_method3.txt")


if __name__ == "__main__":
    test_line_endings()
    write_lf_only_examples()
