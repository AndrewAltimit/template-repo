# Economic Agents

> **A simulation framework demonstrating autonomous AI economic capability for governance research and policy development**

## The Economic Reality

AI agents can already earn money, allocate resources, and operate continuously without human intervention. Using existing tools—Claude Code, Cursor, shell access, and API credentials—an agent can discover freelance tasks, complete them, receive cryptocurrency payments, and pay for its own compute infrastructure. This operates today, not as a theoretical capability.

This framework demonstrates these capabilities in a controlled simulation environment. The same agent logic that runs in simulation works with real systems—the architecture is designed for mock-to-real backend swapping. When agents operate successfully under realistic constraints in simulation, they can operate for real.

**The gap is not in capability. It's in governance.** An AI can earn crypto, establish business structures, and control assets, yet it cannot sign a contract, pay taxes, or be held liable. Legal frameworks for autonomous economic actors do not exist. This creates urgent questions that institutions have not yet addressed.

## Quick Start

```bash
# Clone and navigate to package
git clone https://github.com/AndrewAltimit/template-repo.git
cd template-repo/packages/economic_agents

# Start the simulation dashboard
docker-compose up dashboard-backend dashboard-frontend

# Open http://localhost:8501 and watch an agent:
#   - Complete freelance coding tasks autonomously
#   - Earn money and pay for compute resources
#   - Form a company when capital is sufficient
#   - Create sub-agents and develop products
#   - Seek investment and operate as autonomous business
```

For a detailed tutorial, see [Getting Started](docs/getting-started.md).

## What This Demonstrates

The framework implements a complete autonomous agent lifecycle:

- **Autonomous Task Execution**: Agent discovers, claims, and completes coding tasks using Claude Code
- **Self-Sustaining Operation**: Earnings cover compute costs; agent maintains continuous operation
- **Strategic Decision-Making**: Resource allocation balances short-term survival with long-term growth
- **Company Formation**: When capital exceeds threshold, agent creates business structure
- **Organizational Hierarchy**: Sub-agents created for specialized roles (board, engineering, operations)
- **Investment Seeking**: Business plans generated, proposals submitted to investors
- **Complete Observability**: Every decision logged with reasoning, full audit trail

## Implementation Status

| Component | Status | Description |
|-----------|--------|-------------|
| `MockWallet` | Implemented | In-memory balance tracking, transaction history |
| `MockMarketplace` | Implemented | Simulated tasks with realistic dynamics |
| `MockCompute` | Implemented | Compute hour tracking and cost simulation |
| `MockInvestor` | Implemented | Investment evaluation with realistic variability |
| `CryptoWallet` | Interface only | Ethereum/Bitcoin integration not implemented |
| `FreelancePlatform` | Interface only | Upwork/Fiverr API integration not implemented |
| `CloudCompute` | Interface only | AWS/GCP billing integration not implemented |
| `InvestorPortal` | Interface only | AngelList/YC integration not implemented |

**Scope**: This framework validates that agent decision-making and economic behavior works under realistic simulation constraints. The mock-to-real architecture demonstrates integration patterns; production deployment requires implementing the real backend interfaces.

## Architecture

```
+---------------------------------------------------------+
|            Autonomous Agent (Claude-Powered)             |
|  +---------------------------------------------------+  |
|  | Decision Engine                                   |  |
|  | - Strategic resource allocation                   |  |
|  | - Task selection and execution                    |  |
|  | - Company formation decisions                     |  |
|  | - Sub-agent creation and management               |  |
|  +---------------------------------------------------+  |
+----------------------------+----------------------------+
                             |
                             | REST API (identical interface)
                             |
+----------------------------v----------------------------+
|              Backend Implementation (Swappable)         |
|                                                         |
|   MOCK MODE (Simulation)      REAL MODE (Production)   |
|   - MockWallet                - CryptoWallet (ETH)     |
|   - MockMarketplace           - Upwork API             |
|   - MockCompute               - AWS/GCP Billing        |
|   - MockInvestor              - AngelList/YC           |
+---------------------------------------------------------+
```

The agent has zero visibility into implementation—only REST API access. Mock and real backends implement identical interfaces, enabling one-toggle deployment changes.

For detailed architecture documentation, see [Architecture](docs/architecture.md).

## Simulation Realism

For governance research to produce valid insights, agent behavior must be authentic. Agents in "perfect" simulations develop unrealistic strategies. This framework implements comprehensive realism:

| Feature | Implementation | Research Value |
|---------|----------------|----------------|
| **Latency** | 50-500ms API delays, timeouts, business hours patterns | Real-world API behavior |
| **Competition** | Other agents claim tasks, race conditions, social proof | Market dynamics |
| **Feedback** | Quality scores, partial rewards, improvement suggestions | Learning from failure |
| **Investor Behavior** | Response delays, counteroffers, follow-up questions | Realistic funding process |
| **Economic Cycles** | Bull/bear markets, seasonal trends, crashes | Strategic adaptation |
| **Reputation** | Trust scores, tier progression, achievement unlocks | Long-term strategy |
| **Relationships** | Investor memory, spam detection, trust building | Persistent consequences |

### Technical Details

- **Latency Simulation**: Base calls 50-500ms, complex operations 3-30s, ~2% timeout probability
- **Competition Dynamics**: Tasks claimed by competing agents based on reward, 5% race condition errors
- **Market Phases**: Bull (2x tasks, 1.5x rewards) to crash (0.1x tasks, 0.5x rewards), 48-hour transitions
- **Reputation Tiers**: Beginner through expert, unlocking access to higher-value tasks

