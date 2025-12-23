"""
Config Loader for Reaction Images

Fetches and caches the reaction config.yaml from GitHub.
Uses a 1-week TTL for the local cache.
"""

import json
import logging
import os
from pathlib import Path
import time
from typing import Any, Dict, List, Optional

import requests
import yaml

logger = logging.getLogger(__name__)

# GitHub raw URL for the reaction config
CONFIG_URL = "https://raw.githubusercontent.com/AndrewAltimit/Media/refs/heads/main/reaction/config.yaml"

# Cache settings
CACHE_TTL_SECONDS = 7 * 24 * 60 * 60  # 1 week
DEFAULT_CACHE_DIR = Path.home() / ".cache" / "mcp_reaction_search"


class ConfigLoader:
    """
    Loader for reaction image configuration.

    Fetches config from GitHub and caches locally with 1-week TTL.
    Falls back to cached version if network is unavailable.
    """

    def __init__(
        self,
        config_url: str = CONFIG_URL,
        cache_dir: Optional[Path] = None,
        cache_ttl: int = CACHE_TTL_SECONDS,
    ):
        """
        Initialize the config loader.

        Args:
            config_url: URL to fetch config from
            cache_dir: Directory for cache files
            cache_ttl: Cache time-to-live in seconds (default: 1 week)
        """
        self.config_url = config_url
        self.cache_dir = cache_dir or DEFAULT_CACHE_DIR
        self.cache_ttl = cache_ttl
        self._config: Optional[Dict[str, Any]] = None

    @property
    def cache_file(self) -> Path:
        """Path to the cached config file."""
        return self.cache_dir / "reaction_config.json"

    @property
    def cache_meta_file(self) -> Path:
        """Path to the cache metadata file."""
        return self.cache_dir / "cache_meta.json"

    def _ensure_cache_dir(self) -> None:
        """Create cache directory if it doesn't exist."""
        self.cache_dir.mkdir(parents=True, exist_ok=True)

    def _is_cache_valid(self) -> bool:
        """Check if the cache exists and is within TTL."""
        if not self.cache_file.exists() or not self.cache_meta_file.exists():
            return False

        try:
            with open(self.cache_meta_file, "r", encoding="utf-8") as f:
                meta = json.load(f)
            cached_at: float = meta.get("cached_at", 0)
            return bool((time.time() - cached_at) < self.cache_ttl)
        except (json.JSONDecodeError, IOError) as e:
            logger.warning("Failed to read cache metadata: %s", e)
            return False

    def _load_from_cache(self) -> Optional[Dict[str, Any]]:
        """Load config from local cache."""
        try:
            with open(self.cache_file, "r", encoding="utf-8") as f:
                config: Dict[str, Any] = json.load(f)
            logger.debug("Loaded config from cache: %s", self.cache_file)
            return config
        except (json.JSONDecodeError, IOError) as e:
            logger.warning("Failed to load cache: %s", e)
            return None

    def _save_to_cache(self, config: Dict[str, Any]) -> None:
        """Save config to local cache with metadata."""
        self._ensure_cache_dir()

        try:
            # Save config
            with open(self.cache_file, "w", encoding="utf-8") as f:
                json.dump(config, f, indent=2)

            # Save metadata
            with open(self.cache_meta_file, "w", encoding="utf-8") as f:
                json.dump(
                    {
                        "cached_at": time.time(),
                        "source_url": self.config_url,
                        "reaction_count": len(config.get("reaction_images", [])),
                    },
                    f,
                    indent=2,
                )
            logger.info("Saved config to cache: %s", self.cache_file)
        except IOError as e:
            logger.error("Failed to save cache: %s", e)

    def _fetch_from_github(self) -> Optional[Dict[str, Any]]:
        """Fetch config from GitHub."""
        try:
            logger.info("Fetching reaction config from: %s", self.config_url)
            response = requests.get(self.config_url, timeout=30)
            response.raise_for_status()

            config: Dict[str, Any] = yaml.safe_load(response.text)
            logger.info(
                "Fetched %d reactions from GitHub",
                len(config.get("reaction_images", [])),
            )
            return config
        except requests.RequestException as e:
            logger.error("Failed to fetch config from GitHub: %s", e)
            return None
        except yaml.YAMLError as e:
            logger.error("Failed to parse YAML config: %s", e)
            return None

    def load(self, force_refresh: bool = False) -> Dict[str, Any]:
        """
        Load the reaction config.

        Uses cached version if valid, otherwise fetches from GitHub.
        Falls back to cache if network is unavailable.

        Args:
            force_refresh: Force fetch from GitHub, ignoring cache

        Returns:
            Config dictionary with 'reaction_images' list

        Raises:
            RuntimeError: If no config could be loaded
        """
        # Return cached in-memory config if available and not forcing refresh
        if self._config is not None and not force_refresh:
            return self._config

        # Check local cache first (unless forcing refresh)
        if not force_refresh and self._is_cache_valid():
            cached = self._load_from_cache()
            if cached:
                self._config = cached
                return self._config

        # Fetch from GitHub
        config = self._fetch_from_github()
        if config:
            self._save_to_cache(config)
            self._config = config
            return self._config

        # Fall back to expired cache if available
        logger.warning("Falling back to expired cache")
        cached = self._load_from_cache()
        if cached:
            self._config = cached
            return self._config

        raise RuntimeError("Failed to load reaction config: no cache available and GitHub fetch failed")

    def get_reactions(self) -> List[Dict[str, Any]]:
        """
        Get the list of reaction images.

        Returns:
            List of reaction dictionaries
        """
        config = self.load()
        reactions: List[Dict[str, Any]] = config.get("reaction_images", [])
        return reactions

    def get_cache_info(self) -> Dict[str, Any]:
        """
        Get information about the cache status.

        Returns:
            Dict with cache status information
        """
        info = {
            "cache_dir": str(self.cache_dir),
            "cache_file_exists": self.cache_file.exists(),
            "cache_valid": self._is_cache_valid(),
            "cache_ttl_seconds": self.cache_ttl,
            "config_url": self.config_url,
        }

        if self.cache_meta_file.exists():
            try:
                with open(self.cache_meta_file, "r", encoding="utf-8") as f:
                    meta = json.load(f)
                info["cached_at"] = meta.get("cached_at")
                info["reaction_count"] = meta.get("reaction_count")
                cached_at_val = info.get("cached_at")
                if cached_at_val is not None and isinstance(cached_at_val, (int, float)):
                    age_seconds = time.time() - cached_at_val
                    info["cache_age_hours"] = round(age_seconds / 3600, 1)
                    info["cache_expires_in_hours"] = round((self.cache_ttl - age_seconds) / 3600, 1)
            except (json.JSONDecodeError, IOError):
                pass

        return info

    def clear_cache(self) -> bool:
        """
        Clear the local cache.

        Returns:
            True if cache was cleared, False if no cache existed
        """
        cleared = False
        for cache_path in [self.cache_file, self.cache_meta_file]:
            if cache_path.exists():
                cache_path.unlink()
                cleared = True
        self._config = None
        logger.info("Cache cleared")
        return cleared


# Module-level singleton for convenience
_default_loader: Optional[ConfigLoader] = None


def get_loader() -> ConfigLoader:
    """Get or create the default config loader."""
    global _default_loader
    if _default_loader is None:
        # Allow override via environment variable
        cache_dir = os.getenv("REACTION_CACHE_DIR")
        _default_loader = ConfigLoader(cache_dir=Path(cache_dir) if cache_dir else None)
    return _default_loader


def load_reactions() -> List[Dict[str, Any]]:
    """Convenience function to load reactions using default loader."""
    return get_loader().get_reactions()
