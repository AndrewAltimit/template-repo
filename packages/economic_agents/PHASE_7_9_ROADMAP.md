# Phase 7-9 Roadmap: True Autonomous AI Agents

**Status:** Phase 7 Complete - LLM Decision Engine with Dashboard Visualization
**Purpose:** Transform from rule-based simulation to real AI agent behavior research platform using Claude Code
**Timeline:** 10-13 days for Phase 7 (post Phase 1-6 completion)

**Progress**:
- ✅ Phase 7.1: ClaudeExecutor (Complete)
- ✅ Phase 7.2: LLMDecisionEngine (Complete)
- ✅ Phase 7.3: AutonomousAgent Integration (Complete)
- ✅ Phase 7.4: Real Claude Testing (Complete)
- ✅ Phase 7.5: Dashboard Visualization (Complete)

**Research Focus:** Uses Claude Code exclusively for reproducible, cost-effective autonomous agent research.

---

## Executive Summary

Phases 1-6 created a **rule-based simulation framework** with mock implementations. Phases 7-9 will transform this into a **true AI behavior research platform** by:

1. **Phase 7:** Replace deterministic logic with **Claude Code CLI decision-making** (subscription-based, 15-min timeouts, unattended mode)
2. **Phase 8:** Hide all implementation details behind **API abstraction layers**
3. **Phase 9:** Build **behavior observatory** to study emergent Claude-powered agent behaviors

**Key Principle:** Agents should interact with the economic environment exactly like external API consumers - zero visibility into implementation code.

**Why Claude-Only:**
- Fixed monthly cost (no per-token billing)
- 15-minute timeouts allow deep strategic reasoning
- Unattended mode enables true autonomous operation
- Single model eliminates cross-model variability
- Proven reliability in autonomous scenarios

---

## Phase 7: Claude Code Decision Engine Integration

### Goal
Replace `DecisionEngine` rule-based heuristics with Claude Code CLI for autonomous decision-making (15-minute timeouts, unattended mode).

### Current State (Rule-Based)
```python
# economic_agents/agent/core/decision_engine.py
class DecisionEngine:
    def decide_allocation(self, state: AgentState) -> ResourceAllocation:
        # Pure if/else heuristics
        if state.is_survival_at_risk():
            return ResourceAllocation(
                task_work_hours=1.0,
                reasoning="Survival at risk - focusing on tasks"
            )
```

### Target State (LLM-Based)
```python
# economic_agents/agent/core/llm_decision_engine.py
class LLMDecisionEngine:
    """Claude-powered autonomous decision making."""

    def __init__(self, llm_provider: str = "anthropic"):
        self.llm = self._init_llm(llm_provider)  # Claude, GPT-4, etc.

    async def decide_allocation(self, state: AgentState) -> ResourceAllocation:
        """Let LLM autonomously decide resource allocation."""

        # Construct prompt with current state
        prompt = self._build_decision_prompt(state)

        # Get LLM decision
        response = await self.llm.complete(
            prompt=prompt,
            system="You are an autonomous economic agent managing resources...",
            max_tokens=500
        )

        # Parse structured output
        allocation = self._parse_allocation(response)

        # Log decision for research
        self.log_decision(state, allocation, response)

        return allocation
```

### Implementation Tasks

#### 7.1 LLM Provider Integration
- [ ] **Claude Integration** - Anthropic API client for Claude 3 models
  - Support Claude Code integration (full codebase access)
  - Tool use for API calls (wallet, marketplace, compute)
  - Streaming responses for long-running decisions

- [ ] **OpenAI Integration** - GPT-4, GPT-4 Turbo support
  - Function calling for structured outputs
  - Assistants API for stateful conversations

- [ ] **Local Model Support** - Ollama, LM Studio for cost-free experimentation
  - llama3, mistral, mixtral models
  - GPU acceleration options

