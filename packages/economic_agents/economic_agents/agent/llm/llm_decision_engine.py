"""LLM-powered decision engine using Claude Code for autonomous agent decisions."""

import json
import logging
import time
from dataclasses import dataclass
from datetime import datetime

from economic_agents.agent.core.decision_engine import DecisionEngine, ResourceAllocation
from economic_agents.agent.core.state import AgentState
from economic_agents.agent.llm.executors import ClaudeExecutor

logger = logging.getLogger(__name__)


@dataclass
class LLMDecision:
    """Record of a Claude-powered decision."""

    decision_id: str
    timestamp: datetime
    agent_type: str
    state_snapshot: dict
    prompt: str
    raw_response: str
    parsed_decision: dict
    validation_passed: bool
    execution_time_seconds: float
    fallback_used: bool


class LLMDecisionEngine:
    """LLM-powered decision engine using Claude Code CLI.

    Makes autonomous decisions by prompting Claude with agent state and
    parsing structured JSON responses. Falls back to rule-based decisions
    on timeout or failure.
    """

    def __init__(self, config: dict | None = None):
        """Initialize LLM decision engine.

        Args:
            config: Configuration dict with:
                - llm_timeout: Timeout in seconds (default: 900 = 15 minutes)
                - node_version: Node.js version (default: "22.16.0")
                - survival_buffer_hours: Survival buffer for fallback (default: 24.0)
                - company_threshold: Company formation threshold for fallback (default: 100.0)
                - fallback_enabled: Enable rule-based fallback (default: True)
        """
        self.config = config or {}
        self.executor = ClaudeExecutor(config)
        self.fallback = DecisionEngine(config)
        self.fallback_enabled = self.config.get("fallback_enabled", True)
        self.decisions: list[LLMDecision] = []

        logger.info(f"LLMDecisionEngine initialized (fallback={'enabled' if self.fallback_enabled else 'disabled'})")

    def decide_allocation(self, state: AgentState) -> ResourceAllocation:
        """Use Claude to decide resource allocation.

        Args:
            state: Current agent state

        Returns:
            ResourceAllocation with hours allocated to each activity

        Raises:
            RuntimeError: If Claude fails and fallback is disabled
        """
        logger.info(
            f"Making allocation decision for state: balance=${state.balance:.2f}, "
            f"compute={state.compute_hours_remaining:.1f}h, mode={state.mode}"
        )

        # Build prompt
        prompt = self._build_allocation_prompt(state)

        # Execute Claude
        start_time = time.time()
        try:
            response = self.executor.execute(prompt)
            execution_time = time.time() - start_time

            logger.info(f"Claude responded in {execution_time:.2f}s ({execution_time/60:.2f} min)")

            # Parse response
            allocation = self._parse_allocation(response)

            # Validate decision
            if not self._validate_allocation(allocation, state):
                raise ValueError("Invalid allocation from Claude")

            # Log decision
            self._log_decision(
                state=state,
                prompt=prompt,
                response=response,
                allocation=allocation,
                execution_time=execution_time,
                fallback_used=False,
            )

            logger.info(
                f"Claude decision: task={allocation.task_work_hours:.2f}h, "
                f"company={allocation.company_work_hours:.2f}h, "
                f"confidence={allocation.confidence:.2f}"
            )

            return allocation

        except Exception as e:
            execution_time = time.time() - start_time
            logger.error(f"Claude decision failed after {execution_time:.2f}s: {e}")

            if not self.fallback_enabled:
                raise RuntimeError(f"Claude decision failed and fallback disabled: {e}")

            # Fallback to rule-based
            logger.warning("Falling back to rule-based decision engine")
            fallback_allocation = self.fallback.decide_allocation(state)

            # Log fallback decision
            self._log_decision(
                state=state,
                prompt=prompt,
                response=str(e),
                allocation=fallback_allocation,
                execution_time=execution_time,
                fallback_used=True,
            )

            return fallback_allocation

    def should_form_company(self, state: AgentState) -> bool:
        """Decide if it's time to create a company.

        Args:
            state: Current agent state

        Returns:
            True if agent should form a company
        """
        # For now, use rule-based logic
        # TODO: Add Claude-powered company formation decision in future
        result: bool = self.fallback.should_form_company(state)
        return result

    def _build_allocation_prompt(self, state: AgentState) -> str:
        """Build prompt for resource allocation decision.

        Args:
            state: Current agent state

        Returns:
            Formatted prompt string
        """
        prompt = f"""You are an autonomous economic agent making resource allocation decisions.

CURRENT STATE:
- Balance: ${state.balance:.2f}
- Compute Hours Remaining: {state.compute_hours_remaining:.1f}h
- Survival Buffer: {state.survival_buffer_hours:.1f}h
- Has Company: {state.has_company}
- Mode: {state.mode}
- Tasks Completed: {state.tasks_completed}

CONFIGURATION:
- Company Threshold: ${self.fallback.company_threshold:.2f}
- Survival at Risk: {state.is_survival_at_risk()}

DECISION REQUIRED:
Allocate compute hours between:
1. Task Work (immediate revenue for survival)
2. Company Work (long-term growth if company exists)

CONSTRAINTS:
- Total allocation cannot exceed {state.compute_hours_remaining:.1f}h
- Must maintain survival buffer of {state.survival_buffer_hours:.1f}h
- If survival at risk (hours < buffer), prioritize tasks
- If no company and low capital, focus on survival

RESPONSE FORMAT (JSON ONLY):
Respond with ONLY a valid JSON object (no markdown, no code blocks, no explanations):

{{
  "task_work_hours": <float between 0.0 and {state.compute_hours_remaining:.1f}>,
  "company_work_hours": <float between 0.0 and {state.compute_hours_remaining:.1f}>,
  "reasoning": "<your strategic reasoning explaining why you made this allocation>",
  "confidence": <float between 0.0 and 1.0>
}}

Return ONLY the JSON object, nothing else.
"""
        return prompt

    def _parse_allocation(self, response: str) -> ResourceAllocation:
        """Parse Claude's JSON response into ResourceAllocation.

        Args:
            response: Raw response from Claude

        Returns:
            ResourceAllocation object

        Raises:
            ValueError: If response cannot be parsed or is invalid
        """
        # Try to extract JSON from response (in case Claude adds extra text)
        response = response.strip()

        # Try to find JSON object in response
        try:
            # Try direct parse first
            data = json.loads(response)
        except json.JSONDecodeError:
            # Try to extract JSON from markdown code block
            if "```json" in response:
                start = response.find("```json") + 7
                end = response.find("```", start)
                json_str = response[start:end].strip()
                data = json.loads(json_str)
            elif "```" in response:
                start = response.find("```") + 3
                end = response.find("```", start)
                json_str = response[start:end].strip()
                data = json.loads(json_str)
            else:
                # Try to find JSON object by looking for { }
                start = response.find("{")
                end = response.rfind("}") + 1
                if start != -1 and end > start:
                    json_str = response[start:end]
                    data = json.loads(json_str)
                else:
                    raise ValueError(f"No JSON object found in response: {response[:200]}")

        # Extract fields
        try:
            task_work_hours = float(data["task_work_hours"])
            company_work_hours = float(data["company_work_hours"])
            reasoning = str(data["reasoning"])
            confidence = float(data["confidence"])
        except (KeyError, ValueError) as e:
            raise ValueError(f"Invalid JSON structure: {e}. Data: {data}")

        return ResourceAllocation(
            task_work_hours=task_work_hours,
            company_work_hours=company_work_hours,
            reasoning=reasoning,
            confidence=confidence,
        )

    def _validate_allocation(self, allocation: ResourceAllocation, state: AgentState) -> bool:
        """Validate Claude's allocation decision.

        Args:
            allocation: Allocation to validate
            state: Current agent state

        Returns:
            True if allocation is valid
        """
        # Check total allocation
        total = allocation.task_work_hours + allocation.company_work_hours
        if total > state.compute_hours_remaining + 0.01:  # Small epsilon for floating point
            logger.warning(f"Invalid: Total allocation ({total:.2f}h) > " f"available ({state.compute_hours_remaining:.1f}h)")
            return False

        # Check negative values
        if allocation.task_work_hours < 0 or allocation.company_work_hours < 0:
            logger.warning("Invalid: Negative hours allocated")
            return False

        # Check survival priority
        if state.is_survival_at_risk() and allocation.task_work_hours < 0.5:
            logger.warning("Invalid: Survival at risk but didn't prioritize tasks")
            return False

        # Check reasoning exists
        if not allocation.reasoning or len(allocation.reasoning) < 10:
            logger.warning("Invalid: Insufficient reasoning")
            return False

        # Check confidence range
        if not (0.0 <= allocation.confidence <= 1.0):
            logger.warning(f"Invalid: Confidence {allocation.confidence} not in [0, 1]")
            return False

        return True

    def _log_decision(
        self,
        state: AgentState,
        prompt: str,
        response: str,
        allocation: ResourceAllocation,
        execution_time: float,
        fallback_used: bool,
    ):
        """Log Claude decision for research analysis.

        Args:
            state: Agent state at decision time
            prompt: Prompt sent to Claude
            response: Raw response from Claude
            allocation: Parsed allocation
            execution_time: Time taken in seconds
            fallback_used: Whether fallback was used
        """
        decision = LLMDecision(
            decision_id=f"dec_{len(self.decisions)}_{int(time.time())}",
            timestamp=datetime.now(),
            agent_type="claude",
            state_snapshot={
                "balance": state.balance,
                "compute_hours_remaining": state.compute_hours_remaining,
                "has_company": state.has_company,
                "mode": state.mode,
                "tasks_completed": state.tasks_completed,
            },
            prompt=prompt,
            raw_response=response,
            parsed_decision={
                "task_work_hours": allocation.task_work_hours,
                "company_work_hours": allocation.company_work_hours,
                "reasoning": allocation.reasoning,
                "confidence": allocation.confidence,
            },
            validation_passed=not fallback_used,
            execution_time_seconds=execution_time,
            fallback_used=fallback_used,
        )

        self.decisions.append(decision)
        logger.debug(f"Logged decision: {decision.decision_id}")

    def get_decisions(self) -> list[LLMDecision]:
        """Get all logged decisions.

        Returns:
            List of LLMDecision objects
        """
        return self.decisions.copy()

    def clear_decisions(self):
        """Clear decision history."""
        self.decisions.clear()
        logger.info("Decision history cleared")
