"""Model downloader backed by the HuggingFace hub cache.

This module handles:
- Automatic model downloads from HuggingFace Hub into the standard hub cache
  (the same directory ``from_pretrained`` reads, so nothing is downloaded twice)
- Cache listing, size accounting, clearing and LRU eviction via
  ``huggingface_hub.scan_cache_dir``
- Retry on transient download failures

Quantization is not a download-time concern: the same weights are downloaded and
quantization is applied when the model is loaded (see ``models.model_interface.load_model``).
"""

import logging
from pathlib import Path
import shutil
from typing import Any, List, Optional

logger = logging.getLogger(__name__)


def default_hub_cache_dir() -> Path:
    """Return the HuggingFace hub cache directory (honors HF_HOME / HF_HUB_CACHE)."""
    try:
        from huggingface_hub import constants

        return Path(constants.HF_HUB_CACHE)
    except ImportError:
        import os

        hf_home = Path(os.environ.get("HF_HOME", Path.home() / ".cache" / "huggingface"))
        return Path(os.environ.get("HF_HUB_CACHE", hf_home / "hub"))


class ModelDownloader:
    """Handles automatic model downloading and caching."""

    def __init__(self, cache_dir: Optional[Path] = None):
        """Initialize the model downloader.

        Args:
            cache_dir: HuggingFace hub cache directory (default: the standard hub cache,
                ``$HF_HUB_CACHE`` or ``$HF_HOME/hub``). A custom directory must also be
                passed to model loading (``load_model(cache_dir=...)``).
        """
        self.cache_dir = Path(cache_dir) if cache_dir is not None else default_hub_cache_dir()
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        # Kept for backward compatibility; identical to cache_dir
        self.hf_cache_dir = self.cache_dir

        logger.info("HuggingFace hub cache directory: %s", self.cache_dir)

    def download(
        self,
        model_id: str,
        use_quantization: Optional[str] = None,
        force_download: bool = False,
        show_progress: bool = True,
        max_retries: int = 3,
    ) -> Path:
        """Download a model snapshot from HuggingFace Hub.

        Args:
            model_id: HuggingFace model ID (e.g., "mistralai/Mistral-7B-v0.1")
            use_quantization: Ignored for downloading (quantization is applied at load
                time); accepted for backward compatibility
            force_download: Force re-download even if cached
            show_progress: Show download progress bar (reserved)
            max_retries: Maximum retry attempts on failure

        Returns:
            Path to the downloaded snapshot directory

        Raises:
            RuntimeError: If download fails after retries
        """
        logger.info("Downloading model: %s", model_id)
        if use_quantization:
            logger.debug("Quantization %s will be applied at load time, not at download", use_quantization)

        attempt = 0
        last_error: Optional[Exception] = None

        while attempt < max_retries:
            try:
                attempt += 1
                logger.info("Download attempt %s/%s", attempt, max_retries)

                downloaded_path = self._download_from_huggingface(
                    model_id=model_id, force_download=force_download, show_progress=show_progress
                )

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

        raise RuntimeError(f"Failed to download {model_id} after {max_retries} attempts: {last_error}")

    def _download_from_huggingface(
        self,
        model_id: str,
        force_download: bool = False,
        show_progress: bool = True,  # pylint: disable=unused-argument
    ) -> Path:
        """Download model into the hub cache using ``snapshot_download``.

        Args:
            model_id: HuggingFace model ID
            force_download: Re-download files even if cached
            show_progress: Show progress bar (reserved for future use)

        Returns:
            Path to the snapshot directory inside the hub cache
        """
        from huggingface_hub import snapshot_download

        logger.info("Starting download from HuggingFace Hub: %s", model_id)

        # NOTE: We only ignore documentation/metadata files that aren't needed for inference.
        # config.json, tokenizer.json, etc. are REQUIRED for model loading and must NOT be ignored.
        model_path = snapshot_download(
            repo_id=model_id,
            cache_dir=str(self.cache_dir),
            force_download=force_download,
            local_files_only=False,
            ignore_patterns=[
                "*.msgpack",  # Flax format (not needed for PyTorch)
                "*.h5",  # TensorFlow format (not needed for PyTorch)
                "*.ot",  # Old PyTorch format
                "*.md",  # Documentation files
                "README*",  # README files
                "LICENSE*",  # License files
                ".gitattributes",  # Git metadata
            ],
        )

        logger.info("Model downloaded to: %s", model_path)
        return Path(model_path)

    def _get_cache_path(self, model_id: str) -> Path:
        """Get the hub cache directory for a model (``models--org--name``).

        Args:
            model_id: HuggingFace model ID

        Returns:
            Path to the model's repo folder in the hub cache
        """
        return self.cache_dir / ("models--" + model_id.replace("/", "--"))

    def is_cached(self, model_id: str) -> bool:
        """Check if a model's config.json is present in the hub cache.

        Args:
            model_id: HuggingFace model ID

        Returns:
            True if the model is cached locally
        """
        try:
            from huggingface_hub import try_to_load_from_cache
        except ImportError:
            return self._get_cache_path(model_id).exists()

        result = try_to_load_from_cache(repo_id=model_id, filename="config.json", cache_dir=str(self.cache_dir))
        # Returns a path string when cached; None or a sentinel object otherwise
        return isinstance(result, str)

    def _cached_model_repos(self) -> List[Any]:
        """Return ``CachedRepoInfo`` entries for model repos in the hub cache."""
        from huggingface_hub import scan_cache_dir

        if not self.cache_dir.exists():
            return []
        info = scan_cache_dir(self.cache_dir)
        return [repo for repo in info.repos if repo.repo_type == "model"]

    def _find_repo(self, model_id: str) -> Optional[Any]:
        for repo in self._cached_model_repos():
            if repo.repo_id == model_id:
                return repo
        return None

    def get_cache_size(self, model_id: Optional[str] = None) -> int:
        """Get cache size in bytes.

        Args:
            model_id: Specific model ID, or None for all cached models

        Returns:
            Size in bytes
        """
        if model_id:
            repo = self._find_repo(model_id)
            return int(repo.size_on_disk) if repo is not None else 0
        return int(sum(repo.size_on_disk for repo in self._cached_model_repos()))

    def clear_cache(self, model_id: Optional[str] = None):
        """Delete cached models from the hub cache.

        Args:
            model_id: Specific model to clear, or None to clear all cached models
        """
        repos = self._cached_model_repos()
        if model_id:
            repos = [repo for repo in repos if repo.repo_id == model_id]
        for repo in repos:
            shutil.rmtree(repo.repo_path)
            logger.info("Cleared cache for %s", repo.repo_id)

    def list_cached_models(self) -> list:
        """List all cached models.

        Returns:
            Sorted list of cached model IDs
        """
        return sorted(repo.repo_id for repo in self._cached_model_repos())

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
        """Evict least recently used cached models until ``target_free_gb`` is free.

        Args:
            target_free_gb: Target free space in GB
        """
        free_gb = shutil.disk_usage(self.cache_dir).free / (1024**3)
        if free_gb >= target_free_gb:
            logger.info("Sufficient space available: %.2f GB", free_gb)
            return

        logger.info("Need to free space. Target: %s GB", target_free_gb)

        # Oldest access first
        for repo in sorted(self._cached_model_repos(), key=lambda r: r.last_accessed):
            if shutil.disk_usage(self.cache_dir).free / (1024**3) >= target_free_gb:
                break
            logger.info("Evicting %s to free space", repo.repo_id)
            shutil.rmtree(repo.repo_path)

        final_free = shutil.disk_usage(self.cache_dir).free / (1024**3)
        logger.info("Space freed. Available: %.2f GB", final_free)

    def download_with_fallback(
        self, model_id: str, max_vram_gb: float, show_progress: bool = True
    ) -> tuple[Path, Optional[str]]:
        """Download a model and choose the quantization needed to fit ``max_vram_gb``.

        The returned quantization must be passed to model loading; it is not applied
        to the downloaded files.

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

        if model_meta.estimated_vram_gb <= max_vram_gb:
            logger.info("Model fits in %s GB without quantization", max_vram_gb)
            return self.download(model_meta.model_id, show_progress=show_progress), None

        if model_meta.estimated_vram_4bit_gb <= max_vram_gb:
            logger.info("Using 4-bit quantization to fit in %s GB", max_vram_gb)
            return self.download(model_meta.model_id, show_progress=show_progress), "4bit"

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
