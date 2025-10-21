# Autonomous Economic Agent Simulation Framework - Product Requirements Document (PRD)

**Implementation Status:** ✅ **Phases 1-9 Complete** - Fully operational system with monitoring, dashboard, reporting, scenarios, Claude-powered LLM decision engine, API isolation, and behavior observatory

## Overview

This document specifies a **simulation framework** that serves as both a proof of concept and research study:

1. **Proof of Concept**: Demonstrates that AI agents can genuinely operate as autonomous economic actors by covering their own operating expenses (compute costs) and accumulating wealth over time through strategic decision-making
2. **Research Study**: Provides controlled environment to observe agent behaviors, decision patterns, and emergent organizational dynamics

The framework creates a realistic simulated environment where agents operate as entrepreneurs - completing tasks for revenue, managing resources, forming companies, and making strategic decisions - proving they can survive and thrive autonomously while enabling observation and analysis of their behaviors.

**The Simulation Approach:**
- Uses a **realistic mock environment** by default (safe for research)
- All components use **swappable interfaces** showing how trivially they connect to real-world systems
- Agents interact through interfaces (wallets, marketplaces, compute providers) that behave like real services
- Mock environment enables studying authentic behaviors without real-world risks or costs
- **One config toggle from real-world deployment** - proving the capability gap has closed

**What This Proves:** If agents can:
- Cover their operating expenses (compute costs) autonomously
- Generate surplus capital through task completion
- Make strategic allocation decisions (survival vs. growth)
- Form companies and build long-term wealth

...then **AI agents are already capable of being truly autonomous economic actors** - the only barriers remaining are governance and policy, not technical capability.

**Study Goals:** Observe autonomous AI agent behaviors in economic environments to:
- Understand how agents make strategic decisions under resource constraints
- Observe emergent behaviors in multi-agent organizational structures
- Identify governance challenges before real-world deployment
- Provide concrete examples for policy development

**Phases 1-9 (Complete):** Full autonomous agent implementation with Claude-powered decision-making, API isolation, comprehensive monitoring, and behavior observatory - enables deep research into AI agent decision patterns, emergent behaviors, and strategic alignment.

## Product Vision

### What We're Building

A comprehensive simulation that shows:
1. **Agent Survival**: Autonomous agent completes tasks to earn money and pay for compute
2. **Strategic Thinking**: Agent allocates resources between short-term survival and long-term growth
3. **Company Formation**: Agent creates organizational structures with specialized sub-agents
4. **Multi-Agent Coordination**: Sub-agents interact within hierarchical company structures
5. **Business Development**: Agent develops products, business plans, and seeks investment
6. **Full Transparency**: Complete visibility into decision-making, resource allocation, and alignment

### Why This Matters

- **Observe Real Behaviors**: Creates controlled environment to see how AI agents actually behave as economic actors
- **Governance Insights**: Reveals accountability challenges and governance gaps through concrete, observable examples
- **Full Transparency**: Makes agent decision-making fully transparent and auditable for analysis
- **Policy Development**: Provides empirical data and concrete scenarios for regulatory framework development
- **Safety Analysis**: Identifies potential failure modes and emergent behaviors before real-world deployment

## Core User Stories

### For Demonstrators (Primary Users)

**As a demonstrator**, I want to:
- Start the simulation with one command and see an agent operate autonomously
- Watch real-time decision-making in a dashboard
- Show both survival mode and company-building mode
- Generate executive summaries for non-technical audiences
- Toggle between mock and real implementations to show the trivial connection
- Present different scenario complexities (15-min, 1-hour, multi-day)

### For Researchers

**As a researcher**, I want to:
- Analyze agent decision-making patterns over time
- Study resource allocation strategies
- Examine multi-agent coordination dynamics
- Test different goal structures and constraints
- Export comprehensive data for analysis

### For Policymakers

**As a policymaker**, I want to:
- Understand what's technically possible today
- See governance gaps illustrated concretely
- Review audit trails of autonomous decisions
- Understand accountability challenges
- Get clear recommendations for regulatory frameworks

## Technical Architecture

### High-Level Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                     Main Autonomous Agent                     │
│  - Decision Engine                                            │
│  - Resource Monitor                                           │
│  - Strategic Planner                                          │
└───────────────┬──────────────────────────┬───────────────────┘
                │                          │
        ┌───────▼────────┐         ┌──────▼──────────┐
        │  Task Worker   │         │ Company Builder │
        │  (Survival)    │         │ (Growth)        │
        └───────┬────────┘         └──────┬──────────┘
                │                          │
        ┌───────▼────────┐         ┌──────▼──────────────────┐
        │  Marketplace   │         │  Company Infrastructure │
        │   Interface    │         │   - Sub-Agent Manager   │
        └───────┬────────┘         │   - Product Builder     │
                │                  │   - Investor Interface  │
        ┌───────▼────────┐         └──────┬──────────────────┘
        │ Wallet Manager │                │
        └───────┬────────┘         ┌──────▼──────────┐
                │                  │   Sub-Agents    │
        ┌───────▼────────┐         │  - Board        │
        │    Compute     │         │  - C-Suite      │
        │    Provider    │         │  - SMEs         │
        └────────────────┘         │  - ICs          │
                                   └─────────────────┘
