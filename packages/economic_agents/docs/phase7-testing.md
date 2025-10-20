# Phase 7.4: Real Claude Testing Documentation

## Overview

Phase 7.4 validates the complete LLM decision engine integration with real Claude Code CLI execution. This phase tests the full autonomous agent lifecycle with Claude making actual decisions.

## Prerequisites

1. **Claude Code CLI** installed and authenticated
   ```bash
   # Verify Claude is available
   claude --version
   ```

2. **Node.js 22.16.0** via NVM
   ```bash
   nvm use 22.16.0
   ```

3. **Claude Authentication** configured (subscription-based)

4. **Economic Agents Package** installed
   ```bash
   pip install -e .
   ```

## Test Scripts

### Quick Test (Recommended for First Run)

**File**: `tests/manual/test_llm_quick.py`

**Purpose**: Minimal test to verify Claude integration works

**Runtime**: ~1-2 minutes

**Usage**:
```bash
cd packages/economic_agents
python tests/manual/test_llm_quick.py
```

**What it tests**:
- Single decision cycle with Claude
- JSON response parsing
- Decision logging
- Basic validation

**Expected output**:
```
✅ Decision completed in 45.23s

Allocation:
  Task work: 1.00h
  Company work: 0.00h

Reasoning: Given the current state with balance of $100 and 50h of compute remaining,
I'm prioritizing task work for immediate revenue generation...

Confidence: 0.85

Decision logged: dec_0_1729445123
Fallback used: False

✅ Test passed!
```

### Comprehensive Test Suite

**File**: `tests/manual/test_autonomous_agent_llm_manual.py`

**Purpose**: Full integration testing with multiple scenarios

**Runtime**: ~5-10 minutes

**Usage**:
```bash
cd packages/economic_agents
python tests/manual/test_autonomous_agent_llm_manual.py
```

**Tests included**:

1. **Single LLM Decision Cycle**
   - One decision with Claude
   - Validates decision structure
   - Checks execution time
   - Verifies decision logging

2. **Multiple LLM Decision Cycles**
   - 3 consecutive decisions
   - Company mode testing
   - Performance metrics
   - Decision history analysis

3. **Fallback Behavior**
   - Short timeout (5s) to trigger fallback
   - Verifies rule-based fallback works
   - Tests graceful degradation

4. **LLM vs Rule-Based Comparison**
   - Same state, different engines
   - Compares decision quality
   - Validates autonomous reasoning

**Expected output**:
```
Test Summary
================================================================================
Single LLM Cycle: ✅ PASSED
Multiple LLM Cycles: ✅ PASSED
Fallback Behavior: ✅ PASSED
LLM vs Rule-Based: ✅ PASSED

Total: 4/4 tests passed

🎉 All tests passed!
```

## Configuration Parameters

### LLM Engine Config

```python
config = {
    "engine_type": "llm",
    "llm_timeout": 900,           # 15 minutes (900s) for production
    "node_version": "22.16.0",    # Node.js version
    "fallback_enabled": True,     # Enable rule-based fallback
    "survival_buffer_hours": 24.0,
    "company_threshold": 100.0
}
```

### Timeout Guidelines

- **Quick tests**: 60-120 seconds (sufficient for simple decisions)
- **Production**: 900 seconds (15 minutes for deep reasoning)
- **Fallback testing**: 5 seconds (intentionally short to trigger fallback)

## Verification Checklist

After running tests, verify:

- [ ] Claude CLI executed successfully (no subprocess errors)
- [ ] JSON responses parsed correctly
- [ ] All 6 validation rules passed
- [ ] Decision logging captured full prompt/response
- [ ] Execution times reasonable (30-120s typically)
- [ ] Fallback mechanism works when needed
- [ ] LLM decisions differ from rule-based (autonomous reasoning)

## Common Issues

### Issue: Claude CLI not found

**Error**: `FileNotFoundError: [Errno 2] No such file or directory: 'claude'`

