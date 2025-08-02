# Multi-Agent System: Gemini Feedback Integration

## Overview

Consulted Gemini about our multi-agent architecture and received valuable technical feedback. This document summarizes the key recommendations and changes made.

## Key Recommendations from Gemini

### 1. CLI Wrapper Approach ✅
**Gemini Confirmed**: The CLI wrapper pattern is optimal for integrating terminal-based tools.
- Classic Adapter pattern application
- Encapsulates agent-specific logic
- Provides consistent interface

### 2. Process Management Strategy ✅
**Recommendation**: Spawn processes per task, not long-running processes.

**Rationale**:
- **Isolation**: Prevents state leakage between tasks
- **Stability**: Agent crashes don't affect system
- **Simplicity**: Avoids complex IPC and health checks
- Process creation overhead negligible for CI/CD tasks

**Status**: Already implemented this way in our design.

### 3. Graceful Termination ✅
**Recommendation**: Implement proper timeout handling with SIGTERM then SIGKILL.

**Implementation**:
```python
# First try SIGTERM
proc.terminate()
try:
    await asyncio.wait_for(proc.wait(), timeout=2.0)
except asyncio.TimeoutError:
    # Force kill if still running
    proc.kill()
    await proc.wait()
```

**Status**: Implemented in `cli_agent_wrapper.py`

### 4. Structured Error Handling ✅
**Recommendation**: Create custom exceptions with context.

**Implementation**:
- `AgentTimeoutError`: Includes timeout duration and partial output
- `AgentExecutionError`: Includes return code and stderr
- `AgentAuthenticationError`: Tracks auth method
- `AgentOutputParsingError`: Shows expected vs actual format

**Status**: Implemented in `exceptions.py`

### 5. Authentication Flexibility ✅
**Recommendation**: Add dedicated auth methods per agent.

**Implementation**:
```python
def get_auth_command() -> Optional[List[str]]:
    """Override in subclasses for agent-specific auth"""

async def authenticate() -> bool:
    """Run authentication if required"""
```

**Status**: Added to base `CLIAgentWrapper`

### 6. Agent-Specific Features
**Recommendation**: Use conditional casting for unique features.

**Example**:
```python
if isinstance(agent, CrushAgent) and hasattr(agent, 'use_mcp'):
    agent.use_mcp(mcp_config)
```

**Status**: Design supports this pattern.

### 7. Upstream Contributions 🔄
**Strong Recommendation**: Contribute non-interactive modes upstream.

**Benefits**:
- Simplifies output parsing
- Reduces brittleness
- Benefits community

**Action Items**:
1. OpenCode: Request `--json-output` flag
2. Codex CLI: Request `--non-interactive` mode
3. Crush: Request structured output format

## Implementation Changes Made

### 1. Enhanced Exception Handling
- Created comprehensive exception hierarchy
- Include stdout/stderr in exceptions
- Better debugging information

### 2. Improved Timeout Management
- Graceful SIGTERM → SIGKILL sequence
- Capture partial output on timeout
- 2-second grace period for cleanup

### 3. Authentication Framework
- Base methods for auth commands
- Per-agent auth customization
- Clear auth failure reporting

### 4. Better Error Context
- All exceptions include agent name
- Execution errors show return codes
- Timeout errors include partial output

## Architecture Validation

Gemini validated our core design decisions:
- ✅ CLI wrapper pattern (Adapter pattern)
- ✅ Per-task process spawning
- ✅ Unified agent interface
- ✅ Configuration-driven approach
- ✅ Host-based execution model

## Security Considerations

Gemini emphasized:
1. **Minimum Permissions**: Run agents with minimal filesystem/network access
2. **Host Environment**: Tightly control agent execution environment
3. **Authentication**: Secure handling of diverse auth methods

## Alternative Approaches Considered

Gemini mentioned a "CLI-to-API translation service" but agreed it's overkill for our needs:
- **Pros**: Centralized CLI management, reusable
- **Cons**: Significantly more complex, unnecessary for current scope

## Next Steps Based on Feedback

1. **Immediate**:
   - ✅ Implement custom exceptions
   - ✅ Add graceful termination
   - ✅ Create auth helper methods

2. **Short-term**:
   - Test enhanced error handling
   - Document security best practices
   - Create agent permission profiles

3. **Long-term**:
   - Open upstream feature requests
   - Consider capability detection system
   - Build performance benchmarks

## Conclusion

Gemini's feedback strongly validates our architecture while providing specific improvements for robustness and maintainability. The CLI wrapper pattern with per-task process spawning is confirmed as the optimal approach for integrating these terminal-based AI agents.
