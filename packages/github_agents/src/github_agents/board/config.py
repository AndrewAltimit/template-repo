"""Configuration management for board integration."""

import os
from pathlib import Path

import yaml

from github_agents.board.errors import ValidationError
from github_agents.board.models import BoardConfig


def load_config(config_path: str | None = None) -> BoardConfig:
    """
    Load board configuration from file or environment variables.

    Args:
        config_path: Path to configuration YAML file.
                    Defaults to ai-agents-board.yml

    Returns:
        BoardConfig instance

    Raises:
        ValidationError: If configuration is invalid
        FileNotFoundError: If config file doesn't exist
    """
    if config_path is None:
        config_path = _find_config_file()

    if config_path and Path(config_path).exists():
        return _load_from_file(config_path)
    return _load_from_env()


def _find_config_file() -> str | None:
    """
    Find configuration file in standard locations.

    Searches:
    1. ai-agents-board.yml (root - recommended)
    2. ai-agents-board.yaml (root - alternative)
    3. .github/ai-agents-board.yml (legacy location)
    4. .github/ai-agents-board.yaml (legacy location)

    Returns:
        Path to config file if found, None otherwise
    """
    search_paths = [
        "ai-agents-board.yml",
        "ai-agents-board.yaml",
        ".github/ai-agents-board.yml",
        ".github/ai-agents-board.yaml",
    ]

    for path in search_paths:
        if Path(path).exists():
            return path

    return None


def _load_from_file(config_path: str) -> BoardConfig:
    """
    Load configuration from YAML file.

    Args:
        config_path: Path to YAML configuration file

    Returns:
        BoardConfig instance

    Raises:
        ValidationError: If configuration is invalid
    """
    try:
        with open(config_path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)

        if not data:
            raise ValidationError(f"Configuration file {config_path} is empty")

        # Validate required fields
        project = data.get("project", {})
        if not project.get("number"):
            raise ValidationError("Configuration missing required field: project.number")
        if not project.get("owner"):
            raise ValidationError("Configuration missing required field: project.owner")

        # Add repository from environment if not in config
        if "repository" not in data:
            data["repository"] = os.getenv("GITHUB_REPOSITORY", "")

        return BoardConfig.from_dict(data)

    except yaml.YAMLError as e:
        raise ValidationError(f"Invalid YAML in configuration file: {e}") from e
    except Exception as e:
        raise ValidationError(f"Failed to load configuration: {e}") from e


def _load_from_env() -> BoardConfig:
    """
    Load configuration from environment variables.

    Environment variables:
    - BOARD_PROJECT_NUMBER: GitHub Project number
    - BOARD_PROJECT_OWNER: Project owner
    - GITHUB_REPOSITORY: Repository name
    - BOARD_CLAIM_TIMEOUT: Claim timeout in seconds (default: 86400)
    - BOARD_ENABLED_AGENTS: Comma-separated agent names

    Returns:
        BoardConfig instance

    Raises:
        ValidationError: If required environment variables are missing
    """
    project_number = os.getenv("BOARD_PROJECT_NUMBER")
    owner = os.getenv("BOARD_PROJECT_OWNER")
    repository = os.getenv("GITHUB_REPOSITORY", "")

    if not project_number:
        raise ValidationError("BOARD_PROJECT_NUMBER environment variable required when config file not found")
    if not owner:
        raise ValidationError("BOARD_PROJECT_OWNER environment variable required when config file not found")

    try:
        project_num = int(project_number)
    except ValueError as e:
        raise ValidationError(f"BOARD_PROJECT_NUMBER must be an integer, got: {project_number}") from e

    # Parse optional settings
    claim_timeout = int(os.getenv("BOARD_CLAIM_TIMEOUT", "86400"))
    enabled_agents_str = os.getenv("BOARD_ENABLED_AGENTS", "")
    enabled_agents = [a.strip() for a in enabled_agents_str.split(",") if a.strip()]

    return BoardConfig(
        project_number=project_num,
        owner=owner,
        repository=repository,
        claim_timeout=claim_timeout,
        enabled_agents=enabled_agents,
    )


def validate_config(config: BoardConfig) -> list[str]:
    """
    Validate board configuration.

    Args:
        config: BoardConfig to validate

    Returns:
        List of validation error messages (empty if valid)
    """
    errors = []

    if config.project_number <= 0:
        errors.append("project_number must be positive")

    if not config.owner:
        errors.append("owner cannot be empty")

    if config.claim_timeout < 60:
        errors.append("claim_timeout should be at least 60 seconds")

    if config.claim_renewal_interval >= config.claim_timeout:
        errors.append("claim_renewal_interval must be less than claim_timeout")

    # Validate field mappings
    required_fields = ["status", "priority", "agent", "type", "blocked_by"]
    for field in required_fields:
        if field not in config.field_mappings:
            errors.append(f"Missing required field mapping: {field}")

    return errors


def create_default_config(project_number: int, owner: str, repository: str) -> str:
    """
    Create a default configuration YAML string.

    Args:
        project_number: GitHub Project number
        owner: Project owner
        repository: Repository name

    Returns:
        YAML configuration string
    """
    config_dict = {
        "project": {"number": project_number, "owner": owner},
        "repository": repository,
        "fields": {
            "status": "Status",
            "priority": "Priority",
            "agent": "Agent",
            "type": "Type",
            "blocked_by": "Blocked By",
            "discovered_from": "Discovered From",
            "size": "Estimated Size",
        },
        "agents": {
            "auto_discover": True,
            "enabled_agents": ["claude", "opencode", "gemini", "crush"],
        },
        "work_queue": {
            "exclude_labels": ["wontfix", "duplicate"],
            "priority_labels": {
                "critical": ["security", "outage", "critical-bug"],
                "high": ["bug", "regression"],
                "medium": ["enhancement", "feature"],
                "low": ["documentation", "cleanup"],
            },
        },
        "work_claims": {
            "timeout": 86400,
            "renewal_interval": 3600,
            "notify_expired": True,
            "notification_interval": 86400,
            "enforce_claims": True,
        },
    }

    return yaml.dump(config_dict, default_flow_style=False, sort_keys=False)
