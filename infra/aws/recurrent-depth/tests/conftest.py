def pytest_configure(config):
    config.addinivalue_line("markers", "emulator: needs the local AWS Emulator (scripts/emulator-e2e.sh)")
