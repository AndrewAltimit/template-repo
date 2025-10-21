# Economic Agents Examples

This directory contains example scripts demonstrating different ways to use the Autonomous Economic Agents framework.

## Overview

The framework supports two backend modes:
- **Mock Mode**: Uses in-memory mock implementations (fast, no dependencies)
- **API Mode**: Uses REST API microservices (realistic, production-like)

All examples show how the same agent code works with both backends.

## Examples

### 1. Basic Mock Example (`basic_mock_example.py`)

**Purpose**: Simplest way to get started with mock implementations.

**Usage**:
```bash
python examples/basic_mock_example.py
```

**What it shows**:
- Creating mock backend implementations directly
- Initializing an autonomous agent
- Running decision cycles
- Viewing results

**Best for**: Quick experiments, testing, development

---

### 2. API Mode Example (`api_mode_example.py`)

**Purpose**: Using the agent with real API microservices.

**Prerequisites**:
```bash
# Start all API services
docker-compose up wallet-api compute-api marketplace-api investor-api

# Or start them individually
docker-compose up -d wallet-api
docker-compose up -d compute-api
docker-compose up -d marketplace-api
docker-compose up -d investor-api
```

**Usage**:
```bash
python examples/api_mode_example.py
```

**What it shows**:
- Configuring API endpoints
- Creating API-based backends using the factory
- Running agent with zero code visibility (API-only interaction)
- Same agent code as mock mode

**Best for**: Realistic simulation, testing deployment scenarios, research use

---

### 3. Backend Factory Example (`backend_factory_example.py`)

**Purpose**: Demonstrates the backend factory pattern for easy mode switching.

**Usage**:
```bash
python examples/backend_factory_example.py
```

**What it shows**:
- Using `BackendConfig` for configuration
- Switching between mock and API modes
- Environment-based configuration
- How identical agent code works with different backends

**Best for**: Understanding the architecture, production deployment patterns

---

## Quick Start

### Option 1: Mock Mode (No Setup Required)

```python
from economic_agents.api.factory import create_backends
from economic_agents.api.config import BackendConfig, BackendMode
from economic_agents.agent.core.autonomous_agent import AutonomousAgent

# Create mock backends
config = BackendConfig(mode=BackendMode.MOCK)
wallet, compute, marketplace, investor = create_backends(config)

# Create agent
agent = AutonomousAgent(
    wallet=wallet,
    compute=compute,
    marketplace=marketplace,
    config={"survival_buffer_hours": 10.0, "company_threshold": 150.0}
)

# Run
agent.run(max_cycles=10)
```

### Option 2: API Mode (Requires Services Running)

```python
from economic_agents.api.factory import create_backends
from economic_agents.api.config import BackendConfig, BackendMode, APIConfig

# Configure API endpoints
api_config = APIConfig(
    wallet_api_url="http://localhost:8001",
    compute_api_url="http://localhost:8002",
    marketplace_api_url="http://localhost:8003",
    investor_api_url="http://localhost:8004",
)

config = BackendConfig(
    mode=BackendMode.API,
    api_config=api_config,
    api_key="your_api_key"
)

# Create API backends
wallet, compute, marketplace, investor = create_backends(config)

# Create agent (same code as mock mode!)
agent = AutonomousAgent(
    wallet=wallet,
    compute=compute,
    marketplace=marketplace,
    config={"survival_buffer_hours": 10.0, "company_threshold": 150.0}
)

# Run (now interacting with APIs)
agent.run(max_cycles=10)
```

### Option 3: Environment-Based Configuration

```bash
# Set environment variables
export BACKEND_MODE=mock
export INITIAL_BALANCE=200.0
export INITIAL_COMPUTE_HOURS=48.0
```

```python
from economic_agents.api.factory import create_backends
from economic_agents.api.config import BackendConfig
from economic_agents.agent.core.autonomous_agent import AutonomousAgent

# Load config from environment
config = BackendConfig.from_env()
wallet, compute, marketplace, investor = create_backends(config)

# Create agent
agent = AutonomousAgent(
    wallet=wallet,
    compute=compute,
    marketplace=marketplace,
    config={"survival_buffer_hours": 10.0, "company_threshold": 150.0}
)

agent.run(max_cycles=10)
```

## Environment Variables

The framework supports these environment variables:

| Variable | Description | Default |
|----------|-------------|---------|
| `BACKEND_MODE` | Backend mode: `mock` or `api` | `mock` |
| `API_KEY` | API key for authentication | None |
| `WALLET_API_URL` | Wallet service URL | `http://localhost:8001` |
| `COMPUTE_API_URL` | Compute service URL | `http://localhost:8002` |
| `MARKETPLACE_API_URL` | Marketplace service URL | `http://localhost:8003` |
| `INVESTOR_API_URL` | Investor portal URL | `http://localhost:8004` |
| `INITIAL_BALANCE` | Starting wallet balance | `100.0` |
| `INITIAL_COMPUTE_HOURS` | Starting compute hours | `24.0` |
| `COMPUTE_COST_PER_HOUR` | Cost per compute hour | `0.0` |
| `MARKETPLACE_SEED` | Random seed for task generation | `None` |

## API Services

### Starting Services

```bash
# Start all services
docker-compose up -d wallet-api compute-api marketplace-api investor-api

# Check health
curl http://localhost:8001/health  # Wallet
curl http://localhost:8002/health  # Compute
curl http://localhost:8003/health  # Marketplace
curl http://localhost:8004/health  # Investor
```

### Service Ports

- **Wallet API**: 8001
- **Compute API**: 8002
- **Marketplace API**: 8003
- **Investor Portal API**: 8004

### API Documentation

Each service provides OpenAPI documentation:
- http://localhost:8001/docs (Wallet)
- http://localhost:8002/docs (Compute)
- http://localhost:8003/docs (Marketplace)
- http://localhost:8004/docs (Investor)

## Key Benefits of Backend Factory Pattern

1. **Zero Code Changes**: Same agent code works with mock or API backends
2. **Easy Testing**: Quickly switch to mock mode for fast iteration
3. **Production Ready**: Switch to API mode for realistic deployment
4. **Configuration-Based**: Control via environment variables or config objects
5. **Type Safety**: All backends implement the same interfaces

## Common Use Cases

### Development
```python
# Use mock mode for fast iteration
config = BackendConfig(mode=BackendMode.MOCK)
```

### Testing
```python
# Use deterministic seed for reproducible tests
config = BackendConfig(mode=BackendMode.MOCK, marketplace_seed=42)
```

### Research
```python
# Use API mode for realistic constraints
config = BackendConfig(mode=BackendMode.API, api_config=api_config)
```

### Production
```python
# Load from environment for deployment
config = BackendConfig.from_env()
```

## Next Steps

1. Start with `basic_mock_example.py` to understand the basics
2. Try `backend_factory_example.py` to see mode switching
3. Start API services and run `api_mode_example.py`
4. Review the main documentation in `../README.md`
5. Explore the scenarios in `../tests/validation/`

## Questions?

See the main documentation:
- Package README: `../README.md`
- Technical Specification: `../SPECIFICATION.md`
- API Reference: `../docs/`
