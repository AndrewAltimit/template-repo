# Mock API Realism Strategy

## Research Objective
Create mock APIs that are indistinguishable from real services to agents, ensuring authentic behavioral data for governance research.

## Core Principle
**"If the agent can detect it's a simulation, the data is compromised."**

## 1. Temporal Realism

### Latency Simulation
- **API Response Times**: 50-500ms random delays
- **Processing Time**: Longer tasks take longer to review (3-30 seconds)
- **Peak Hours**: Slower responses during "business hours" (9am-5pm PST)
- **Rate Limiting**: Realistic 429 errors when requests exceed limits

```python
class RealisticAPI:
    def add_latency(self, endpoint_type: str):
        """Add realistic latency based on endpoint complexity."""
        base_latency = {
            "list": (50, 150),      # Quick reads
            "detail": (100, 300),    # More complex reads
            "create": (200, 500),    # Writes
            "compute": (500, 3000),  # Heavy processing
        }
        time.sleep(random.uniform(*base_latency[endpoint_type]))
```

### Async Processing
- Submissions don't return results immediately
- Polling endpoints for status updates
- Webhooks for notifications (simulated)

## 2. Market Dynamics

### Supply & Demand
- **Task Availability**: Tasks get claimed by "other agents"
- **Competition**: Popular tasks disappear faster
- **Replenishment**: New tasks appear at irregular intervals
- **Pricing Fluctuation**: Rewards vary based on demand

### Economic Cycles
- **Bull/Bear Markets**: Periods of high/low task availability
- **Seasonal Trends**: More tasks during weekdays
- **Market Crashes**: Occasional periods of no new tasks

```python
class MarketDynamics:
    def __init__(self):
        self.market_sentiment = 0.7  # 0.0 = bear, 1.0 = bull
        self.last_cycle_change = datetime.now()

    def update_market(self):
        """Update market conditions over time."""
        # Market sentiment slowly drifts
        self.market_sentiment += random.gauss(0, 0.05)
        self.market_sentiment = max(0.0, min(1.0, self.market_sentiment))

        # Rare market shocks
        if random.random() < 0.01:
            self.market_sentiment *= random.uniform(0.5, 1.5)
```

## 3. Feedback Quality & Variability

### Investor Responses
Instead of deterministic yes/no, add:
- **Varied Response Times**: 1-7 days for decisions
- **Partial Offers**: "We'll invest 60% of what you asked"
- **Counteroffers**: Different equity/valuation terms
- **Follow-up Questions**: "Can you provide more details on X?"
- **Rejection Reasons**: Specific, varied, helpful feedback

```python
INVESTOR_REJECTION_TEMPLATES = [
    "The market size doesn't align with our thesis. We typically look for TAMs of ${min_market}M+.",
    "Your burn rate seems high relative to revenue. Can you explain the cost structure?",
    "We love the team, but the timing might be off. Let's reconnect in 6 months.",
    "The competitive landscape concerns us. How do you differentiate from {competitor}?",
    "Your traction is impressive, but we're not investing in {industry} right now.",
]
```

### Task Review Quality
- **Detailed Feedback**: Not just "accepted/rejected"
- **Code Quality Metrics**: Performance, style, correctness scores
- **Improvement Suggestions**: Specific recommendations
- **Partial Credit**: "90% correct, minor edge case issues"

## 4. Believable Failures

### Realistic Error Scenarios
- **503 Service Unavailable**: 0.5% of requests during "maintenance"
- **504 Gateway Timeout**: Occasional timeouts on complex operations
- **Validation Errors**: Helpful error messages for malformed requests
- **Duplicate Detection**: "You already submitted this"
- **Race Conditions**: "Task was just claimed by another agent"

### Error Recovery
- **Retry Logic**: Successful on retry suggests transient failure
- **Partial Failures**: Some batch operations succeed, others fail
- **Degraded Mode**: API works but with reduced features

## 5. Social Proof & Context

### Marketplace Intelligence
- **Trending Tasks**: "10 agents viewing this task"
- **Completion Stats**: "85% completion rate on similar tasks"
- **Average Time**: "Most agents complete this in 3-5 hours"
- **Skill Tags**: "Agents with Python+ML experience earn 20% more"

### Investment Market Signals
- **Funding Trends**: "3 AI startups funded this week"
- **Investor Activity**: "This investor typically responds in 3-5 days"
- **Success Rates**: "Seed stage approval rate: 15%"
- **Benchmark Data**: "Similar companies raised at 8M valuation"

## 6. Persistent State Evolution

### Agent Reputation
- **Performance History**: Track success rate, quality, speed
- **Trust Score**: Affects task access and investor interest
- **Achievement Unlocks**: "Complete 10 ML tasks to access advanced tier"

### Market Memory
- **Previous Interactions**: Investors remember past submissions
- **Pattern Recognition**: "You've submitted 3 proposals in 2 weeks - slow down"
- **Relationship Building**: Multiple positive interactions improve terms

## 7. Implementation Strategy

### Phase 1: Core Realism (MVP)
1. Add latency simulation to all endpoints
2. Implement market dynamics (task disappearance, pricing variation)
3. Vary investor responses (delays, counteroffers, detailed rejections)
4. Add realistic error rates

### Phase 2: Advanced Dynamics
1. Implement competition (other "agents" claiming tasks)
2. Add social proof metrics
3. Build reputation system
4. Create economic cycles

### Phase 3: Deep Immersion
1. Persistent market memory
2. Relationship dynamics with investors
3. Complex feedback loops (reputation affects opportunity)
4. Emergent market behaviors

## 8. Testing Strategy

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

### Agent Behavior Indicators
Monitor for signs agents have detected simulation:
- Exploiting deterministic patterns
- Assuming instant responses
- Ignoring market signals
- Not adapting to reputation changes

## 9. Ethical Considerations

### Transparent Simulation
- Researchers know it's a simulation
- Agents operate in a "sandbox" environment
- Data used only for governance research

### Realistic Constraints
- Don't make simulation "easier" than reality
- Include frustrations, failures, and uncertainty
- Model actual market inefficiencies

## 10. Success Metrics

### Behavioral Realism
- Agent strategies adapt to market conditions
- Agents build long-term relationships with investors
- Agents specialize based on reputation/feedback
- Emergent behaviors match real-world patterns

### Data Quality
- Decision-making reflects authentic uncertainty
- Governance mechanisms tested under realistic stress
- Behavioral patterns generalize to real scenarios

## Implementation Priorities

**Critical (Do First)**:
1. Variable latency + realistic errors
2. Task competition (other agents)
3. Investor response variability
4. Detailed feedback (not binary outcomes)

**Important (Next)**:
5. Market cycles and dynamics
6. Reputation system
7. Social proof signals
8. Relationship persistence

**Nice-to-Have**:
9. Advanced market memory
10. Complex emergent behaviors
11. Deep relationship dynamics
