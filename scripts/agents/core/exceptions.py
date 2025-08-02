"""Custom exceptions for the multi-agent system."""


class AgentError(Exception):
    """Base exception for all agent-related errors."""

    def __init__(self, agent_name: str, message: str):
        self.agent_name = agent_name
        self.message = message
        super().__init__(f"[{agent_name}] {message}")


class AgentTimeoutError(AgentError):
    """Raised when an agent command exceeds its timeout."""

    def __init__(self, agent_name: str, timeout: int, stdout: str = "", stderr: str = ""):
        self.timeout = timeout
        self.stdout = stdout
        self.stderr = stderr
        message = f"Command timed out after {timeout}s"
        if stderr:
            message += f"\nStderr: {stderr[:200]}..."
        super().__init__(agent_name, message)


class AgentExecutionError(AgentError):
    """Raised when an agent command fails to execute."""

    def __init__(self, agent_name: str, return_code: int, stdout: str = "", stderr: str = ""):
        self.return_code = return_code
        self.stdout = stdout
        self.stderr = stderr
        message = f"Command failed with exit code {return_code}"
        if stderr:
            message += f"\nStderr: {stderr[:500]}..."
        super().__init__(agent_name, message)


class AgentNotAvailableError(AgentError):
    """Raised when an agent is not installed or configured."""

    def __init__(self, agent_name: str, reason: str):
        self.reason = reason
        super().__init__(agent_name, f"Agent not available: {reason}")


class AgentAuthenticationError(AgentError):
    """Raised when agent authentication fails."""

    def __init__(self, agent_name: str, auth_method: str):
        self.auth_method = auth_method
        super().__init__(agent_name, f"Authentication failed using method: {auth_method}")


class AgentOutputParsingError(AgentError):
    """Raised when agent output cannot be parsed."""

    def __init__(self, agent_name: str, output: str, expected_format: str):
        self.output = output
        self.expected_format = expected_format
        super().__init__(agent_name, f"Failed to parse output. Expected format: {expected_format}\nGot: {output[:200]}...")
