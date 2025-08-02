# Multi-Agent System Production Readiness Improvements

## Security Improvements

### 1. Autonomous Mode for CI/CD (`--dangerously-skip-permissions`)
- **Purpose**: The Claude CLI uses `--dangerously-skip-permissions` to enable fully autonomous operation in CI/CD environments
- **Security Context**:
  - This is REQUIRED for automated workflows where no human interaction is possible
  - All agents run in sandboxed environments (containers/VMs) for security
  - The flag prevents interactive prompts that would block CI/CD pipelines
- **Best Practices**:
  - Only use in isolated, sandboxed environments
  - Never use on developer workstations with access to sensitive data
  - Consider using ANTHROPIC_API_KEY for additional security layer

### 2. Temporary File Security
```python
# Current issue in cli_agent_wrapper.py:
with tempfile.NamedTemporaryFile(mode="w", suffix=suffix, delete=False) as f:
    f.write(content)
    return f.name

# Improvement:
import atexit
import weakref

class SecureTempFileManager:
    def __init__(self):
        self._temp_files = weakref.WeakSet()
        atexit.register(self._cleanup_all)

    def create_temp_file(self, content, suffix=".txt"):
        with tempfile.NamedTemporaryFile(mode="w", suffix=suffix, delete=False) as f:
            f.write(content)
            self._temp_files.add(f.name)
            return f.name

    def _cleanup_all(self):
        for filepath in list(self._temp_files):
            try:
                os.unlink(filepath)
            except Exception:
                pass
```

### 3. Subprocess Resource Limits
```python
# Add to _execute_with_timeout method:
proc = await asyncio.create_subprocess_exec(
    *cmd,
    stdout=asyncio.subprocess.PIPE,
    stderr=asyncio.subprocess.PIPE,
    env=env,
    cwd=self.working_dir,
    preexec_fn=lambda: resource.setrlimit(resource.RLIMIT_AS, (500 * 1024 * 1024, -1))  # 500MB memory limit
)
```

### 4. Input Validation
```python
def validate_prompt(prompt: str, max_length: int = 10000) -> str:
    """Validate and sanitize user prompts."""
    if not prompt or not isinstance(prompt, str):
        raise ValueError("Prompt must be a non-empty string")

    if len(prompt) > max_length:
        raise ValueError(f"Prompt exceeds maximum length of {max_length} characters")

    # Remove any potential command injection attempts
    dangerous_patterns = [';', '&&', '||', '`', '$', '\\n']
    for pattern in dangerous_patterns:
        if pattern in prompt:
            logger.warning(f"Potentially dangerous pattern '{pattern}' found in prompt")
            # Could either reject or sanitize based on security policy

    return prompt.strip()
```

## Configuration Improvements

### 1. Create Default Configuration
```yaml
# .agents.yaml.default
enabled_agents:
  - claude      # Primary agent, always available
  - gemini      # Secondary agent for reviews

agent_priorities:
  issue_creation: [claude]
  pr_reviews: [gemini, claude]
  code_fixes: [claude]

# Security settings
security:
  allow_dangerous_mode: false
  max_prompt_length: 10000
  temp_file_cleanup: true
  subprocess_timeout: 600  # 10 minutes max
  memory_limit_mb: 500

# Rate limiting
rate_limits:
  requests_per_minute: 10
  requests_per_hour: 100
```

### 2. Environment Variable Documentation
```bash
# Required for specific agents
export OPENROUTER_API_KEY="your-key"      # For OpenCode, Crush, Codex
export OPENAI_API_KEY="your-key"          # For Codex
export ANTHROPIC_API_KEY="your-key"       # For Claude API mode