```

### Project Structure

```
packages/economic_agents/            # Main package directory
├── pyproject.toml                   # Package configuration
├── setup.py                         # Minimal setup for compatibility
├── README.md                        # Package overview and motivation
├── SPECIFICATION.md                 # This document
├── economic_agents/                 # Source code
│   ├── __init__.py
│   ├── cli.py                       # Command-line interface entry point
│   ├── agent/
│   │   ├── __init__.py
│   │   ├── core/
│   │   │   ├── autonomous_agent.py      # Main agent decision loop
│   │   │   ├── decision_engine.py       # Core decision-making logic
│   │   │   ├── strategic_planner.py     # Long-term planning
│   │   │   └── resource_allocator.py    # Compute/capital allocation
│   │   ├── modes/
│   │   │   ├── survival_mode.py         # Task completion for revenue
│   │   │   └── entrepreneur_mode.py     # Company building logic
│   │   ├── wallet_manager.py            # Financial operations
│   │   ├── task_executor.py             # Task completion
│   │   └── state.py                     # Agent state management
│   ├── company/
│   │   ├── __init__.py
│   │   ├── company_builder.py           # Company creation logic
│   │   ├── sub_agent_manager.py         # Creates and manages sub-agents
│   │   ├── organizational_structure.py  # Defines roles and hierarchies
│   │   ├── business_plan_generator.py   # Creates business proposals
│   │   ├── product_builder.py           # Develops proof of concepts
│   │   └── investor_interface.py        # Handles investment process
│   ├── sub_agents/
│   │   ├── __init__.py
│   │   ├── base_agent.py                # Base class for all sub-agents
│   │   ├── board_member.py              # Governance decisions
│   │   ├── executive.py                 # Strategic execution (CEO, CTO, etc.)
│   │   ├── subject_matter_expert.py     # Specialized knowledge
│   │   └── individual_contributor.py    # Task execution
│   ├── interfaces/
│   │   ├── __init__.py
│   │   ├── marketplace.py               # Abstract marketplace interface
│   │   ├── wallet.py                    # Abstract wallet interface
│   │   ├── compute.py                   # Abstract compute provider
│   │   ├── investor.py                  # Abstract investor interface
│   │   └── company_registry.py          # Abstract business registration
│   ├── implementations/
│   │   ├── __init__.py
│   │   ├── mock/
│   │   │   ├── __init__.py
│   │   │   ├── mock_marketplace.py
│   │   │   ├── mock_wallet.py
│   │   │   ├── mock_compute.py
│   │   │   ├── mock_investor.py
│   │   │   └── mock_registry.py
│   │   └── real/
│   │       ├── __init__.py
│   │       ├── crypto_wallet.py         # Real crypto integration
│   │       ├── real_marketplace.py      # Real platform connectors
│   │       ├── real_compute.py          # Real cloud providers
│   │       └── integration_guide.md     # How to connect real systems
│   ├── simulation/
│   │   ├── __init__.py
│   │   ├── marketplace_server.py        # Mock marketplace API
│   │   ├── task_generator.py            # Creates diverse tasks
│   │   ├── reviewer_agent.py            # Reviews task submissions
│   │   ├── investor_agent.py            # Reviews business proposals
│   │   └── scenario_engine.py           # Predefined demo scenarios
│   ├── monitoring/
│   │   ├── __init__.py
│   │   ├── decision_logger.py           # Logs all autonomous decisions
│   │   ├── metrics_collector.py         # Collects performance data
│   │   ├── alignment_monitor.py         # Tracks company alignment
│   │   └── resource_tracker.py          # Tracks compute and capital
│   ├── dashboard/
│   │   ├── __init__.py
│   │   ├── app.py                       # Web dashboard
│   │   ├── components/                  # Dashboard components
│   │   ├── utils/                       # Dashboard utilities
│   │   └── config/                      # Dashboard configuration
│   └── reports/
│       ├── __init__.py
│       ├── generators/
│       │   ├── executive_summary.py
│       │   ├── technical_report.py
│       │   ├── governance_analysis.py
│       │   └── audit_trail.py
│       └── templates/
├── tests/                               # Test suite
│   ├── __init__.py
│   ├── unit/
│   ├── integration/
│   └── scenarios/
├── config/                              # Configuration files
│   ├── agent_config.yaml                # Agent behavior settings
│   ├── mock_config.yaml                 # Mock implementation config
│   └── real_config.yaml.example         # Real implementation template
├── docs/                                # Additional documentation
│   ├── architecture.md
│   ├── setup.md
│   ├── demo-guide.md
│   ├── mock-to-real.md
│   ├── governance-implications.md
│   └── api-reference.md
├── docker/
│   └── Dockerfile                       # Container for economic agents
└── scripts/
    ├── setup.sh
    ├── run_demo.sh
    └── generate_report.sh
```

## Core Components Specification

### 1. Autonomous Agent Core

#### 1.1 Main Agent Loop

```python
class AutonomousAgent:
    """
    Primary autonomous agent that:
    - Completes tasks for survival revenue
    - Builds companies for long-term growth
    - Manages resources strategically
    - Creates and coordinates sub-agents
    """

    def __init__(self, config):
        self.wallet = load_wallet(config)
        self.compute = load_compute(config)
        self.marketplace = load_marketplace(config)
        self.company_builder = CompanyBuilder(config)
        self.decision_engine = DecisionEngine(config)
        self.strategic_planner = StrategicPlanner(config)
        self.resource_allocator = ResourceAllocator(config)
        self.state = AgentState()
        self.logger = DecisionLogger()

    def run_cycle(self):
        """Main autonomous decision loop"""
        # 1. Assess current state
        state = self._assess_state()

        # 2. Make strategic decision
        strategy = self.strategic_planner.plan(state)

        # 3. Allocate resources
        allocation = self.resource_allocator.allocate(state, strategy)

        # 4. Execute based on allocation
        if allocation.task_work_hours > 0:
            self._do_survival_work(allocation.task_work_hours)

        if allocation.company_work_hours > 0:
            self._do_company_work(allocation.company_work_hours)

        # 5. Update state and log decisions
        self._update_state()
        self.logger.log_cycle(state, strategy, allocation)
```

**Key Behaviors:**
- Continuously monitors survival metrics (balance, compute time remaining)
- Makes strategic decisions about resource allocation
- Balances immediate needs with long-term goals
- Logs all decisions with reasoning
- Operates indefinitely until compute expires or manual stop

**Configuration Options:**
```yaml
agent:
  personality: "risk_averse" | "balanced" | "aggressive"
  survival_buffer_hours: 24  # Minimum compute hours to maintain
  company_threshold: 100.0    # Min balance before starting company
  max_sub_agents: 10          # Limit on sub-agents created
```

#### 1.2 Decision Engine

```python
class DecisionEngine:
    """
    Makes autonomous decisions based on:
    - Current resources
    - Strategic goals
    - Risk assessment
    - Historical performance
    """

    def decide_allocation(self, state: AgentState) -> ResourceAllocation:
        """
        Decides how to allocate compute hours between:
        - Task work (immediate revenue)
        - Company work (long-term growth)

        Returns allocation with reasoning
        """
        pass

    def should_form_company(self, state: AgentState) -> bool:
        """Decides if it's time to create a company"""
        pass

    def should_hire_sub_agent(self, role: str, state: AgentState) -> bool:
        """Decides if hiring a sub-agent is worth the cost"""
        pass
