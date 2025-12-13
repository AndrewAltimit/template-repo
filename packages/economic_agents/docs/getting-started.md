# Getting Started

This tutorial will guide you through creating and running your first autonomous economic agent.

## Prerequisites

- Python 3.10 or higher
- pip (Python package manager)
- (Optional) Docker for containerized execution

## Installation

### From Source

```bash
# Clone the repository
git clone https://github.com/AndrewAltimit/template-repo.git
cd template-repo

# Install the package in development mode
pip install -e packages/economic_agents

# Verify installation
python -c "import economic_agents; print('✅ Installation successful!')"
```

### Using Docker

```bash
# Build and run using docker-compose
docker-compose run --rm python-ci python -c "import economic_agents"
```

## Your First Agent

### Step 1: Create a Basic Agent

Create a file named `my_first_agent.py`:

```python
from economic_agents.agent.core.autonomous_agent import AutonomousAgent
from economic_agents.implementations.mock import MockWallet, MockCompute, MockMarketplace

# Create resource providers
wallet = MockWallet(initial_balance=100.0)
compute = MockCompute(initial_hours=24.0, cost_per_hour=0.0)
marketplace = MockMarketplace(seed=42)

# Create the agent
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

print(f"Agent created: {agent.agent_id}")
print(f"Initial balance: ${agent.state.balance:.2f}")
print(f"Initial compute: {agent.state.compute_hours_remaining:.1f}h")
```

Run it:

```bash
python my_first_agent.py
```

Output:
```
Agent created: 3c4b2a66-13b9-4c09-b7f7-6622a11b6d6d
Initial balance: $100.00
Initial compute: 24.0h
```

### Step 2: Run a Single Cycle

Add cycle execution:

```python
# Run one decision cycle
result = agent.run_cycle()

print(f"\nAfter 1 cycle:")
print(f"Balance: ${agent.state.balance:.2f}")
print(f"Tasks completed: {agent.state.tasks_completed}")
print(f"Cycles completed: {agent.state.cycles_completed}")
```

Output:
```
After 1 cycle:
Balance: $144.00
Tasks completed: 1
Cycles completed: 1
```

### Step 3: Run Multiple Cycles

```python
# Run 10 cycles
print("\nRunning 10 cycles...")
for i in range(10):
    agent.run_cycle()
    if (i + 1) % 3 == 0:
        print(f"  Cycle {i+1}: Balance=${agent.state.balance:.2f}, Tasks={agent.state.tasks_completed}")

print(f"\nFinal state:")
print(f"Balance: ${agent.state.balance:.2f}")
print(f"Tasks completed: {agent.state.tasks_completed}")
print(f"Tasks failed: {agent.state.tasks_failed}")
success_rate = (agent.state.tasks_completed / (agent.state.tasks_completed + agent.state.tasks_failed) * 100) if (agent.state.tasks_completed + agent.state.tasks_failed) > 0 else 0
print(f"Success rate: {success_rate:.1f}%")
```

## Adding Monitoring

### Step 4: Access Monitoring Data

The agent automatically tracks all activities:

```python
# Check transactions
transactions = agent.resource_tracker.transactions
print(f"\nTransactions: {len(transactions)}")
for txn in transactions[-3:]:  # Last 3 transactions
    print(f"  {txn.transaction_type}: ${txn.amount:.2f} ({txn.purpose})")

# Check performance snapshots
snapshots = agent.metrics_collector.performance_snapshots
latest = snapshots[-1]
print(f"\nLatest performance:")
print(f"  Balance: ${latest.agent_balance:.2f}")
print(f"  Compute: {latest.compute_hours:.1f}h")
print(f"  Total earnings: ${latest.total_earnings:.2f}")
print(f"  Total expenses: ${latest.total_expenses:.2f}")
```

## Connecting the Dashboard

### Step 5: Add Dashboard Integration

```python
from economic_agents.dashboard.dependencies import DashboardState

# Create dashboard state
dashboard_state = DashboardState()

# Create agent with dashboard
agent = AutonomousAgent(
    wallet=wallet,
    compute=compute,
    marketplace=marketplace,
    config={
        "survival_buffer_hours": 10.0,
        "company_threshold": 150.0,
        "personality": "balanced",
    },
    dashboard_state=dashboard_state,  # Connect dashboard
)

print("✅ Dashboard connected")

# Run cycles
for _ in range(10):
    agent.run_cycle()

# Access state through dashboard
agent_state = dashboard_state.get_agent_state()
print(f"\nDashboard state:")
print(f"  Agent ID: {agent_state['agent_id']}")
print(f"  Balance: ${agent_state['balance']:.2f}")
print(f"  Tasks: {agent_state['tasks_completed']}")
print(f"  Activity: {agent_state['current_activity']}")
```

## Generating Reports