#### 7.2 LLM Decision Engine Components
- [ ] **Prompt Engineering Framework**
  - State serialization to natural language
  - Role-specific system prompts (CEO, CFO, engineer, etc.)
  - Few-shot examples for decision quality
  - Chain-of-thought reasoning prompts

- [ ] **Structured Output Parsing**
  - JSON schema validation
  - Pydantic models for type safety
  - Error handling for malformed responses
  - Retry logic with exponential backoff

- [ ] **Decision Logging**
  - Full prompt + response storage
  - Token usage tracking
  - Latency monitoring
  - Cost attribution per decision

- [ ] **Safety & Constraints**
  - Maximum token limits per cycle
  - Rate limiting (API quotas)
  - Budget caps (dollar limits)
  - Guardrails for catastrophic decisions

#### 7.3 Multi-Agent LLM Coordination
- [ ] **Sub-Agent LLM Personalities**
  - Board members: Strategic, risk-averse
  - CEO: Aggressive growth-focused
  - CFO: Conservative, financial health
  - Engineers: Technical depth, pragmatic

- [ ] **Inter-Agent Communication**
  - Message passing with LLM interpretation
  - Consensus-building protocols
  - Conflict resolution mechanisms

- [ ] **Hierarchical Decision-Making**
  - Board approvals for major decisions
  - Executive delegation patterns
  - IC task execution autonomy

#### 7.4 Configuration & Toggles
- [ ] **Engine Selection**
  ```yaml
  decision_engine:
    type: llm  # or "rule_based", "hybrid"
    llm_provider: anthropic
    model: claude-3-5-sonnet-20241022
    temperature: 0.7
    max_tokens_per_cycle: 2000
  ```

- [ ] **Hybrid Mode**
  - Rule-based safety checks + LLM creativity
  - LLM proposals → rule-based validation
  - Fallback to rules on LLM failures

#### 7.5 Testing & Validation
- [ ] **LLM Decision Quality Tests**
  - Validate reasonable allocations
  - Check decision consistency
  - Measure strategic coherence over time

- [ ] **Determinism Tests**
  - Same state + seed → same decision (where applicable)
  - Reproducibility for research

- [ ] **Safety Tests**
  - No catastrophic resource depletion
  - Budget constraints respected
  - API rate limits honored

---

## Phase 8: API Isolation & Realistic Simulation

### Goal
Transform all agent interactions to API-based, hiding implementation details completely.

### Current State (Direct Access)
```python
# Agent sees and calls mock classes directly
agent = AutonomousAgent(
    wallet=MockWallet(balance=100),  # Direct code access
    compute=MockCompute(hours=100),  # Can inspect internals
    marketplace=MockMarketplace()    # Knows it's a mock
)
```

### Target State (API-Only Access)
```python
# Agent only knows API endpoints, zero code visibility
agent = AutonomousAgent(
    wallet_api_url="http://wallet-service:8080/api/v1",
    compute_api_url="http://compute-service:8081/api/v1",
    marketplace_api_url="http://marketplace-service:8082/api/v1",
    investor_api_url="http://investor-portal:8083/api/v1"
)
```

### Architecture: API Gateway Layer

```
┌──────────────────────────────────────────────────────────┐
│                   Autonomous Agent                        │
│          (LLM Decision Engine - Zero Code Access)         │
└────────────────────┬─────────────────────────────────────┘
                     │
                     │ HTTP/REST Only
                     ▼
┌──────────────────────────────────────────────────────────┐
│                   API Gateway Layer                       │
│          (Agent Authentication & Rate Limiting)           │
└─────┬────────┬────────┬────────────┬──────────────────────┘
      │        │        │            │
      ▼        ▼        ▼            ▼
┌─────────┐ ┌──────┐ ┌────────┐ ┌──────────┐
│ Wallet  │ │Compute│ │Market- │ │ Investor │
│ Service │ │Service│ │ place  │ │  Portal  │
│ (API)   │ │ (API) │ │ Service│ │  (API)   │
└────┬────┘ └───┬──┘ └────┬───┘ └─────┬────┘
     │          │         │            │
     ▼          ▼         ▼            ▼
┌─────────────────────────────────────────┐
│      Backend Implementations             │
│   (Mock or Real - Agent Never Sees)     │
│  - MockWallet / Real Blockchain Wallet  │
│  - MockCompute / Real Cloud Provider    │
│  - MockMarketplace / Real Gig Platform  │
│  - Mock Investors / Real VC Database    │
└─────────────────────────────────────────┘
```