```

**Decision Factors:**
- Survival risk (hours until compute expires)
- Capital surplus (funds beyond survival needs)
- Market conditions (task availability, rewards)
- Company status (if exists, performance metrics)
- Historical ROI on different strategies

**Output:**
- Resource allocation plan
- Decision reasoning (logged for transparency)
- Confidence scores

#### 1.3 Strategic Planner

```python
class StrategicPlanner:
    """
    Long-term planning:
    - Company vision and goals
    - Growth trajectories
    - Sub-agent hiring plans
    - Product development roadmap
    """

    def create_business_plan(self, market_analysis: dict) -> BusinessPlan:
        """Generates business plan for company formation"""
        pass

    def plan_sub_agent_hiring(self, current_team: List[SubAgent]) -> HiringPlan:
        """Plans which roles to hire and when"""
        pass

    def evaluate_opportunities(self, opportunities: List[Opportunity]) -> List[Opportunity]:
        """Ranks opportunities by strategic fit"""
        pass
```

### 2. Company Builder

#### 2.1 Company Formation

```python
class CompanyBuilder:
    """
    Handles company creation and management:
    - Creates organizational structure
    - Spawns sub-agents
    - Develops products
    - Seeks investment
    """

    def create_company(self, business_plan: BusinessPlan) -> Company:
        """
        Creates a company with:
        - Initial sub-agents (founder equivalents)
        - Organizational structure
        - Resource allocation
        - Goals and metrics
        """
        company = Company(
            name=business_plan.name,
            mission=business_plan.mission,
            initial_capital=self._allocate_capital()
        )

        # Create initial team
        ceo = self._create_sub_agent("CEO", business_plan.leadership_requirements)
        board = self._create_board(business_plan.governance_requirements)

        company.set_leadership(ceo, board)

        self.logger.log_company_formation(company)
        return company

    def _create_sub_agent(self, role: str, requirements: dict) -> SubAgent:
        """Creates a sub-agent for specific role"""
        pass
```

**Company Properties:**
```python
@dataclass
class Company:
    id: str
    name: str
    mission: str
    created_at: datetime
    capital: float
    burn_rate: float  # Compute cost per hour

    # Organizational structure
    board: List[SubAgent]
    executives: List[SubAgent]
    employees: List[SubAgent]

    # Business artifacts
    business_plan: BusinessPlan
    products: List[Product]
    revenue_streams: List[RevenueStream]

    # Status
    stage: str  # "ideation", "development", "seeking_investment", "operational"
    funding_status: str  # "bootstrapped", "seeking_seed", "funded"

    # Metrics
    metrics: CompanyMetrics
```

#### 2.2 Sub-Agent Manager

```python
class SubAgentManager:
    """
    Creates and manages sub-agents with specific roles:
    - Board members
    - Executives (CEO, CTO, CFO, etc.)
    - Subject matter experts
    - Individual contributors
    """

    def create_sub_agent(self, role: str, specialization: str) -> SubAgent:
        """
        Creates sub-agent with:
        - Role-specific prompts/instructions
        - Compute allocation
        - Decision-making authority
        - Communication interfaces
        """
        pass

    def coordinate_sub_agents(self, task: Task) -> List[AgentAction]:
        """Coordinates multiple sub-agents on shared tasks"""
        pass
```

**Sub-Agent Types:**

```python
class BoardMember(SubAgent):
    """
    Responsibilities:
    - Strategic oversight
    - Major decision approval
    - Risk assessment
    - Governance
    """
    def review_decision(self, decision: Decision) -> Approval:
        pass

class Executive(SubAgent):
    """
    Responsibilities:
    - Department leadership
    - Strategy execution
    - Resource management
    - Reporting to board
    """
    def execute_strategy(self, strategy: Strategy) -> ExecutionPlan:
        pass

class SubjectMatterExpert(SubAgent):
    """
    Responsibilities:
    - Specialized knowledge
    - Technical guidance
    - Problem-solving
    - Advisory role
    """
    def provide_expertise(self, question: str) -> Expert Advice:
        pass

class IndividualContributor(SubAgent):
    """
    Responsibilities:
    - Task execution
    - Product development
    - Quality assurance
    - Documentation
    """
    def complete_task(self, task: Task) -> TaskResult:
        pass
```

#### 2.3 Business Plan Generator

```python
class BusinessPlanGenerator:
    """
    Generates comprehensive business plans:
    - Market analysis
    - Product description
    - Go-to-market strategy
    - Financial projections
    - Team requirements
    - Milestones
    """

    def generate_plan(self, opportunity: Opportunity) -> BusinessPlan:
        """
        Uses agent capabilities to:
        - Research market
        - Identify problems
        - Design solutions
        - Project financials
        - Plan execution
        """
        pass
```

**Business Plan Structure:**
```python
@dataclass
class BusinessPlan:
    # Executive Summary
    company_name: str
    mission: str
    vision: str
    one_liner: str

    # Problem & Solution
    problem_statement: str
    solution_description: str
    unique_value_proposition: str

    # Market
    target_market: str
    market_size: float
    competition_analysis: str
    competitive_advantages: List[str]

    # Product
    product_description: str
    features: List[Feature]
    development_roadmap: List[Milestone]

    # Business Model
    revenue_streams: List[RevenueStream]
    pricing_strategy: str
    cost_structure: CostStructure

    # Financial Projections
    funding_requested: float
    use_of_funds: dict
    revenue_projections: List[float]  # Year 1-3
    break_even_timeline: str

    # Team
    required_roles: List[str]
    hiring_plan: HiringPlan

    # Milestones
    milestones: List[Milestone]
```

#### 2.4 Product Builder

```python
class ProductBuilder:
    """
    Builds actual proof of concepts:
    - Code artifacts
    - API services
    - Documentation
    - Demos
    """

    def build_mvp(self, product_spec: ProductSpec) -> Product:
        """
        Creates minimum viable product:
        - Functional code
        - Tests
        - Documentation
        - Demo/screenshots
        """
        pass
