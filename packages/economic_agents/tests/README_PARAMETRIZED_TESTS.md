# Parametrized Backend Testing

This guide explains how to write tests that work with both mock and API backends using pytest parametrization.

## Overview

The framework supports two backend modes:
- **Mock Mode**: In-memory implementations (fast, no dependencies)
- **API Mode**: REST API microservices (realistic, production-like)

Tests can be written once and automatically run against both backends using pytest fixtures.

## Quick Start

### Using the `all_backends` Fixture

The simplest way to write a parametrized test:

```python
from economic_agents.agent.core.autonomous_agent import AutonomousAgent

def test_agent_behavior(all_backends):
    """Test runs in both mock and API modes.

    Args:
        all_backends: Fixture providing (wallet, compute, marketplace, investor)
    """
    # Unpack backends
    wallet, compute, marketplace, investor = all_backends

    # Create agent (same code for both modes!)
    agent = AutonomousAgent(
        wallet=wallet,
        compute=compute,
        marketplace=marketplace,
        config={"survival_buffer_hours": 10.0, "company_threshold": 150.0}
    )

    # Run your test
    agent.run(max_cycles=10)

    # Assertions work the same regardless of backend
    assert agent.state.balance > 0
    assert agent.state.tasks_completed > 0
```

That's it! The test will run in mock mode by default, and can optionally run in API mode.

## Available Fixtures

### Backend Mode Fixtures

- **`backend_mode`**: Parametrized string ('mock' or 'api')
- **`backend_config`**: BackendConfig object for the current mode
- **`all_backends`**: Tuple of (wallet, compute, marketplace, investor)

### Individual Backend Fixtures

If you only need specific backends:

- **`wallet_backend`**: Wallet implementation
- **`compute_backend`**: Compute implementation
- **`marketplace_backend`**: Marketplace implementation
- **`investor_portal_backend`**: Investor portal implementation (None in mock mode)

### Example: Using Individual Fixtures

```python
def test_wallet_only(wallet_backend):
    """Test that only needs wallet."""
    wallet = wallet_backend

    initial_balance = wallet.balance
    wallet.deposit(50.0, "test deposit")

    assert wallet.balance == initial_balance + 50.0
```

## Running Tests

### Default: Mock Mode Only

```bash
# Runs tests in mock mode (fast)
pytest tests/validation/test_24hour_survival.py
```

### Enable API Mode Testing

```bash
# Run tests in BOTH mock and API modes
RUN_API_TESTS=1 pytest tests/validation/test_24hour_survival.py

# Must have API services running first!
docker-compose up -d wallet-api compute-api marketplace-api investor-api
```

### Run Specific Backend Mode

```bash
# Mock mode only (explicit)
pytest tests/validation/test_24hour_survival.py -k "mock"

# API mode only (if RUN_API_TESTS=1)
RUN_API_TESTS=1 pytest tests/validation/test_24hour_survival.py -k "api"
```

## Writing New Parametrized Tests

### Pattern 1: Full Backend Parametrization

For tests that create agents and need all backends:

```python
def test_my_feature(all_backends):
    """Test description."""
    wallet, compute, marketplace, investor = all_backends

    # Your test code here
    agent = AutonomousAgent(
        wallet=wallet,
        compute=compute,
        marketplace=marketplace,
        config={"survival_buffer_hours": 10.0}
    )

    # Run test
    agent.run(max_cycles=5)

    # Assertions
    assert agent.state.cycles_completed == 5
```

### Pattern 2: Single Backend Testing

For tests that only need one backend type:

```python
def test_wallet_transactions(wallet_backend):
    """Test wallet in isolation."""
    wallet = wallet_backend

    # Test code
    wallet.deposit(100.0, "deposit")
    wallet.withdraw(30.0, "withdrawal")

    # Assertions
    assert wallet.balance == 70.0
```

### Pattern 3: Backend Config Access

For tests that need to know the backend mode:

```python
def test_with_mode_awareness(backend_config, all_backends):
    """Test that behaves differently based on mode."""
    wallet, compute, marketplace, investor = all_backends

    if backend_config.mode == BackendMode.API:
        # API-specific test logic
        print("Testing with real microservices")
    else:
        # Mock-specific test logic
        print("Testing with mock implementations")

    # Common test logic
    agent = AutonomousAgent(wallet=wallet, compute=compute, marketplace=marketplace)
    agent.run(max_cycles=5)
```

## Migration Guide

### Converting Existing Tests

