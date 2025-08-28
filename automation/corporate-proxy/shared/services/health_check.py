#!/usr/bin/env python3
"""
Health check utility for ensuring services are ready
"""

import sys
import time
from typing import List, Tuple

import requests


def check_service_health(url: str, timeout: int = 1) -> bool:
    """Check if a service is healthy by hitting its health endpoint."""
    try:
        response = requests.get(url, timeout=timeout)
        return response.status_code == 200
    except (requests.ConnectionError, requests.Timeout):
        return False


def wait_for_services(services: List[Tuple[str, int]], max_wait: int = 30) -> bool:
    """
    Wait for multiple services to be ready.

    Args:
        services: List of (host, port) tuples
        max_wait: Maximum seconds to wait

    Returns:
        True if all services are ready, False if timeout
    """
    start_time = time.time()

    while time.time() - start_time < max_wait:
        all_ready = True

        for host, port in services:
            url = f"http://{host}:{port}/health"
            if not check_service_health(url):
                all_ready = False
                print(f"⏳ Waiting for {host}:{port}...")
                break

        if all_ready:
            print("✅ All services are ready!")
            return True

        time.sleep(1)

    print(f"❌ Timeout after {max_wait} seconds waiting for services")
    return False


if __name__ == "__main__":
    # Default services to check
    services_to_check = [
        ("localhost", 8050),  # Mock API
        ("localhost", 8052),  # Translation Wrapper
    ]

    # Parse command line arguments if provided
    if len(sys.argv) > 1:
        services_to_check = []
        for arg in sys.argv[1:]:
            if ":" in arg:
                host, port = arg.split(":")
                services_to_check.append((host, int(port)))

    # Wait for services and exit with appropriate code
    if wait_for_services(services_to_check):
        sys.exit(0)
    else:
        sys.exit(1)