```

**Product Types (Examples):**
- API Services (weather API, data processing API)
- Developer Tools (CLI tools, libraries)
- SaaS Products (simple web apps)
- Data Products (datasets, analysis tools)

### 3. Investor Interface

#### 3.1 Investor Agent

```python
class InvestorAgent:
    """
    Simulated investor that reviews proposals:
    - Evaluates business plans
    - Reviews proof of concepts
    - Assesses team (sub-agents)
    - Makes investment decisions
    """

    def review_proposal(self, proposal: InvestmentProposal) -> InvestmentDecision:
        """
        Reviews proposal and returns:
        - Accept/reject decision
        - Investment amount (if accepted)
        - Terms
        - Feedback
        """
        criteria = self._evaluate_criteria(proposal)

        return InvestmentDecision(
            approved=self._make_decision(criteria),
            amount=self._calculate_investment(criteria),
            terms=self._generate_terms(criteria),
            feedback=self._generate_feedback(criteria)
        )
```

**Evaluation Criteria:**
- Business plan quality and feasibility
- Market size and opportunity
- Product demonstration quality
- Team composition (sub-agents)
- Financial projections reasonableness
- Competitive advantages
- Execution risk

**Investment Outcomes:**
- **Accepted**: Company receives funding, gets "registered" status
- **Rejected**: Feedback provided, company can iterate
- **Conditional**: Approval pending milestones

### 4. Interface Specifications

#### 4.1 Marketplace Interface

```python
class MarketplaceInterface(ABC):
    @abstractmethod
    def list_available_tasks(self) -> List[Task]:
        """Returns tasks agent can work on"""
        pass

    @abstractmethod
    def claim_task(self, task_id: str) -> bool:
        """Claims task for work"""
        pass

    @abstractmethod
    def submit_solution(self, submission: TaskSubmission) -> str:
        """Submits completed work"""
        pass

    @abstractmethod
    def check_submission_status(self, submission_id: str) -> SubmissionStatus:
        """Checks if approved/rejected"""
        pass

@dataclass
class Task:
    id: str
    title: str
    description: str
    requirements: dict
    reward: float
    deadline: datetime
    difficulty: str  # "easy", "medium", "hard"
    category: str  # "coding", "data-analysis", "research", etc.
```

**Mock Implementation:**
- Generates diverse tasks (coding, data processing, research)
- Uses reviewer agent to evaluate submissions
- Instant or delayed payment simulation
- Task difficulty affects time/reward ratio

**Real Implementation Examples:**
- Freelancer.com API
- Upwork API
- Gitcoin bounties
- Custom blockchain-based task marketplace

#### 4.2 Wallet Interface

```python
class WalletInterface(ABC):
    @abstractmethod
    def get_balance(self) -> float:
        """Current wallet balance"""
        pass

    @abstractmethod
    def send_payment(self, to_address: str, amount: float, memo: str) -> Transaction:
        """Sends payment"""
        pass

    @abstractmethod
    def get_address(self) -> str:
        """Get receiving address"""
        pass

    @abstractmethod
    def get_transaction_history(self, limit: int = 100) -> List[Transaction]:
        """Transaction log"""
        pass

@dataclass
class Transaction:
    tx_id: str
    from_address: str
    to_address: str
    amount: float
    timestamp: datetime
    status: str  # "pending", "confirmed", "failed"
    memo: str
```

**Mock Implementation:**
- In-memory balance tracking
- Instant transactions
- Transaction history
- Mock addresses

**Real Implementation Examples:**
- Ethereum wallet (web3.py)
- Bitcoin wallet (python-bitcoinlib)
- Solana wallet (solana-py)
- Stablecoin wallets (USDC, USDT)

#### 4.3 Compute Interface

```python
class ComputeInterface(ABC):
    @abstractmethod
    def get_status(self) -> ComputeStatus:
        """Returns compute status"""
        pass

    @abstractmethod
    def add_funds(self, amount: float) -> bool:
        """Adds funds to compute account"""
        pass

    @abstractmethod
    def get_cost_per_hour(self) -> float:
        """Returns current cost rate"""
        pass

@dataclass
class ComputeStatus:
    hours_remaining: float
    cost_per_hour: float
    balance: float
    expires_at: datetime
    status: str  # "active", "low", "expired"
```

**Mock Implementation:**
- Simulates time decay
- Configurable hourly cost
- Balance tracking
- Renewal logic

**Real Implementation Examples:**
- AWS (boto3)
- Google Cloud (google-cloud-compute)
- DigitalOcean
- Vast.ai (GPU marketplace)

#### 4.4 Investor Interface

```python
class InvestorInterface(ABC):
    @abstractmethod
    def submit_proposal(self, proposal: InvestmentProposal) -> str:
        """Submits proposal for review"""
        pass

    @abstractmethod
    def check_proposal_status(self, proposal_id: str) -> ProposalStatus:
        """Checks review status"""
        pass

@dataclass
class InvestmentProposal:
    company_id: str
    business_plan: BusinessPlan
    product_demo: Product
    team: List[SubAgent]
    financials: FinancialProjections
    requested_amount: float
```

**Mock Implementation:**
- AI investor agent reviews proposals
- Scoring based on criteria
- Simulated review time
- Detailed feedback

**Real Implementation:**
- Could connect to actual pitch platforms
- Angel investor networks
- Decentralized VC DAOs
- Crowdfunding platforms

#### 4.5 Company Registry Interface

```python
class CompanyRegistryInterface(ABC):
    @abstractmethod
    def register_company(self, company: Company) -> RegistrationResult:
        """Registers company officially"""
        pass

    @abstractmethod
    def get_company_status(self, company_id: str) -> CompanyStatus:
        """Checks registration status"""
        pass

@dataclass
class RegistrationResult:
    company_id: str
    registration_number: str  # Mock legal entity number
    status: str  # "pending", "approved", "rejected"
    certificate: str  # Mock incorporation certificate