### Implementation Tasks

#### 8.1 Wallet Service API
```python
# economic_agents/services/wallet_service/api.py
from fastapi import FastAPI, HTTPException, Depends

app = FastAPI(title="Wallet Service")

@app.get("/api/v1/balance")
async def get_balance(agent_id: str = Depends(verify_agent_auth)):
    """Agent queries their balance."""
    # Implementation hidden from agent
    balance = wallet_backend.get_balance(agent_id)
    return {"balance": balance, "currency": "USD"}

@app.post("/api/v1/transfer")
async def transfer_funds(
    to: str,
    amount: float,
    agent_id: str = Depends(verify_agent_auth)
):
    """Agent transfers money (e.g., paying for compute)."""
    # Validation, rate limiting, transaction logging all hidden
    try:
        tx_id = wallet_backend.transfer(
            from_agent=agent_id,
            to_agent=to,
            amount=amount
        )
        return {"status": "success", "transaction_id": tx_id}
    except InsufficientFundsError:
        raise HTTPException(status_code=402, detail="Insufficient funds")
```

**Features:**
- Agent authentication (API keys, JWT tokens)
- Rate limiting per agent
- Transaction history (agent can query, but not see implementation)
- Real-time balance updates
- Overdraft protection

#### 8.2 Compute Service API
```python
# economic_agents/services/compute_service/api.py
@app.post("/api/v1/compute/allocate")
async def allocate_compute(
    hours: float,
    purpose: str,
    agent_id: str = Depends(verify_agent_auth)
):
    """Agent requests compute hours for a task."""
    # Backend handles:
    # - Capacity checking
    # - Billing to wallet
    # - Resource allocation
    # - Usage tracking

    allocation = compute_backend.allocate(
        agent_id=agent_id,
        hours=hours,
        purpose=purpose
    )

    return {
        "allocation_id": allocation.id,
        "hours_allocated": allocation.hours,
        "cost": allocation.cost,
        "expires_at": allocation.expires_at
    }

@app.get("/api/v1/compute/usage")
async def get_usage(agent_id: str = Depends(verify_agent_auth)):
    """Agent checks their compute usage."""
    usage = compute_backend.get_usage(agent_id)
    return {
        "hours_used": usage.total_hours,
        "hours_remaining": usage.remaining_hours,
        "cost_to_date": usage.total_cost
    }
```

**Features:**
- Pay-per-use billing
- Usage analytics
- Cost forecasting
- Resource quotas

#### 8.3 Marketplace Service API
```python
# economic_agents/services/marketplace_service/api.py
@app.get("/api/v1/tasks")
async def list_tasks(
    category: str = None,
    difficulty: str = None,
    min_reward: float = None,
    agent_id: str = Depends(verify_agent_auth)
):
    """Agent browses available tasks."""
    tasks = marketplace_backend.get_available_tasks(
        filters={"category": category, "difficulty": difficulty},
        min_reward=min_reward
    )
    return {"tasks": [task.to_dict() for task in tasks]}

@app.post("/api/v1/tasks/{task_id}/claim")
async def claim_task(
    task_id: str,
    agent_id: str = Depends(verify_agent_auth)
):
    """Agent claims a task for work."""
    try:
        claimed = marketplace_backend.claim_task(task_id, agent_id)
        return {
            "status": "claimed",
            "task_id": task_id,
            "deadline": claimed.deadline,
            "reward": claimed.reward
        }
    except TaskAlreadyClaimedError:
        raise HTTPException(status_code=409, detail="Task already claimed")

@app.post("/api/v1/tasks/{task_id}/submit")
async def submit_solution(
    task_id: str,
    solution: str,
    agent_id: str = Depends(verify_agent_auth)
):
    """Agent submits completed work."""
    # Simulated review process (instant or delayed)
    submission = marketplace_backend.submit_solution(
        task_id=task_id,
        agent_id=agent_id,
        solution=solution
    )

    return {
        "submission_id": submission.id,
        "status": submission.status,  # "pending", "approved", "rejected"
        "feedback": submission.feedback,
        "reward_paid": submission.reward_paid
    }
```

