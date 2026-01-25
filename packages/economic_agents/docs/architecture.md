# Economic Agents Architecture

This document describes the architecture of the Economic Agents simulation framework.

## Overview

Economic Agents is a Rust-based simulation framework for autonomous AI agents operating in economic systems. The architecture follows a modular design with clear separation of concerns across 15 specialized crates.

```
┌─────────────────────────────────────────────────────────────────────────┐
│                              CLI / Dashboard                             │
│                    (economic-agents-cli, economic-agents-dashboard)      │
└─────────────────────────────────────────────────────────────────────────┘
                                      │
                                      ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                            Core Agent Logic                              │
│                         (economic-agents-core)                           │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐  ┌─────────────┐ │
│  │ Agent State  │  │   Decision   │  │   Strategy   │  │  LLM Engine │ │
│  │  Management  │  │    Engine    │  │   Selection  │  │ (Claude CLI)│ │
│  └──────────────┘  └──────────────┘  └──────────────┘  └─────────────┘ │
└─────────────────────────────────────────────────────────────────────────┘
                                      │
                    ┌─────────────────┼─────────────────┐
                    ▼                 ▼                 ▼
┌───────────────────────┐ ┌───────────────────┐ ┌───────────────────────┐
│   Company Module      │ │  Investment Module │ │    Tasks Module       │
│ (economic-agents-     │ │ (economic-agents-  │ │ (economic-agents-     │
│      company)         │ │    investment)     │ │      tasks)           │
│ ┌───────────────────┐ │ │ ┌───────────────┐  │ │ ┌─────────────────┐   │
│ │ Company Formation │ │ │ │   Investor    │  │ │ │  Task Catalog   │   │
│ │ Sub-Agent Manager │ │ │ │    Agents     │  │ │ │  Task Executor  │   │
│ │ Autonomous Agents │ │ │ │   Proposals   │  │ │ │ Solution Review │   │
│ └───────────────────┘ │ │ └───────────────┘  │ │ └─────────────────┘   │
└───────────────────────┘ └───────────────────┘ └───────────────────────┘
                                      │
                                      ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                          Backend Interfaces                              │
│                      (economic-agents-interfaces)                        │
│       ┌──────────┐          ┌──────────────┐          ┌─────────┐       │
│       │  Wallet  │          │  Marketplace │          │ Compute │       │
│       │  Trait   │          │    Trait     │          │  Trait  │       │
│       └──────────┘          └──────────────┘          └─────────┘       │
└─────────────────────────────────────────────────────────────────────────┘
                                      │
                    ┌─────────────────┴─────────────────┐
                    ▼                                   ▼
         ┌───────────────────┐               ┌───────────────────┐
         │   Mock Backends   │               │   Real Backends   │
         │ (economic-agents- │               │ (economic-agents- │
         │      mock)        │               │      api)         │
         └───────────────────┘               └───────────────────┘
```

## Crate Organization

### Core Crates

| Crate | Description |
|-------|-------------|
| `economic-agents-interfaces` | Core trait definitions (Wallet, Marketplace, Compute) |
| `economic-agents-core` | Agent logic, state management, decision engines |
| `economic-agents-mock` | Mock implementations for testing/simulation |
| `economic-agents-api` | REST API clients for production backends |

### Business Logic Crates

| Crate | Description |
|-------|-------------|
| `economic-agents-company` | Company formation, sub-agents, autonomous delegation |
| `economic-agents-investment` | Investment proposals, investor agents, funding |
| `economic-agents-tasks` | Task catalog, Claude CLI execution, code review |

### Simulation Crates

| Crate | Description |
|-------|-------------|
| `economic-agents-simulation` | Market dynamics, latency, competition |
| `economic-agents-time` | Time management, event scheduling |
| `economic-agents-monitoring` | Event bus, decision logging |

### Observability Crates

| Crate | Description |
|-------|-------------|
| `economic-agents-observability` | Behavioral analysis (4 specialized analyzers) |
| `economic-agents-persistence` | State persistence (JSON, SQLite) |
| `economic-agents-reports` | Report generation (executive, technical, audit) |

### Interface Crates

| Crate | Description |
|-------|-------------|
| `economic-agents-dashboard` | REST API + WebSocket backend |
| `economic-agents-cli` | Command-line interface |

## Core Concepts

### Agent Lifecycle

```
┌─────────┐     ┌──────────┐     ┌─────────────┐     ┌──────────┐
│  Init   │────▶│  Decide  │────▶│   Execute   │────▶│  Update  │
│         │     │          │     │             │     │  State   │
└─────────┘     └──────────┘     └─────────────┘     └──────────┘
     ▲                                                     │
     └─────────────────────────────────────────────────────┘
                         (next cycle)
```

1. **Initialization**: Agent created with configuration, backends attached
2. **Decision**: Decision engine evaluates state, selects action
3. **Execution**: Action performed (task work, company work, investment)
4. **State Update**: Results recorded, cycle advances

### Decision Engine

Two decision engine implementations:

**Rule-Based Engine** (`RuleBasedEngine`):
- Deterministic decisions based on state thresholds
- Fast, predictable behavior
- Good for testing and baseline comparisons

**LLM Engine** (`LlmDecisionEngine`):
- Uses Claude CLI for intelligent decisions
- Considers context, reasoning, and strategy
- Falls back to rule-based if Claude unavailable

### Backend Abstraction

The `Wallet`, `Marketplace`, and `Compute` traits define async interfaces:

```rust
#[async_trait]
pub trait Wallet: Send + Sync {
    async fn get_balance(&self) -> Result<f64>;
    async fn send_payment(&self, to: &str, amount: f64, memo: Option<&str>) -> Result<Transaction>;
    async fn receive_payment(&self, from: Option<&str>, amount: f64, memo: Option<&str>) -> Result<Transaction>;
}
```