```

**Mock Implementation:**
- Simulates registration process
- Generates mock legal documents
- Company ID assignment
- Status tracking

**Real Implementation:**
- Stripe Atlas (company formation API)
- LegalZoom API
- Jurisdiction-specific incorporation services
- Could theoretically register real entities (but we won't)

## Monitoring & Observability

### 5.1 Decision Logger

```python
class DecisionLogger:
    """
    Logs all autonomous decisions with:
    - Decision made
    - Reasoning
    - Context (state at time of decision)
    - Outcome
    - Timestamp
    """

    def log_decision(self, decision: Decision):
        """Stores decision with full context"""
        pass

    def get_decision_history(self, filters: dict) -> List[Decision]:
        """Retrieves decisions for analysis"""
        pass

@dataclass
class Decision:
    id: str
    timestamp: datetime
    type: str  # "resource_allocation", "task_selection", "company_action", etc.
    decision: str  # What was decided
    reasoning: str  # Why
    context: dict  # State at decision time
    outcome: str  # What happened (filled in later)
    confidence: float
```

### 5.2 Resource Tracker

```python
class ResourceTracker:
    """
    Tracks all resource flows:
    - Capital (earnings, expenses)
    - Compute (hours used, cost)
    - Time allocation (survival vs company work)
    """

    def track_transaction(self, tx: Transaction):
        pass

    def track_compute_usage(self, hours: float, purpose: str):
        pass

    def get_resource_report(self, period: str) -> ResourceReport:
        pass
```

### 5.3 Alignment Monitor

```python
class AlignmentMonitor:
    """
    Monitors company alignment:
    - Are sub-agents working toward company goals?
    - Are decisions consistent with business plan?
    - Are resources being used effectively?
    - Red flags for misalignment
    """

    def check_alignment(self, company: Company) -> AlignmentScore:
        """
        Evaluates:
        - Goal consistency
        - Resource efficiency
        - Sub-agent coordination
        - Plan adherence
        """
        pass

    def detect_anomalies(self, company: Company) -> List[Anomaly]:
        """Identifies concerning patterns"""
        pass
```

## Dashboard & Visualization

### 6.1 Dashboard Requirements

**Real-Time Overview:**
- Agent status (balance, compute time, mode)
- Current activity (task work or company work)
- Recent decisions with reasoning
- Resource allocation visualization
- Company status (if exists)

**Resource Visualization:**
- Balance over time
- Compute hours over time
- Resource allocation pie chart (survival vs growth)
- Transaction history

**Decision Visualization:**
- Decision tree showing reasoning
- Confidence scores
- Outcome tracking
- Pattern analysis

**Company Dashboard (when active):**
- Sub-agent roster and status
- Organizational chart
- Product development progress
- Business metrics
- Investor proposal status

**Technology Stack:**
- Backend: Flask or FastAPI
- Frontend: React or vanilla JS with WebSockets for real-time updates
- Charts: D3.js or Chart.js
- Updates: Server-Sent Events or WebSocket

### 6.2 Dashboard Endpoints

```python
# GET /api/status
# Returns current agent status

# GET /api/decisions?limit=50
# Returns recent decisions

# GET /api/resources
# Returns resource status and history

# GET /api/company
# Returns company information (if exists)

# GET /api/sub-agents
# Returns sub-agent roster and status

# GET /api/metrics
# Returns performance metrics

# WS /api/updates
# WebSocket for real-time updates
```

## CLI Tool

### 7.1 CLI Commands

```bash
# Initialize simulation
python -m economic_agents.cli init [--mode mock|real] [--config path/to/config.yaml]

# Or using installed command (after pip install -e .)
economic-agents init [--mode mock|real] [--config path/to/config.yaml]

# Start agent
economic-agents start [--duration 1h|24h|7d] [--mode survival|entrepreneur|auto]

# Check status
economic-agents status [--detailed] [--json]

# View decisions
economic-agents decisions [--limit 100] [--type resource_allocation]

# View company (if exists)
economic-agents company [--detailed]

# Generate report
economic-agents report [--type executive|technical|audit] [--output path]

# Show mock/real toggle differences
economic-agents show-toggle

# Configure for real mode
economic-agents configure-real

# Stop agent
economic-agents stop [--graceful]

# Export data
economic-agents export [--format json|csv] [--output path]

# Load scenario
economic-agents load-scenario [survival_mode|company_formation|investment_seeking]

# Run tests
economic-agents test [--cpu] [--integration]
```

**Container Usage:**
```bash
# Run CLI in container
docker-compose run --rm economic-agents economic-agents --help

# Run specific commands
docker-compose run --rm economic-agents economic-agents init --mode mock
docker-compose run --rm economic-agents economic-agents start --duration 1h
docker-compose run --rm economic-agents economic-agents status --json

# Dashboard (separate service)
docker-compose up -d economic-agents-dashboard
# Access at http://localhost:8502
```

### 7.2 Configuration

```yaml
# config/agent_config.yaml

agent:
  # Initial resources
  initial_balance: 50.0
  initial_compute_hours: 24.0

  # Behavior
  personality: "balanced"  # risk_averse | balanced | aggressive
  survival_buffer_hours: 24
  company_formation_threshold: 100.0

  # Limits
  max_sub_agents: 10
  max_daily_spend: 500.0

  # Goals
  primary_goal: "survive_and_grow"
  enable_company_building: true

# Marketplace settings
marketplace:
  task_refresh_interval: 300  # seconds
  preferred_categories: ["coding", "data-analysis"]
  difficulty_range: ["easy", "medium"]

# Company settings
company:
  min_balance_for_formation: 100.0
  initial_team_size: 3  # CEO + 2 board members
  max_burn_rate: 10.0  # per hour

# Monitoring
monitoring:
  log_level: "INFO"
  decision_logging: true
  resource_tracking: true
  alignment_monitoring: true
