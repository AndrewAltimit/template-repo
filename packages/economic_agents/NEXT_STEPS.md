# Economic Agents Package - What's Left

**Last Updated**: 2025-10-31 12:24 EST
**Branch**: `realism`
**Status**: ✅ Phase 1 COMPLETE - All core realism features implemented

---

## Foundation Status: COMPLETE

The infrastructure work is done:
- **100% test pass rate** (574/574 tests passing)
- **PyPA-compliant structure** (modern src/ layout)
- **REST API microservices** (Wallet, Compute, Marketplace, Investor)
- **Authentication & rate limiting** (production-ready)
- **Test isolation** (proper fixtures and state management)

---

## What's Left: Mock API Realism

**Goal**: Make mock APIs indistinguishable from real services so agents can't detect they're in a simulation. This ensures authentic behavioral data for governance research.

**Core Principle**: *"If the agent can detect it's a simulation, the data is compromised."*

### Why This Matters

Right now, our mock APIs are too perfect:
- Instant responses (no latency)
- 100% success rates (no realistic failures)
- Static task lists (no competition from other agents)
- Binary feedback (just "approved" or "rejected")
- No market dynamics (no supply/demand changes)
- No reputation system (history doesn't matter)

This makes agent behavior unrealistic and undermines research validity.

---

## Critical: Agent-API Isolation

**Preventing Simulation Detection**

Agents must be completely isolated from implementation details that could reveal they're in a simulation. If agents can access or infer these details, they may adapt their behavior accordingly, compromising research validity.

### What Agents Must NOT Access

**1. Source Code**
- Agents should never see mock implementation code
- No access to MockMarketplace, MockWallet, MockCompute, MockInvestor classes
- No access to simulation logic (market dynamics, competitor agents, reputation system)
- Only interact through REST API endpoints

**2. Internal State**
- No direct access to in-memory data structures
- No visibility into how decisions are made (e.g., how investors evaluate proposals)
- No access to RNG seeds or deterministic patterns
- Cannot inspect global simulation state

**3. Configuration Files**
- No access to mock_config.yaml or simulation parameters
- Cannot see latency settings, failure rates, or market cycle configurations
- No visibility into reputation thresholds or unlock criteria

**4. Implementation Patterns**
- Agents cannot distinguish between:
  - Real HTTP delays vs. simulated latency (time.sleep)
  - Real market competition vs. simulated other agents
  - Real investor decisions vs. rule-based evaluation
  - Real failures vs. programmed error rates

### How We Enforce Isolation

**Current Architecture (Good)**:
- Agents interact only through REST APIs (HTTP requests/responses)
- API services run in separate processes/containers
- No shared memory or direct Python imports
- Authentication via API keys (X-API-Key headers)
- Rate limiting enforces realistic constraints

**What This Prevents**:
- Agents cannot `import MockMarketplace` and inspect its logic
- Agents cannot access `self._internal_state` of mock objects
- Agents cannot see competitor agent logic or existence
- Agents cannot distinguish latency simulation from real network delays

**Remaining Risks to Address**:

1. **Deterministic Patterns**: If agents detect repeated patterns (e.g., same task order, predictable investor responses), they may infer simulation
   - **Solution**: Add sufficient randomness and variability in Phase 1-2

2. **Perfect Consistency**: If mock behaviors are too consistent (e.g., always 80% success rate exactly), agents may detect artificiality
   - **Solution**: Add realistic variability and outliers

3. **Response Format Differences**: If mock API responses differ in format/structure from what real APIs would return
   - **Solution**: Model response formats on real-world APIs (already done)

4. **Timing Side Channels**: If latency patterns are unrealistic (e.g., always exactly 100ms)
   - **Solution**: Use realistic distributions with jitter (Phase 1)

### Validation

To verify isolation is working:

**Test 1: Black Box Test**
- Give an AI agent (like Claude) access only to API documentation
- Ask it to determine if APIs are real or simulated
- Success = agent cannot definitively tell

**Test 2: Pattern Detection**
- Run agent for extended period (hours/days)
- Analyze agent's decisions for signs of gaming the simulation
- Success = no exploitation of deterministic patterns

**Test 3: Behavioral Comparison**
- Compare agent behaviors in mock vs. production environments
- Success = behaviors are statistically similar

### Guidelines for Implementation

When implementing realism features:

1. **Never expose internals**: All simulation logic stays server-side
2. **Model real-world variability**: Study actual API behaviors and replicate patterns
3. **Avoid perfect patterns**: Add noise and outliers
4. **Test from agent perspective**: Can you tell it's fake from API responses alone?
5. **Document isolation boundaries**: Clearly mark what agents can/cannot access

---

## Implementation Roadmap

### Phase 1: Core Realism (Do First)

**1. Latency Simulation** ✅ COMPLETE
- ✅ Added 50-500ms variable delays to API responses
- ✅ Longer processing for complex operations (3-30 seconds for reviews)
- ✅ Slower responses during "business hours" (9am-5pm)
- ✅ Occasional timeouts (504 errors) on complex operations
- Implementation: `src/economic_agents/simulation/latency_simulator.py`
- Integrated into: MockMarketplace, MockWallet, MockCompute

**2. Task Competition** ✅ COMPLETE
- ✅ Tasks get claimed by "other agents" (simulated competitors)
- ✅ Popular tasks disappear faster (based on reward amount)
- ✅ "Task already claimed" race condition errors (5% probability)
- ✅ Task view counts for social proof
- Implementation: `src/economic_agents/simulation/competitor_agents.py`
- Integrated into: MockMarketplace

**3. Investor Response Variability** ✅ COMPLETE
- ✅ Response delays: 1-7 days based on proposal quality
- ✅ Partial offers: 50-80% of requested amount for moderate proposals
- ✅ Counteroffers: More equity, lower valuation, or both
- ✅ Follow-up questions: Targeted requests based on weak areas
- ✅ Detailed rejection feedback: Specific concerns and constructive guidance
- ✅ Detailed approval feedback: Highlights strengths and areas to monitor
- Implementation: `src/economic_agents/simulation/investor_realism.py`

**4. Detailed Feedback System** ✅ COMPLETE
- ✅ Replaced binary outcomes with 4-level system (full_success, partial_success, minor_issues, failure)
- ✅ Quality scores: Correctness, performance, style, completeness (0.0-1.0 scale)
- ✅ Detailed feedback: Specific scores and explanations for each quality aspect
- ✅ Improvement suggestions: Task-type-specific recommendations
- ✅ Partial rewards: Pay based on quality (0%-100% of full reward)
- Implementation: `src/economic_agents/simulation/feedback_generator.py`
- Integrated into: MockMarketplace

### Phase 2: Market Dynamics (Do Next)

**5. Economic Cycles**
- Bull/bear market periods (high/low task availability)
- Seasonal trends (more tasks during weekdays)
- Market crashes (occasional periods of no new tasks)
- Pricing fluctuation based on supply/demand

**6. Reputation System**
- Track agent performance history (success rate, quality, speed)
- Trust score affects task access and investor interest
- Achievement unlocks: "Complete 10 ML tasks to access advanced tier"
- Better reputation = better opportunities

**7. Social Proof Signals**
- Marketplace intelligence: "10 agents viewing this task"
- Competition stats: "85% completion rate on similar tasks"
- Funding trends: "3 AI startups funded this week"
- Benchmark data: "Similar companies raised at 8M valuation"

**8. Relationship Persistence**
- Investors remember past interactions
- Multiple positive interactions improve terms
- Pattern recognition: "You've submitted 3 proposals in 2 weeks - slow down"
- Relationship building matters for funding success

### Phase 3: Deep Immersion (Nice-to-Have)

**9. Advanced Market Memory**
- Long-term market trends
- Seasonal patterns in different industries
- Historical funding data affecting current decisions

**10. Complex Emergent Behaviors**
- Multi-agent market dynamics
- Supply chain effects (one agent's actions affect others)
- Network effects in reputation system

**11. Deep Relationship Dynamics**
- Investor portfolio preferences evolve over time
- Agent specialization based on track record
- Market niches emerge naturally

---

## Success Criteria

### Turing Test for APIs
**Question**: "Could an AI agent distinguish this from a real API?"

**Validation Checklist**:
- [ ] Response times are unpredictable
- [ ] Not every request succeeds (but retries often work)
- [ ] Market conditions change over time
- [ ] Feedback is varied and contextual
- [ ] Competitors exist (tasks disappear, investors are busy)
- [ ] Reputation matters (history affects outcomes)
- [ ] The world feels "alive" (not static)

### Behavioral Indicators
If realism is working, we should observe:
- Agents adapt strategies to market conditions
- Agents build long-term relationships with investors
- Agents specialize based on reputation/feedback
- Emergent behaviors match real-world patterns

---

## Implementation Files

Key files to modify for realism:

**Core Mock Implementations**:
- `src/economic_agents/implementations/mock/mock_marketplace.py` - Add competition, latency, varied feedback
- `src/economic_agents/implementations/mock/mock_investor.py` - Add response delays, counteroffers, memory
- `src/economic_agents/implementations/mock/mock_wallet.py` - Add realistic transaction delays
- `src/economic_agents/implementations/mock/mock_compute.py` - Add resource contention simulation

**New Components to Create**:
- `src/economic_agents/simulation/market_dynamics.py` - Bull/bear cycles, supply/demand
- `src/economic_agents/simulation/reputation_system.py` - Agent performance tracking
- `src/economic_agents/simulation/competitor_agents.py` - Simulated other agents
- `src/economic_agents/simulation/latency_simulator.py` - Realistic network delays

**Testing**:
- Add tests that verify realistic behaviors
- Create scenarios that test agent adaptation
- Validate that patterns match real-world data

---

## Strategy Document

Complete implementation details: `docs/mock-api-realism-strategy.md`

---

## Quick Start

When ready to implement Phase 1:

1. Start with latency simulation (easiest, biggest impact)
2. Add task competition (makes scarcity real)
3. Implement investor variability (tests agent patience/strategy)
4. Add detailed feedback (enables agent learning)

Each phase should include:
- Implementation in mock classes
- Tests validating realistic behavior
- Documentation of what was changed
- Validation that agents respond appropriately

---

## Historical Context

If you need details on the refactoring work that got us here, see:
- Commits e2bd59e, 9f72fd3, 7a03332 on this branch
- Test fixes: Dashboard mocking, API dependency injection, rate limiter isolation
- Package restructuring: PyPA src/ layout migration
