#!/usr/bin/env python3
"""Monitor OSC messages from VRChat to understand input/output flow."""

import argparse
from datetime import datetime

from pythonosc import dispatcher, osc_server


class VRChatOSCMonitor:
    """Monitor and log all OSC messages from VRChat."""

    def __init__(self, port: int = 9001):
        """Initialize the monitor."""
        self.port = port
        self.message_count = 0
        self.unique_addresses: set[str] = set()

    def log_osc_message(self, address: str, *args):
        """Log any OSC message received."""
        self.message_count += 1
        self.unique_addresses.add(address)

        timestamp = datetime.now().strftime("%H:%M:%S.%f")[:-3]

        # Format the arguments
        if args:
            arg_str = ", ".join(str(arg) for arg in args)
            print(f"[{timestamp}] {address} = {arg_str}")
        else:
            print(f"[{timestamp}] {address}")

        # Special handling for interesting addresses
        if "input" in address.lower() or "velocity" in address.lower():
            print(f"  >> MOVEMENT-RELATED: {address}")
        elif "VRCEmote" in address:
            print(f"  >> EMOTE: {address} = {args[0] if args else 'no value'}")

    def start_monitoring(self):
        """Start the OSC server to monitor messages."""
        print(f"Starting VRChat OSC Monitor on port {self.port}")
        print("This will listen for messages FROM VRChat")
        print("-" * 50)

        # Create dispatcher
        disp = dispatcher.Dispatcher()

        # Register handler for all messages
        disp.set_default_handler(self.log_osc_message)

        # Create and start server
        server = osc_server.ThreadingOSCUDPServer(("0.0.0.0", self.port), disp)

        print(f"Listening on 0.0.0.0:{self.port}")
        print("Press Ctrl+C to stop")
        print("-" * 50)

        try:
            server.serve_forever()
        except KeyboardInterrupt:
            print("\n" + "-" * 50)
            print("Monitor stopped. Statistics:")
            print(f"  Total messages: {self.message_count}")
            print(f"  Unique addresses: {len(self.unique_addresses)}")
            if self.unique_addresses:
                print("\nUnique OSC addresses seen:")
                for addr in sorted(self.unique_addresses):
                    print(f"  - {addr}")
            server.shutdown()


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(description="Monitor OSC messages from VRChat")
    parser.add_argument(
        "--port",
        type=int,
        default=9001,
        help="Port to listen on for VRChat OSC output (default: 9001)",
    )

    args = parser.parse_args()

    monitor = VRChatOSCMonitor(args.port)

    try:
        monitor.start_monitoring()
    except Exception as e:
        print(f"Error: {e}")
        return 1

    return 0


if __name__ == "__main__":
    exit(main())