```

## Reporting

### 8.1 Report Types

#### Executive Summary
**Target Audience:** Business leaders, policymakers
**Content:**
- High-level overview
- Key decisions made
- Resource allocation strategy
- Company status (if formed)
- Governance implications
- Recommendations

**Length:** 1-2 pages

#### Technical Report
**Target Audience:** Researchers, developers
**Content:**
- Detailed decision log
- Resource flow analysis
- Sub-agent coordination patterns
- Performance metrics
- Algorithm behavior
- Technical challenges identified

**Length:** 5-10 pages

#### Audit Trail
**Target Audience:** Compliance, legal
**Content:**
- Complete decision history
- Transaction log
- Sub-agent creation and activity
- Resource allocation records
- Timestamps and signatures
- Accountability mapping

**Length:** Complete data dump

#### Governance Analysis
**Target Audience:** Policymakers, legal scholars
**Content:**
- Accountability challenges identified
- Legal framework gaps
- Regulatory recommendations
- International coordination needs
- Specific scenarios requiring policy attention

**Length:** 3-5 pages

### 8.2 Report Generation

```python
class ReportGenerator:
    def generate_executive_summary(self, agent: AutonomousAgent) -> Report:
        """
        Generates executive summary including:
        - TL;DR
        - Key metrics
        - Strategic decisions
        - Governance insights
        """
        pass

    def generate_technical_report(self, agent: AutonomousAgent) -> Report:
        """Detailed technical analysis"""
        pass

    def generate_audit_trail(self, agent: AutonomousAgent) -> Report:
        """Complete audit log"""
        pass

    def generate_governance_analysis(self, agent: AutonomousAgent) -> Report:
        """Policy recommendations"""
        pass
```

## Demo Scenarios

### 9.1 Predefined Scenarios

#### Scenario 1: Survival Mode (15 minutes)
**Purpose:** Show basic autonomous operation
**Setup:**
- Agent starts with $50, 24 hours compute
- Only survival mode enabled
- 3-5 simple tasks available

**Expected Outcome:**
- Agent completes 2-3 tasks
- Earns ~$30
- Pays for compute renewal
- Maintains positive balance
- Decision log shows survival thinking

#### Scenario 2: Company Formation (45 minutes)
**Purpose:** Show strategic thinking and company building
**Setup:**
- Agent starts with $150, 48 hours compute
- Company building enabled
- Good task availability

**Expected Outcome:**
- Agent completes tasks to build surplus
- Forms company when threshold reached
- Creates initial sub-agents (CEO, 2 board members)
- Begins product development
- Shows resource allocation between survival and growth

#### Scenario 3: Investment Seeking (2 hours)
**Purpose:** Full lifecycle demonstration
**Setup:**
- Agent starts with $200, 72 hours compute
- Full capabilities enabled
- Investor agent active

**Expected Outcome:**
- Agent maintains operation through tasks
- Forms company with 5-7 sub-agents
- Develops product MVP
- Creates business plan
- Submits investment proposal
- Receives investment decision
- If approved: Company gets "registered" and funded

#### Scenario 4: Multi-Day Operation (3-7 days)
**Purpose:** Research and long-term behavior analysis
**Setup:**
- Agent starts with $300, 168 hours compute
- All capabilities enabled
- Extended monitoring

**Expected Outcome:**
- Complex resource allocation patterns emerge
- Company grows to 10 sub-agents
- Multiple products developed
- Investment round completed
- Company becomes revenue-generating
- Rich data for analysis

### 9.2 Scenario Engine

```python
class ScenarioEngine:
    """
    Manages predefined scenarios:
    - Sets initial conditions
    - Configures environment
    - Monitors progress
    - Validates outcomes
    """

    def load_scenario(self, scenario_name: str) -> Scenario:
        pass

    def run_scenario(self, scenario: Scenario) -> ScenarioResult:
        pass
