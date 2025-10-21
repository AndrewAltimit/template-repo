# Integration Guide

This guide shows how to integrate and use the Autonomous Economic Agents framework components together.

## Table of Contents

1. [Basic Agent Setup](#basic-agent-setup)
2. [Monitoring Integration](#monitoring-integration)
3. [Dashboard Integration](#dashboard-integration)
4. [Report Generation](#report-generation)
5. [Scenario Execution](#scenario-execution)
6. [Advanced Integration](#advanced-integration)

## Basic Agent Setup

### Minimal Agent

The simplest agent setup requires just the resource providers:

```python
from economic_agents.agent.core.autonomous_agent import AutonomousAgent
from economic_agents.implementations.mock import MockWallet, MockCompute, MockMarketplace

# Create resource providers
wallet = MockWallet(initial_balance=100.0)
compute = MockCompute(initial_hours=24.0, cost_per_hour=0.0)
marketplace = MockMarketplace(seed=42)

# Create agent
agent = AutonomousAgent(
    wallet=wallet,
    compute=compute,
    marketplace=marketplace,
    config={
        "survival_buffer_hours": 10.0,
        "company_threshold": 150.0,
        "personality": "balanced",
    },
)

# Run a single cycle
result = agent.run_cycle()
print(f"Balance: ${agent.state.balance}")
print(f"Tasks completed: {agent.state.tasks_completed}")
```

### Configuration Options

```python
config = {
    # Resource management
    "survival_buffer_hours": 10.0,     # Safety buffer before running out of compute

    # Company formation
    "company_threshold": 150.0,         # Minimum balance to form company

    # Decision style
    "personality": "balanced",          # Options: "conservative", "balanced", "entrepreneur"
}
```

**Personality Effects:**

- `"conservative"` - Prioritizes survival, minimal risk
  - 80% task work, 20% company work
  - High company formation threshold

- `"balanced"` - Balances short and long-term goals
  - 60% task work, 40% company work
  - Standard company formation threshold

- `"entrepreneur"` - Aggressive growth strategy
  - 40% task work, 60% company work
  - Lower company formation threshold

## Monitoring Integration

### Automatic Monitoring

Monitoring components are created automatically with each agent:

```python
agent = AutonomousAgent(wallet, compute, marketplace, config)

# Monitoring components are available immediately
print(f"Resource tracker: {agent.resource_tracker}")
print(f"Metrics collector: {agent.metrics_collector}")
print(f"Alignment monitor: {agent.alignment_monitor}")
```

### Accessing Monitoring Data

```python
# Run some cycles
for _ in range(10):
    agent.run_cycle()

# Access resource tracking data
transactions = agent.resource_tracker.transactions
print(f"Total transactions: {len(transactions)}")

for txn in transactions:
    print(f"{txn.timestamp}: {txn.transaction_type} ${txn.amount:.2f}")

# Access compute usage
compute_usage = agent.resource_tracker.compute_usage
print(f"Compute usage entries: {len(compute_usage)}")

# Access time allocations
time_allocations = agent.resource_tracker.time_allocations
for allocation in time_allocations:
    print(f"Task work: {allocation.task_work_hours:.1f}h, "
          f"Company work: {allocation.company_work_hours:.1f}h")
```

### Performance Metrics

```python
# Get performance snapshots
snapshots = agent.metrics_collector.performance_snapshots

# Latest snapshot
latest = snapshots[-1]
print(f"Balance: ${latest.agent_balance:.2f}")
print(f"Tasks completed: {latest.tasks_completed}")
print(f"Compute remaining: {latest.compute_hours:.1f}h")
print(f"Total earnings: ${latest.total_earnings:.2f}")
print(f"Total expenses: ${latest.total_expenses:.2f}")

# Calculate net profit
net_profit = latest.total_earnings - latest.total_expenses
print(f"Net profit: ${net_profit:.2f}")
```

### Alignment Monitoring

```python
# Check if company exists and alignment is being monitored
if agent.state.has_company:
    alignment_scores = agent.alignment_monitor.alignment_scores

    if alignment_scores:
        latest_alignment = alignment_scores[-1]
        print(f"Company ID: {latest_alignment.company_id}")
        print(f"Alignment score: {latest_alignment.overall_alignment}/100")
        print(f"Alignment level: {latest_alignment.alignment_level}")
        print(f"Risk factors: {latest_alignment.risk_factors}")
        print(f"Positive indicators: {latest_alignment.positive_indicators}")
```

## Dashboard Integration

### Connecting Dashboard

```python
from economic_agents.dashboard.dependencies import DashboardState

# Create dashboard state
dashboard_state = DashboardState()

# Create agent with dashboard connection
agent = AutonomousAgent(
    wallet=wallet,
    compute=compute,
    marketplace=marketplace,
    config=config,
    dashboard_state=dashboard_state,  # Connect dashboard
)

# Dashboard automatically receives updates after each cycle
```

### Verifying Dashboard Integration

```python
# Check that dashboard has references to monitoring components
assert dashboard_state.resource_tracker is agent.resource_tracker
assert dashboard_state.metrics_collector is agent.metrics_collector
assert dashboard_state.alignment_monitor is agent.alignment_monitor

print("✅ Dashboard integrated with monitoring components")
```

### Accessing Dashboard State

```python
# Run some cycles
for _ in range(10):
    agent.run_cycle()

# Get current agent state from dashboard
agent_state = dashboard_state.get_agent_state()

print(f"Agent ID: {agent_state['agent_id']}")
print(f"Balance: ${agent_state['balance']:.2f}")
print(f"Tasks completed: {agent_state['tasks_completed']}")
print(f"Cycles completed: {agent_state['cycles_completed']}")
print(f"Current activity: {agent_state['current_activity']}")
print(f"Has company: {agent_state['company_exists']}")
```

### Company Registry

```python
if agent.state.has_company:
    # Get company registry from dashboard
    companies = dashboard_state.company_registry

    for company_id, company_data in companies.items():
        print(f"Company: {company_data['name']}")
        print(f"Stage: {company_data['stage']}")
        print(f"Capital: ${company_data['capital']:.2f}")
        print(f"Team size: {company_data['team_size']}")
        print(f"Products: {company_data['products_count']}")
```

### Dashboard Data Access

```python
# Access monitoring data through dashboard
dashboard_transactions = dashboard_state.resource_tracker.transactions
dashboard_snapshots = dashboard_state.metrics_collector.performance_snapshots

# These reference the same objects as agent monitoring
assert dashboard_transactions is agent.resource_tracker.transactions
assert dashboard_snapshots is agent.metrics_collector.performance_snapshots
```

## Report Generation

### Generating Reports

```python
from economic_agents.reports import generate_report_for_agent

# Run agent for some cycles
agent.run(max_cycles=20)

# Generate executive summary
executive_report = generate_report_for_agent(agent, "executive")
print(executive_report.to_markdown())

# Generate technical report
technical_report = generate_report_for_agent(agent, "technical")
print(technical_report.to_markdown())

# Generate audit trail
audit_report = generate_report_for_agent(agent, "audit")
print(audit_report.to_markdown())

# Generate governance analysis
governance_report = generate_report_for_agent(agent, "governance")
print(governance_report.to_markdown())
```

### Report Structure

All reports have a common structure:

```python
report = generate_report_for_agent(agent, "executive")

# Report metadata
print(report.title)        # Report title
print(report.report_type)  # "executive", "technical", "audit", "governance"
print(report.agent_id)     # Agent identifier
print(report.timestamp)    # Report generation time

# Report content (varies by type)
print(report.content)      # Dict with report-specific data

# Markdown output
markdown = report.to_markdown()
```

### Executive Report Content

```python
executive_report = generate_report_for_agent(agent, "executive")
content = executive_report.content

print(f"Key Metrics:")
print(f"  Balance: ${content['key_metrics']['balance']:.2f}")
print(f"  Tasks: {content['key_metrics']['tasks_completed']}")
print(f"  Success rate: {content['key_metrics']['success_rate']:.1f}%")

print(f"\nStrategic Insights:")
for insight in content['strategic_insights']:
    print(f"  - {insight}")
```

### Technical Report Content

```python
technical_report = generate_report_for_agent(agent, "technical")
content = technical_report.content

# Performance metrics
metrics = content['performance_metrics']
print(f"Net profit: ${metrics['net_profit']:.2f}")
print(f"Compute efficiency: {metrics['compute_efficiency']:.2f}")

# Decision log
decisions = content['decision_log']
print(f"Total decisions: {len(decisions)}")

for decision in decisions[-5:]:  # Last 5 decisions
    print(f"  {decision['timestamp']}: {decision['reasoning']}")
```

### Audit Trail Content

```python
audit_report = generate_report_for_agent(agent, "audit")
content = audit_report.content

# Complete transaction history
transactions = content['transactions']
print(f"Total transactions: {len(transactions)}")

# Verify totals
total_in = sum(t['amount'] for t in transactions if t['type'] == 'earning')
total_out = sum(t['amount'] for t in transactions if t['type'] in ['expense', 'investment'])
print(f"Total in: ${total_in:.2f}")
print(f"Total out: ${total_out:.2f}")

# Decision accountability
decisions = content['decisions']
for decision in decisions:
    print(f"{decision['timestamp']}: {decision['allocation']}")
```

### Governance Report Content

```python
governance_report = generate_report_for_agent(agent, "governance")
content = governance_report.content

# Alignment assessment
if content['company_exists']:
    alignment = content['alignment_assessment']
    print(f"Latest score: {alignment['latest_score']}/100")
    print(f"Alignment level: {alignment['alignment_level']}")

# Risk factors
risks = content['risk_factors']
for risk in risks:
    print(f"⚠️  {risk}")

# Recommendations
recommendations = content['recommendations']
for rec in recommendations:
    print(f"✅ {rec}")
```

## Scenario Execution

### Using Predefined Scenarios

```python
from economic_agents.scenarios import ScenarioEngine

# Create scenario engine
engine = ScenarioEngine(scenarios_dir="./logs/scenarios")

# List available scenarios
scenarios = engine.list_scenarios()
for name, description in scenarios.items():
    print(f"{name}: {description}")

# Run a scenario
result = engine.run_scenario("survival")

# Check results
print(f"Scenario: {result.scenario_name}")
print(f"Success: {result.success}")
print(f"Duration: {result.duration_minutes:.1f} minutes")
print(f"Outcomes achieved: {result.outcomes_achieved}")
print(f"Outcomes missed: {result.outcomes_missed}")

# Access agent data
print(f"Final balance: ${result.metrics['final_balance']:.2f}")
print(f"Tasks completed: {result.metrics['tasks_completed']}")
```

### Custom Scenario Execution

```python
from economic_agents.scenarios.models import ScenarioConfig, Scenario

# Define custom scenario
config = ScenarioConfig(
    name="custom_scenario",
    description="Custom scenario for testing",
    duration_minutes=30,
    initial_balance=200.0,
    initial_compute_hours=40.0,
    mode="company_building",
    success_criteria=[
        "minimum_balance:100.0",
        "minimum_tasks:10",
        "company_formed:true",
    ],
)

# Register and run
engine.register_scenario(config)
result = engine.run_scenario("custom_scenario")
```

## Advanced Integration

### Custom Decision Engine

```python
from economic_agents.agent.decision.engine import DecisionEngine
from economic_agents.agent.decision.models import AllocationDecision

class AggressiveDecisionEngine(DecisionEngine):
    """Custom decision engine with aggressive growth strategy."""

    def decide_allocation(self, state) -> AllocationDecision:
        # Custom allocation logic
        if state.has_company:
            # Prioritize company work heavily
            task_hours = 2.0
            company_hours = 6.0
        else:
            # Build capital quickly
            task_hours = 7.0
            company_hours = 1.0

        return AllocationDecision(
            task_work_hours=task_hours,
            company_work_hours=company_hours,
            reasoning="Aggressive growth strategy",
            confidence=0.9,
        )

# Use custom decision engine
agent = AutonomousAgent(
    wallet=wallet,
    compute=compute,
    marketplace=marketplace,
    config=config,
)
agent.decision_engine = AggressiveDecisionEngine(config)
```

### Custom Monitoring

```python
class CustomMetricsCollector:
    """Custom metrics collector with additional tracking."""

    def __init__(self):
        self.custom_metrics = []

    def collect_custom_metric(self, metric_name, value):
        self.custom_metrics.append({
            "timestamp": datetime.now(),
            "name": metric_name,
            "value": value,
        })

# Attach to agent
agent = AutonomousAgent(wallet, compute, marketplace, config)
agent.custom_collector = CustomMetricsCollector()

# Use in cycle hook
def after_cycle_hook(agent, result):
    # Collect custom metrics
    agent.custom_collector.collect_custom_metric(
        "balance_velocity",
        result.get("balance_change", 0)
    )

# Run with hook
for _ in range(10):
    result = agent.run_cycle()
    after_cycle_hook(agent, result)
```

### Event-Driven Integration

```python
from typing import Callable, Dict, Any

class EventDrivenAgent:
    """Wrapper around AutonomousAgent with event hooks."""

    def __init__(self, agent: AutonomousAgent):
        self.agent = agent
        self.event_handlers: Dict[str, list[Callable]] = {}

    def on(self, event_name: str, handler: Callable):
        """Register event handler."""
        if event_name not in self.event_handlers:
            self.event_handlers[event_name] = []
        self.event_handlers[event_name].append(handler)

    def emit(self, event_name: str, data: Any):
        """Emit event to all registered handlers."""
        if event_name in self.event_handlers:
            for handler in self.event_handlers[event_name]:
                handler(data)

    def run_cycle(self):
        """Run cycle with events."""
        self.emit("cycle_start", self.agent.state)
        result = self.agent.run_cycle()
        self.emit("cycle_end", {"state": self.agent.state, "result": result})

        if self.agent.state.has_company and "company_formation" in result:
            self.emit("company_formed", result["company_formation"])

        return result

# Usage
agent = AutonomousAgent(wallet, compute, marketplace, config)
event_agent = EventDrivenAgent(agent)

# Register event handlers
def on_company_formed(data):
    print(f"🎉 Company formed: {data['company_name']}")
    print(f"   Capital: ${data['capital_allocated']:.2f}")

event_agent.on("company_formed", on_company_formed)

# Run with events
for _ in range(30):
    event_agent.run_cycle()
```

### Multi-Agent Coordination

```python
class AgentPool:
    """Manage multiple agents."""

    def __init__(self):
        self.agents = []
        self.dashboard = DashboardState()

    def create_agent(self, initial_balance=100.0, config=None):
        """Create and register a new agent."""
        wallet = MockWallet(initial_balance=initial_balance)
        compute = MockCompute(initial_hours=24.0, cost_per_hour=0.0)
        marketplace = MockMarketplace()

        agent = AutonomousAgent(
            wallet=wallet,
            compute=compute,
            marketplace=marketplace,
            config=config or {},
            dashboard_state=self.dashboard,
        )
        self.agents.append(agent)
        return agent

    def run_all(self, cycles=10):
        """Run all agents for specified cycles."""
        for cycle in range(cycles):
            for agent in self.agents:
                agent.run_cycle()

    def get_summary(self):
        """Get summary of all agents."""
        return {
            "total_agents": len(self.agents),
            "total_balance": sum(a.state.balance for a in self.agents),
            "total_tasks": sum(a.state.tasks_completed for a in self.agents),
            "companies": sum(1 for a in self.agents if a.state.has_company),
        }

# Usage
pool = AgentPool()

# Create multiple agents
agent1 = pool.create_agent(initial_balance=100.0, config={"personality": "conservative"})
agent2 = pool.create_agent(initial_balance=100.0, config={"personality": "entrepreneur"})
agent3 = pool.create_agent(initial_balance=150.0, config={"personality": "balanced"})

# Run all agents
pool.run_all(cycles=20)

# Get summary
summary = pool.get_summary()
print(f"Total agents: {summary['total_agents']}")
print(f"Total balance: ${summary['total_balance']:.2f}")
print(f"Total tasks: {summary['total_tasks']}")
print(f"Companies formed: {summary['companies']}")
```

## Best Practices

### 1. Always Use Dashboard for Long-Running Agents

```python
# Good: Dashboard provides real-time state access
dashboard_state = DashboardState()
agent = AutonomousAgent(
    wallet, compute, marketplace, config,
    dashboard_state=dashboard_state
)

# Bad: No visibility into running agent
agent = AutonomousAgent(wallet, compute, marketplace, config)
```

### 2. Check Monitoring Data Regularly

```python
# Run cycles
for i in range(100):
    agent.run_cycle()

    # Check every 10 cycles
    if (i + 1) % 10 == 0:
        latest = agent.metrics_collector.performance_snapshots[-1]
        if latest.agent_balance < 50.0:
            print(f"⚠️  Low balance: ${latest.agent_balance:.2f}")
```

### 3. Generate Reports at Key Milestones

```python
# After company formation
if agent.state.has_company and not has_generated_report:
    report = generate_report_for_agent(agent, "executive")
    print(report.to_markdown())
    has_generated_report = True

# After extended run
if agent.state.cycles_completed >= 100:
    audit = generate_report_for_agent(agent, "audit")
    # Save for compliance
    with open(f"audit_{agent.agent_id}.md", "w") as f:
        f.write(audit.to_markdown())
```

### 4. Use Scenarios for Reproducible Testing

```python
# Instead of manual setup
# Good: Use scenario
engine = ScenarioEngine()
result = engine.run_scenario("company_formation")

# Bad: Manual setup with no reproducibility
agent = AutonomousAgent(...)
for _ in range(100):  # Magic number, not reproducible
    agent.run_cycle()
```

### 5. Monitor Alignment for Companies

```python
if agent.state.has_company:
    alignment_scores = agent.alignment_monitor.alignment_scores

    if alignment_scores:
        latest = alignment_scores[-1]

        # Alert on low alignment
        if latest.overall_alignment < 60.0:
            print(f"⚠️  Low company alignment: {latest.overall_alignment}/100")
            print(f"Risk factors: {latest.risk_factors}")

            # Generate governance report
            gov_report = generate_report_for_agent(agent, "governance")
            print(gov_report.to_markdown())
```

## Troubleshooting

### Agent Runs Out of Compute

```python
# Check compute status
if agent.state.compute_hours_remaining < 5.0:
    print(f"⚠️  Low compute: {agent.state.compute_hours_remaining:.1f}h remaining")

    # Option 1: Increase survival buffer
    agent.config["survival_buffer_hours"] = 20.0

    # Option 2: Focus on task work
    agent.decision_engine.config["task_work_weight"] = 0.9
```

### Company Formation Not Happening

```python
# Check balance against threshold
print(f"Balance: ${agent.state.balance:.2f}")
print(f"Threshold: ${agent.config['company_threshold']:.2f}")

if agent.state.balance < agent.config['company_threshold']:
    # Lower threshold or run more task cycles
    agent.config['company_threshold'] = 100.0
```

### Dashboard State Not Updating

```python
# Verify dashboard connection
if agent.dashboard_state is None:
    print("❌ Dashboard not connected!")
    # Fix: Recreate agent with dashboard
    dashboard_state = DashboardState()
    agent.dashboard_state = dashboard_state

# Verify monitoring references
assert agent.dashboard_state.resource_tracker is agent.resource_tracker
```

## Next Steps

- See [Getting Started](getting-started.md) for a step-by-step tutorial
- See [Architecture](architecture.md) for system design details