# Required for CI/CD autonomous operation
export CLAUDE_AUTONOMOUS_MODE="true"      # Enables --dangerously-skip-permissions
export AGENT_SANDBOX_MODE="true"          # Confirms running in sandboxed environment
export AGENT_MAX_TIMEOUT="600"             # Maximum execution time
export AGENT_TEMP_DIR="/tmp/agents"        # Custom temp directory
```

## Error Handling Improvements

### 1. Better Dependency Checking
```python
class AgentDependencyChecker:
    @staticmethod
    def check_agent_dependencies(agent_name: str) -> Dict[str, bool]:
        """Check all dependencies for an agent."""
        checks = {
            'executable': False,
            'authentication': False,
            'configuration': False,
            'network': False
        }

        # Check executable
        checks['executable'] = shutil.which(agent_name) is not None

        # Check authentication (agent-specific)
        if agent_name == 'claude':
            checks['authentication'] = check_claude_auth()
        elif agent_name == 'gemini':
            checks['authentication'] = check_gemini_auth()

        return checks
```

### 2. Retry Logic
```python
from tenacity import retry, stop_after_attempt, wait_exponential

class RetryableAgent(CLIAgentWrapper):
    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=4, max=10),
        retry=retry_if_exception_type((AgentTimeoutError, AgentExecutionError))
    )
    async def generate_code_with_retry(self, prompt: str, context: Dict[str, str]) -> str:
        return await self.generate_code(prompt, context)
```

## Testing Improvements

### 1. Unit Tests for Agents
```python
# tests/test_multi_agent_system.py
import pytest
from unittest.mock import Mock, patch, AsyncMock
from scripts.agents.implementations import ClaudeAgent, GeminiAgent

@pytest.mark.asyncio
async def test_claude_agent_generate_code():
    agent = ClaudeAgent()

    with patch('subprocess.run') as mock_run:
        mock_run.return_value.returncode = 0
        mock_run.return_value.stdout = b"def test(): pass"

        with patch.object(agent, '_execute_with_timeout') as mock_exec:
            mock_exec.return_value = ("def test(): pass", "")

            result = await agent.generate_code("Write a test function", {})
            assert "def test():" in result
```

### 2. Integration Tests
```python
# tests/test_multi_agent_integration.py
@pytest.mark.integration
async def test_multi_agent_fallback():
    """Test that system falls back to secondary agent if primary fails."""
    manager = MultiAgentSubagentManager()

    # Simulate Claude failure
    with patch.object(manager.agents['claude'], 'is_available', return_value=False):
        # Should fall back to next available agent
        result = manager.get_agent_for_task('issue_creation')
        assert result is not None
```

## Monitoring and Telemetry

### 1. Metrics Collection
```python
class AgentMetrics:
    def __init__(self):
        self.metrics = {
            'requests': Counter('agent_requests_total'),
            'errors': Counter('agent_errors_total'),
            'duration': Histogram('agent_request_duration_seconds'),
            'tokens': Counter('agent_tokens_used_total')
        }

    def record_request(self, agent_name: str, duration: float, success: bool, tokens: int = 0):
        labels = {'agent': agent_name, 'success': str(success)}
        self.metrics['requests'].inc(labels)
        self.metrics['duration'].observe(duration, labels)
        if tokens > 0:
            self.metrics['tokens'].inc(tokens, {'agent': agent_name})
        if not success:
            self.metrics['errors'].inc({'agent': agent_name})
```

### 2. Structured Logging
```python
import structlog

logger = structlog.get_logger()

# Use structured logging for better observability
logger.info(
    "agent_request",
    agent=agent_name,
    prompt_length=len(prompt),
    context_keys=list(context.keys()),
    duration=duration,
    success=success
)
```

## Deployment Checklist

- [ ] Set up environment variables for all required agents
- [ ] Configure rate limiting and security settings
- [ ] Enable monitoring/metrics collection
- [ ] Set up log aggregation
- [ ] Create runbook for common issues
- [ ] Document rollback procedures
- [ ] Test agent fallback mechanisms
- [ ] Verify temp file cleanup
- [ ] Check subprocess resource limits
- [ ] Review and update allow lists
- [ ] Confirm all agents run in sandboxed environments
- [ ] Document autonomous mode requirements
- [ ] Test non-interactive execution for all agents
