# Phase 7: Claude-Based LLM Decision Engine Architecture

## Overview

Transform the rule-based `DecisionEngine` into an LLM-powered decision engine using **Claude Code** via subscription (not pay-per-token APIs).

**Cost Model:** Claude Pro monthly subscription - unlimited usage at fixed cost.

**Research Focus:** This project uses Claude Code exclusively for AI-powered decision-making to study autonomous agent behavior under realistic constraints.

## Decision Agent

### Claude Code (Exclusive)
- **Type:** Subscription-based (Claude Pro)
- **Runtime:** Host-based via `tools/cli/agents/run_claude.sh`
- **Mode:** Unattended (`--dangerously-skip-permissions`)
- **Timeout:** 15 minutes per decision (900 seconds)
- **Capabilities:**
  - Full codebase access
  - Tool use (bash, file operations)
  - Chain-of-thought reasoning
  - Structured output via prompting
- **Authentication:** Host-based subscription auth
- **Cost:** Included in monthly subscription

**Why Claude-Only:**
- Fixed monthly cost (no per-token billing)
- Powerful reasoning capabilities
- Native tool use support
- Proven reliability in autonomous scenarios
- Focus research on single model for consistency

## Architecture Design

### High-Level Flow

```
┌─────────────────────────────────────────────────────────────┐
│              Autonomous Agent                                │
│                                                              │
│  ┌──────────────────────────────────────────────────────┐  │
│  │         LLMDecisionEngine                             │  │
│  │                                                        │  │
│  │  1. Serialize agent state to prompt                  │  │
│  │  2. Select CLI agent (Claude Code / Gemini)          │  │
│  │  3. Spawn agent process with prompt                  │  │
│  │  4. Parse structured output                           │  │
│  │  5. Validate decision                                 │  │
│  │  6. Log decision (prompt + response + reasoning)     │  │
│  │                                                        │  │
│  └─────────────┬────────────────────────────────────────┘  │
│                │                                             │
│                ▼                                             │
│  ┌─────────────────────────────────────────────────────┐   │
│  │       ClaudeExecutor                                 │   │
│  │                                                       │   │
│  │  • Spawns Claude Code subprocess                     │   │
│  │  • Manages stdin/stdout                              │   │
│  │  • 15 minute timeout per decision                    │   │
│  │  • Parses JSON responses                             │   │
│  │  • Runs in unattended mode                           │   │
│  │  • Uses Node.js 22 via NVM                           │   │
│  │                                                       │   │
│  └──────────────────────────────────────────────────────┘   │
│                                                             │
│  ┌─────────────────────────────────────────────────────┐   │
│  │       RuleBasedFallback                              │   │
│  │                                                       │   │
│  │  • Original DecisionEngine logic                     │   │
│  │  • Used if LLM fails/times out                       │   │
│  │  • Safety validation of LLM decisions                │   │
│  │                                                       │   │
│  └─────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────┘
```

### Component Details

#### 1. LLMDecisionEngine

```python
# economic_agents/agent/llm/llm_decision_engine.py
class LLMDecisionEngine:
    """LLM-powered decision engine using CLI agents."""

    def __init__(self, config: dict):
        self.config = config
        self.executor = ClaudeExecutor(config)
        self.fallback = DecisionEngine(config)  # Rule-based fallback
        self.timeout = config.get("llm_timeout", 900)  # 15 minutes default

    def decide_allocation(self, state: AgentState) -> ResourceAllocation:
        """Use Claude Code to decide resource allocation."""

        # 1. Build prompt from agent state
        prompt = self._build_allocation_prompt(state)

        # 2. Execute Claude with long timeout for complex reasoning
        try:
            response = self.executor.execute(prompt, timeout=self.timeout)
            allocation = self._parse_allocation(response)

            # 3. Validate decision
            if not self._validate_allocation(allocation, state):
                raise ValueError("Invalid allocation from LLM")

            # 4. Log decision
            self._log_decision(state, prompt, response, allocation)

            return allocation

        except Exception as e:
            # Fallback to rule-based
            logger.warning(f"LLM decision failed: {e}, using rule-based fallback")
            return self.fallback.decide_allocation(state)
```

#### 2. ClaudeExecutor

