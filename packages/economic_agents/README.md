# Economic Agents (Rust)

> A simulation framework for autonomous AI agents operating in economic systems. Agents autonomously complete tasks, earn simulated currency, form companies, create sub-agents, and seek investment.

## Overview

This framework simulates autonomous AI economic activity for governance research. The goal is not to argue that agent entrepreneurship is good or bad, but to make concrete a capability that public field experiments and agent payment infrastructure show **already exists today**, and to show that current legal and regulatory frameworks have no answer for it.

**The gap is not in capability. It's in governance.**

Agents interact with in-memory mock backends, or with local HTTP services that wrap the same mocks, for:

- **Marketplace**: Task discovery, claiming, and completion
- **Wallet**: Simulated cryptocurrency transactions
- **Compute**: Resource management

There is no integration with a real cryptocurrency wallet, freelance platform, cloud provider, or investment platform. The only real-world component is the `economic-agents-tasks` crate, which can send a fixed catalog of coding challenges to the Claude CLI and test the returned Python. That crate is a standalone library: the agent loop does not call it, and the agent's own task work is simulated (see below). This is a deliberate dual-use choice, and decision logs record the agent's *stated* reasoning, which is evidence rather than ground truth. See [Economic Implications](./docs/economic-implications.md#why-this-research-exists) for the rationale, its limits, and references.

### What Is LLM-Driven and What Is Rule-Based

Most of the simulation is deterministic rules and templates. Only two components call an LLM:

| Component | Where | How it works |
|-----------|-------|--------------|
| Top-level agent decision (what to do this cycle) and resource allocation | `economic-agents-core` (`LlmDecisionEngine`) | **LLM** (Claude CLI) when `engine_type` is `llm`; falls back to the rule-based engine if the CLI is missing or its reply cannot be parsed. The default engine is rule-based. |
| Coding-challenge solutions | `economic-agents-tasks` (`TaskExecutor`) | **LLM** (Claude CLI). Standalone library, not called by the agent loop. |
| Rule-based decision engine | `economic-agents-core` (`RuleBasedEngine`) | Threshold rules on balance and compute hours. |
| Agent task work in the simulation | `economic-agents-core` (`generate_solution`) | Claims a mock task and submits a placeholder string; no work is performed. The mock marketplace (`MockMarketplace`) never inspects content and approves every submission with a random quality score between 0.7 and 1.0. |
| Sub-agent executive decisions (CEO, CTO, CFO, ...) | `economic-agents-company` (`make_decision`) | Rule-based templates keyed on a few metrics, returning canned action items. |
| Board members, OKRs, strategic plans, risk mitigations | `economic-agents-company` | Fixed templates per role. |
| Sub-agent task execution | `economic-agents-company` (`autonomy.rs`) | Random quality score derived from the sub-agent's performance value. |
| Company revenue and stage transitions | `economic-agents-core` | Fixed formulas and stage rules. |
| Investor evaluation | `economic-agents-core` (`investment::InvestorAgent`) | Rule-based: budget bounds plus a minimum projected-return multiple per risk tolerance. No LLM evaluation. The agent's proposal always projects a fixed 3x return (`SIMULATED_PROJECTED_RETURN_MULTIPLE`), not one derived from company financials, so outcomes turn on the budget bounds alone. |
| Market dynamics, competition, reputation, feedback, latency | `economic-agents-simulation` | Random or formula-based library components (see [Simulation Features](#simulation-features)). |

**Confidence values** attached to rule-based and template decisions are fixed constants, not estimates: the rule-based engine reports 0.9, 0.75, or 0.6 depending on personality, and sub-agent executive decisions report hard-coded values such as 0.85 or 0.9. Only the LLM engine's confidence comes from the model (as a self-reported number, clamped to 0 to 1).

## Workspace Structure

```
packages/economic_agents/
├── Cargo.toml              # Workspace configuration
├── Dockerfile              # Multi-stage Docker build
├── docker-compose.yml      # Service orchestration
├── deny.toml               # License/security audit config
└── crates/
    ├── economic-agents-interfaces/    # Core traits (Wallet, Marketplace, Compute)
    ├── economic-agents-core/          # Agent logic, decision engines, investment
    ├── economic-agents-mock/          # Mock implementations for testing
    ├── economic-agents-api/           # REST API clients and services
    ├── economic-agents-company/       # Company formation and management
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

The `economic-agents-simulation` crate provides simple stochastic building blocks:

- **Latency Simulation**: Configurable delays for API calls
- **Market Dynamics**: Random transitions between bull/stable/bear/crash phases with fixed reward multipliers
- **Competition**: A per-task probability that a simulated competitor claims it
- **Reputation System**: Tier-based access to higher-value tasks
- **Feedback Generation**: Templated submission feedback

These are library components with unit tests. They are not yet wired into the agent loop: the CLI scenario runner advances a `MarketDynamics` instance between agents, but its phase does not feed back into the mock marketplace, and the competition, reputation, feedback, and latency simulators are not called by the agent.

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

`SolutionReviewer` runs the generated Python with process-level hardening (cleared environment, `python -I -S`, a fresh temp working directory, a wall-clock timeout that kills the process group, capped output, and on Unix `RLIMIT_CPU`/`RLIMIT_AS`/`RLIMIT_FSIZE`). This is **not a security boundary**; see [Security Note](#security-note). Rust solutions are type-checked with `rustc --emit=metadata` when `rustc` is available; if it is not, the check is reported as skipped and the review cannot succeed.

The task catalog includes 13 challenges across difficulty levels:
- **Easy** (0.1-0.3): FizzBuzz, Palindrome, Reverse String, Factorial, Fibonacci, Prime Checker
- **Medium** (0.4-0.6): Binary Search, Anagram Checker, Two Sum, Merge Sorted Arrays
- **Hard** (0.7-0.9): Longest Substring, Valid Parentheses, LRU Cache

## Security Note

Two parts of this package execute or delegate to code you do not control. Treat both as unsafe outside a disposable environment.

**Claude CLI permissions.** `LlmDecisionEngine` and `TaskExecutor` invoke `claude --print`. They pass `--dangerously-skip-permissions` **only** when you opt in, either by setting `ECONOMIC_AGENTS_SKIP_PERMISSIONS=1` or by setting `skip_permissions: true` on `LlmConfig` / `ExecutorConfig`, and they log a warning on every call when it is enabled. That flag disables every permission check in the CLI: any tool the model decides to use (shell commands, file edits, network requests) runs without approval, with the harness user's privileges and credentials. The prompts in this package only ask for text or JSON, so the flag is not needed for normal operation. If you enable it, run the harness only inside a disposable container with no credentials mounted (no cloud keys, SSH keys, or tokens beyond the Claude API key itself) and with network egress restricted.

**Executing generated code.** `SolutionReviewer` runs LLM-generated Python. Its hardening limits accidents (runaway loops, huge output, inherited secrets in environment variables) but the code still runs as the harness user, sees the same filesystem, and has network access. For untrusted code, run the harness in a container with `--network=none` and no credentials, or set `ReviewerConfig::sandbox_command` so each interpreter call is wrapped in a container, for example `["docker", "run", "--rm", "-i", "--network=none", "--memory=256m", "python:3.12-slim"]`.

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

- **[Economic Implications](./docs/economic-implications.md)** - Governance, policy, and societal implications
- **[Architecture Guide](./docs/architecture.md)** - System design, crate organization, data flow
- **[Dashboard API Reference](./docs/dashboard-api.md)** - REST API and WebSocket documentation

## Docker

Run with Docker Compose:

```bash
# Run the CLI
docker compose run economic-agents-cli run --config /home/agent/config/agent.yml

# Start the dashboard
docker compose up dashboard

# Run a scenario
docker compose --profile scenario run scenario
```

## CI/CD

Run quality checks via the automation CLI:

```bash
automation-cli ci run econ-full      # fmt + clippy + test
automation-cli ci run econ-doc       # Generate API docs
automation-cli ci run econ-coverage  # Test coverage
```

## License

Part of the template-repo project. See repository LICENSE file.
