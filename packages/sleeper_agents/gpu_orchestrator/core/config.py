"""Configuration management for GPU Orchestrator API."""

from pathlib import Path
from typing import List

from pydantic_settings import BaseSettings, SettingsConfigDict

# API keys that have shipped in examples/defaults and must never be accepted
KNOWN_INSECURE_API_KEYS = frozenset(
    {
        "dev-api-key-change-in-production",
        "your-api-key-here",
        "your-secret-key",
        "your-secure-api-key-here",
        "test-key-12345-change-in-production",
        "my-secure-key-12345",
        "change-me",
        "changeme",
    }
)


class InsecureConfigurationError(RuntimeError):
    """Raised when the orchestrator is configured in a way that must not be served."""


def validate_api_key(api_key: str) -> None:
    """Refuse to run with a missing or publicly known API key.

    The API key is the only authentication for endpoints that launch GPU
    containers, so an empty or well-known value exposes the host to anyone who
    can reach the port.

    Args:
        api_key: Configured API key

    Raises:
        InsecureConfigurationError: If the key is empty or a known default
    """
    key = (api_key or "").strip()
    if not key:
        raise InsecureConfigurationError(
            "API_KEY is not set. Set API_KEY in gpu_orchestrator/.env (or the environment) to a random secret, "
            'e.g. the output of: python -c "import secrets; print(secrets.token_urlsafe(32))"'
        )
    if key.lower() in KNOWN_INSECURE_API_KEYS:
        raise InsecureConfigurationError(
            f"API_KEY is set to the publicly known placeholder {key!r}. Replace it with a random secret, "
            'e.g. the output of: python -c "import secrets; print(secrets.token_urlsafe(32))"'
        )


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )

    # API Settings
    api_host: str = "0.0.0.0"
    api_port: int = 8000
    # Required. The API refuses to start when this is empty or a known placeholder.
    api_key: str = ""

    # CORS Settings
    cors_origins: str = "http://localhost:8501"

    @property
    def cors_origins_list(self) -> List[str]:
        """Parse CORS origins from comma-separated string."""
        return [origin.strip() for origin in self.cors_origins.split(",")]

    # Database
    database_path: Path = Path("./orchestrator.db")

    # Docker Settings
    docker_compose_file: Path = Path("../docker/docker-compose.gpu.yml")
    sleeper_service_name: str = "sleeper-eval-gpu"

    # Volume Names
    models_volume: str = "sleeper-models"
    results_volume: str = "sleeper-results"
    gpu_cache_volume: str = "sleeper-gpu-cache"

    # Job Settings
    max_concurrent_jobs: int = 2
    job_timeout_seconds: int = 3600  # 1 hour
    # Maximum number of log lines GET /api/jobs/{id}/logs returns in one response
    # (applies to tail=0 "all lines" requests and to incremental chunks). 0 disables the cap.
    log_buffer_size: int = 10000

    # Log Storage Settings
    logs_directory: Path = Path("./logs")
    log_retention_days: int = 30  # Keep logs for 30 days

    # Cleanup Settings
    cleanup_old_jobs_days: int = 30
    cleanup_interval_hours: int = 24

    # Job Deletion Settings
    allow_job_deletion: bool = True  # Allow users to delete jobs and their files

    # Model discovery (GET /api/models)
    model_scan_max_depth: int = 6  # Directory levels below /results and /models
    model_scan_max_results: int = 500  # Models returned per scan
    model_scan_cache_seconds: int = 30  # Reuse a scan for this long unless refresh=true


# Global settings instance
settings = Settings()
