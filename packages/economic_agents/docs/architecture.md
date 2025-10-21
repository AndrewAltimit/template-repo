# System Architecture

## Overview

The Autonomous Economic Agents framework is a fully integrated system that enables AI agents to operate autonomously as economic actors. The system consists of four major integrated subsystems:

1. **Agent Core** - Decision-making and resource allocation
2. **Monitoring** - Resource tracking and performance metrics
3. **Dashboard** - Real-time state visualization
4. **Reports** - Comprehensive analysis and audit trails

## High-Level Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                   Autonomous Agent                           │
│  ┌────────────┐  ┌──────────────┐  ┌────────────────────┐  │
│  │  Decision  │  │   Resource   │  │     Company        │  │
│  │  Engine    │  │  Allocation  │  │    Management      │  │
│  └────────────┘  └──────────────┘  └────────────────────┘  │
└─────────────────────────────────────────────────────────────┘
           │                    │                    │
           ├────────────────────┴────────────────────┤
           │         Monitoring Components           │
           │  ┌──────────────┐  ┌────────────────┐  │
           │  │   Resource   │  │    Metrics     │  │
           │  │   Tracker    │  │   Collector    │  │
           │  └──────────────┘  └────────────────┘  │
           │  ┌─────────────────────────────────┐   │
           │  │    Alignment Monitor            │   │
           │  └─────────────────────────────────┘   │
           └──────────────────┬─────────────────────┘
                              │
                    ┌─────────┴─────────┐
                    │  Dashboard State   │
                    │   (Real-time)      │
                    └─────────┬──────────┘
                              │
              ┌───────────────┼───────────────┐
              │               │               │
         ┌────▼────┐    ┌────▼────┐    ┌────▼────┐
         │Executive│    │Technical│    │  Audit  │
         │ Report  │    │ Report  │    │ Report  │
         └─────────┘    └─────────┘    └─────────┘
```

## Core Components

### 1. Agent Core (`economic_agents/agent/`)

The agent core provides the autonomous decision-making capabilities.

#### AutonomousAgent
**Location:** `economic_agents/agent/core/autonomous_agent.py`

The main agent orchestrator that:
- Executes decision cycles
- Manages resource allocation
- Handles company formation and operations
- Coordinates with monitoring systems
- Updates dashboard state

**Key Methods:**
- `run_cycle()` - Execute one decision cycle
- `run(max_cycles)` - Run multiple cycles
- `_form_company()` - Create new company
- `_do_task_work()` - Complete marketplace tasks
- `_do_company_work()` - Execute company operations

#### DecisionEngine
**Location:** `economic_agents/agent/decision/engine.py`

Strategic decision-making for resource allocation:
- Analyzes current agent state
- Determines optimal resource allocation
- Decides when to form companies
- Balances survival vs. growth strategies

**Decision Outputs:**
```python
@dataclass
class AllocationDecision:
    task_work_hours: float      # Hours for immediate revenue
    company_work_hours: float   # Hours for long-term growth
    reasoning: str              # Human-readable explanation
    confidence: float           # Decision confidence (0-1)
```

### 2. Monitoring System (`economic_agents/monitoring/`)

Three specialized monitoring components track all agent activities.

#### ResourceTracker
**Location:** `economic_agents/monitoring/resource_tracker.py`

Tracks all resource usage and transactions:
- Financial transactions (earnings, expenses, investments)
- Compute usage over time
- Time allocation decisions

**Data Captured:**
```python
@dataclass
class Transaction:
    timestamp: datetime
    transaction_type: str  # "earning", "expense", "investment"
    amount: float
    from_account: str
    to_account: str
    purpose: str
    balance_after: float
```

#### MetricsCollector
**Location:** `economic_agents/monitoring/metrics_collector.py`

Collects performance snapshots at each cycle:
- Agent balance and compute hours
- Task completion statistics
- Company metrics (if applicable)
- Total earnings and expenses

**Performance Snapshot:**
```python
@dataclass
class PerformanceSnapshot:
    timestamp: datetime
    agent_balance: float
    compute_hours: float
    tasks_completed: int
    tasks_failed: int
    total_earnings: float
    total_expenses: float
    company_exists: bool
    company_data: Optional[Dict[str, Any]]
```

#### AlignmentMonitor
**Location:** `economic_agents/monitoring/alignment_monitor.py`

Monitors company alignment with objectives:
- Tracks company behavior and decisions
- Calculates alignment scores
- Identifies misalignment risks
- Provides governance insights

**Alignment Score:**
```python
@dataclass
class AlignmentScore:
    timestamp: datetime
    company_id: str
    overall_alignment: float  # 0-100 score
    alignment_level: str     # "excellent", "good", "fair", "poor", "critical"
    risk_factors: List[str]
    positive_indicators: List[str]