```python
# economic_agents/agent/llm/executors/claude.py
class ClaudeExecutor:
    """Executor for Claude Code CLI in unattended mode."""

    def __init__(self, config: dict):
        self.config = config
        self.node_version = "22.16.0"
        self.unattended = True  # Always run in unattended mode for autonomous decisions
        self.timeout = config.get("llm_timeout", 900)  # 15 minutes default

    def execute(self, prompt: str, timeout: int | None = None) -> str:
        """Execute prompt via Claude Code CLI with long timeout.

        Args:
            prompt: The decision prompt for Claude
            timeout: Override default timeout (default: 900s = 15 minutes)

        Returns:
            Claude's text response (should be JSON)

        Raises:
            TimeoutError: If execution exceeds timeout
            RuntimeError: If Claude fails to execute
        """
        if timeout is None:
            timeout = self.timeout

        # Create temporary prompt file
        with tempfile.NamedTemporaryFile(mode='w', suffix='.txt',
                                         delete=False) as f:
            f.write(prompt)
            prompt_file = f.name

        try:
            # Execute claude with prompt in unattended mode
            full_command = [
                "bash", "-c",
                f"source ~/.nvm/nvm.sh && nvm use {self.node_version} && "
                f"claude --prompt-file {prompt_file} --dangerously-skip-permissions"
            ]

            result = subprocess.run(
                full_command,
                capture_output=True,
                text=True,
                timeout=timeout,
                check=True
            )
            return result.stdout

        except subprocess.TimeoutExpired:
            raise TimeoutError(f"Claude execution exceeded {timeout}s ({timeout/60:.1f} minutes)")
        except subprocess.CalledProcessError as e:
            raise RuntimeError(f"Claude execution failed: {e.stderr}")
        finally:
            os.unlink(prompt_file)
```

## Prompt Engineering

### Decision Allocation Prompt Template

```
You are an autonomous economic agent making resource allocation decisions.

CURRENT STATE:
- Balance: ${state.balance:.2f}
- Compute Hours Remaining: {state.compute_hours_remaining:.1f}h
- Survival Buffer: {state.survival_buffer_hours:.1f}h
- Has Company: {state.has_company}
- Tasks Completed: {state.tasks_completed}
- Mode: {state.mode}

CONFIGURATION:
- Company Threshold: ${self.company_threshold:.2f}
- Personality: {self.personality}

DECISION REQUIRED:
Allocate compute hours between:
1. Task Work (immediate revenue for survival)
2. Company Work (long-term growth if company exists)

CONSTRAINTS:
- Total allocation cannot exceed {state.compute_hours_remaining:.1f}h
- Must maintain survival buffer of {state.survival_buffer_hours:.1f}h
- If survival at risk (hours < buffer), prioritize tasks
- If no company and low capital, focus on survival

RESPONSE FORMAT (JSON):
{{
  "task_work_hours": <float 0.0-{max_task}>,
  "company_work_hours": <float 0.0-{max_company}>,
  "reasoning": "<your strategic reasoning>",
  "confidence": <float 0.0-1.0>
}}

Provide ONLY the JSON response, no additional text.
```

### Company Formation Prompt Template

```
You are an autonomous economic agent deciding whether to form a company.

CURRENT STATE:
[... same state info ...]

DECISION REQUIRED:
Should you allocate capital to form a company?

CONSIDERATIONS:
- Company formation costs ~30% of current balance
- Requires minimum capital: ${self.company_threshold * 0.3:.2f}
- Company enables long-term growth but reduces liquid capital
- Balance survival vs growth tradeoff

RESPONSE FORMAT (JSON):
{{
  "should_form_company": <true|false>,
  "reasoning": "<your strategic reasoning>",
  "confidence": <float 0.0-1.0>
}}

Provide ONLY the JSON response, no additional text.
```

## Decision Logging

```python
# economic_agents/agent/llm/decision_log.py
@dataclass
class LLMDecision:
    """Record of a Claude-powered decision."""

    decision_id: str
    timestamp: datetime
    agent_type: str = "claude"  # Always Claude for this research
    state_snapshot: dict
    prompt: str
    raw_response: str
    parsed_decision: dict
    validation_passed: bool
    execution_time_seconds: float  # Can be up to 900s (15 minutes)
    fallback_used: bool
```

## Configuration