**Before (hardcoded mocks):**
```python
from economic_agents.implementations.mock import MockWallet, MockCompute, MockMarketplace

def test_agent():
    wallet = MockWallet(initial_balance=200.0)
    compute = MockCompute(initial_hours=48.0, cost_per_hour=0.0)
    marketplace = MockMarketplace(seed=42)

    agent = AutonomousAgent(wallet, compute, marketplace, config={})
    agent.run(max_cycles=10)

    assert agent.state.balance > 0
```

**After (parametrized):**
```python
def test_agent(all_backends):
    wallet, compute, marketplace, investor = all_backends

    agent = AutonomousAgent(wallet, compute, marketplace, config={})
    agent.run(max_cycles=10)

    assert agent.state.balance > 0
```

**Changes needed:**
1. Add `all_backends` parameter to test function
2. Unpack backends from fixture
3. Remove direct Mock* imports
4. That's it!

## API Mode Requirements

For API mode tests to run, you need:

1. **Environment variable set**:
   ```bash
   export RUN_API_TESTS=1
   ```

2. **API services running**:
   ```bash
   docker-compose up -d wallet-api compute-api marketplace-api investor-api
   ```

3. **Services healthy**:
   ```bash
   # Check health
   curl http://localhost:8001/health  # Wallet
   curl http://localhost:8002/health  # Compute
   curl http://localhost:8003/health  # Marketplace
   curl http://localhost:8004/health  # Investor
   ```

If services aren't available, API tests will be automatically skipped.

## Best Practices

### 1. Write Mode-Agnostic Tests

Tests should work identically in both modes:

```python
# ✅ Good: Mode-agnostic
def test_balance_tracking(all_backends):
    wallet, compute, marketplace, investor = all_backends
    agent = AutonomousAgent(wallet, compute, marketplace, config={})

    initial = agent.state.balance
    agent.run(max_cycles=5)

    assert agent.state.balance != initial  # Works in both modes

# ❌ Bad: Assumes mock internals
def test_balance_tracking(all_backends):
    wallet, compute, marketplace, investor = all_backends

    # Assumes wallet is a MockWallet with _transactions attribute
    assert len(wallet._transactions) == 0  # Breaks in API mode!
```

### 2. Use Backend Config for Mode-Specific Logic

```python
def test_with_mode_handling(backend_config, all_backends):
    wallet, compute, marketplace, investor = all_backends

    # Mode-specific setup
    if backend_config.mode == BackendMode.API:
        timeout = 30.0  # API calls may be slower
    else:
        timeout = 1.0   # Mocks are instant

    # Common test logic
    agent = AutonomousAgent(wallet, compute, marketplace, config={})
    # ...
```

### 3. Keep Tests Fast by Default

By default, tests only run in mock mode (fast). API mode is opt-in via `RUN_API_TESTS=1`.

### 4. Document Backend Requirements

```python
def test_investor_proposals(all_backends):
    """Test investment proposal submission.

    Note: In API mode, requires investor-api service running.
    In mock mode, uses built-in investor evaluation.
    """
    wallet, compute, marketplace, investor = all_backends

    # Test works in both modes
    if investor is None:
        pytest.skip("Investor not available in this mode")

    # Test code...
```

## Troubleshooting

### Tests Skip in API Mode

**Problem**: Tests marked as "skipped" when `RUN_API_TESTS=1`

**Solution**: Check that API services are running and healthy:
```bash
docker-compose ps
curl http://localhost:8001/health
```

### Import Errors

**Problem**: `ImportError: cannot import name 'BackendConfig'`

**Solution**: Make sure you're using fixtures, not importing directly:
```python
# ❌ Don't import
from economic_agents.api.config import BackendConfig

# ✅ Use fixture
def test_something(backend_config):
    # backend_config is provided by fixture
    pass
```

### Tests Pass in Mock but Fail in API

**Problem**: Test works with mocks but fails with API backends

**Common causes**:
1. Assuming mock-specific attributes exist
2. Not handling API latency/timeouts
3. Making assumptions about internal state
4. Race conditions in async operations

**Solution**: Write tests that only rely on public interfaces.

## Examples

See these files for complete examples:
- `tests/validation/test_24hour_survival.py` - Full agent test
- `tests/integration/test_api_microservices.py` - API-specific tests
- `examples/backend_factory_example.py` - Non-test usage

## Summary

**Parametrized testing allows you to:**
- Write tests once, run in multiple modes
- Ensure mock and API backends behave identically
- Catch integration issues early
- Maintain fast default test runs (mock mode)
- Optionally validate against real APIs

**Key fixtures:**
- `all_backends` - Most common, provides all backends
- `backend_config` - When you need mode awareness
- Individual fixtures - When testing specific backends

**Remember:**
- Tests run in mock mode by default (fast)
- Set `RUN_API_TESTS=1` to include API mode
- API mode requires services running
- Write mode-agnostic tests using public interfaces only
