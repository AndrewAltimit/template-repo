"""
Pytest configuration for corporate-proxy tests.

Some tests in this directory patch module-level CONFIG dictionaries in
gemini_proxy_wrapper and translation modules. When running with pytest-xdist
in parallel mode, these patches can conflict across workers.

This conftest groups tests that modify shared module state to run on the
same worker, preventing race conditions.
"""

import pytest


def pytest_collection_modifyitems(items):
    """
    Group tests that patch shared module-level CONFIG to run on same worker.

    Tests in test_per_model_modes.py patch gemini_proxy_wrapper.CONFIG and
    translation.CONFIG, which are module-level dictionaries. When running
    in parallel, these patches can interfere with each other.

    By adding xdist_group marker, pytest-xdist ensures all tests with the
    same group name run on the same worker.
    """
    for item in items:
        # Group all tests from test_per_model_modes.py together
        if "test_per_model_modes" in str(item.fspath):
            item.add_marker(pytest.mark.xdist_group("per_model_modes"))
