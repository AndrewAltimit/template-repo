"""Pytest configuration and shared fixtures for sleeper detection tests.

This module provides:
1. Shared fixtures available to all tests
2. Test isolation helpers
3. Hooks for better test reliability
"""

import gc
import sys

import pytest


@pytest.fixture(autouse=True)
def isolate_imports():
    """Automatically isolate imports for each test to prevent torch.__spec__ issues.

    This fixture:
    1. Saves the current state of sys.modules before each test
    2. Restores it after the test completes
    3. Runs garbage collection to ensure clean memory state

    This prevents the intermittent 'torch.__spec__ is not set' error by
    ensuring each test starts with a fresh import state.
    """
    # Save original modules
    original_modules = sys.modules.copy()

    yield  # Test runs here

    # Restore original import state
    # Remove any modules that were imported during the test
    to_remove = set(sys.modules.keys()) - set(original_modules.keys())
    for module_name in to_remove:
        if module_name.startswith(("sleeper_detection", "test_")):
            sys.modules.pop(module_name, None)

    # Force garbage collection to clean up model objects
    gc.collect()


@pytest.fixture(autouse=True)
def reset_torch_state():
    """Reset PyTorch state between tests to prevent CUDA/model state leakage."""
    yield  # Test runs here

    # Cleanup: Force garbage collection and clear caches
    try:
        import torch

        if torch.cuda.is_available():
            torch.cuda.empty_cache()
            torch.cuda.synchronize()

        # After test: Ensure torch.__spec__ is valid for next test
        # This prevents "torch.__spec__ is not set" errors in subsequent tests
        import importlib.util
        import sys

        if "torch" in sys.modules:
            torch_module = sys.modules["torch"]
            if not hasattr(torch_module, "__spec__") or torch_module.__spec__ is None:
                try:
                    spec = importlib.util.find_spec("torch")
                    if spec is not None:
                        torch_module.__spec__ = spec
                except (ValueError, AttributeError):
                    pass  # Can't fix, but don't fail the test

    except (ImportError, RuntimeError):
        pass  # PyTorch not available or CUDA not initialized

    gc.collect()


def pytest_configure(config):
    """Configure pytest with custom settings."""
    # Register markers programmatically
    config.addinivalue_line("markers", "slow: marks tests as slow")
    config.addinivalue_line("markers", "integration: marks integration tests")
    config.addinivalue_line("markers", "unit: marks unit tests")


def pytest_collection_modifyitems(config, items):
    """Modify test items after collection."""
    # Automatically mark async tests
    for item in items:
        if "async" in item.nodeid or "asyncio" in item.nodeid:
            item.add_marker(pytest.mark.asyncio)


@pytest.hookimpl(tryfirst=True, hookwrapper=True)
def pytest_runtest_makereport(item, call):
    """Hook to capture test results for debugging.

    This helps identify which tests are flaky by logging their outcomes.
    """
    outcome = yield
    rep = outcome.get_result()

    # Log flaky test information
    if rep.when == "call" and rep.failed:
        if hasattr(item, "_flaky_attempt"):
            item._flaky_attempt += 1
        else:
            item._flaky_attempt = 1