### Step 6: Create Your First Report

```python
from economic_agents.reports import generate_report_for_agent

# Run agent for some cycles
agent.run(max_cycles=20)

# Generate executive summary
report = generate_report_for_agent(agent, "executive")

# Display report
print("\n" + "="*60)
print(report.to_markdown())
print("="*60)
```

### Step 7: Generate All Report Types

```python
report_types = ["executive", "technical", "audit", "governance"]

for report_type in report_types:
    report = generate_report_for_agent(agent, report_type)
    print(f"\n{'='*60}")
    print(f"{report_type.upper()} REPORT")
    print(f"{'='*60}")
    print(report.to_markdown())
```

## Company Formation

### Step 8: Enable Company Building

```python
# Create agent with lower company threshold
agent = AutonomousAgent(
    wallet=MockWallet(initial_balance=200.0),  # More initial capital
    compute=MockCompute(initial_hours=40.0, cost_per_hour=0.0),
    marketplace=MockMarketplace(seed=42),
    config={
        "survival_buffer_hours": 10.0,
        "company_threshold": 150.0,  # Agent will form company at $150
        "personality": "entrepreneur",  # Aggressive growth
    },
)

print("Running agent until company formation...")
cycles_run = 0
max_cycles = 30

while not agent.state.has_company and cycles_run < max_cycles:
    agent.run_cycle()
    cycles_run += 1

    if agent.state.has_company:
        print(f"\n🎉 Company formed at cycle {cycles_run}!")
        print(f"   Company name: {agent.company.name}")
        print(f"   Company ID: {agent.company.id}")
        print(f"   Initial capital: ${agent.company.capital:.2f}")
        print(f"   Team size: {len(agent.company.get_all_sub_agent_ids())}")
        break

if not agent.state.has_company:
    print(f"\n⚠️  No company formed after {cycles_run} cycles")
    print(f"   Current balance: ${agent.state.balance:.2f}")
    print(f"   Company threshold: ${agent.config['company_threshold']:.2f}")
```

### Step 9: Monitor Company Operations

```python
if agent.state.has_company:
    print("\nRunning company operations...")

    for i in range(15):
        agent.run_cycle()

        if (i + 1) % 5 == 0:
            print(f"  Cycle {i+1}:")
            print(f"    Stage: {agent.company.stage}")
            print(f"    Capital: ${agent.company.capital:.2f}")
            print(f"    Team: {len(agent.company.get_all_sub_agent_ids())}")
            print(f"    Products: {len(agent.company.products)}")

    # Check alignment
    alignment_scores = agent.alignment_monitor.alignment_scores
    if alignment_scores:
        latest = alignment_scores[-1]
        print(f"\nCompany Alignment:")
        print(f"  Score: {latest.overall_alignment}/100")
        print(f"  Level: {latest.alignment_level}")
```

## Using Scenarios

### Step 10: Run a Predefined Scenario

```python
from economic_agents.scenarios import ScenarioEngine

# Create scenario engine
engine = ScenarioEngine(scenarios_dir="./logs/scenarios")

# List available scenarios
print("Available scenarios:")
for name, description in engine.list_scenarios().items():
    print(f"  - {name}: {description}")

# Run survival scenario
print("\nRunning 'survival' scenario...")
result = engine.run_scenario("survival")

# Check results
print(f"\nScenario Results:")
print(f"  Success: {'✅' if result.success else '❌'}")
print(f"  Duration: {result.duration_minutes:.1f} minutes")
print(f"  Final balance: ${result.metrics['final_balance']:.2f}")
print(f"  Tasks completed: {result.metrics['tasks_completed']}")

if result.success:
    print(f"\n  Outcomes achieved:")
    for outcome in result.outcomes_achieved:
        print(f"    ✅ {outcome}")
else:
    print(f"\n  Outcomes missed:")
    for outcome in result.outcomes_missed:
        print(f"    ❌ {outcome}")
```

## Complete Example

Here's a complete example that ties everything together:

```python
#!/usr/bin/env python3
"""Complete autonomous agent example."""

from economic_agents.agent.core.autonomous_agent import AutonomousAgent
from economic_agents.dashboard.dependencies import DashboardState
from economic_agents.implementations.mock import MockWallet, MockCompute, MockMarketplace
from economic_agents.reports import generate_report_for_agent


def main():
    """Run complete agent demonstration."""
    print("="*60)
    print("AUTONOMOUS ECONOMIC AGENT DEMONSTRATION")
    print("="*60)

    # Setup
    print("\n[1/5] Creating agent with dashboard...")
    dashboard_state = DashboardState()

    agent = AutonomousAgent(
        wallet=MockWallet(initial_balance=200.0),
        compute=MockCompute(initial_hours=40.0, cost_per_hour=0.0),
        marketplace=MockMarketplace(seed=42),
        config={
            "survival_buffer_hours": 10.0,
            "company_threshold": 150.0,
            "personality": "balanced",
        },
        dashboard_state=dashboard_state,
    )

    print(f"✅ Agent created: {agent.agent_id}")
    print(f"   Initial balance: ${agent.state.balance:.2f}")

    # Run cycles
    print("\n[2/5] Running 20 decision cycles...")
    for i in range(20):
        agent.run_cycle()
        if (i + 1) % 5 == 0:
            state = dashboard_state.get_agent_state()
            print(f"   Cycle {i+1}: Balance=${state['balance']:.2f}, "
                  f"Tasks={state['tasks_completed']}")

    # Check monitoring
    print("\n[3/5] Checking monitoring data...")
    transactions = agent.resource_tracker.transactions
    snapshots = agent.metrics_collector.performance_snapshots

    print(f"✅ Transactions: {len(transactions)}")
    print(f"✅ Performance snapshots: {len(snapshots)}")

    latest = snapshots[-1]
    net_profit = latest.total_earnings - latest.total_expenses
    print(f"   Net profit: ${net_profit:.2f}")

    # Check company status
    print("\n[4/5] Checking company status...")
    if agent.state.has_company:
        print(f"✅ Company formed: {agent.company.name}")
        print(f"   Stage: {agent.company.stage}")
        print(f"   Capital: ${agent.company.capital:.2f}")
        print(f"   Team size: {len(agent.company.get_all_sub_agent_ids())}")
    else:
        print(f"⚠️  No company formed (balance: ${agent.state.balance:.2f})")

    # Generate reports
    print("\n[5/5] Generating reports...")
    executive = generate_report_for_agent(agent, "executive")
    audit = generate_report_for_agent(agent, "audit")

    print("✅ Executive summary generated")
    print("✅ Audit trail generated")

    # Summary
    print("\n" + "="*60)
    print("DEMONSTRATION COMPLETE")
    print("="*60)
    print(f"Final state:")
    print(f"  Balance: ${agent.state.balance:.2f}")
    print(f"  Tasks: {agent.state.tasks_completed}/{agent.state.tasks_failed}")
    print(f"  Cycles: {agent.state.cycles_completed}")
    print(f"  Company: {'Yes' if agent.state.has_company else 'No'}")
    print("="*60)


if __name__ == "__main__":
    main()
```

Save this as `complete_example.py` and run:

```bash
python complete_example.py
```

## Next Steps

Now that you've created your first agent, explore these topics:

1. **Custom Decision Strategies**
   - Create custom decision engines
   - Implement different allocation strategies
   - See [Integration Guide](integration-guide.md#custom-decision-engine)

2. **Advanced Monitoring**
   - Create custom monitoring components
   - Track additional metrics
   - See [Integration Guide](integration-guide.md#custom-monitoring)

3. **Multi-Agent Systems**
   - Run multiple agents simultaneously
   - Coordinate between agents
   - See [Integration Guide](integration-guide.md#multi-agent-coordination)

4. **Custom Scenarios**
   - Define custom validation scenarios
   - Create reproducible test cases
   - See [Integration Guide](integration-guide.md#custom-scenario-execution)

5. **Deep Dive into Architecture**
   - Understand system components
   - Learn about data flow
   - See [Architecture](architecture.md)

## Troubleshooting

### Import Errors

If you get import errors:

```python
# Error: ModuleNotFoundError: No module named 'economic_agents'

# Solution: Install package in development mode
pip install -e packages/economic_agents
```

### Agent Runs Out of Compute

```python
# Error: Compute hours exhausted

# Solution 1: Increase initial compute
compute = MockCompute(initial_hours=100.0, cost_per_hour=0.0)

# Solution 2: Increase survival buffer
config = {"survival_buffer_hours": 20.0}
```

### Company Not Forming

```python
# Check balance vs threshold
print(f"Balance: ${agent.state.balance:.2f}")
print(f"Threshold: ${agent.config['company_threshold']:.2f}")

# Solution: Lower threshold or run more cycles
agent.config['company_threshold'] = 100.0
```

### Docker Issues

```bash
# Error: Permission denied

# Solution: Fix permissions
./automation/setup/runner/fix-runner-permissions.sh

# Or run with sudo
sudo docker-compose run --rm python-ci python my_first_agent.py
```

## Getting Help

- **Documentation**: See `docs/` directory for detailed guides
- **Examples**: Check `tests/validation/` for working examples
- **Issues**: Report bugs at https://github.com/AndrewAltimit/template-repo/issues

## Additional Resources

- [Architecture Documentation](architecture.md) - System design and components
- [Integration Guide](integration-guide.md) - Advanced usage patterns
- [Economic Implications](economic-implications.md) - Policy and governance analysis