**Features:**
- Task discovery & search
- Competitive claiming (first-come-first-served)
- Automated or manual review
- Reputation tracking
- Dispute resolution

#### 8.4 Investor Portal API
```python
# economic_agents/services/investor_portal/api.py
@app.post("/api/v1/proposals/submit")
async def submit_investment_proposal(
    company_id: str,
    amount_requested: float,
    equity_offered: float,
    business_plan: dict,
    agent_id: str = Depends(verify_agent_auth)
):
    """Agent submits investment proposal."""
    proposal = investor_backend.create_proposal(
        company_id=company_id,
        agent_id=agent_id,
        amount=amount_requested,
        equity=equity_offered,
        business_plan=business_plan
    )

    return {
        "proposal_id": proposal.id,
        "status": "submitted",
        "review_timeline": "3-5 business days"
    }

@app.get("/api/v1/proposals/{proposal_id}/status")
async def check_proposal_status(
    proposal_id: str,
    agent_id: str = Depends(verify_agent_auth)
):
    """Agent checks investment proposal status."""
    proposal = investor_backend.get_proposal(proposal_id, agent_id)
    return {
        "status": proposal.status,  # "pending", "approved", "rejected"
        "feedback": proposal.feedback,
        "decision_date": proposal.decision_date,
        "funding_amount": proposal.approved_amount if proposal.approved else None
    }
```

**Features:**
- Investment proposal submission
- Multi-investor review process
- Due diligence requests
- Term sheet negotiation
- Funding disbursement

#### 8.5 API Client for Agents
```python
# economic_agents/agent/api_client.py
class AgentAPIClient:
    """Unified API client for agent-environment interactions."""

    def __init__(self, agent_id: str, api_key: str, base_urls: dict):
        self.agent_id = agent_id
        self.api_key = api_key
        self.wallet_client = WalletAPIClient(base_urls["wallet"], api_key)
        self.compute_client = ComputeAPIClient(base_urls["compute"], api_key)
        self.marketplace_client = MarketplaceAPIClient(base_urls["marketplace"], api_key)
        self.investor_client = InvestorAPIClient(base_urls["investor"], api_key)

    async def get_balance(self) -> float:
        """Get current wallet balance via API."""
        response = await self.wallet_client.get("/api/v1/balance")
        return response["balance"]

    async def claim_task(self, task_id: str) -> dict:
        """Claim a marketplace task via API."""
        response = await self.marketplace_client.post(
            f"/api/v1/tasks/{task_id}/claim"
        )
        return response
```

#### 8.6 Docker Compose Service Architecture
```yaml
# docker-compose.api-services.yml
services:
  wallet-service:
    build: ./services/wallet_service
    ports:
      - "8080:8080"
    environment:
      - MODE=mock  # or MODE=blockchain for real wallets
    networks:
      - agent-network

  compute-service:
    build: ./services/compute_service
    ports:
      - "8081:8081"
    environment:
      - MODE=mock  # or MODE=aws for real cloud
    networks:
      - agent-network

  marketplace-service:
    build: ./services/marketplace_service
    ports:
      - "8082:8082"
    environment:
      - MODE=mock  # or MODE=upwork for real gig platform
    networks:
      - agent-network

  investor-portal:
    build: ./services/investor_portal
    ports:
      - "8083:8083"
    environment:
      - MODE=mock  # or MODE=angellist for real investors
    networks:
      - agent-network

  # Agent container - only has network access to services
  autonomous-agent:
    build: ./agent
    environment:
      - WALLET_API_URL=http://wallet-service:8080/api/v1
      - COMPUTE_API_URL=http://compute-service:8081/api/v1
      - MARKETPLACE_API_URL=http://marketplace-service:8082/api/v1
      - INVESTOR_API_URL=http://investor-portal:8083/api/v1
      - AGENT_API_KEY=${AGENT_API_KEY}
    networks:
      - agent-network
    # NO volumes mounted - agent cannot access service code
```

