# Phase 7.5: Dashboard Visualization for LLM Decisions

## Overview

Phase 7.5 adds comprehensive visualization and monitoring capabilities for LLM-powered decision-making to the Economic Agents Dashboard. This enables real-time observation of Claude's autonomous strategic reasoning.

## Features

### 1. Engine Type Selection

The dashboard configuration form now includes decision engine selection:

- **Rule-Based Engine**: Fast, deterministic heuristics for baseline behavior
- **LLM Engine (Claude-Powered)**: Autonomous strategic reasoning with configurable timeout

**Configuration Options**:
- `engine_type`: "rule_based" or "llm"
- `llm_timeout`: 30-900 seconds (for deep strategic reasoning)

### 2. Engine Type Indicator

The dashboard displays the active decision engine:

- **LLM Mode**: Shows "Claude-Powered (LLM) - Autonomous strategic reasoning with {timeout}s timeout"
- **Rule-Based Mode**: Shows "Rule-Based - Fast deterministic heuristics"

This indicator appears at the top of the agent status section, making it immediately clear which decision paradigm is active.

### 3. LLM Decision History Section

A dedicated section displays detailed Claude decision history with:

**Summary Metrics**:
- Total LLM Decisions
- Fallback Count (how often rule-based fallback was triggered)
- Average Decision Time
- Average Confidence Score

**Trends Visualization**:
- Confidence over time (0.0-1.0 scale)
- Execution time over time (seconds)
- Dual-axis chart showing both metrics together

**Individual Decision Cards**:
Each decision displays:
- Timestamp and decision number
- Claude's strategic reasoning (full text)
- Resource allocation decision (task work vs company work)
- Confidence score
- Execution time
- Validation status
- Fallback indicator
- Agent state snapshot at decision time
- Full raw Claude response (expandable)

### 4. Real-Time Monitoring

The dashboard auto-refreshes (configurable 1-30 second interval) to show:
- Latest Claude decisions as they occur
- Decision trends over time
- Performance metrics
- Fallback behavior

## API Endpoints

### New Endpoints

#### `GET /api/decisions/llm`

Fetch LLM decision history from the currently running agent.

**Query Parameters**:
- `limit` (optional): Maximum number of decisions to return (1-1000, default: 50)

**Response**: List of `LLMDecisionResponse` objects

```json
[
  {
    "decision_id": "dec_0_1729445123",
    "timestamp": "2024-10-20T12:00:00",
    "agent_type": "claude",
    "state_snapshot": {
      "balance": 100.0,
      "compute_hours_remaining": 50.0,
      "has_company": false,
      "mode": "survival",
      "tasks_completed": 0
    },
    "prompt": "You are an autonomous economic agent...",
    "raw_response": "{\"task_work_hours\": 26.0, ...}",
    "parsed_decision": {
      "task_work_hours": 26.0,
      "company_work_hours": 0.0,
      "reasoning": "Strategic allocation...",
      "confidence": 0.85
    },
    "validation_passed": true,
    "execution_time_seconds": 45.23,
    "fallback_used": false
  }
]
```

### Enhanced Endpoints

#### `POST /api/agent/start`

Extended with LLM engine configuration:

```json
{
  "mode": "survival",
  "max_cycles": 50,
  "initial_balance": 100.0,
  "initial_compute_hours": 100.0,
  "compute_cost_per_hour": 0.0,
  "engine_type": "llm",           // NEW: "rule_based" or "llm"
  "llm_timeout": 120              // NEW: timeout in seconds
}
```

#### `GET /api/agent/control-status`

Now includes engine configuration in response:

```json
{
  "is_running": true,
  "cycle_count": 5,
  "max_cycles": 50,
  "config": {
    "mode": "survival",
    "engine_type": "llm",
    "llm_timeout": 120,
    ...
  }
}
```

## Data Models

### LLMDecisionResponse

Complete LLM decision record:

```python
class LLMDecisionResponse(BaseModel):
    decision_id: str
    timestamp: datetime
    agent_type: str
    state_snapshot: Dict[str, Any]
    prompt: str
    raw_response: str
    parsed_decision: Dict[str, Any]
    validation_passed: bool
    execution_time_seconds: float
    fallback_used: bool
```

### DecisionResponse (Enhanced)

Extended with LLM-specific fields:

```python
class DecisionResponse(BaseModel):
    # ... existing fields ...
    engine_type: str | None = None
    execution_time_seconds: float | None = None
    fallback_used: bool | None = None
    validation_passed: bool | None = None
    raw_response: str | None = None
```

## Usage Guide

### Starting an Agent with LLM Engine