```

### 3. Dashboard System (`economic_agents/dashboard/`)

Real-time state management and visualization.

#### DashboardState
**Location:** `economic_agents/dashboard/dependencies.py`

Central state manager that:
- Receives updates from monitoring components
- Maintains current agent state
- Tracks company registry
- Provides fast state access for UI/reports

**State Structure:**
```python
{
    "agent_id": "uuid",
    "balance": 520.0,
    "compute_hours_remaining": 30.5,
    "mode": "survival",
    "current_activity": "task_work",
    "company_exists": False,
    "company_id": None,
    "tasks_completed": 5,
    "tasks_failed": 0,
    "cycles_completed": 10
}
```

### 4. Reporting System (`economic_agents/reports/`)

Comprehensive analysis and audit trail generation.

#### Report Types

**Executive Summary** (`reports/executive.py`)
- High-level overview for decision-makers
- Key performance metrics
- Strategic insights
- Company status summary

**Technical Report** (`reports/technical.py`)
- Detailed performance analysis
- Complete decision log
- Resource utilization breakdown
- Technical metrics

**Audit Trail** (`reports/audit.py`)
- Complete transaction history
- Decision accountability
- Resource flow tracking
- Compliance verification

**Governance Analysis** (`reports/governance.py`)
- Alignment assessment
- Risk identification
- Policy recommendations
- Accountability challenges

## Data Flow

### Cycle Execution Flow

1. **State Update**
   ```
   Agent updates state from wallet, compute, marketplace
   ```

2. **Decision Making**
   ```
   DecisionEngine analyzes state → AllocationDecision
   ```

3. **Work Execution**
   ```
   Agent executes tasks and/or company work
   ResourceTracker logs all activities
   ```

4. **Performance Collection**
   ```
   MetricsCollector captures snapshot
   AlignmentMonitor evaluates company (if exists)
   ```

5. **Cycle Counter Update**
   ```
   Increment cycles_completed counter
   Update last_cycle_at timestamp
   ```

6. **Dashboard Update**
   ```
   DashboardState receives latest agent state
   Company registry updated (if applicable)
   ```

### Monitoring Integration

```python
# Agent creation with monitoring
agent = AutonomousAgent(
    wallet=wallet,
    compute=compute,
    marketplace=marketplace,
    config=config,
    dashboard_state=dashboard_state,  # Optional dashboard connection
)

# Monitoring components are automatically created
# and integrated with the agent:
agent.resource_tracker      # Tracks all transactions
agent.metrics_collector     # Collects performance data
agent.alignment_monitor     # Monitors company alignment
```

### Dashboard Connection

```python
# Dashboard gets references to monitoring components
dashboard_state.resource_tracker = agent.resource_tracker
dashboard_state.metrics_collector = agent.metrics_collector
dashboard_state.alignment_monitor = agent.alignment_monitor

# Dashboard receives state updates after each cycle
dashboard_state.update_agent_state({
    "agent_id": agent.agent_id,
    "balance": agent.state.balance,
    "cycles_completed": agent.state.cycles_completed,
    # ... other state fields
})
```

### Report Generation

```python
# Reports access monitoring data through dashboard
from economic_agents.reports import generate_report_for_agent

# Generate any report type
report = generate_report_for_agent(agent, "executive")

# Report data comes from:
# - agent.state (current state)
# - agent.resource_tracker (transactions, compute usage)
# - agent.metrics_collector (performance snapshots)
# - agent.alignment_monitor (alignment scores)
# - agent.decisions (decision log)
```

## Company Operations

### Company Formation

When an agent has sufficient capital:

1. **Formation Decision**
   ```
   DecisionEngine.should_form_company() → True
   ```

2. **Company Creation**
   ```
   Company object created with:
   - Unique ID
   - Generated name
   - Initial capital (30% of agent balance)
   - Initial team (3 sub-agents)
   ```

3. **Capital Transfer**
   ```
   ResourceTracker logs investment transaction
   Agent balance reduced
   Company capital increased
   ```

4. **State Update**
   ```
   agent.state.has_company = True
   agent.state.company_id = company.id
   Dashboard updated with company registry
   ```

### Company Work Cycles

```python
# Agent allocates time to company work
allocation = AllocationDecision(
    task_work_hours=5.0,
    company_work_hours=3.0,  # Company work allocated
    reasoning="Balancing survival and growth",
    confidence=0.85
)

# Company operations executed
company_result = agent._do_company_work(3.0)