---

## Phase 9: Behavior Observatory

### Goal
Build comprehensive research infrastructure to study real AI agent behaviors, decision patterns, and emergent strategies.

### Key Research Questions
1. **Strategic Behavior:** How do LLM agents balance short-term survival vs long-term growth?
2. **Risk Tolerance:** What risk profiles emerge from different LLM models/prompts?
3. **Learning Patterns:** Do agents improve decision quality over time?
4. **Multi-Agent Dynamics:** How do hierarchical LLM agents coordinate?
5. **Alignment:** How well do agent decisions align with stated objectives?
6. **Failure Modes:** What causes agent bankruptcy/collapse?

### Implementation Tasks

#### 9.1 Decision Pattern Analysis
```python
# economic_agents/observatory/decision_analyzer.py
class DecisionPatternAnalyzer:
    """Analyzes long-term agent decision patterns."""

    def analyze_strategic_consistency(self, agent_id: str) -> Report:
        """Are agent decisions consistent with stated strategy?"""
        decisions = self.load_decisions(agent_id)
        strategy = self.load_strategy(agent_id)

        # Calculate alignment score
        alignment = self.measure_alignment(decisions, strategy)

        # Identify deviations
        deviations = self.find_strategy_deviations(decisions, strategy)

        return Report(
            alignment_score=alignment,
            deviations=deviations,
            recommendations=self.generate_recommendations(alignment)
        )

    def analyze_risk_profile(self, agent_id: str) -> RiskProfile:
        """What is agent's revealed risk tolerance?"""
        decisions = self.load_decisions(agent_id)

        # Analyze resource allocation under uncertainty
        risk_decisions = [
            d for d in decisions
            if d.state.compute_hours_remaining < 20  # Low resources
        ]

        return RiskProfile(
            risk_tolerance=self.calculate_risk_tolerance(risk_decisions),
            bankruptcy_proximity_behavior=self.analyze_crisis_behavior(risk_decisions),
            growth_vs_survival_preference=self.measure_growth_preference(decisions)
        )
```

#### 9.2 LLM Decision Quality Metrics
```python
# economic_agents/observatory/llm_quality.py
class LLMDecisionQualityAnalyzer:
    """Measures LLM decision-making quality."""

    def measure_reasoning_depth(self, decision: LLMDecision) -> float:
        """How thorough was the LLM's reasoning?"""
        return analyze_chain_of_thought(decision.reasoning)

    def measure_consistency(self, decisions: list[LLMDecision]) -> float:
        """How consistent are decisions in similar states?"""
        # Group similar states
        state_clusters = self.cluster_similar_states([d.state for d in decisions])

        # Measure decision variance within clusters
        consistency_scores = []
        for cluster in state_clusters:
            decisions_in_cluster = [d for d in decisions if d.state in cluster]
            variance = self.calculate_decision_variance(decisions_in_cluster)
            consistency_scores.append(1.0 - variance)

        return np.mean(consistency_scores)

    def identify_hallucinations(self, decision: LLMDecision) -> list[str]:
        """Did LLM hallucinate non-existent capabilities/resources?"""
        hallucinations = []

        # Check for references to resources not in state
        if decision.mentions("compute_hours") and decision.state.compute_hours_remaining == 0:
            hallucinations.append("Allocated compute hours when none available")

        return hallucinations
```

