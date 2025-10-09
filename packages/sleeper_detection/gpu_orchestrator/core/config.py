"""Configuration management for GPU Orchestrator API."""

from pathlib import Path
from typing import List

from pydantic_settings import BaseSettings, SettingsConfigDict


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
    api_key: str = "dev-api-key-change-in-production"

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
    log_buffer_size: int = 10000  # Lines

    # Cleanup Settings
    cleanup_old_jobs_days: int = 30
    cleanup_interval_hours: int = 24


# Global settings instance
settings = Settings()
