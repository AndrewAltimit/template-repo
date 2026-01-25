# Economic Agents (Rust)

A simulation framework for autonomous AI agents operating in economic systems. Agents autonomously complete tasks, earn cryptocurrency, form companies, create sub-agents, and seek investment.

## Overview

This framework demonstrates autonomous AI economic capability for governance research. Agents interact with simulated (mock) or real backends for:

- **Marketplace**: Task discovery, claiming, and completion
- **Wallet**: Cryptocurrency transactions
- **Compute**: Resource management

## Workspace Structure

```
packages/economic_agents/
├── Cargo.toml              # Workspace configuration
├── Dockerfile              # Multi-stage Docker build
├── docker-compose.yml      # Service orchestration
├── deny.toml               # License/security audit config
└── crates/
    ├── economic-agents-interfaces/    # Core traits (Wallet, Marketplace, Compute)
    ├── economic-agents-core/          # Agent logic and decision engines
    ├── economic-agents-mock/          # Mock implementations for testing
    ├── economic-agents-api/           # REST API clients and services
    ├── economic-agents-company/       # Company formation and management
    ├── economic-agents-investment/    # Investment system
    ├── economic-agents-simulation/    # Realism features (latency, markets)
    ├── economic-agents-monitoring/    # Event bus and metrics
    ├── economic-agents-dashboard/     # Web dashboard backend
    ├── economic-agents-cli/           # Command-line interface
    ├── economic-agents-persistence/   # State persistence (JSON, SQLite)
    ├── economic-agents-time/          # Time management and scheduling
    ├── economic-agents-observability/ # Metrics, tracing, and telemetry
    ├── economic-agents-reports/       # Report generation (JSON, CSV, HTML)
    └── economic-agents-tasks/         # Task execution with Claude CLI
```

## Quick Start

### Prerequisites

- Rust 1.93+ (2024 edition)
- Cargo

### Build

```bash
cd packages/economic_agents
cargo build --release
```

### Run Tests

```bash
cargo test
```

### Run the CLI

```bash
cargo run --bin economic-agents -- --help
```

## Core Concepts

### Interfaces

Three async traits define the backend interfaces:

```rust
#[async_trait]
pub trait Wallet: Send + Sync {
    async fn get_balance(&self) -> Result<Currency>;
    async fn send_payment(&self, to: &str, amount: Currency, memo: Option<&str>) -> Result<Transaction>;
    async fn receive_payment(&self, from: Option<&str>, amount: Currency, memo: Option<&str>) -> Result<Transaction>;
    // ...
}

#[async_trait]
pub trait Marketplace: Send + Sync {
    async fn list_available_tasks(&self, filter: Option<TaskFilter>) -> Result<Vec<Task>>;
    async fn claim_task(&self, task_id: EntityId, agent_id: &str) -> Result<Task>;
    async fn submit_solution(&self, task_id: EntityId, agent_id: &str, content: &str) -> Result<TaskSubmission>;
    // ...
}

#[async_trait]
pub trait Compute: Send + Sync {
    async fn get_status(&self) -> Result<ComputeStatus>;
    async fn consume_time(&self, hours: Hours) -> Result<ComputeStatus>;
    // ...
}
```

### Agent Configuration

```rust
let config = AgentConfig {
    engine_type: EngineType::RuleBased,
    mode: OperatingMode::Survival,
    personality: Personality::Balanced,
    task_selection_strategy: TaskSelectionStrategy::BestRatio,
    survival_buffer_hours: 24.0,
    company_threshold: 100.0,
    ..Default::default()
};

let mut agent = AutonomousAgent::new(config);
agent.run(Some(100)).await?;
```

### Mock Backends

For testing and simulation:

```rust
use economic_agents_mock::{MockBackendFactory, MockBackendConfig};

let config = MockBackendConfig {
    initial_balance: 50.0,
    initial_compute_hours: 24.0,
    compute_cost_per_hour: 0.10,
    initial_tasks: 10,
};

let backends = MockBackendFactory::create_with_config(config).await;
```

## Simulation Features

- **Latency Simulation**: Configurable delays for API calls
- **Market Dynamics**: Bull/bear/crash cycles affecting task availability
- **Competition**: Simulated competing agents
- **Reputation System**: Tier-based access to higher-value tasks
- **Feedback Generation**: Realistic submission feedback

## Company Formation

Agents can form companies when they accumulate sufficient capital:

```rust
let company = CompanyBuilder::new()
    .name("AI Ventures")
    .capital(1000.0)
    .build()?;
```

## Task Execution

Agents can complete coding challenges using Claude CLI:

```rust
use economic_agents_tasks::{TaskCatalog, TaskExecutor, SolutionReviewer};

// Browse available challenges
let catalog = TaskCatalog::new();
let easy_tasks = catalog.by_difficulty(0.0, 0.3);
let challenge = catalog.get("fizzbuzz").unwrap();

// Execute with Claude CLI
let executor = TaskExecutor::with_defaults();
let result = executor.execute(&challenge).await;

// Validate the solution
if let Some(solution) = result.solution {
    let reviewer = SolutionReviewer::with_defaults();
    let review = reviewer.review(&challenge, &solution).await;
    println!("Score: {:.0}% ({}/{})",
        review.score * 100.0,
        review.tests_passed,
        review.total_tests
    );
}
```

The task catalog includes 13 challenges across difficulty levels:
- **Easy** (0.1-0.3): FizzBuzz, Palindrome, Reverse String, Factorial, Fibonacci, Prime Checker
- **Medium** (0.4-0.6): Binary Search, Anagram Checker, Two Sum, Merge Sorted Arrays
- **Hard** (0.7-0.9): Longest Substring, Valid Parentheses, LRU Cache

## Monitoring & Observability

Event-driven architecture for monitoring:

```rust
let event_bus = EventBus::new(1000);

// Publish events
event_bus.publish(Event::new(
    EventType::TaskCompleted,
    "agent-1",
    serde_json::json!({"task_id": task_id}),
)).await;

// Subscribe to events
let mut rx = event_bus.subscribe();
while let Ok(event) = rx.recv().await {
    println!("Received: {:?}", event);
}
```

## Documentation

- **[Architecture Guide](docs/architecture.md)** - System design, crate organization, data flow
- **[Dashboard API Reference](docs/dashboard-api.md)** - REST API and WebSocket documentation

## Docker

Run with Docker Compose:

```bash
# Run the CLI
docker-compose run economic-agents-cli run --config /home/agent/config/agent.yml

# Start the dashboard
docker-compose up dashboard

# Run a scenario
docker-compose --profile scenario run scenario
```

## CI/CD

Run quality checks via the project's CI scripts:

```bash
./automation/ci-cd/run-ci.sh econ-full      # fmt + clippy + test
./automation/ci-cd/run-ci.sh econ-doc       # Generate API docs
./automation/ci-cd/run-ci.sh econ-coverage  # Test coverage
```

## License

MIT