**Solution**:
```bash
# Install Claude Code CLI
npm install -g @anthropic-ai/claude-code-cli

# Or verify PATH
which claude
```

### Issue: Node.js version mismatch

**Error**: `NVM node version not found`

**Solution**:
```bash
nvm install 22.16.0
nvm use 22.16.0
```

### Issue: Authentication failure

**Error**: `Claude authentication required`

**Solution**:
```bash
claude auth login
# Follow prompts to authenticate
```

### Issue: Timeout on complex decisions

**Error**: `TimeoutError: Claude execution exceeded 120 seconds`

**Solution**:
- Increase `llm_timeout` to 900 (15 minutes)
- Enable `fallback_enabled: True` for graceful degradation

### Issue: JSON parsing failures

**Error**: `ValueError: No JSON object found in response`

**Debugging**:
- Check `decision.raw_response` in decision logs
- Claude may have wrapped JSON in markdown
- Parser handles ````json` blocks automatically

## Performance Metrics

**Typical execution times** (based on testing):

| Scenario | Time (seconds) | Notes |
|----------|----------------|-------|
| Simple decision | 30-60s | Basic allocation |
| Complex decision | 60-120s | Multi-factor reasoning |
| First decision (cold start) | 45-90s | Claude initialization |
| Subsequent decisions | 30-75s | Faster after warm-up |
| Timeout trigger | 5-10s | When timeout < decision time |

**Resource usage**:
- Memory: ~100MB for Claude subprocess
- CPU: Low (Claude API handles computation)
- Network: Required for Claude API calls

## Decision Quality Metrics

Analyze decision quality using:

```python
# Get decision history
decisions = engine.get_decisions()

for decision in decisions:
    print(f"Confidence: {decision.parsed_decision['confidence']}")
    print(f"Reasoning length: {len(decision.parsed_decision['reasoning'])}")
    print(f"Execution time: {decision.execution_time_seconds}s")
    print(f"Validation passed: {decision.validation_passed}")
```

**Quality indicators**:
- Confidence: 0.7-0.95 (typical range)
- Reasoning length: 50-500 characters
- Validation: Should always pass (or fallback triggers)
- Consistency: Similar states → similar decisions

## Next Steps

After successful Phase 7.4 testing:

- **Phase 7.5**: Dashboard visualization of Claude decisions
  - Real-time decision stream
  - Reasoning display
  - Confidence tracking
  - LLM vs rule-based comparison charts

- **Phase 8**: API isolation (hiding implementation from agents)

- **Phase 9**: Behavior observatory (studying emergent Claude behaviors)

## Research Applications

With Phase 7.4 complete, you can:

1. **Study Claude's economic reasoning**
   - How does Claude balance risk/reward?
   - What strategies emerge over time?
   - How does Claude handle resource constraints?

2. **Compare decision paradigms**
   - LLM autonomous vs rule-based
   - GPT-4 vs Claude vs local models (future)
   - Multi-agent coordination patterns

3. **Analyze failure modes**
   - When does Claude make poor decisions?
   - How often is fallback needed?
   - What causes validation failures?

4. **Optimize prompts**
   - Which prompt styles yield better decisions?
   - How does reasoning chain length affect quality?
   - Impact of few-shot examples

## Documentation Updates

After testing, update:

- [ ] Phase 7 roadmap with 7.4 completion status
- [ ] Main README with LLM testing examples
- [ ] CHANGELOG with Phase 7.4 achievements
- [ ] Research notes with interesting Claude behaviors

## Success Criteria

Phase 7.4 is complete when:

- ✅ Quick test runs successfully with real Claude
- ✅ Comprehensive test suite passes all 4 tests
- ✅ Decision logging captures full Claude interactions
- ✅ Fallback mechanism verified working
- ✅ LLM shows autonomous reasoning (differs from rules)
- ✅ Documentation updated with findings
- ✅ Performance metrics documented
