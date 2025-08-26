#!/usr/bin/env python3
"""Test VRChat OSC movement commands with different approaches."""

import argparse
import time

from pythonosc import udp_client


def test_movement_approaches(host: str, port: int = 9000):
    """Test different movement OSC approaches."""
    client = udp_client.SimpleUDPClient(host, port)

    print(f"Testing VRChat OSC movement at {host}:{port}")
    print("-" * 50)

    # Test 1: Standard axes input with different value ranges
    print("\n1. Testing standard axes input (float values -1 to 1):")
    movements = [
        ("Forward", "/input/Vertical", 1.0),
        ("Backward", "/input/Vertical", -1.0),
        ("Right", "/input/Horizontal", 1.0),
        ("Left", "/input/Horizontal", -1.0),
    ]

    for name, path, value in movements:
        print(f"   {name}: {path} = {value}")
        client.send_message(path, value)
        time.sleep(2)
        # Reset to 0
        client.send_message(path, 0.0)
        time.sleep(0.5)

    # Test 2: Try integer values (some avatars might expect this)
    print("\n2. Testing with integer values:")
    for name, path, value in movements:
        int_value = int(value)
        print(f"   {name}: {path} = {int_value}")
        client.send_message(path, int_value)
        time.sleep(2)
        client.send_message(path, 0)
        time.sleep(0.5)

    # Test 3: Try alternative paths
    print("\n3. Testing alternative OSC paths:")
    alt_paths = [
        ("/input/MoveForward", 1.0),
        ("/input/MoveBackward", 1.0),
        ("/input/MoveLeft", 1.0),
        ("/input/MoveRight", 1.0),
    ]

    for path, value in alt_paths:
        print(f"   Testing: {path} = {value}")
        client.send_message(path, value)
        time.sleep(2)
        client.send_message(path, 0.0)
        time.sleep(0.5)

    # Test 4: Try combined Axes approach (both X and Y at once)
    print("\n4. Testing combined axes (Move + Look):")
    print("   Moving diagonally forward-right and looking around")
    client.send_message("/input/Vertical", 0.7)
    client.send_message("/input/Horizontal", 0.7)
    client.send_message("/input/LookHorizontal", 0.5)
    time.sleep(3)
    # Reset all
    client.send_message("/input/Vertical", 0.0)
    client.send_message("/input/Horizontal", 0.0)
    client.send_message("/input/LookHorizontal", 0.0)

    # Test 5: Try Run modifier with movement
    print("\n5. Testing movement with Run modifier:")
    print("   Walking forward slowly")
    client.send_message("/input/Run", 0)
    client.send_message("/input/Vertical", 0.3)
    time.sleep(2)

    print("   Running forward fast")
    client.send_message("/input/Run", 1)
    client.send_message("/input/Vertical", 1.0)
    time.sleep(2)

    # Reset
    client.send_message("/input/Run", 0)
    client.send_message("/input/Vertical", 0.0)

    # Test 6: Try button-style input (press/release pattern)
    print("\n6. Testing button-style input (press/release):")
    button_tests = [
        ("/input/Jump", "Jump"),
        ("/input/Crouch", "Crouch"),
    ]

    for path, name in button_tests:
        print(f"   {name}: Press")
        client.send_message(path, 1)
        time.sleep(1)
        print(f"   {name}: Release")
        client.send_message(path, 0)
        time.sleep(1)

    # Test 7: Movement as avatar parameters
    print("\n7. Testing movement as avatar parameters:")
    param_tests = [
        ("/avatar/parameters/VelocityX", 1.0),
        ("/avatar/parameters/VelocityY", 0.0),
        ("/avatar/parameters/VelocityZ", 1.0),
    ]

    for path, value in param_tests:
        print(f"   Testing: {path} = {value}")
        client.send_message(path, value)
        time.sleep(1)

    # Reset
    for path, _ in param_tests:
        client.send_message(path, 0.0)

    print("\n" + "-" * 50)
    print("Movement test complete!")
    print("\nIf movement worked with any approach, note which one.")
    print("The server logs should show which OSC messages were received.")


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(description="Test VRChat OSC movement")
    parser.add_argument(
        "--host",
        default="192.168.0.152",
        help="VRChat host IP (default: 192.168.0.152)",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=9000,
        help="VRChat OSC port (default: 9000)",
    )

    args = parser.parse_args()

    try:
        test_movement_approaches(args.host, args.port)
    except Exception as e:
        print(f"Error: {e}")
        return 1

    return 0


if __name__ == "__main__":
    exit(main())