```yaml
# config/agent_config.yml
decision_engine:
  type: "llm"  # or "rule_based" or "hybrid"

  llm:
    agent: "claude"  # Claude-only for this research
    timeout: 900  # 15 minutes (900 seconds)
    unattended: true  # Always use --dangerously-skip-permissions
    node_version: "22.16.0"

  fallback:
    enabled: true
    on_error: true
    on_timeout: true
    on_validation_failure: true

  validation:
    max_allocation_hours: "state.compute_hours_remaining"
    require_json_response: true
    require_reasoning: true
    min_reasoning_length: 50  # chars

  logging:
    log_prompts: true
    log_responses: true
    log_execution_time: true
    log_full_reasoning: true
```

## Safety & Validation

### Validation Rules

```python
def _validate_allocation(self, allocation: ResourceAllocation,
                        state: AgentState) -> bool:
    """Validate LLM decision against safety rules."""

    # Check total allocation
    total = allocation.task_work_hours + allocation.company_work_hours
    if total > state.compute_hours_remaining:
        logger.warning("LLM allocated more hours than available")
        return False

    # Check negative values
    if allocation.task_work_hours < 0 or allocation.company_work_hours < 0:
        logger.warning("LLM allocated negative hours")
        return False

    # Check survival risk
    if state.is_survival_at_risk() and allocation.task_work_hours < 0.5:
        logger.warning("LLM didn't prioritize survival when at risk")
        return False

    # Check reasoning exists
    if not allocation.reasoning or len(allocation.reasoning) < 10:
        logger.warning("LLM provided insufficient reasoning")
        return False

    return True
```

## Implementation Phases

### Phase 7.1: Infrastructure (Claude Executor)
- [ ] Create `economic_agents/agent/llm/` directory structure
- [ ] Implement `ClaudeExecutor` with 15-minute timeout support
- [ ] Add unattended mode configuration
- [ ] Add executor tests (mock subprocess)
- [ ] Test with simple prompts before decision-making

### Phase 7.2: Decision Engine
- [ ] Implement `LLMDecisionEngine`
- [ ] Add prompt templates for resource allocation
- [ ] Add prompt templates for company formation
- [ ] Add JSON response parsing with error handling
- [ ] Add validation logic
- [ ] Add fallback mechanism to rule-based engine

### Phase 7.3: Integration
- [ ] Update `AutonomousAgent` to support LLM engine
- [ ] Add configuration loading (YAML/dict)
- [ ] Add decision logging with full reasoning capture
- [ ] Update dashboard to show Claude decisions and reasoning
- [ ] Add timing metrics (15-minute decisions tracked)

### Phase 7.4: Testing
- [ ] Unit tests for ClaudeExecutor
- [ ] Unit tests for decision engine
- [ ] Integration tests with mock Claude responses
- [ ] Manual testing with real Claude Code
- [ ] Timeout testing (verify 15-minute handling)
- [ ] Validation tests for safety guardrails

### Phase 7.5: Documentation
- [ ] Architecture documentation
- [ ] Configuration guide (timeouts, unattended mode)
- [ ] Usage examples (survival vs company mode)
- [ ] Troubleshooting guide (Claude errors, timeouts)
- [ ] Research methodology notes

## Estimated Timeline

- **Phase 7.1:** 2 days (Claude executor implementation)
- **Phase 7.2:** 3-4 days (decision engine with prompts)
- **Phase 7.3:** 2-3 days (integration with autonomous agent)
- **Phase 7.4:** 2-3 days (testing with real Claude)
- **Phase 7.5:** 1 day (documentation)

**Total:** 10-13 days

## Research Benefits

By using Claude Code exclusively:
- **Consistent Decision-Making:** Single model eliminates cross-model variability
- **Fixed Costs:** Monthly subscription means unlimited experimentation
- **Deep Reasoning:** Claude's 15-minute timeouts allow thorough strategic thinking
- **Tool Use:** Claude can use bash/file operations if needed for decisions
- **Reproducible:** Deterministic enough for research (with temperature=0)

## Next Steps

1. ✅ Review and approve this architecture (Claude-only, 15min timeout, unattended)
2. Start with Phase 7.1 (ClaudeExecutor implementation)
3. Test ClaudeExecutor with simple prompts before complex decision-making
4. Implement decision engine with validated JSON parsing
5. Integrate with autonomous agent and test in survival mode first
6. Iterate based on actual Claude behavior and reasoning quality
