"""Configuration management for GitHub AI Agents."""

import os
from pathlib import Path
from typing import Any, Dict, List, Optional

import yaml


class AgentConfig:
    """Configuration loader for AI agents."""

    def __init__(self, config_path: Optional[Path] = None):
        """Initialize configuration.

        Args:
            config_path: Path to configuration file. If not provided,
                        looks for .agents.yaml in the project root.
        """
        self.config = self._load_config(config_path)

    def _load_config(self, config_path: Optional[Path]) -> Dict[str, Any]:
        """Load configuration from file or use defaults."""
        # Default configuration
        default_config = {
            "enabled_agents": ["claude", "gemini", "opencode", "crush"],
            "agent_priorities": {
                "issue_creation": ["claude"],
                "pr_reviews": ["gemini", "claude"],
                "code_fixes": ["claude"],
            },
            "security": {
                "autonomous_mode": True,
                "require_sandbox": True,
                "max_prompt_length": 10000,
                "temp_file_cleanup": True,
                "subprocess_timeout": 600,
                "memory_limit_mb": 500,
            },
            "rate_limits": {
                "requests_per_minute": 10,
                "requests_per_hour": 100,
                "claude": {"requests_per_minute": 20},
                "gemini": {"requests_per_minute": 5},
            },
            "model_overrides": {
                "gemini": {
                    "pro_model": "gemini-2.5-pro",
                    "flash_model": "gemini-2.5-flash",
                    "default_model": "gemini-2.5-pro",
                },
                "opencode": {
                    "model": "qwen/qwen-2.5-coder-32b-instruct",
                    "temperature": 0.2,
                },
                "crush": {
                    "model": "qwen/qwen-2.5-coder-32b-instruct",
                    "temperature": 0.1,
                },
            },
            "openrouter": {
                "default_model": "qwen/qwen-2.5-coder-32b-instruct",
                "fallback_models": [
                    "deepseek/deepseek-coder-v2-instruct",
                    "meta-llama/llama-3.1-70b-instruct",
                ],
            },
            "advanced": {
                "debug_mode": False,
                "temp_directory": os.environ.get("AGENT_TEMP_DIR", "/tmp/agents"),
                "max_retries": 2,
                "retry_delay_seconds": 5,
                "isolate_environment": True,
                "enable_telemetry": False,
                "non_interactive_flags": {
                    "claude": ["--print", "--dangerously-skip-permissions"],
                    "gemini": ["-m", "gemini-2.5-pro", "-p"],
                    "opencode": [],  # OpenCode doesn't have a non-interactive flag
                    "crush": [],  # Crush doesn't support --non-interactive or --no-update
                },
            },
        }

        # Try to find config file
        if config_path is None:
            # Look for .agents.yaml in the project root
            current_dir = Path.cwd()
            while current_dir != current_dir.parent:
                potential_config = current_dir / ".agents.yaml"
                if potential_config.exists():
                    config_path = potential_config
                    break
                current_dir = current_dir.parent

        # Load configuration from file if found
        if config_path and config_path.exists():
            try:
                with open(config_path) as f:
                    file_config = yaml.safe_load(f)
                    if file_config:
                        # Deep merge with defaults
                        return self._deep_merge(default_config, file_config)
            except Exception:
                # Fall back to defaults on any error
                pass

        return default_config

    def _deep_merge(self, base: Dict[str, Any], updates: Dict[str, Any]) -> Dict[str, Any]:
        """Deep merge two dictionaries."""
        result = base.copy()
        for key, value in updates.items():
            if isinstance(value, dict) and key in result and isinstance(result[key], dict):
                result[key] = self._deep_merge(result[key], value)
            else:
                result[key] = value
        return result

    def get_enabled_agents(self) -> List[str]:
        """Get list of enabled agents."""
        return list(self.config.get("enabled_agents", []))

    def get_agent_priority(self, task_type: str) -> List[str]:
        """Get agent priority for a specific task type."""
        priorities = self.config.get("agent_priorities", {})
        return list(priorities.get(task_type, []))

    def get_security_config(self) -> Dict[str, Any]:
        """Get security configuration."""
        return dict(self.config.get("security", {}))

    def get_rate_limits(self, agent: Optional[str] = None) -> Dict[str, Any]:
        """Get rate limit configuration for an agent."""
        rate_limits = self.config.get("rate_limits", {})
        if agent and agent in rate_limits:
            # Merge agent-specific limits with defaults
            default_limits = {k: v for k, v in rate_limits.items() if not isinstance(v, dict)}
            agent_limits = rate_limits.get(agent, {})
            return {**default_limits, **agent_limits}
        return {k: v for k, v in rate_limits.items() if not isinstance(v, dict)}

    def get_model_config(self, agent: str) -> Dict[str, Any]:
        """Get model configuration for an agent."""
        model_overrides = self.config.get("model_overrides", {})
        return dict(model_overrides.get(agent, {}))

    def get_openrouter_config(self) -> Dict[str, Any]:
        """Get OpenRouter configuration."""
        return dict(self.config.get("openrouter", {}))

    def get_advanced_config(self) -> Dict[str, Any]:
        """Get advanced configuration."""
        return dict(self.config.get("advanced", {}))

    def get_non_interactive_flags(self, agent: str) -> List[str]:
        """Get non-interactive flags for an agent."""
        advanced = self.get_advanced_config()
        flags = advanced.get("non_interactive_flags", {})
        return list(flags.get(agent, []))

    def get_subprocess_timeout(self) -> int:
        """Get subprocess timeout in seconds."""
        security = self.get_security_config()
        return int(security.get("subprocess_timeout", 600))

    def is_autonomous_mode(self) -> bool:
        """Check if autonomous mode is enabled."""
        security = self.get_security_config()
        return bool(security.get("autonomous_mode", True))
