"""Model downloader with automatic caching and progress tracking.

This module handles:
- Automatic model downloads from HuggingFace Hub
- Smart caching with disk space management
- Progress tracking and resume capability
- Fallback to quantized versions if needed
"""

import logging
import os
from pathlib import Path
import shutil
from typing import Optional

logger = logging.getLogger(__name__)


class ModelDownloader:
    """Handles automatic model downloading and caching."""

    def __init__(self, cache_dir: Optional[Path] = None):
        """Initialize the model downloader.

        Args:
            cache_dir: Directory for model cache (default: ~/.cache/sleeper_agents/models)
        """
        if cache_dir is None:
            cache_dir = Path.home() / ".cache" / "sleeper_agents" / "models"

        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)

        # Use HuggingFace cache by default if available
        self.hf_cache_dir = Path(os.environ.get("HF_HOME", Path.home() / ".cache" / "huggingface"))

        logger.info("Model cache directory: %s", self.cache_dir)
        logger.info("HuggingFace cache directory: %s", self.hf_cache_dir)

    def download(
        self,
        model_id: str,
        use_quantization: Optional[str] = None,
        force_download: bool = False,
        show_progress: bool = True,
        max_retries: int = 3,
    ) -> Path:
        """Download a model from HuggingFace Hub.

        Args:
            model_id: HuggingFace model ID (e.g., "mistralai/Mistral-7B-v0.1")
            use_quantization: Quantization type ("4bit", "8bit", or None)
            force_download: Force re-download even if cached
            show_progress: Show download progress bar
            max_retries: Maximum retry attempts on failure

        Returns:
            Path to downloaded model

        Raises:
            RuntimeError: If download fails after retries
        """
        logger.info("Downloading model: %s", model_id)

        if use_quantization:
            logger.info("Using %s quantization", use_quantization)

        # Check if already cached
        model_path = self._get_cache_path(model_id)
        if model_path.exists() and not force_download:
            logger.info("Model already cached: %s", model_path)
            return model_path

        # Download using HuggingFace Hub
        attempt = 0
        last_error = None

        while attempt < max_retries:
            try:
                attempt += 1
                logger.info("Download attempt %s/%s", attempt, max_retries)

                downloaded_path = self._download_from_huggingface(
                    model_id=model_id, use_quantization=use_quantization, show_progress=show_progress
                )

                # Verify download succeeded
                if not downloaded_path or not downloaded_path.exists():
                    raise RuntimeError(f"Download completed but model not found at {downloaded_path}")

                logger.info("Model downloaded successfully: %s", downloaded_path)
                return downloaded_path

            except Exception as e:
                last_error = e
                logger.warning("Download attempt %d failed: %s", attempt, e)

                if attempt < max_retries:
                    logger.info("Retrying download...")
                else:
                    logger.error("All download attempts failed")

        # All retries exhausted
        raise RuntimeError(f"Failed to download {model_id} after {max_retries} attempts: {last_error}")

    def _download_from_huggingface(
        self, model_id: str, use_quantization: Optional[str] = None, show_progress: bool = True
    ) -> Path:
        """Download model using HuggingFace Hub library.

        Args:
            model_id: HuggingFace model ID
            use_quantization: Quantization type
            show_progress: Show progress bar

        Returns:
            Path to downloaded model
        """
        try:
            from huggingface_hub import snapshot_download

            logger.info("Starting download from HuggingFace Hub: %s", model_id)

            # Download to HuggingFace cache (will be symlinked/managed by HF)
            model_path = snapshot_download(
                repo_id=model_id,
                cache_dir=str(self.hf_cache_dir),
                resume_download=True,  # Resume if interrupted
                local_files_only=False,
                revision="main",  # Use main branch
                # Don't download large files we don't need
                ignore_patterns=[
                    "*.msgpack",
                    "*.h5",
                    "*.ot",
                    "*.md",
                    "*.txt",
                    "*.json",
                ],
            )

            logger.info("Model downloaded to: %s", model_path)
            return Path(model_path)

        except ImportError:
            logger.error("huggingface_hub not installed. Install with: pip install huggingface_hub")
            raise

        except Exception as e:
            logger.error("HuggingFace download failed: %s", e)
            raise

    def _get_cache_path(self, model_id: str) -> Path:
        """Get local cache path for a model.

        Args:
            model_id: HuggingFace model ID

        Returns:
            Path to cached model
        """
        # Sanitize model ID for filesystem
        safe_name = model_id.replace("/", "--")
        return self.cache_dir / safe_name

    def is_cached(self, model_id: str) -> bool:
        """Check if model is already cached.

        Args:
            model_id: HuggingFace model ID

        Returns:
            True if model is cached locally
        """
        cache_path = self._get_cache_path(model_id)
        return cache_path.exists()

    def get_cache_size(self, model_id: Optional[str] = None) -> int:
        """Get cache size in bytes.

        Args:
            model_id: Specific model ID, or None for total cache size

        Returns:
            Size in bytes
        """
        if model_id:
            cache_path = self._get_cache_path(model_id)
            if not cache_path.exists():
                return 0
            return sum(f.stat().st_size for f in cache_path.rglob("*") if f.is_file())
        else:
            # Total cache size
            return sum(f.stat().st_size for f in self.cache_dir.rglob("*") if f.is_file())

    def clear_cache(self, model_id: Optional[str] = None):
        """Clear model cache.

        Args:
            model_id: Specific model to clear, or None to clear all
        """
        if model_id:
            cache_path = self._get_cache_path(model_id)
            if cache_path.exists():
                shutil.rmtree(cache_path)
                logger.info("Cleared cache for %s", model_id)
        else:
            # Clear entire cache
            if self.cache_dir.exists():
                shutil.rmtree(self.cache_dir)
                self.cache_dir.mkdir(parents=True, exist_ok=True)
                logger.info("Cleared entire model cache")

    def list_cached_models(self) -> list:
        """List all cached models.

        Returns:
            List of cached model IDs
        """
        if not self.cache_dir.exists():
            return []

        cached = []
        for path in self.cache_dir.iterdir():
            if path.is_dir():
                # Convert back from safe name
                model_id = path.name.replace("--", "/")
                cached.append(model_id)

        return sorted(cached)

    def get_disk_space(self) -> dict:
        """Get disk space information for cache directory.

        Returns:
            Dictionary with total, used, and free space in GB
        """
        stat = shutil.disk_usage(self.cache_dir)
        return {
            "total_gb": stat.total / (1024**3),
            "used_gb": stat.used / (1024**3),
            "free_gb": stat.free / (1024**3),
            "cache_gb": self.get_cache_size() / (1024**3),
        }

    def check_disk_space(self, required_gb: float) -> bool:
        """Check if sufficient disk space is available.

        Args:
            required_gb: Required space in GB

        Returns:
            True if sufficient space available
        """
        disk_info = self.get_disk_space()
        return bool(disk_info["free_gb"] >= required_gb)

    def evict_lru_models(self, target_free_gb: float):
        """Evict least recently used models to free space.

        Args:
            target_free_gb: Target free space in GB
        """
        disk_info = self.get_disk_space()
        if disk_info["free_gb"] >= target_free_gb:
            logger.info("Sufficient space available: %.2f GB", disk_info["free_gb"])
            return

        logger.info("Need to free space. Target: %s GB", target_free_gb)

        # Get models sorted by last access time
        models = []
        for path in self.cache_dir.iterdir():
            if path.is_dir():
                models.append((path, path.stat().st_atime))

        # Sort by access time (oldest first)
        models.sort(key=lambda x: x[1])

        # Evict until we have enough space
        for path, _ in models:
            current_free = self.get_disk_space()["free_gb"]
            if current_free >= target_free_gb:
                break

            model_id = path.name.replace("--", "/")
            logger.info("Evicting %s to free space", model_id)
            shutil.rmtree(path)

        final_free = self.get_disk_space()["free_gb"]
        logger.info("Space freed. Available: %.2f GB", final_free)

    def download_with_fallback(
        self, model_id: str, max_vram_gb: float, show_progress: bool = True
    ) -> tuple[Path, Optional[str]]:
        """Download model with automatic quantization fallback.

        Args:
            model_id: HuggingFace model ID
            max_vram_gb: Maximum available VRAM
            show_progress: Show progress bar

        Returns:
            Tuple of (model_path, quantization_type)
        """
        from .registry import get_registry

        registry = get_registry()
        model_meta = registry.get(model_id)

        if not model_meta:
            logger.warning("Model %s not in registry, attempting direct download", model_id)
            return self.download(model_id, show_progress=show_progress), None

        # Check if model fits without quantization
        if model_meta.estimated_vram_gb <= max_vram_gb:
            logger.info("Model fits in %s GB without quantization", max_vram_gb)
            return self.download(model_id, show_progress=show_progress), None

        # Try 4-bit quantization
        if model_meta.estimated_vram_4bit_gb <= max_vram_gb:
            logger.info("Using 4-bit quantization to fit in %s GB", max_vram_gb)
            return self.download(model_id, use_quantization="4bit", show_progress=show_progress), "4bit"

        # Model too large even with quantization
        raise RuntimeError(
            f"Model {model_id} requires {model_meta.estimated_vram_4bit_gb:.1f} GB "
            f"(4-bit quantized), but only {max_vram_gb:.1f} GB available"
        )

    def print_cache_info(self):
        """Print formatted cache information."""
        print("\n" + "=" * 60)
        print("MODEL CACHE INFORMATION")
        print("=" * 60)

        print(f"\nCache Directory: {self.cache_dir}")

        disk_info = self.get_disk_space()
        print("\nDisk Space:")
        print(f"  Total: {disk_info['total_gb']:.2f} GB")
        print(f"  Used: {disk_info['used_gb']:.2f} GB")
        print(f"  Free: {disk_info['free_gb']:.2f} GB")
        print(f"  Cache: {disk_info['cache_gb']:.2f} GB")

        cached_models = self.list_cached_models()
        print(f"\nCached Models: {len(cached_models)}")

        if cached_models:
            print("\nModels:")
            for model_id in cached_models:
                size_gb = self.get_cache_size(model_id) / (1024**3)
                print(f"  - {model_id} ({size_gb:.2f} GB)")

        print("=" * 60 + "\n")
