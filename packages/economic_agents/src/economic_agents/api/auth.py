"""Authentication middleware for API services."""

from datetime import datetime, timedelta
import secrets
from typing import Any, Dict, Optional

from fastapi import Header, HTTPException, status
from pydantic import BaseModel


class APIKeyManager:
    """Manages API keys for agent authentication."""

    def __init__(self) -> None:
        """Initialize API key manager."""
        self.api_keys: Dict[str, Dict[str, Any]] = {}  # key -> {agent_id, expires_at}

    def generate_key(self, agent_id: str, expires_in_days: Optional[int] = None) -> str:
        """Generate a new API key for an agent.

        Args:
            agent_id: Agent ID to associate with key
            expires_in_days: Optional expiration period in days

        Returns:
            Generated API key
        """
        api_key = f"ea_{secrets.token_urlsafe(32)}"
        key_data = {
            "agent_id": agent_id,
            "created_at": datetime.now(),
            "expires_at": datetime.now() + timedelta(days=expires_in_days) if expires_in_days else None,
        }
        self.api_keys[api_key] = key_data
        return api_key

    def validate_key(self, api_key: str) -> Optional[str]:
        """Validate an API key and return associated agent ID.

        Args:
            api_key: API key to validate

        Returns:
            Agent ID if valid, None otherwise
        """
        if api_key not in self.api_keys:
            return None

        key_data = self.api_keys[api_key]

        # Check expiration
        if key_data.get("expires_at"):
            if datetime.now() > key_data["expires_at"]:
                return None

        return str(key_data["agent_id"])

    def revoke_key(self, api_key: str) -> bool:
        """Revoke an API key.

        Args:
            api_key: API key to revoke

        Returns:
            True if key was revoked, False if key didn't exist
        """
        if api_key in self.api_keys:
            del self.api_keys[api_key]
            return True
        return False

    def get_agent_keys(self, agent_id: str) -> list:
        """Get all API keys for an agent.

        Args:
            agent_id: Agent ID

        Returns:
            List of API keys for the agent
        """
        return [key for key, data in self.api_keys.items() if data["agent_id"] == agent_id]


# Global API key manager instance
api_key_manager = APIKeyManager()


async def verify_api_key(x_api_key: str = Header(..., description="API key for authentication")) -> str:
    """Dependency to verify API key and return agent ID.

    Args:
        x_api_key: API key from request header

    Returns:
        Agent ID associated with the API key

    Raises:
        HTTPException: If API key is invalid or expired
    """
    agent_id = api_key_manager.validate_key(x_api_key)

    if not agent_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired API key",
            headers={"WWW-Authenticate": "Bearer"},
        )

    return agent_id


class AuthConfig(BaseModel):
    """Configuration for authentication system."""

    enabled: bool = True
    default_key_expiration_days: Optional[int] = None
    require_key_rotation: bool = False


# Default auth config
auth_config = AuthConfig()