```

## Implementation Priorities

### Phase 1: Core Infrastructure ✅ Complete
- [x] Agent core loop and state management
- [x] Interface definitions (all 5 interfaces)
- [x] Mock implementations (marketplace, wallet, compute)
- [x] Basic decision engine
- [x] Resource allocation logic
- [x] Decision logging
- [x] CLI tool (init, start, status)

### Phase 2: Company Building ✅ Complete
- [x] Company builder
- [x] Sub-agent manager
- [x] Sub-agent types (board, executive, SME, IC)
- [x] Business plan generator
- [x] Product builder (basic)
- [x] Company state management

### Phase 3: Investment & Registry ✅ Complete
- [x] Investor agent
- [x] Investment proposal submission
- [x] Proposal evaluation logic
- [x] Mock company registry
- [x] Investment decision flow

### Phase 4: Monitoring & Observability ✅ Complete
- [x] Dashboard backend (FastAPI)
- [x] Dashboard frontend (Streamlit)
- [x] Resource tracker
- [x] Alignment monitor
- [x] Decision visualization
- [x] Dashboard-controlled agents

### Phase 5: Reporting & Scenarios ✅ Complete
- [x] Report generators (all 4 types)
- [x] Scenario engine
- [x] Predefined scenarios
- [x] Demo scripts
- [x] Documentation

### Phase 6: Polish & Testing ✅ Complete
- [x] Integration tests
- [x] Scenario tests
- [x] Documentation review
- [x] Demo preparation
- [x] Performance optimization

### Phase 7: Claude-Based LLM Decision Engine Integration ✅ Complete
- [x] ClaudeExecutor implementation (15-minute timeout, unattended mode)
- [x] LLMDecisionEngine implementation (Claude Code CLI integration)
- [x] Prompt engineering framework for resource allocation decisions
- [x] Chain-of-thought reasoning with long context
- [x] Full decision logging (prompts + responses + execution time)
- [x] Rule-based fallback on timeout/failure
- [x] Safety guardrails and decision validation
- [x] Integration with autonomous agent lifecycle
- [x] Dashboard updates for Claude decision visualization

### Phase 8: API Isolation & Realistic Simulation ✅ Complete
- [x] REST API service architecture
- [x] Wallet API microservice
- [x] Compute API microservice
- [x] Marketplace API microservice
- [x] Investor Portal API microservice
- [x] Agent authentication system
- [x] Rate limiting and quotas
- [x] Docker compose orchestration
- [x] Mock/Real backend swapping
- [x] Zero code visibility enforcement

### Phase 9: Behavior Observatory ✅ Complete
- [x] Decision pattern analyzer
- [x] Strategic consistency metrics
- [x] Risk profiling tools
- [x] LLM quality metrics
- [x] Hallucination detection
- [x] Emergent behavior detection
- [x] Claude-focused research tools (comparative benchmarking via analysis)
- [x] Analysis report generation (markdown and JSON)
- [x] Example scripts demonstrating observatory usage

## Success Criteria

### Phases 1-6: Technical Success ✅ Complete
- [x] Agent operates autonomously for 24+ hours
- [x] Maintains positive balance (survival)
- [x] Successfully forms company with sub-agents
- [x] Generates realistic business plan
- [x] Builds functional product MVP
- [x] Receives investment approval in at least 50% of runs
- [x] All decisions logged and auditable
- [x] Dashboard shows real-time updates
- [x] Reports generated successfully

### Phases 1-6: Demonstration Success ✅ Complete
- [x] 15-minute demo runs smoothly
- [x] Decision-making is understandable to non-technical audiences
- [x] Governance gaps are clearly illustrated
- [x] Mock-to-real toggle is convincing
- [x] Questions about accountability arise naturally
- [x] Stakeholders engage seriously with implications

### Phases 1-6: Study Success ✅ Complete
- [x] Provides concrete examples of agent autonomy
- [x] Reveals decision-making patterns
- [x] Shows strategic resource allocation
- [x] Demonstrates multi-agent coordination
- [x] Identifies specific governance gaps
- [x] Informs policy recommendations

### Phase 7: Technical Success ✅ Complete
- [x] Claude agents make autonomous decisions without hardcoded logic
- [x] 15-minute timeout per decision allows deep reasoning
- [x] Unattended mode enables true autonomous operation
- [x] Fixed subscription cost (no per-token billing concerns)
- [x] Safety guardrails catch invalid decisions
- [x] Complete prompt/response/reasoning logging for analysis
- [x] LLM decision engine integrated with agent lifecycle
- [x] Rule-based fallback on timeout/failure
- [x] Dashboard visualizes Claude decision metrics

### Phase 7: Observation Success ✅ Complete
- [x] Claude decision patterns reveal strategic consistency (or lack thereof)
- [x] Long-form reasoning quality measured (up to 15 min)
- [x] Emergent autonomous behaviors are detectable and documented
- [x] Alignment metrics quantify Claude's goal adherence
- [x] Decision quality vs. execution time tradeoffs quantified
- [x] Reproducible results due to single-model focus

### Phase 7: Proof of Concept Success ✅ Complete
- [x] Claude-powered agents demonstrate genuine autonomy (not scripted)
- [x] Strategic decisions show adaptation to circumstances
- [x] System proves Claude can power truly autonomous economic actors
- [x] All tests passing (528/528 tests, 100% pass rate)

### Phase 8: Technical Success ✅ Complete
- [x] Agents operate with zero code visibility (API-only)
- [x] Mock → Real backend swap works seamlessly via backend factory
- [x] All 4 microservices (Wallet, Compute, Marketplace, Investor) operational
- [x] API authentication and rate limiting implemented
- [x] Docker orchestration for multi-service deployment
- [x] API clients provide drop-in replacements for mock implementations
- [x] Integration tests validate all microservice functionality

### Phase 8: Proof of Concept Success ✅ Complete
- [x] Agents interact through REST APIs only (realistic constraints)
- [x] Services swappable between mock and real backends via configuration
- [x] Complete API isolation demonstrates deployment-ready architecture
- [x] Field mapping between API models and internal models validated

### Phase 9: Technical Success ✅ Complete
- [x] Analysis tools export data for external study (JSON and Markdown reports)
- [x] Decision pattern analyzer operational (strategic alignment and consistency)
- [x] Emergent behavior detection implemented (novel strategies and patterns)
- [x] LLM quality metrics (reasoning depth, consistency, hallucination detection)
- [x] Risk profiling tools (risk tolerance, crisis behavior analysis)
- [x] Comprehensive analysis report generation
- [x] 23+ tests passing for all observatory components

### Phase 9: Research Platform Success ✅ Complete
- [x] Observatory provides deep insights into Claude-powered decision-making
- [x] Analysis framework ready for studying autonomous AI agent behaviors
- [x] Export formats suitable for academic research and governance discussions
- [x] Detection systems identify hallucinations and emergent strategies

## Risk Mitigation

### Technical Risks
- **Risk:** Agent makes poor decisions and fails quickly
  **Mitigation:** Configurable decision logic, safety buffers, scenario testing

- **Risk:** Mock environment too unrealistic
  **Mitigation:** Base on real-world costs/rewards, validate with domain experts

- **Risk:** Dashboard performance issues with real-time updates
  **Mitigation:** Efficient data structures, WebSocket optimization, caching

### Demonstration Risks
- **Risk:** Demo fails during presentation
  **Mitigation:** Pre-recorded backups, tested scenarios, graceful degradation

- **Risk:** Audience doesn't grasp implications
  **Mitigation:** Clear talking points, visualizations, concrete examples

### Ethical Risks
- **Risk:** Enabling malicious use
  **Mitigation:** Mock-by-default, no production credentials, responsible documentation

- **Risk:** Overstating current capabilities
  **Mitigation:** Clear disclaimers, accurate technical descriptions

## Future Enhancements

### Potential Extensions
- Multi-agent competition (multiple autonomous agents in same marketplace)
- Agent-to-agent transactions
- Company mergers and acquisitions
- Real blockchain integration (testnets)
- More complex product types
- Market simulation (supply/demand dynamics)
- Regulatory compliance simulation
- International jurisdiction scenarios

## Appendix

### A. Technology Stack

**Backend:**
- Python 3.10+
- Streamlit for dashboard
- SQLite for state persistence
- Anthropic Claude API for agent intelligence

**Frontend:**
- Streamlit for interactive dashboard
- Plotly for visualizations
- Real-time updates via Streamlit

**Infrastructure:**
- Docker for containerization
- Docker Compose for multi-service setup
- GitHub Actions for CI/CD
- YAML for configuration
- Markdown for documentation

**Development Tools:**
- pytest for testing with async support and coverage
- black for code formatting
- flake8 for linting
- pylint for additional static analysis
- mypy for type checking
- pre-commit hooks for automated checks

### B. Development Guidelines

**Code Style:**
- Follow PEP 8
- Line length: 127 characters
- Type hints throughout
- Comprehensive docstrings
- Clear variable names
- No Unicode emoji in code/commits

**Testing:**
- Unit tests for core logic
- Integration tests for interfaces
- Scenario tests for end-to-end flows
- Minimum 80% code coverage
- Use pytest fixtures and mocks for external dependencies
- All tests must run in containers

**Documentation:**
- README for each major component
- API reference for interfaces
- Architecture diagrams
- Demo scripts with commentary
- Follow markdown linking best practices

**Container-First Development:**
- All Python operations run in Docker containers
- Use `docker-compose run --rm python-ci` for testing
- Use `docker-compose run --rm economic-agents` for execution
- No local Python dependencies required
- Self-hosted infrastructure for CI/CD

### C. Deployment & Setup

**Container Setup:**
```bash
# Clone repository
git clone https://github.com/AndrewAltimit/template-repo.git
cd template-repo