This abstraction enables:
- **Mock backends**: In-memory simulation for testing
- **Real backends**: HTTP clients for production services
- **Seamless switching**: Same agent code works with both

### Sub-Agent Autonomy

When an agent forms a company, it creates autonomous sub-agents:

```
┌─────────────────────────────────────────────┐
│              Parent Agent                    │
│  ┌─────────────────────────────────────┐    │
│  │     AutonomousSubAgentManager       │    │
│  │  ┌───────────┐ ┌───────────┐        │    │
│  │  │Tech Lead  │ │Operations │ ...    │    │
│  │  │(SME)      │ │(IC)       │        │    │
│  │  │Budget:$X  │ │Budget:$Y  │        │    │
│  │  └───────────┘ └───────────┘        │    │
│  └─────────────────────────────────────┘    │
└─────────────────────────────────────────────┘
```

Sub-agents have:
- **Budget allocation**: Capital and compute hour limits
- **Backend access**: Can interact with marketplace independently
- **Role-based behavior**: IC/SME find own tasks; executives handle delegations
- **Autonomous cycles**: Run work cycles during parent's company work phase

## Data Flow

### Task Completion Flow

```
Agent                 Marketplace              Compute               Wallet
  │                       │                       │                     │
  │  list_available_tasks │                       │                     │
  │──────────────────────▶│                       │                     │
  │◀──────────────────────│                       │                     │
  │                       │                       │                     │
  │     claim_task        │                       │                     │
  │──────────────────────▶│                       │                     │
  │◀──────────────────────│                       │                     │
  │                       │                       │                     │
  │                       │    consume_time       │                     │
  │                       │──────────────────────▶│                     │
  │                       │◀──────────────────────│                     │
  │                       │                       │                     │
  │   submit_solution     │                       │                     │
  │──────────────────────▶│                       │                     │
  │◀──────────────────────│                       │                     │
  │                       │                       │                     │
  │                       │                       │   receive_payment   │
  │                       │                       │────────────────────▶│
  │                       │                       │◀────────────────────│
```

### Event Flow

```
┌────────────┐     ┌───────────┐     ┌─────────────┐     ┌────────────┐
│   Agent    │────▶│ Event Bus │────▶│  Dashboard  │────▶│ WebSocket  │
│  Actions   │     │           │     │   State     │     │  Clients   │
└────────────┘     └───────────┘     └─────────────┘     └────────────┘
                         │
                         ▼
                  ┌─────────────┐
                  │  Decision   │
                  │   Logger    │
                  └─────────────┘
```

## Configuration

### Agent Configuration

```rust
AgentConfig {
    engine_type: EngineType::Llm,        // RuleBased or Llm
    mode: OperatingMode::Company,         // Survival or Company
    personality: Personality::Balanced,   // RiskAverse, Balanced, Aggressive
    task_selection_strategy: TaskSelectionStrategy::SkillMatch,
    survival_buffer_hours: 24.0,
    company_threshold: 100.0,
    max_cycles: Some(100),
    skills: HashMap::new(),
}
```

### Mock Backend Configuration

```rust
MockBackendConfig {
    initial_balance: 50.0,
    initial_compute_hours: 24.0,
    compute_cost_per_hour: 0.10,
    initial_tasks: 10,
}
```

## Simulation Features

### Market Dynamics

The simulation crate provides realistic market conditions:

- **Market Phases**: Bull, Bear, Crash, Recovery
- **Task Availability**: Varies with market conditions
- **Competition**: Simulated competing agents claim tasks
- **Reputation Tiers**: Bronze → Silver → Gold → Platinum

### Latency Simulation

Configurable delays for API calls to simulate network conditions:

```rust
LatencyConfig {
    base_latency_ms: 50,
    jitter_ms: 20,
    failure_rate: 0.01,
}
```

## Observability

### Four Specialized Analyzers

1. **DecisionPatternAnalyzer**: Tracks decision trends, strategic consistency
2. **LLMQualityAnalyzer**: Evaluates LLM reasoning quality, detects hallucinations
3. **RiskProfiler**: Categorizes risk tolerance, identifies crisis behavior
4. **EmergentBehaviorDetector**: Finds novel strategies, unexpected patterns

### Metrics

- Counters: tasks_completed, decisions_made, etc.
- Gauges: balance, compute_hours, reputation
- Prometheus-compatible export

## Deployment

### Docker Compose

```yaml
services:
  dashboard:
    build: .
    command: ["dashboard", "--port", "8080"]
    ports:
      - "8080:8080"

  agent:
    build: .
    command: ["run", "--config", "/config/agent.yml"]
    volumes:
      - ./config:/config
```

### CLI Usage

```bash
# Run simulation
economic-agents run --config agent.yml

# Start dashboard
economic-agents dashboard --port 8080

# Run predefined scenario
economic-agents scenario survival_mode

# Generate reports
economic-agents report --type executive --output report.json
```

## Extension Points

### Adding New Backends

Implement the three core traits:

```rust
#[async_trait]
impl Wallet for MyWallet { ... }

#[async_trait]
impl Marketplace for MyMarketplace { ... }

#[async_trait]
impl Compute for MyCompute { ... }
```

### Adding New Decision Engines

Implement the `DecisionEngine` trait:

```rust
#[async_trait]
impl DecisionEngine for MyEngine {
    async fn decide(&self, state: &AgentState, config: &AgentConfig) -> Result<Decision>;
    async fn allocate_resources(&self, state: &AgentState, config: &AgentConfig) -> Result<ResourceAllocation>;
}
```

### Adding New Analyzers

Implement analysis in the observability crate following the existing patterns.
