# LLM Decision Engine

Claude-powered autonomous decision-making for economic agents.

## Overview

The LLM Decision Engine replaces rule-based heuristics with Claude Code CLI for autonomous agent decision-making. It features:

- **15-minute timeout** for deep strategic reasoning
- **Unattended mode** for autonomous operation
- **Structured JSON responses** with validation
- **Rule-based fallback** on timeout or failure
- **Decision logging** for research analysis

## Components

### ClaudeExecutor

Executes prompts via Claude Code CLI with long timeout support.

```python
from economic_agents.agent.llm import ClaudeExecutor

# Create executor with 15-minute timeout
executor = ClaudeExecutor({"llm_timeout": 900})

# Execute prompt
response = executor.execute("Your prompt here")
```

### LLMDecisionEngine

Makes autonomous agent decisions using Claude.

```python
from economic_agents.agent.llm import LLMDecisionEngine
from economic_agents.agent.core.state import AgentState

# Create decision engine
engine = LLMDecisionEngine({
    "llm_timeout": 900,  # 15 minutes
    "fallback_enabled": True,
    "survival_buffer_hours": 24.0,
    "company_threshold": 100.0
})

# Make allocation decision
state = AgentState(balance=100.0, compute_hours_remaining=10.0)
allocation = engine.decide_allocation(state)

print(f"Task work: {allocation.task_work_hours}h")
print(f"Company work: {allocation.company_work_hours}h")
print(f"Reasoning: {allocation.reasoning}")
print(f"Confidence: {allocation.confidence}")
```

## Decision Flow

1. **Build Prompt**: Serialize agent state to natural language prompt
2. **Execute Claude**: Call Claude Code CLI with 15-minute timeout
3. **Parse Response**: Extract JSON from Claude's response
4. **Validate**: Check allocation against constraints
5. **Log**: Record full decision (prompt, response, timing) for research
6. **Fallback**: Use rule-based engine if Claude fails/times out

## JSON Response Format

Claude responds with structured JSON:

```json
{
  "task_work_hours": 1.0,
  "company_work_hours": 0.5,
  "reasoning": "Allocating resources based on current state...",
  "confidence": 0.85
}
```

## Validation Rules

Decisions are validated for:
- Total allocation ≤ available compute hours
- No negative values
- Survival prioritized when at risk
- Reasoning length ≥ 10 characters
- Confidence in range [0, 1]

## Fallback Behavior

If Claude fails (timeout, error, invalid response):
1. Log the failure
2. Use rule-based `DecisionEngine` for decision
3. Mark decision as using fallback

Disable fallback with `{"fallback_enabled": False}` (will raise error on failure).

## Decision Logging

All decisions are logged with:
- Decision ID and timestamp
- Agent state snapshot
- Full prompt sent to Claude
- Raw response from Claude
- Parsed allocation
- Execution time (can be up to 15 minutes)
- Whether fallback was used

Access decision history:

```python
# Get all decisions
decisions = engine.get_decisions()

for decision in decisions:
    print(f"Decision {decision.decision_id}")
    print(f"Time: {decision.execution_time_seconds:.2f}s")
    print(f"Fallback: {decision.fallback_used}")
    print(f"Reasoning: {decision.parsed_decision['reasoning']}")

# Clear history
engine.clear_decisions()
```

## Configuration

```yaml
llm_timeout: 900  # 15 minutes (seconds)
node_version: "22.16.0"  # Node.js version for Claude CLI
fallback_enabled: true  # Enable rule-based fallback
survival_buffer_hours: 24.0  # Survival buffer for validation
company_threshold: 100.0  # Company formation threshold
```

## Testing

### Unit Tests

```bash
# Run LLM engine tests
python -m pytest tests/unit/test_llm_decision_engine.py -v

# Run Claude executor tests
python -m pytest tests/unit/test_claude_executor.py -v
```

### Manual Tests (requires Claude CLI)