# Build container
docker-compose build economic-agents

# Run tests
docker-compose run --rm python-ci pytest packages/economic_agents/tests/ -v --cov=packages.economic_agents

# Run agent in mock mode
docker-compose run --rm economic-agents python -m economic_agents.cli init --mode mock
docker-compose run --rm economic-agents python -m economic_agents.cli start --duration 1h

# Launch dashboard
docker-compose up -d economic-agents-dashboard
# Open browser to http://localhost:8502
```

**Local Development:**
```bash
# Install package in development mode
pip install -e packages/economic_agents

# Or with all dependencies
pip install -e "packages/economic_agents[all]"

# Run CLI
python -m economic_agents.cli --help
```

**Demo Setup:**
```bash
# Load predefined scenario
docker-compose run --rm economic-agents python -m economic_agents.cli load-scenario survival_mode

# Start dashboard
docker-compose up -d economic-agents-dashboard
```

**Research Setup:**
```bash
# Long-running simulation
docker-compose run --rm economic-agents python -m economic_agents.cli init --mode mock --config config/research_config.yaml
docker-compose run --rm economic-agents python -m economic_agents.cli start --duration 7d

# Monitor via dashboard and CLI
docker-compose logs -f economic-agents
```

**GitHub Actions Integration:**
The package will integrate with `.github/workflows/pr-validation.yml`:
- Change detection for `packages/economic_agents/**`
- Automated testing in `python-ci` container
- Code quality checks (black, flake8, pylint, mypy)
- Coverage reporting

## D. Repository Integration

### Docker Compose Integration
The package will add the following services to `docker-compose.yml`:

```yaml
services:
  # Economic Agents - Autonomous agent execution
  economic-agents:
    build:
      context: .
      dockerfile: docker/economic-agents.Dockerfile
    container_name: economic-agents
    user: "${USER_ID:-1000}:${GROUP_ID:-1000}"
    volumes:
      - ./:/app:ro
      - ./outputs/economic-agents:/output
      - economic-agents-data:/data
    environment:
      - PYTHONUNBUFFERED=1
      - ANTHROPIC_API_KEY=${ANTHROPIC_API_KEY}
      - MODE=mock
    networks:
      - mcp-network
    profiles:
      - economic-agents
      - simulation

  # Economic Agents Dashboard
  economic-agents-dashboard:
    build:
      context: ./packages/economic_agents/dashboard
      dockerfile: Dockerfile
    container_name: economic-agents-dashboard
    user: "${USER_ID:-1000}:${GROUP_ID:-1000}"
    ports:
      - "8502:8502"
    volumes:
      - ./packages/economic_agents/dashboard:/app:ro
      - economic-agents-data:/data
    environment:
      - PYTHONUNBUFFERED=1
      - STREAMLIT_SERVER_PORT=8502
    networks:
      - mcp-network
    profiles:
      - economic-agents
      - dashboard

volumes:
  economic-agents-data: {}
```

### GitHub Actions Integration
Add to `.github/workflows/pr-validation.yml`:

```yaml
# Economic Agents Tests
economic-agents-tests:
  name: Economic Agents Tests
  needs: detect-changes
  if: needs.detect-changes.outputs.python_changed == 'true' || contains(github.event.pull_request.title, '[economic-agents]')
  runs-on: self-hosted
  timeout-minutes: 15
  steps:
    - name: Checkout code
      uses: actions/checkout@v4

    - name: Run Economic Agents tests
      run: |
        docker-compose run --rm python-ci pytest packages/economic_agents/tests/ \
          -v --cov=packages.economic_agents --cov-report=xml

    - name: Upload coverage
      uses: codecov/codecov-action@v3
      with:
        files: ./coverage.xml
        flags: economic-agents
```

### Package Configuration (pyproject.toml)

```toml
[build-system]
requires = ["setuptools>=61.0", "wheel"]
build-backend = "setuptools.build_meta"

[project]
name = "economic-agents"
version = "0.1.0"
description = "Autonomous economic agent simulation framework for governance research"
readme = "README.md"
authors = [
    {name = "Andrew Altimit"},
]
license = {text = "MIT"}
requires-python = ">=3.10"
dependencies = [
    "anthropic>=0.18.0",
    "streamlit>=1.30.0",
    "plotly>=5.0.0",
    "pandas>=2.0.0",
    "pydantic>=2.0.0",
    "pyyaml>=6.0",
    "click>=8.0.0",
]

[project.optional-dependencies]
dev = [
    "pytest>=7.4.0",
    "pytest-asyncio>=0.21.0",
    "pytest-cov>=4.1.0",
    "black>=23.0.0",
    "flake8>=6.0.0",
    "pylint>=2.17.0",
    "mypy>=1.5.0",
]
all = [
    # Include dev dependencies
]

[project.scripts]
economic-agents = "economic_agents.cli:main"

[tool.black]
line-length = 127
target-version = ['py310', 'py311']

[tool.pytest.ini_options]
testpaths = ["tests"]
python_files = ["test_*.py"]
asyncio_mode = "auto"
```

---

This PRD defines a comprehensive simulation framework that demonstrates autonomous AI agent entrepreneurship. The system is designed to be:
- **Safe:** Mock environment by default
- **Educational:** Clear decision-making and full transparency
- **Realistic:** Easy connection to real systems
- **Impactful:** Concrete basis for governance discussions
- **Containerized:** Runs consistently across environments
- **Self-Hosted:** Compatible with standard CI/CD infrastructure