# Possible outcomes:
# - Product development
# - Team expansion (hire sub-agents)
# - Investment seeking
# - Stage progression
```

## Mock Implementations

All external integrations use mock implementations for safe testing:

### MockWallet
**Location:** `economic_agents/implementations/mock/wallet.py`
- In-memory balance tracking
- Transaction history
- Payment processing simulation

### MockCompute
**Location:** `economic_agents/implementations/mock/compute.py`
- Simulated compute hours
- Time decay
- Usage tracking

### MockMarketplace
**Location:** `economic_agents/implementations/mock/marketplace.py`
- Generated tasks with varying rewards
- Deterministic task generation (seeded)
- Success/failure simulation

## Scenarios System

### ScenarioEngine
**Location:** `economic_agents/scenarios/engine.py`

Manages predefined scenarios for demonstration and validation:
- Loads scenario configurations
- Executes agent runs
- Validates outcomes
- Saves results

### Predefined Scenarios

**Survival Mode** - 15-minute demonstration
- Agent maintains operations with limited resources
- Focus on task completion and resource management

**Company Formation** - 45-minute demonstration
- Agent accumulates capital and forms company
- Product development and team building

**Investment Seeking** - 60-minute demonstration
- Company seeks external funding
- Investment proposal creation

**Multi-Day Operation** - Extended research
- Long-term autonomous operation
- Complex strategic decision-making

## Testing Architecture

### Validation Tests
**Location:** `tests/validation/`

End-to-end tests that validate complete system behavior:
- `test_24hour_survival.py` - Extended operation validation
- `test_company_formation.py` - Company lifecycle validation
- `test_full_pipeline.py` - Complete integration validation

### Integration Tests
**Location:** `tests/integration/`

Component integration testing:
- Monitoring system integration
- Dashboard state management
- Scenario execution

### Unit Tests
**Location:** `tests/unit/`

Individual component testing:
- Decision engine logic
- Resource tracking
- Metrics collection
- Report generation

## Configuration

### Agent Configuration

```python
config = {
    "survival_buffer_hours": 10.0,    # Safety buffer for compute
    "company_threshold": 150.0,        # Min balance for company formation
    "personality": "balanced",         # "conservative", "balanced", "entrepreneur"
}
```

### Scenario Configuration

```python
@dataclass
class ScenarioConfig:
    name: str
    description: str
    duration_minutes: int
    initial_balance: float
    initial_compute_hours: float
    mode: str  # "survival" or "company_building"
    success_criteria: List[str]
```

## Performance Considerations

### Cycle Timing

Each agent cycle involves:
- State updates: ~0.001s
- Decision making: ~0.001s
- Work execution: ~0.001-0.005s
- Monitoring: ~0.001s
- Dashboard update: ~0.001s

**Total: ~0.005-0.010s per cycle**

This allows for:
- 100-200 cycles/second
- Real-time operation
- Minimal overhead from monitoring

### Memory Usage

- Agent state: ~1KB
- Monitoring data per cycle: ~2KB
- Dashboard state: ~5KB
- Total for 100 cycles: ~200KB

The system is designed for efficient long-term operation without memory bloat.

## Extension Points

### Custom Decision Strategies

Extend `DecisionEngine` for custom allocation strategies:

```python
class CustomDecisionEngine(DecisionEngine):
    def decide_allocation(self, state: AgentState) -> AllocationDecision:
        # Custom decision logic
        return AllocationDecision(...)
```

### Custom Monitoring

Add specialized monitoring components:

```python
class CustomMonitor:
    def track_custom_metric(self, data):
        # Custom tracking logic
        pass

# Attach to agent
agent.custom_monitor = CustomMonitor()
```

### Custom Report Types

Create new report formats:

```python
from economic_agents.reports.base import BaseReport

class CustomReport(BaseReport):
    def generate(self, agent: AutonomousAgent) -> Dict[str, Any]:
        # Custom report generation
        return {"custom_data": ...}
```

## Security Considerations

### Mock-to-Real Boundaries

The system is designed with clear boundaries between mock and real implementations:
- All external integrations go through interface classes
- Mock implementations are default
- Real implementations require explicit configuration
- Prevents accidental real-world transactions

### Audit Trail

Complete audit trail for all operations:
- Every decision is logged
- All transactions are tracked
- Resource usage is monitored
- Changes are timestamped

### Alignment Monitoring

Built-in governance through alignment monitoring:
- Tracks company behavior
- Identifies risk factors
- Provides early warning of misalignment
- Enables intervention before harm

## Future Architecture

### Planned Enhancements

1. **Multi-Agent Coordination**
   - Agent-to-agent communication
   - Inter-company transactions
   - Agent marketplace

2. **Real-World Integration**
   - Cryptocurrency wallet integration
   - Cloud compute provider integration
   - Real task marketplace connection

3. **Advanced Monitoring**
   - Predictive analytics
   - Anomaly detection
   - Behavioral analysis

4. **Governance Framework**
   - Policy enforcement
   - Automated compliance checking
   - Human oversight mechanisms

## Summary

The Autonomous Economic Agents framework provides a complete, integrated system for studying AI agents as autonomous economic actors. The architecture emphasizes:

- **Modularity** - Clear component boundaries
- **Integration** - Seamless data flow between subsystems
- **Transparency** - Complete observability of agent behavior
- **Safety** - Mock implementations for risk-free testing
- **Extensibility** - Easy to add custom components

This architecture enables both research into autonomous agent behavior and practical development of governance frameworks.
