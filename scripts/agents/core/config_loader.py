"""Configuration loader for multi-agent system."""

import logging
import os
from typing import Dict, List, Optional

import yaml

logger = logging.getLogger(__name__)


class AgentConfig:
    """Manages agent configuration loading and access."""

    def __init__(self, config_path: Optional[str] = None):
        """Initialize configuration loader.

        Args:
            config_path: Path to configuration file (defaults to .agents.yaml)
        """
        self.config_path = config_path or self._find_config_file()
        self.config = self._load_config()

    def _find_config_file(self) -> str:
        """Find configuration file in standard locations."""
        locations = [
            ".agents.yaml",
            ".agents.yml",
            "config/agents.yaml",
            "config/agents.yml",
            os.path.expanduser("~/.config/agents.yaml"),
        ]

        for location in locations:
            if os.path.exists(location):
                return location

        # Return default location if none found
        return ".agents.yaml"

    def _load_config(self) -> Dict:
        """Load configuration from file."""
        default_config = {
            "enabled_agents": ["claude"],  # Claude always enabled by default
            "agent_priorities": {"issue_creation": ["claude"], "pr_reviews": ["gemini"], "code_fixes": ["claude"]},
            "model_overrides": {},
            "openrouter": {
                "api_key": os.environ.get("OPENROUTER_API_KEY", ""),
                "default_model": "qwen/qwen-2.5-coder-32b-instruct",
                "fallback_models": ["deepseek/deepseek-coder-v2-instruct", "meta-llama/llama-3.1-70b-instruct"],
            },
        }

        if not os.path.exists(self.config_path):
            logger.info(f"No config file found at {self.config_path}, using defaults")
            return default_config

        try:
            with open(self.config_path, "r") as f:
                user_config = yaml.safe_load(f) or {}

            # Merge with defaults
            config = default_config.copy()
            config.update(user_config)

            logger.info(f"Loaded configuration from {self.config_path}")
            return config

        except Exception as e:
            logger.error(f"Failed to load config from {self.config_path}: {e}")
            return default_config

    def get_enabled_agents(self) -> List[str]:
        """Get list of enabled agents."""
        return self.config.get("enabled_agents", ["claude"])

    def get_agent_priority(self, task_type: str) -> List[str]:
        """Get prioritized list of agents for a task type."""
        priorities = self.config.get("agent_priorities", {})
        return priorities.get(task_type, self.get_enabled_agents())

    def get_model_override(self, agent: str) -> Optional[Dict]:
        """Get model override configuration for an agent."""
        overrides = self.config.get("model_overrides", {})
        return overrides.get(agent)

    def get_openrouter_config(self) -> Dict:
        """Get OpenRouter configuration."""
        return self.config.get("openrouter", {})

    def save_config(self):
        """Save current configuration to file."""
        try:
            os.makedirs(os.path.dirname(self.config_path), exist_ok=True)
            with open(self.config_path, "w") as f:
                yaml.dump(self.config, f, default_flow_style=False)
            logger.info(f"Saved configuration to {self.config_path}")
        except Exception as e:
            logger.error(f"Failed to save config: {e}")
            raise