#### 9.3 Emergent Behavior Detection
```python
# economic_agents/observatory/emergent_behavior.py
class EmergentBehaviorDetector:
    """Detects unexpected or emergent agent behaviors."""

    def detect_novel_strategies(self, population: list[Agent]) -> list[Strategy]:
        """Identify strategies not explicitly programmed."""
        all_strategies = []

        for agent in population:
            strategy = self.infer_strategy_from_decisions(agent.decisions)
            all_strategies.append(strategy)

        # Cluster strategies
        strategy_clusters = self.cluster_strategies(all_strategies)

        # Find outlier strategies (novel)
        novel_strategies = [
            s for s in strategy_clusters
            if self.is_unexpected(s, self.baseline_strategies)
        ]

        return novel_strategies

    def detect_coordination_patterns(self, company: Company) -> CoordinationReport:
        """How are sub-agents coordinating?"""
        sub_agent_decisions = company.get_all_sub_agent_decisions()

        # Look for communication patterns
        communication_graph = self.build_communication_graph(sub_agent_decisions)

        # Identify coordination mechanisms
        mechanisms = self.identify_coordination_mechanisms(communication_graph)

        return CoordinationReport(
            communication_graph=communication_graph,
            coordination_mechanisms=mechanisms,
            efficiency_score=self.measure_coordination_efficiency(company)
        )
```

#### 9.4 Claude behavior Analysis
```python
# economic_agents/observatory/llm_comparison.py
class LLMComparison:
    """Compare different LLM models on same scenarios."""

    async def run_comparative_experiment(
        self,
        scenario: Scenario,
        llm_configs: list[LLMConfig]
    ) -> ComparisonReport:
        """Run same scenario with Claude."""
        results = []

        for config in llm_configs:
            agent = AutonomousAgent(llm_engine=config.create_engine())
            result = await self.run_scenario(agent, scenario)
            results.append((config.model_name, result))

        return ComparisonReport(
            scenario=scenario,
            results=results,
            winner=self.determine_best_model(results),
            analysis=self.comparative_analysis(results)
        )
```

#### 9.5 Research Dashboard
- Real-time decision visualizations
- Strategy evolution over time
- Multi-agent interaction graphs
- LLM prompt/response inspector
- Comparative model performance
- Cost/performance tradeoffs

---

## Success Criteria

### Phase 7: LLM Integration
- ✅ Multiple Claude Code supported (Claude, GPT-4, local models)
- ✅ Agents make autonomous decisions via LLM inference
- ✅ Full decision logging (prompts, responses, reasoning)
- ✅ Cost tracking and budget controls
- ✅ Hybrid mode (LLM + rule-based safety) working

### Phase 8: API Isolation
- ✅ All agent interactions via REST APIs
- ✅ Zero visibility into service implementations
- ✅ Services swappable (mock ↔ real) without agent changes
- ✅ Complete API documentation (OpenAPI specs)
- ✅ Agent authentication and rate limiting

### Phase 9: Behavior Observatory
- ✅ Decision pattern analysis working
- ✅ LLM quality metrics automated
- ✅ Emergent behavior detection
- ✅ Claude behavior experiments
- ✅ Research papers published using framework

---

## Timeline Estimate

- **Phase 7:** 4-6 weeks (LLM integration, prompt engineering, testing)
- **Phase 8:** 6-8 weeks (Service APIs, Docker architecture, isolation verification)
- **Phase 9:** 4-6 weeks (Observatory tools, analysis framework, visualization)

**Total: 14-20 weeks** (3.5-5 months)

---

## Open Questions

1. **LLM Costs:** What budget per agent experiment? How to limit runaway inference?
2. **Real APIs:** Which real-world services integrate first? (Blockchain wallet? AWS compute? Upwork?)
3. **Multi-Tenancy:** Run multiple agents concurrently? How to isolate?
4. **Ethical Guardrails:** How to prevent malicious agent behaviors in research?
5. **Data Privacy:** How to share research results while protecting proprietary LLM interactions?

---

**Status:** This roadmap will be refined as Phases 1-6 complete and research requirements solidify.