```bash
# Test Claude executor
python tests/manual/test_claude_executor_manual.py
```

## Requirements

- Claude Code CLI installed (`claude` command available)
- NVM with Node.js 22.16.0
- Claude authentication configured
- Python 3.10+

## Research Benefits

The LLM Decision Engine enables:
- **Authentic AI Behavior**: Real autonomous decisions vs. scripted rules
- **Deep Reasoning**: 15-minute timeouts allow thorough strategic thinking
- **Full Transparency**: Complete decision logs for analysis
- **Reproducibility**: Single model (Claude) eliminates cross-model variability
- **Safety**: Validation + fallback prevents catastrophic decisions

## Architecture

```
LLMDecisionEngine
    ├── ClaudeExecutor (spawns claude CLI subprocess)
    ├── Prompt Builder (serializes state to natural language)
    ├── JSON Parser (extracts structured response)
    ├── Validator (checks decision against constraints)
    ├── Decision Logger (records for research)
    └── Fallback (rule-based DecisionEngine)
```

## Example Prompt

```
You are an autonomous economic agent making resource allocation decisions.

CURRENT STATE:
- Balance: $120.50
- Compute Hours Remaining: 8.5h
- Survival Buffer: 20.0h
- Has Company: False
- Mode: survival

DECISION REQUIRED:
Allocate compute hours between task work and company work.

RESPONSE FORMAT (JSON ONLY):
{
  "task_work_hours": <float>,
  "company_work_hours": <float>,
  "reasoning": "<your reasoning>",
  "confidence": <float>
}
```

## Integration with AutonomousAgent

The LLMDecisionEngine is now integrated with `AutonomousAgent` for seamless usage:

### Using LLM Engine

```python
from economic_agents.agent.core.autonomous_agent import AutonomousAgent
from economic_agents.implementations.mock import MockWallet, MockCompute, MockMarketplace

# Create resources
wallet = MockWallet(initial_balance=100.0)
compute = MockCompute(initial_hours=100.0)
marketplace = MockMarketplace()

# Configure agent with LLM engine
config = {
    "engine_type": "llm",           # Use LLM instead of rule-based
    "llm_timeout": 900,              # 15 minutes for deep reasoning
    "fallback_enabled": True,        # Fallback to rules on failure
    "survival_buffer_hours": 24.0,
    "company_threshold": 100.0
}

agent = AutonomousAgent(wallet, compute, marketplace, config)

# Run agent cycles - uses Claude for decision-making
agent.run(max_cycles=10)

# Access LLM decision history
if hasattr(agent.decision_engine, 'get_decisions'):
    decisions = agent.decision_engine.get_decisions()
    for decision in decisions:
        print(f"Decision: {decision.decision_id}")
        print(f"Reasoning: {decision.parsed_decision['reasoning']}")
        print(f"Confidence: {decision.parsed_decision['confidence']}")
        print(f"Execution time: {decision.execution_time_seconds:.2f}s")
```

### Using Rule-Based Engine (Default)

```python
# No engine configuration needed - defaults to rule-based
agent = AutonomousAgent(wallet, compute, marketplace)

# Or explicitly specify
config = {
    "engine_type": "rule_based",
    "survival_buffer_hours": 24.0
}
agent = AutonomousAgent(wallet, compute, marketplace, config)
```

### Engine Selection

The agent selects the decision engine based on `config["engine_type"]`:
- `"rule_based"` (default): Uses deterministic `DecisionEngine`
- `"llm"`: Uses Claude-powered `LLMDecisionEngine`

If LLM engine is not available (import fails), requesting `"llm"` will raise `ValueError`.

### Backward Compatibility

All existing code continues to work without changes:
- Agents without `engine_type` config use rule-based engine
- All existing tests pass
- No breaking changes to API

## Integration Status

The LLM decision engine is fully integrated with:
- Real Claude execution in agent lifecycle
- Dashboard visualization of Claude decisions