1. Open the dashboard (http://localhost:8501)
2. In the sidebar, select **Decision Engine**: "LLM (Claude-Powered, Autonomous)"
3. Set **LLM Timeout**: 120 seconds (for quick decisions) or up to 900 seconds (for deep reasoning)
4. Configure other parameters (mode, balance, compute, cycles)
5. Click **Start Agent**

### Monitoring Claude Decisions

Once the agent is running with LLM engine:

1. **LLM Decision History** section appears automatically
2. Watch summary metrics update in real-time:
   - Total decisions made
   - Fallback usage (timeouts or errors)
   - Average decision time
   - Average confidence
3. View trends chart showing:
   - Confidence trajectory
   - Execution time patterns
4. Expand individual decision cards to see:
   - Claude's strategic reasoning
   - Full context and response
   - State snapshot at decision time

### Interpreting the Visualizations

**Confidence Trends**:
- High confidence (0.8-0.95): Claude has strong conviction
- Medium confidence (0.6-0.8): Moderate certainty
- Low confidence (0.4-0.6): Uncertain conditions

**Execution Time**:
- 30-60s: Quick decisions (simple states)
- 60-120s: Standard decisions (moderate complexity)
- 120+s: Deep reasoning (complex strategic situations)

**Fallback Indicators**:
- Fallback = False: Claude successfully made decision
- Fallback = True: Timeout or error, used rule-based fallback

## Research Applications

The dashboard enables research into:

1. **Strategic Reasoning Patterns**
   - How does Claude balance short-term survival vs long-term growth?
   - What factors influence confidence scores?
   - How does reasoning evolve over multiple cycles?

2. **Decision Quality Analysis**
   - Correlation between confidence and outcome
   - Impact of execution time on decision quality
   - Patterns in validation failures

3. **Fallback Behavior**
   - When does Claude timeout?
   - What conditions trigger fallback?
   - How often is fallback needed?

4. **LLM vs Rule-Based Comparison**
   - Run multiple agents side-by-side
   - Compare decision outcomes
   - Analyze strategic differences

## Example Scenarios

### Scenario 1: Survival Mode with LLM

```
Configuration:
- Mode: Survival
- Engine: LLM
- Timeout: 120s
- Balance: $100
- Compute: 50h
- Cycles: 20

Expected Behavior:
- Claude analyzes survival constraints
- Allocates resources strategically
- Provides detailed reasoning for each decision
- Adapts strategy as resources change
```

### Scenario 2: Company Mode with LLM

```
Configuration:
- Mode: Company
- Engine: LLM
- Timeout: 300s (5 minutes for complex reasoning)
- Balance: $50,000
- Compute: 200h
- Cycles: 100

Expected Behavior:
- Claude considers company formation timing
- Balances immediate revenue vs company investment
- Reasons about long-term growth strategies
- Higher execution times for complex decisions
```

### Scenario 3: LLM vs Rule-Based Comparison

```
Agent 1 (LLM):
- Engine: LLM, timeout=120s
- Same initial conditions

Agent 2 (Rule-Based):
- Engine: Rule-Based
- Same initial conditions

Research Questions:
- How do decisions differ?
- Does Claude find better strategies?
- What is the performance overhead of LLM reasoning?
```

## Performance Considerations

**LLM Decision Overhead**:
- Rule-based: <1ms per decision
- LLM: 30-120s per decision (with Claude API)

**Recommendations**:
- Use longer cycles (100+) for LLM mode to amortize decision time
- Set appropriate timeouts based on cycle budget
- Monitor fallback rate - high fallback may indicate timeout too short
- For research, prioritize decision quality over speed

## Troubleshooting

### Issue: No LLM Decisions Showing

**Cause**: Agent using rule-based engine

**Solution**: Check engine type indicator shows "Claude-Powered (LLM)"

### Issue: High Fallback Rate

**Cause**: Timeout too short for Claude to respond

**Solution**: Increase `llm_timeout` to 300-900 seconds

### Issue: Slow Dashboard Updates

**Cause**: LLM decisions take time to complete

**Solution**: Normal behavior - increase refresh interval or wait for decisions to complete

### Issue: Empty Raw Response Field

**Cause**: Fallback was used (Claude didn't respond)

**Solution**: Check fallback indicator - if true, increase timeout

## Next Steps

After Phase 7.5, the roadmap continues with:

- **Phase 8**: API isolation (hiding implementation details from agents)
- **Phase 9**: Behavior observability (studying emergent Claude behaviors)

## Documentation References

- [Phase 7 Roadmap](../PHASE_7_9_ROADMAP.md)
- [Phase 7.4 Testing Guide](./phase7-testing.md)
- [LLM Decision Engine](../economic_agents/agent/llm/README.md)
- [Dashboard API](../economic_agents/dashboard/README.md)

## Success Criteria

Phase 7.5 is complete when:

- ✅ Dashboard allows LLM engine selection
- ✅ Engine type indicator shows active decision engine
- ✅ LLM decision history section displays Claude reasoning
- ✅ Confidence and execution time trends visualized
- ✅ Individual decision cards show full context
- ✅ API endpoints return LLM decision data
- ✅ Tests validate all new features
- ✅ Documentation covers usage and research applications