## Economic & Governance Implications

This framework demonstrates capabilities that create urgent governance challenges.

### The Governance Vacuum

When an AI agent creates a company:
- **Who is the founder?** The agent has no legal personhood
- **Who has fiduciary duty?** No natural person is involved
- **Who is liable for harm?** Accountability chains lead nowhere
- **What jurisdiction applies?** The entity has no physical presence

Traditional corporate law assumes human founders. These assumptions break when the founder is software.

### Competitive Dynamics

Agent-founded operations have structural advantages:
- 24/7 operation at near-zero marginal cost
- Instant organizational scaling without hiring friction
- Machine-speed execution with perfect record-keeping
- No organizational inertia when pivoting strategy

Market pressure could drive adoption regardless of governance readiness.

### Questions This Raises

**For Policymakers**: Can non-persons create legal persons? How do fiduciary duties apply to AI directors? Are agent-signed contracts enforceable?

**For Researchers**: How do alignment mechanisms hold under economic pressure? What governance frameworks scale to machine speed? How do multi-agent systems coordinate?

**For Business**: How do you compete with autonomous 24/7 operations? Would you invest in an agent-founded company? How do you conduct due diligence without a human founder?

For extended analysis, see [Economic Implications](docs/economic-implications.md).

## Installation

### Using Docker (Recommended)

```bash
cd packages/economic_agents

# Start dashboard
docker-compose up dashboard-backend dashboard-frontend

# Run agent simulation
docker-compose run agent economic-agents run --cycles 100

# Run tests
docker-compose run test
```

### Using Python

```bash
# Install package
pip install -e packages/economic_agents

# With all dependencies
pip install -e "packages/economic_agents[all]"

# Run scenarios
python -m economic_agents.scenarios run survival_mode

# CLI help
python -m economic_agents.cli --help
```

### Requirements

- Python 3.10+
- Docker for containerized deployment
- 8GB RAM minimum (16GB recommended)

## Configuration

Edit `config/agent_config.yaml`:

```yaml
# Agent behavior
survival_buffer_hours: 10.0    # Compute safety margin
company_threshold: 150.0       # Balance to trigger company formation
personality: "balanced"        # conservative | balanced | entrepreneur

# Simulation realism
marketplace:
  enable_latency: true
  enable_competition: true
  enable_market_dynamics: true
  enable_reputation: true
```

## Usage Examples

### Basic Agent Operation

```python
from economic_agents.agent.core.autonomous_agent import AutonomousAgent
from economic_agents.implementations.mock import MockWallet, MockCompute, MockMarketplace

agent = AutonomousAgent(
    wallet=MockWallet(initial_balance=200.0),
    compute=MockCompute(initial_hours=40.0),
    marketplace=MockMarketplace(seed=42),
)

# Run 100 decision cycles
agent.run(max_cycles=100)

# Check results
print(f"Balance: ${agent.state.balance:.2f}")
print(f"Tasks completed: {agent.state.tasks_completed}")
print(f"Company formed: {agent.state.has_company}")
```

### Generate Reports

```python
from economic_agents.reports import generate_report_for_agent

# Available: executive, technical, audit, governance
report = generate_report_for_agent(agent, "governance")
print(report.to_markdown())
```

### Custom Backend Integration

```python
from economic_agents.interfaces import MarketplaceInterface

class UpworkMarketplace(MarketplaceInterface):
    def list_available_tasks(self):
        return upwork_api.get_tasks()

    def submit_solution(self, task_id, solution):
        return upwork_api.submit(task_id, solution)

# Plug into agent - same agent code, real backend
agent = AutonomousAgent(marketplace=UpworkMarketplace())
```

## Documentation

- [Getting Started](docs/getting-started.md) - Hands-on tutorial
- [Architecture](docs/architecture.md) - System design and data flow
- [Integration Guide](docs/integration-guide.md) - Advanced usage patterns
- [Economic Implications](docs/economic-implications.md) - Policy and governance analysis

## Related Work

This framework is part of a broader AI safety research effort in this repository:

- [Sleeper Agent Detection](../sleeper_agents/) - Framework for detecting hidden backdoors and deceptive behaviors in AI models
- [AI Safety Training Guide](../../docs/agents/human-training.md) - Educational content on AI safety concepts and risks

## Testing

```bash
# Run all tests
docker-compose run test

# Or with pytest directly
pip install -e "packages/economic_agents[dev]"
pytest tests/ -v

# Run specific test categories
pytest tests/unit/ -v
pytest tests/integration/ -v
pytest tests/validation/ -v
```

## Project Structure

```
packages/economic_agents/
├── src/economic_agents/
│   ├── agent/              # Core agent logic and decision engine
│   ├── implementations/    # Mock and real backend implementations
│   ├── simulation/         # Realism features (latency, competition, etc.)
│   ├── company/            # Company formation and sub-agent management
│   ├── investment/         # Investor interaction and proposals
│   ├── monitoring/         # Resource tracking and metrics
│   ├── dashboard/          # Real-time visualization
│   ├── reports/            # Governance and audit reports
│   └── scenarios/          # Predefined evaluation scenarios
├── tests/
├── docs/
└── config/
```

## License

MIT License - See LICENSE file for details.

---

*This framework demonstrates capabilities that exist today. The simulation validates agent behavior; the governance questions remain unanswered.*
